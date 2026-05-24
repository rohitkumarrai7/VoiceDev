import pytest
from pathlib import Path
import tempfile

from voicedev.config import VoiceDevConfig


class TestConfig:
    def test_default_config(self):
        config = VoiceDevConfig()
        assert config.stt_backend == "auto"
        assert config.vad_aggressiveness == 2
        assert config.silence_threshold_ms == 1200
        assert config.noise_reduction is True
        assert config.audio_feedback is True
        assert config.show_confidence is True
        assert config.confirm_before_send is False
        assert config.confirmation_timeout_s == 2.0

    def test_config_dir(self):
        assert VoiceDevConfig.config_dir() == Path.home() / ".voicedev"

    def test_sessions_dir(self):
        assert VoiceDevConfig.sessions_dir() == Path.home() / ".voicedev" / "sessions"

    def test_load_with_overrides(self):
        config = VoiceDevConfig.load({"noise_reduction": False})
        assert config.noise_reduction is False

    def test_load_with_new_fields(self):
        config = VoiceDevConfig.load({
            "audio_feedback": False,
            "show_confidence": False,
            "confirm_before_send": True,
            "confirmation_timeout_s": 3.5,
        })
        assert config.audio_feedback is False
        assert config.show_confidence is False
        assert config.confirm_before_send is True
        assert config.confirmation_timeout_s == 3.5

    def test_load_ignores_unknown_keys(self):
        config = VoiceDevConfig.load({"unknown_future_key": "value"})
        assert not hasattr(config, "unknown_future_key")

    def test_save_and_load(self, tmp_path):
        config = VoiceDevConfig()
        config_path = tmp_path / ".voicedev" / "config.yaml"

        with pytest.MonkeyPatch.context() as m:
            m.setattr(VoiceDevConfig, "config_path", classmethod(lambda cls: config_path))
            m.setattr(VoiceDevConfig, "config_dir", classmethod(lambda cls: config_path.parent))

            config.save()
            assert config_path.exists()

            loaded = VoiceDevConfig.load()
            assert loaded.noise_reduction == config.noise_reduction
            assert loaded.vad_aggressiveness == config.vad_aggressiveness
            assert loaded.audio_feedback == config.audio_feedback
            assert loaded.show_confidence == config.show_confidence

    def test_ensure_dirs(self, tmp_path):
        config = VoiceDevConfig()
        config_dir = tmp_path / "test_voicedev"

        with pytest.MonkeyPatch.context() as m:
            m.setattr(VoiceDevConfig, "config_dir", lambda cls: config_dir)
            m.setattr(VoiceDevConfig, "sessions_dir", lambda cls: config_dir / "sessions")
            config.ensure_dirs()
            assert config_dir.exists()
            assert (config_dir / "sessions").exists()
