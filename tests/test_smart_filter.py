import numpy as np
import pytest

from voicedev.config import VoiceDevConfig
from voicedev.stt.base import TranscriptionResult


class FakeVoiceDev:
    """Minimal stub to test _is_garbage without the full VoiceDev class."""

    def __init__(self, config: VoiceDevConfig):
        self.config = config
        self._filler_set = {w.lower().strip() for w in config.filler_words}

    def _is_garbage(self, audio: np.ndarray, result: TranscriptionResult, strict: bool = True):
        from voicedev.audio.capture import SAMPLE_RATE
        text = (result.text or "").strip()
        if not text:
            return "empty transcription"

        if not any(ch.isalnum() for ch in text):
            return "no words detected"

        if result.has_confidence and result.confidence < self.config.min_confidence:
            return f"low confidence ({result.confidence_pct} < {int(self.config.min_confidence*100)}%)"

        if not strict:
            return None

        audio_duration = len(audio) / SAMPLE_RATE
        if audio_duration < self.config.min_audio_duration_s:
            return f"too short ({audio_duration:.1f}s < {self.config.min_audio_duration_s}s)"

        text_lower = text.lower().strip().rstrip(".!?,;:")
        if text_lower in self._filler_set:
            return f"filler word ('{text_lower}')"

        return None


@pytest.fixture
def filt():
    cfg = VoiceDevConfig(
        min_audio_duration_s=0.4,
        min_confidence=0.35,
        filler_words=["um", "uh", "hmm", "like", "you know", "thank you"],
    )
    return FakeVoiceDev(cfg)


def _audio(seconds: float) -> np.ndarray:
    return np.zeros(int(16000 * seconds), dtype=np.int16)


class TestSmartFilter:
    def test_too_short(self, filt):
        reason = filt._is_garbage(_audio(0.1), TranscriptionResult(text="hello", confidence=0.9))
        assert reason is not None
        assert "too short" in reason

    def test_exactly_min_duration_passes(self, filt):
        reason = filt._is_garbage(_audio(0.4), TranscriptionResult(text="hello", confidence=0.9))
        assert reason is None

    def test_empty_transcription(self, filt):
        reason = filt._is_garbage(_audio(1.0), TranscriptionResult(text="", confidence=0.9))
        assert reason is not None
        assert "empty" in reason

    def test_punctuation_only_transcription(self, filt):
        reason = filt._is_garbage(_audio(1.0), TranscriptionResult(text=". .", confidence=0.9))
        assert reason is not None
        assert "no words" in reason

    def test_low_confidence(self, filt):
        reason = filt._is_garbage(_audio(1.0), TranscriptionResult(text="hello", confidence=0.1))
        assert reason is not None
        assert "low confidence" in reason

    def test_borderline_confidence_passes(self, filt):
        reason = filt._is_garbage(_audio(1.0), TranscriptionResult(text="hello", confidence=0.35))
        assert reason is None

    def test_no_confidence_passes(self, filt):
        reason = filt._is_garbage(_audio(1.0), TranscriptionResult(text="hello", confidence=-1.0))
        assert reason is None

    def test_non_strict_mode_skips_duration_and_filler(self, filt):
        reason = filt._is_garbage(_audio(0.1), TranscriptionResult(text="okay", confidence=0.9), strict=False)
        assert reason is None

    def test_filler_word_um(self, filt):
        reason = filt._is_garbage(_audio(1.0), TranscriptionResult(text="Um", confidence=0.9))
        assert reason is not None
        assert "filler" in reason

    def test_filler_word_with_punctuation(self, filt):
        reason = filt._is_garbage(_audio(1.0), TranscriptionResult(text="Hmm.", confidence=0.9))
        assert reason is not None
        assert "filler" in reason

    def test_filler_multi_word(self, filt):
        reason = filt._is_garbage(_audio(1.0), TranscriptionResult(text="you know", confidence=0.9))
        assert reason is not None
        assert "filler" in reason

    def test_real_sentence_passes(self, filt):
        reason = filt._is_garbage(
            _audio(2.0),
            TranscriptionResult(text="Create a function that parses JSON", confidence=0.85),
        )
        assert reason is None

    def test_short_command_passes(self, filt):
        reason = filt._is_garbage(
            _audio(0.8),
            TranscriptionResult(text="undo that", confidence=0.75),
        )
        assert reason is None

    def test_thank_you_filtered(self, filt):
        reason = filt._is_garbage(
            _audio(1.0),
            TranscriptionResult(text="Thank you.", confidence=0.9),
        )
        assert reason is not None
        assert "filler" in reason
