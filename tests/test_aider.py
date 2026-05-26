from voicedev.agent.aider import (
    AiderBackend,
    MINIMAX_DEFAULT_MODEL,
    OPENROUTER_API_BASE,
    OPENROUTER_DEFAULT_MODEL,
)


class TestAiderCommand:
    def test_minimax_key_does_not_force_minimax(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        monkeypatch.delenv("VOICEDEV_USE_MINIMAX", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("QWEN3_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        cmd = AiderBackend()._build_cmd("aider")

        assert "--openai-api-key" not in cmd
        assert "--openai-api-base" not in cmd
        assert MINIMAX_DEFAULT_MODEL not in cmd

    def test_explicit_minimax_model_adds_api_settings(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        monkeypatch.delenv("VOICEDEV_USE_MINIMAX", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        cmd = AiderBackend(extra_args=["--model", "minimax/minimax-m2.7"])._build_cmd("aider")

        assert "--openai-api-key" in cmd
        assert "test-key" in cmd
        assert "--openai-api-base" in cmd
        assert "https://api.minimaxi.chat/v1" in cmd

    def test_env_flag_can_enable_minimax_default(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        monkeypatch.setenv("VOICEDEV_USE_MINIMAX", "true")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        cmd = AiderBackend()._build_cmd("aider")

        assert "--openai-api-key" in cmd
        assert MINIMAX_DEFAULT_MODEL in cmd

    def test_openrouter_key_wires_api_and_model(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        monkeypatch.delenv("QWEN3_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.delenv("AIDER_MODEL", raising=False)

        cmd = AiderBackend()._build_cmd("aider")

        assert "--openai-api-key" in cmd
        assert "sk-or-test" in cmd
        assert OPENROUTER_API_BASE in cmd
        assert OPENROUTER_DEFAULT_MODEL in cmd

    def test_qwen3_key_alias_for_openrouter(self, monkeypatch):
        monkeypatch.setenv("QWEN3_API_KEY", "sk-or-qwen")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        cmd = AiderBackend()._build_cmd("aider")

        assert "sk-or-qwen" in cmd
        assert OPENROUTER_API_BASE in cmd

    def test_aider_model_override(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        monkeypatch.setenv("AIDER_MODEL", "openrouter/custom/model")

        cmd = AiderBackend()._build_cmd("aider")

        assert "openrouter/custom/model" in cmd
        assert OPENROUTER_DEFAULT_MODEL not in cmd

    def test_openai_key_without_openrouter_base(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("QWEN3_API_KEY", raising=False)

        cmd = AiderBackend()._build_cmd("aider")

        assert "sk-openai-test" in cmd
        assert OPENROUTER_API_BASE not in cmd
        assert "gpt-4o-mini" in cmd

    def test_openrouter_wins_over_openai(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-wins")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-loses")

        cmd = AiderBackend()._build_cmd("aider")

        assert "sk-or-wins" in cmd
        assert "sk-openai-loses" not in cmd
        assert OPENROUTER_API_BASE in cmd

    def test_resolve_llm_returns_none_without_keys(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("QWEN3_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.delenv("AIDER_API_KEY", raising=False)

        assert AiderBackend._resolve_llm_from_env() is None
