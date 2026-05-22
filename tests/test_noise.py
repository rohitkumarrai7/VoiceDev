import numpy as np
import pytest

from voicedev.audio.noise import reduce_noise


class TestNoiseReduction:
    def test_reduce_noise_short_audio(self):
        short = np.zeros(100, dtype=np.int16)
        result = reduce_noise(short)
        assert len(result) == len(short)

    def test_reduce_noise_preserves_dtype(self):
        audio = np.random.randint(-1000, 1000, size=32000, dtype=np.int16)
        result = reduce_noise(audio)
        assert result.dtype == np.int16

    def test_reduce_noise_does_not_crash_on_silence(self):
        silence = np.zeros(32000, dtype=np.int16)
        result = reduce_noise(silence)
        assert len(result) > 0
