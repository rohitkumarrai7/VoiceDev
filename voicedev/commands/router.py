import os
import glob as globmod
from typing import Callable, Dict, List, Optional, Tuple

from rapidfuzz import fuzz


class CommandRouter:
    COMMANDS: Dict[str, str] = {
        # Listening control
        "stop listening": "pause",
        "start listening": "resume",
        "switch to continuous": "mode_continuous",
        "switch to hands free": "mode_hands_free",
        "hands free mode": "mode_hands_free",
        "go hands free": "mode_hands_free",
        "switch to manual": "mode_manual",
        # Aider slash commands
        "clear context": "/clear",
        "run tests": "/run pytest",
        "undo that": "/undo",
        "cancel that": "/undo",
        "revert that": "/undo",
        "show diff": "/diff",
        "commit changes": "/commit",
        "show help": "/help",
        "architect mode": "/chat-mode architect",
        "code mode": "/chat-mode code",
        "ask mode": "/chat-mode ask",
        "show map": "/map",
        "show tokens": "/tokens",
        "drop all files": "/drop",
        "reset session": "/reset",
        "show git log": "/git log --oneline -10",
        "git status": "/git status",
        # VoiceDev control
        "list files": "list_files",
        "show status": "show_status",
        "show history": "show_history",
        "help me": "help",
        "what can i say": "help",
        "exit": "shutdown",
        "quit": "shutdown",
        # Prompt responses
        "yes": "Y",
        "no": "N",
        "accept": "Y",
        "reject": "N",
    }

    PREFIX_COMMANDS = [
        ("add file", "/add"),
        ("drop file", "/drop"),
        ("run command", "/run"),
        ("ask about", "/ask"),
    ]

    def __init__(self, match_threshold: int = 75):
        self._threshold = match_threshold
        self._custom_commands: Dict[str, str] = {}
        self._history: List[str] = []

    def add_command(self, phrase: str, action: str) -> None:
        self._custom_commands[phrase.lower().strip()] = action

    def remove_command(self, phrase: str) -> None:
        self._custom_commands.pop(phrase.lower().strip(), None)

    @property
    def history(self) -> List[str]:
        return list(self._history)

    def route(self, text: str) -> Optional[Tuple[str, str]]:
        text_lower = text.lower().strip()
        if not text_lower:
            return None

        self._history.append(text_lower)
        if len(self._history) > 100:
            self._history = self._history[-100:]

        for prefix, action_prefix in self.PREFIX_COMMANDS:
            if text_lower.startswith(prefix):
                remainder = text_lower[len(prefix):].strip()
                if remainder:
                    return (text_lower, f"{action_prefix} {remainder}")

        all_commands = {**self.COMMANDS, **self._custom_commands}

        best_match = None
        best_score = 0

        for phrase, action in all_commands.items():
            score = fuzz.ratio(text_lower, phrase)
            if score > best_score:
                best_score = score
                best_match = (phrase, action)

        if best_match and best_score >= self._threshold:
            return best_match

        return None

    @staticmethod
    def list_project_files(max_files: int = 30) -> str:
        cwd = os.getcwd()
        entries = []
        for item in sorted(os.listdir(cwd)):
            if item.startswith(".") or item == "__pycache__" or item == "node_modules":
                continue
            path = os.path.join(cwd, item)
            if os.path.isdir(path):
                entries.append(f"  [dir]  {item}/")
            else:
                size_kb = os.path.getsize(path) / 1024
                entries.append(f"  [file] {item} ({size_kb:.1f}KB)")
            if len(entries) >= max_files:
                entries.append(f"  ... and more")
                break
        return "\n".join(entries) if entries else "  (empty directory)"

    @staticmethod
    def get_help_text() -> str:
        lines = [
            "Voice Commands:",
            "",
            "  Listening Control:",
            '    "stop listening"       — Pause voice recording',
            '    "start listening"      — Resume voice recording',
            '    "switch to continuous" — VAD + wake word mode',
            '    "go hands free"       — VAD hands-free (no wake word)',
            '    "switch to manual"     — Switch back to PTT mode',
            "",
            "  Aider Commands:",
            '    "clear context"    — Clear Aider chat context',
            '    "run tests"        — Run pytest via Aider',
            '    "undo that"        — Undo last Aider change',
            '    "cancel that"      — Undo last Aider change',
            '    "show diff"        — Show current diff',
            '    "commit changes"   — Commit via Aider',
            '    "architect mode"   — Switch to architect mode',
            '    "code mode"        — Switch to code mode',
            '    "ask mode"         — Switch to ask mode',
            '    "show map"         — Show repo map',
            '    "drop all files"   — Drop all files from chat',
            '    "git status"       — Show git status',
            "",
            "  File Commands:",
            '    "add file [name]"  — Add file to Aider chat',
            '    "drop file [name]" — Drop file from Aider chat',
            '    "list files"       — List project files',
            "",
            "  VoiceDev Control:",
            '    "show status"      — Show session statistics',
            '    "show history"     — Show recent voice inputs',
            '    "help me"          — Show this help text',
            '    "exit" / "quit"    — Graceful shutdown',
            "",
            "  Prompt Responses:",
            '    "yes" / "accept"   — Accept Aider prompt',
            '    "no" / "reject"    — Reject Aider prompt',
        ]
        return "\n".join(lines)
