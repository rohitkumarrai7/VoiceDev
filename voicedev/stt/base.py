from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TranscriptionResult:
    text: str
    confidence: float = -1.0
    language: str = ""
    duration_s: float = 0.0

    @property
    def has_confidence(self) -> bool:
        return self.confidence >= 0.0

    @property
    def confidence_pct(self) -> str:
        if not self.has_confidence:
            return "n/a"
        return f"{self.confidence * 100:.0f}%"


class STTBackend(ABC):
    @abstractmethod
    def transcribe(self, audio_data, sample_rate: int = 16000) -> TranscriptionResult:
        ...

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...
