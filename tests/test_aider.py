from voicedev.agent.aider import AiderBackend


class TestAiderCommand:
    def test_minimax_key_does_not_force_minimax(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        monkeypatch.delenv("VOICEDEV_USE_MINIMAX", raising=False)

        cmd = AiderBackend()._build_cmd("aider")

        assert "--openai-api-key" not in cmd
        assert "--openai-api-base" not in cmd
        assert "minimax/minimax-m2.7" not in cmd

    def test_explicit_minimax_model_adds_api_settings(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        monkeypatch.delenv("VOICEDEV_USE_MINIMAX", raising=False)

        cmd = AiderBackend(extra_args=["--model", "minimax/minimax-m2.7"])._build_cmd("aider")

        assert "--openai-api-key" in cmd
        assert "test-key" in cmd
        assert "--openai-api-base" in cmd
        assert "https://api.minimaxi.chat/v1" in cmd

    def test_env_flag_can_enable_minimax_default(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        monkeypatch.setenv("VOICEDEV_USE_MINIMAX", "true")

        cmd = AiderBackend()._build_cmd("aider")

        assert "--openai-api-key" in cmd
        assert "minimax/minimax-m2.7" in cmd
