import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

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
    "require_wake_word": False,
    "noise_reduction": True,
    "session_logging": True,
    "audio_feedback": True,
    "confirm_before_send": False,
    "confirmation_timeout_s": 2.0,
    "show_confidence": True,
    "min_audio_duration_s": 0.4,
    "min_confidence": 0.35,
    "filler_words": [
        "um", "uh", "hmm", "hm", "ah", "oh", "er", "like",
        "you know", "so", "okay", "right", "well",
        "thank you", "thanks",
    ],
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
    require_wake_word: bool = False
    noise_reduction: bool = True
    session_logging: bool = True
    audio_feedback: bool = True
    confirm_before_send: bool = False
    confirmation_timeout_s: float = 2.0
    show_confidence: bool = True
    min_audio_duration_s: float = 0.4
    min_confidence: float = 0.35
    filler_words: list = field(default_factory=lambda: list(DEFAULT_CONFIG["filler_words"]))

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

        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in resolved.items() if k in valid_keys}
        return cls(**filtered)

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
            "require_wake_word": self.require_wake_word,
            "noise_reduction": self.noise_reduction,
            "session_logging": self.session_logging,
            "audio_feedback": self.audio_feedback,
            "confirm_before_send": self.confirm_before_send,
            "confirmation_timeout_s": self.confirmation_timeout_s,
            "show_confidence": self.show_confidence,
            "min_audio_duration_s": self.min_audio_duration_s,
            "min_confidence": self.min_confidence,
            "filler_words": self.filler_words,
        }

        with open(self.config_path(), "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def ensure_dirs(self) -> None:
        self.config_dir().mkdir(parents=True, exist_ok=True)
        self.sessions_dir().mkdir(parents=True, exist_ok=True)


def _resolve_auto_backend(merged: dict) -> dict:
    if merged.get("stt_backend") == "auto":
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if groq_key.strip():
            merged["stt_backend"] = "groq_whisper"
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if api_key.strip():
                merged["stt_backend"] = "whisper_api"
            else:
                merged["stt_backend"] = "faster_whisper"
    return merged
