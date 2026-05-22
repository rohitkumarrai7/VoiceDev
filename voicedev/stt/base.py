from abc import ABC, abstractmethod
from typing import Optional


class STTBackend(ABC):
    @abstractmethod
    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        ...

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...
