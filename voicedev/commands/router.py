from typing import Callable, Dict, Optional, Tuple

from rapidfuzz import fuzz


class CommandRouter:
    COMMANDS: Dict[str, str] = {
        "stop listening": "pause",
        "start listening": "resume",
        "switch to continuous": "mode_continuous",
        "switch to manual": "mode_manual",
        "clear context": "/clear",
        "run tests": "/run pytest",
        "undo that": "/undo",
        "show diff": "/diff",
        "exit": "shutdown",
        "yes": "Y",
        "no": "N",
        "accept": "Y",
        "reject": "N",
    }

    def __init__(self, match_threshold: int = 75):
        self._threshold = match_threshold
        self._custom_commands: Dict[str, str] = {}

    def add_command(self, phrase: str, action: str) -> None:
        self._custom_commands[phrase.lower().strip()] = action

    def remove_command(self, phrase: str) -> None:
        self._custom_commands.pop(phrase.lower().strip(), None)

    def route(self, text: str) -> Optional[Tuple[str, str]]:
        text_lower = text.lower().strip()
        if not text_lower:
            return None

        all_commands = {**self.COMMANDS, **self._custom_commands}

        best_match = None
        best_score = 0

        for phrase, action in all_commands.items():
            score = fuzz.ratio(text_lower, phrase)
            if score > best_score:
                best_score = score
                best_match = (phrase, action)

            if text_lower.startswith("add file"):
                remainder = text_lower[len("add file"):].strip()
                if remainder:
                    return (text_lower, f"/add {remainder}")

        if best_match and best_score >= self._threshold:
            return best_match

        return None
