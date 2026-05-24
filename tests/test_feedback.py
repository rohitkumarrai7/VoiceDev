import numpy as np
import pytest

from voicedev.audio.feedback import AudioFeedback, _generate_tone


class TestToneGeneration:
    def test_generates_correct_length(self):
        tone = _generate_tone(440, 0.1)
        expected = int(16000 * 0.1)
        assert len(tone) == expected

    def test_dtype_is_int16(self):
        tone = _generate_tone(880, 0.08)
        assert tone.dtype == np.int16

    def test_not_all_zeros(self):
        tone = _generate_tone(660, 0.1, volume=0.5)
        assert np.any(tone != 0)

    def test_volume_scaling(self):
        loud = _generate_tone(440, 0.1, volume=0.5)
        quiet = _generate_tone(440, 0.1, volume=0.1)
        assert np.abs(loud).max() > np.abs(quiet).max()


class TestAudioFeedback:
    def test_disabled_does_nothing(self):
        fb = AudioFeedback(enabled=False)
        fb.play("start")

    def test_unknown_tone_does_nothing(self):
        fb = AudioFeedback(enabled=True)
        fb.play("nonexistent_tone")

    def test_set_enabled(self):
        fb = AudioFeedback(enabled=False)
        fb.set_enabled(True)
        assert fb._enabled is True

    def test_all_tone_names_exist(self):
        fb = AudioFeedback(enabled=True)
        for name in ["start", "stop", "success", "error", "command", "cancel"]:
            tone = fb._get_tone(name)
            assert tone is not None
            assert len(tone) > 0
