from abc import ABC, abstractmethod
from typing import Optional


class AgentBackend(ABC):
    @abstractmethod
    def start(self) -> None:
        ...

    @abstractmethod
    def send_query(self, text: str) -> None:
        ...

    @abstractmethod
    def send_command(self, command: str) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...

    @abstractmethod
    def is_running(self) -> bool:
        ...
