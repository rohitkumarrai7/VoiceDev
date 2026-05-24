import numpy as np
import pytest

from voicedev.audio.wakeword import WakeWordDetector


class TestWakeWordDetector:
    def setup_method(self):
        self.detector = WakeWordDetector(phrase="hey dev")

    def test_initial_state_not_armed(self):
        assert self.detector.armed is False

    def test_detect_text_with_phrase(self):
        assert self.detector.detect_text("hey dev start coding") is True
        assert self.detector.armed is True

    def test_detect_text_without_phrase(self):
        assert self.detector.detect_text("hello world") is False
        assert self.detector.armed is False

    def test_detect_text_case_insensitive(self):
        assert self.detector.detect_text("Hey Dev") is True

    def test_armed_passes_through(self):
        self.detector.detect_text("hey dev")
        assert self.detector.detect_text("anything at all") is True

    def test_disarm(self):
        self.detector.detect_text("hey dev")
        assert self.detector.armed is True
        self.detector.disarm()
        assert self.detector.armed is False

    def test_disarm_then_reject(self):
        self.detector.detect_text("hey dev")
        self.detector.disarm()
        assert self.detector.detect_text("random text") is False

    def test_backend_name(self):
        assert self.detector.backend_name in ("openwakeword", "substring")

    def test_detect_audio_without_oww(self):
        audio = np.zeros(480, dtype=np.int16)
        result = self.detector.detect_audio(audio)
        if self.detector.backend_name == "substring":
            assert result is False

    def test_phrase_match_exact(self):
        assert self.detector.detect_text("hey dev") is True

    def test_partial_phrase_match(self):
        assert self.detector.detect_text("hey") is True
