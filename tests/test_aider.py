import pytest

from voicedev.agent.aider import (
    AiderBackend,
    LLM_PROVIDERS,
    MINIMAX_DEFAULT_MODEL,
    OPENROUTER_API_BASE,
    OPENROUTER_DEFAULT_MODEL,
)


def _clear_agent_keys(monkeypatch):
    for name in (
        "OPENROUTER_API_KEY", "QWEN3_API_KEY", "OPENAI_API_KEY",
        "MINIMAX_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
        "DEEPSEEK_API_KEY", "AIDER_API_KEY", "AIDER_MODEL", "QWEN3_MODEL",
        "MINIMAX_MODEL", "CLAUDE_MODEL", "ANTHROPIC_MODEL", "GEMINI_MODEL",
        "DEEPSEEK_MODEL", "VOICEDEV_LLM_PROVIDER", "VOICEDEV_USE_MINIMAX",
        "VOICEDEV_USE_QWEN3",
    ):
        monkeypatch.delenv(name, raising=False)


class TestProviderMatrix:
    @pytest.mark.parametrize("provider_name", [p["name"] for p in LLM_PROVIDERS])
    def test_registry_has_wire_mode(self, provider_name):
        provider = AiderBackend._provider_by_name(provider_name)
        assert provider is not None
        assert provider.get("wire") in ("openai_compatible", "anthropic", "api_key_flag")


class TestAiderCommand:
    def test_minimax_only_key_wires_minimax(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        monkeypatch.setenv("MINIMAX_MODEL", "minimax/minimax-m2.7")

        llm = AiderBackend._resolve_llm_from_env()
        cmd = AiderBackend()._build_cmd("aider")

        assert llm["provider"] == "minimax"
        assert llm["wire"] == "openai_compatible"
        assert "test-key" in cmd
        assert "https://api.minimaxi.chat/v1" in cmd
        assert "minimax/minimax-m2.7" in cmd

    def test_explicit_minimax_model_adds_api_settings(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

        cmd = AiderBackend(extra_args=["--model", "minimax/minimax-m2.7"])._build_cmd("aider")

        assert "--openai-api-key" in cmd
        assert "test-key" in cmd
        assert "--openai-api-base" in cmd
        assert "https://api.minimaxi.chat/v1" in cmd

    def test_minimax_with_llm_provider_flag(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.setenv("VOICEDEV_LLM_PROVIDER", "minimax")

        llm = AiderBackend._resolve_llm_from_env()

        assert llm["provider"] == "minimax"
        assert llm["api_key"] == "mm-key"

    def test_openrouter_key_wires_api_and_model(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

        cmd = AiderBackend()._build_cmd("aider")

        assert "--openai-api-key" in cmd
        assert "sk-or-test" in cmd
        assert OPENROUTER_API_BASE in cmd
        assert OPENROUTER_DEFAULT_MODEL in cmd

    def test_qwen3_key_alias_for_openrouter(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("QWEN3_API_KEY", "sk-or-qwen")

        cmd = AiderBackend()._build_cmd("aider")

        assert "sk-or-qwen" in cmd
        assert OPENROUTER_API_BASE in cmd

    def test_aider_model_override(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        monkeypatch.setenv("AIDER_MODEL", "openrouter/custom/model")

        cmd = AiderBackend()._build_cmd("aider")

        assert "openrouter/custom/model" in cmd
        assert OPENROUTER_DEFAULT_MODEL not in cmd

    def test_openai_key_without_openrouter_base(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")

        cmd = AiderBackend()._build_cmd("aider")

        assert "sk-openai-test" in cmd
        assert OPENROUTER_API_BASE not in cmd
        assert "gpt-4o-mini" in cmd

    def test_multiple_keys_without_provider_returns_error(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-one")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-two")

        llm = AiderBackend._resolve_llm_from_env()
        cmd = AiderBackend()._build_cmd("aider")

        assert llm is not None
        assert "error" in llm
        assert "--openai-api-key" not in cmd

    def test_llm_provider_openai_resolves_conflict(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-one")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-two")
        monkeypatch.setenv("VOICEDEV_LLM_PROVIDER", "openai")

        llm = AiderBackend._resolve_llm_from_env()

        assert llm["provider"] == "openai"
        assert llm["api_key"] == "sk-openai-two"

    def test_anthropic_only_uses_anthropic_flag(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("CLAUDE_MODEL", "anthropic/claude-sonnet-4-20250514")

        llm = AiderBackend._resolve_llm_from_env()
        cmd = AiderBackend()._build_cmd("aider")

        assert llm["provider"] == "anthropic"
        assert llm["wire"] == "anthropic"
        assert "--anthropic-api-key" in cmd
        assert "sk-ant-test" in cmd
        assert "--openai-api-key" not in cmd
        assert "anthropic/claude-sonnet-4-20250514" in cmd

    def test_gemini_api_key_flag(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")

        llm = AiderBackend._resolve_llm_from_env()
        cmd = AiderBackend()._build_cmd("aider")

        assert llm["provider"] == "gemini"
        assert llm["model"] == "gemini/gemini-2.0-flash"
        assert "--api-key" in cmd
        assert "gemini=gem-key" in cmd
        assert "--openai-api-key" not in cmd
        assert "gemini/gemini-2.0-flash" in cmd

    def test_gemini_google_key_alias(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("GOOGLE_API_KEY", "google-gem-key")

        llm = AiderBackend._resolve_llm_from_env()

        assert llm["provider"] == "gemini"
        assert llm["api_key"] == "google-gem-key"

    def test_deepseek_api_key_flag(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
        monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")

        llm = AiderBackend._resolve_llm_from_env()
        cmd = AiderBackend()._build_cmd("aider")

        assert llm["provider"] == "deepseek"
        assert llm["model"] == "deepseek/deepseek-chat"
        assert "deepseek=ds-key" in cmd

    def test_multi_key_anthropic_openrouter_conflict(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or")

        llm = AiderBackend._resolve_llm_from_env()

        assert "error" in llm

    def test_llm_provider_gemini_resolves_conflict(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        monkeypatch.setenv("VOICEDEV_LLM_PROVIDER", "gemini")

        llm = AiderBackend._resolve_llm_from_env()

        assert llm["provider"] == "gemini"

    def test_resolve_llm_returns_none_without_keys(self, monkeypatch):
        _clear_agent_keys(monkeypatch)

        assert AiderBackend._resolve_llm_from_env() is None

    def test_qwen3_model_alias_normalized(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("QWEN3_API_KEY", "sk-or-test")
        monkeypatch.setenv("QWEN3_MODEL", "qwen/qwen3-next-80b-a3b-instruct:free")

        llm = AiderBackend._resolve_llm_from_env()
        cmd = AiderBackend()._build_cmd("aider")

        assert llm["model"] == "openrouter/qwen/qwen3-next-80b-a3b-instruct:free"
        assert "openrouter/qwen/qwen3-next-80b-a3b-instruct:free" in cmd
        assert OPENROUTER_DEFAULT_MODEL not in cmd

    def test_qwen3_model_already_prefixed(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        model = "openrouter/qwen/qwen-2.5-coder-32b-instruct:free"
        monkeypatch.setenv("QWEN3_API_KEY", "sk-or-test")
        monkeypatch.setenv("QWEN3_MODEL", model)

        llm = AiderBackend._resolve_llm_from_env()

        assert llm["model"] == model

    def test_aider_model_wins_over_qwen3_model_for_openrouter(self, monkeypatch):
        _clear_agent_keys(monkeypatch)
        monkeypatch.setenv("QWEN3_API_KEY", "sk-or-test")
        monkeypatch.setenv("QWEN3_MODEL", "qwen/from-qwen3")
        monkeypatch.setenv("AIDER_MODEL", "openrouter/custom/winner")

        llm = AiderBackend._resolve_llm_from_env()

        assert llm["model"] == "openrouter/custom/winner"

    def test_normalize_openrouter_model(self):
        assert AiderBackend._normalize_openrouter_model(
            "qwen/foo"
        ) == "openrouter/qwen/foo"
        assert AiderBackend._normalize_openrouter_model(
            "openrouter/qwen/foo"
        ) == "openrouter/qwen/foo"

    def test_normalize_gemini_model(self):
        assert AiderBackend._normalize_prefixed_model(
            "gemini-2.0-flash", "gemini"
        ) == "gemini/gemini-2.0-flash"
