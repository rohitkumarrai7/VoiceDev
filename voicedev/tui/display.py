import time
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout


class TUIDisplay:
    STATE_IDLE = "idle"
    STATE_LISTENING = "listening"
    STATE_RECORDING = "recording"
    STATE_TRANSCRIBING = "transcribing"
    STATE_SENT = "sent"

    STATE_ICONS = {
        STATE_IDLE: "⏸️",
        STATE_LISTENING: "🎙️",
        STATE_RECORDING: "🔴",
        STATE_TRANSCRIBING: "⚙️",
        STATE_SENT: "✅",
    }

    def __init__(self):
        self._console = Console()
        self._state = self.STATE_IDLE
        self._mode = "PTT"
        self._last_text = ""
        self._query_count = 0
        self._total_audio_s = 0.0
        self._estimated_cost = 0.0
        self._stt_backend = "auto"
        self._log_entries = []

    @property
    def console(self) -> Console:
        return self._console

    def set_state(self, state: str) -> None:
        self._state = state

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def set_stt_backend(self, name: str) -> None:
        self._stt_backend = name

    def record_transcription(
        self,
        text: str,
        is_command: bool = False,
        audio_duration: float = 0.0,
        latency_ms: float = 0.0,
    ) -> None:
        self._last_text = text
        self._query_count += 1
        self._total_audio_s += audio_duration
        self._estimated_cost += (audio_duration / 60.0) * 0.006

        kind = "CMD" if is_command else "Q"
        self._log_entries.append(f"[{kind}] {text}")

        if len(self._log_entries) > 50:
            self._log_entries = self._log_entries[-50:]

    def build_panel(self) -> Panel:
        icon = self.STATE_ICONS.get(self._state, "?")
        state_text = self._state.upper()

        header = Text()
        header.append(f" VoiceDev ", style="bold cyan")
        header.append(f"| {icon} {state_text} ", style="bold")
        header.append(f"| Mode: {self._mode} ", style="green")
        header.append(f"| STT: {self._stt_backend} ", style="yellow")

        info = Text()
        info.append(f"Queries: {self._query_count} ", style="white")
        info.append(f"| Audio: {self._total_audio_s:.1f}s ", style="white")
        info.append(f"| Est. cost: ${self._estimated_cost:.4f}", style="white")

        body_lines = [header, info]

        if self._last_text:
            body_lines.append(Text())
            last = Text()
            last.append("Last: ", style="dim")
            last.append(f'"{self._last_text}"', style="italic")
            body_lines.append(last)

        content = Text("\n").join(body_lines)

        return Panel(
            content,
            title="[bold]VoiceDev[/bold]",
            border_style="blue",
            padding=(0, 1),
        )

    def print_status(self) -> None:
        self._console.print(self.build_panel())

    def print_startup_banner(self, config) -> None:
        self._console.print()
        self._console.rule("[bold cyan]VoiceDev — Speak. Code. Ship.[/bold cyan]")
        self._console.print()
        self._console.print(f"  STT Backend:   [yellow]{self._stt_backend}[/yellow]")
        self._console.print(f"  Mode:          [green]{self._mode}[/green]")
        self._console.print(f"  VAD Level:     {config.vad_aggressiveness}")
        self._console.print(f"  Silence:       {config.silence_threshold_ms}ms")
        self._console.print(f"  Noise Reduce:  {config.noise_reduction}")
        self._console.print(f"  Agent:         {config.agent}")
        self._console.print()
        self._console.print("  [bold]Controls:[/bold]")
        self._console.print("    [dim]PTT:[/dim] Hold SPACE to record, release to send")
        self._console.print("    [dim]Voice:[/dim] Say 'switch to continuous' for hands-free")
        self._console.print("    [dim]Exit:[/dim] Say 'exit' or press Ctrl+C")
        self._console.print()
        self._console.rule()

    def print_transcription(self, text: str, is_command: bool = False) -> None:
        kind = "[bold magenta]CMD[/bold magenta]" if is_command else "[bold green]YOU[/bold green]"
        self._console.print(f"\n{kind}: {text}\n")
