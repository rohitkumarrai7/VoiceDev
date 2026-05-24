import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from voicedev.stt.base import STTBackend, TranscriptionResult


class MockSTTBackend(STTBackend):
    def __init__(self, return_text="hello world", confidence=0.9):
        self._return_text = return_text
        self._confidence = confidence

    def transcribe(self, audio_data, sample_rate=16000):
        return TranscriptionResult(
            text=self._return_text,
            confidence=self._confidence,
        )

    def name(self):
        return "mock"

    def is_available(self):
        return True


class TestTranscriptionResult:
    def test_has_confidence(self):
        r = TranscriptionResult(text="hello", confidence=0.85)
        assert r.has_confidence is True

    def test_no_confidence(self):
        r = TranscriptionResult(text="hello", confidence=-1.0)
        assert r.has_confidence is False

    def test_confidence_pct(self):
        r = TranscriptionResult(text="hello", confidence=0.85)
        assert r.confidence_pct == "85%"

    def test_confidence_pct_na(self):
        r = TranscriptionResult(text="hello")
        assert r.confidence_pct == "n/a"

    def test_default_values(self):
        r = TranscriptionResult(text="test")
        assert r.confidence == -1.0
        assert r.language == ""
        assert r.duration_s == 0.0


class TestSTTBackendInterface:
    def test_mock_backend_implements_interface(self):
        backend = MockSTTBackend()
        assert backend.is_available()
        assert backend.name() == "mock"

    def test_mock_transcribe_returns_result(self):
        backend = MockSTTBackend("test transcription", 0.95)
        audio = np.zeros(16000, dtype=np.int16)
        result = backend.transcribe(audio)
        assert isinstance(result, TranscriptionResult)
        assert result.text == "test transcription"
        assert result.confidence == 0.95

    def test_mock_transcribe_empty(self):
        backend = MockSTTBackend("")
        audio = np.zeros(16000, dtype=np.int16)
        result = backend.transcribe(audio)
        assert result.text == ""


class TestWhisperAPIBackend:
    def test_is_available_no_key(self):
        with patch.dict("os.environ", {}, clear=True):
            from voicedev.stt.whisper_api import WhisperAPIBackend

            backend = WhisperAPIBackend()
            assert backend.is_available() is False

    def test_is_available_with_key(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            from voicedev.stt.whisper_api import WhisperAPIBackend

            backend = WhisperAPIBackend()
            assert backend.is_available() is True

    def test_name(self):
        from voicedev.stt.whisper_api import WhisperAPIBackend

        backend = WhisperAPIBackend()
        assert backend.name() == "whisper_api"


class TestGroqWhisperBackend:
    def test_is_available_no_key(self):
        with patch.dict("os.environ", {}, clear=True):
            from voicedev.stt.groq_whisper import GroqWhisperBackend

            backend = GroqWhisperBackend()
            assert backend.is_available() is False

    def test_is_available_with_key(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": "gsk-test-key"}):
            from voicedev.stt.groq_whisper import GroqWhisperBackend

            backend = GroqWhisperBackend()
            assert backend.is_available() is True

    def test_name(self):
        from voicedev.stt.groq_whisper import GroqWhisperBackend

        backend = GroqWhisperBackend()
        assert backend.name() == "groq_whisper"


class TestFasterWhisperBackend:
    def test_name(self):
        from voicedev.stt.faster_whisper import FasterWhisperBackend

        backend = FasterWhisperBackend()
        assert backend.name() == "faster_whisper"

    def test_is_available(self):
        from voicedev.stt.faster_whisper import FasterWhisperBackend

        backend = FasterWhisperBackend()
        assert isinstance(backend.is_available(), bool)
