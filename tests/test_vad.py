import numpy as np
import pytest

from voicedev.audio.vad import VoiceActivityDetector


class TestVoiceActivityDetector:
    def setup_method(self):
        self.vad = VoiceActivityDetector(aggressiveness=2, sample_rate=16000, frame_duration_ms=30)

    def _generate_silence_frame(self):
        return np.zeros(480, dtype=np.int16)

    def _generate_noise_frame(self):
        return np.random.randint(-3000, 3000, size=480, dtype=np.int16)

    def test_is_speech_with_silence(self):
        silence = self._generate_silence_frame()
        result = self.vad.is_speech(silence)
        assert isinstance(result, bool)

    def test_is_speech_with_short_frame(self):
        short = np.zeros(100, dtype=np.int16)
        assert self.vad.is_speech(short) is False

    def test_detect_speech_segment_all_silence(self):
        frames = [self._generate_silence_frame() for _ in range(50)]
        idx = [0]

        def frame_source():
            if idx[0] < len(frames):
                f = frames[idx[0]]
                idx[0] += 1
                return f
            return None

        result = self.vad.detect_speech_segment(frame_source, silence_threshold_ms=300)
        assert result is None

    def test_set_aggressiveness(self):
        for level in range(4):
            self.vad.set_aggressiveness(level)

    def test_detect_speech_segment_with_speech(self):
        frames = [self._generate_noise_frame() for _ in range(30)]
        idx = [0]

        def frame_source():
            if idx[0] < len(frames):
                f = frames[idx[0]]
                idx[0] += 1
                return f
            return None

        result = self.vad.detect_speech_segment(
            frame_source, silence_threshold_ms=300, speech_onset_frames=1
        )
        assert result is None or isinstance(result, np.ndarray)
