import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import yaml


DEFAULT_CONFIG = {
    "stt_backend": "auto",
    "faster_whisper_model": "base.en",
    "groq_whisper_model": "whisper-large-v3-turbo",
    "whisper_language": "en",
    "vad_aggressiveness": 2,
    "silence_threshold_ms": 1200,
    "ptt_key": "space",
    "agent": "aider",
    "aider_args": [],
    "wake_word": "hey dev",
    "noise_reduction": True,
    "session_logging": True,
}


@dataclass
class VoiceDevConfig:
    stt_backend: str = "auto"
    faster_whisper_model: str = "base.en"
    groq_whisper_model: str = "whisper-large-v3-turbo"
    whisper_language: str = "en"
    vad_aggressiveness: int = 2
    silence_threshold_ms: int = 1200
    ptt_key: str = "space"
    agent: str = "aider"
    aider_args: list = field(default_factory=list)
    wake_word: str = "hey dev"
    noise_reduction: bool = True
    session_logging: bool = True

    @classmethod
    def config_dir(cls) -> Path:
        return Path.home() / ".voicedev"

    @classmethod
    def config_path(cls) -> Path:
        return cls.config_dir() / "config.yaml"

    @classmethod
    def sessions_dir(cls) -> Path:
        return cls.config_dir() / "sessions"

    @classmethod
    def load(cls, overrides: Optional[dict] = None) -> "VoiceDevConfig":
        merged = dict(DEFAULT_CONFIG)

        config_path = cls.config_path()
        if config_path.exists():
            with open(config_path, "r") as f:
                file_config = yaml.safe_load(f) or {}
            merged.update(file_config)

        if overrides:
            merged.update(overrides)

        resolved = _resolve_auto_backend(merged)
        return cls(**resolved)

    def save(self) -> None:
        config_dir = self.config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "stt_backend": self.stt_backend,
            "faster_whisper_model": self.faster_whisper_model,
            "groq_whisper_model": self.groq_whisper_model,
            "whisper_language": self.whisper_language,
            "vad_aggressiveness": self.vad_aggressiveness,
            "silence_threshold_ms": self.silence_threshold_ms,
            "ptt_key": self.ptt_key,
            "agent": self.agent,
            "aider_args": self.aider_args,
            "wake_word": self.wake_word,
            "noise_reduction": self.noise_reduction,
            "session_logging": self.session_logging,
        }

        with open(self.config_path(), "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def ensure_dirs(self) -> None:
        self.config_dir().mkdir(parents=True, exist_ok=True)
        self.sessions_dir().mkdir(parents=True, exist_ok=True)


def _resolve_auto_backend(merged: dict) -> dict:
    if merged["stt_backend"] == "auto":
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if groq_key.strip():
            merged["stt_backend"] = "groq_whisper"
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if api_key.strip():
                merged["stt_backend"] = "whisper_api"
            else:
                merged["stt_backend"] = "faster_whisper"
        # Add a check for whisper_api availability
        if merged["stt_backend"] == "whisper_api":
            try:
                import openai
                openai.OpenAI()
            except Exception:
                merged["stt_backend"] = "faster_whisper"
    return merged
