import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class TUIDisplay:
    STATE_IDLE = "idle"
    STATE_LISTENING = "listening"
    STATE_RECORDING = "recording"
    STATE_TRANSCRIBING = "transcribing"
    STATE_CONFIRMING = "confirming"
    STATE_SENT = "sent"

    STATE_ICONS = {
        STATE_IDLE: "⏸️",
        STATE_LISTENING: "🎙️",
        STATE_RECORDING: "🔴",
        STATE_TRANSCRIBING: "⚙️",
        STATE_CONFIRMING: "❓",
        STATE_SENT: "✅",
    }

    def __init__(self):
        self._console = Console()
        self._state = self.STATE_IDLE
        self._mode = "PTT"
        self._last_text = ""
        self._last_confidence = -1.0
        self._query_count = 0
        self._command_count = 0
        self._total_audio_s = 0.0
        self._estimated_cost = 0.0
        self._stt_backend = "auto"
        self._stt_cost_per_min = 0.0
        self._show_confidence = True
        self._wake_backend = "substring"

    @property
    def console(self) -> Console:
        return self._console

    def set_state(self, state: str) -> None:
        self._state = state

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def set_stt_backend(self, name: str) -> None:
        self._stt_backend = name

    def set_stt_cost_per_min(self, cost: float) -> None:
        self._stt_cost_per_min = cost

    def set_show_confidence(self, show: bool) -> None:
        self._show_confidence = show

    def set_wake_backend(self, name: str) -> None:
        self._wake_backend = name

    def record_transcription(
        self,
        text: str,
        is_command: bool = False,
        audio_duration: float = 0.0,
        latency_ms: float = 0.0,
        confidence: float = -1.0,
    ) -> None:
        self._last_text = text
        self._last_confidence = confidence
        self._query_count += 1
        if is_command:
            self._command_count += 1
        self._total_audio_s += audio_duration
        self._estimated_cost += (audio_duration / 60.0) * self._stt_cost_per_min

    def build_panel(self) -> Panel:
        icon = self.STATE_ICONS.get(self._state, "?")
        state_text = self._state.upper()

        header = Text()
        header.append(" VoiceDev ", style="bold cyan")
        header.append(f"| {icon} {state_text} ", style="bold")
        header.append(f"| Mode: {self._mode} ", style="green")
        header.append(f"| STT: {self._stt_backend} ", style="yellow")

        info = Text()
        info.append(f"Queries: {self._query_count} ", style="white")
        info.append(f"| Commands: {self._command_count} ", style="magenta")
        info.append(f"| Audio: {self._total_audio_s:.1f}s ", style="white")
        info.append(f"| Cost: ${self._estimated_cost:.4f}", style="white")

        body_lines = [header, info]

        if self._last_text:
            body_lines.append(Text())
            last = Text()
            last.append("Last: ", style="dim")
            last.append(f'"{self._last_text}"', style="italic")
            if self._show_confidence and self._last_confidence >= 0:
                pct = self._last_confidence * 100
                style = "green" if pct >= 80 else "yellow" if pct >= 60 else "red"
                last.append(f" [{pct:.0f}%]", style=style)
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

    def print_startup_banner(self, config, mode: str = "PTT") -> None:
        self._console.print()
        self._console.rule("[bold cyan]VoiceDev — Speak. Code. Ship.[/bold cyan]")
        self._console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="dim", width=18)
        table.add_column()
        table.add_row("STT Backend", f"[yellow]{self._stt_backend}[/yellow]")
        table.add_row("Mode", f"[green]{mode}[/green]")
        table.add_row("VAD Level", str(config.vad_aggressiveness))
        table.add_row("Silence Threshold", f"{config.silence_threshold_ms}ms")
        table.add_row("Noise Reduce", str(config.noise_reduction))
        table.add_row("Audio Feedback", str(config.audio_feedback))
        table.add_row("Confidence", str(config.show_confidence))
        table.add_row("Smart Filter", f"min {config.min_audio_duration_s}s / {int(config.min_confidence*100)}% conf")
        if config.require_wake_word:
            table.add_row("Wake Word", f'"{config.wake_word}" ({self._wake_backend})')
        table.add_row("Agent", config.agent)
        self._console.print(table)

        self._console.print()
        self._console.print("  [bold]Controls:[/bold]")
        if mode == "PTT":
            self._console.print("    [dim]PTT:[/dim]    Hold SPACE to record, release to send")
        elif mode == "HandsFree":
            self._console.print("    [dim]Voice:[/dim]  Just speak — no button, no wake word needed")
        else:
            self._console.print("    [dim]Voice:[/dim]  Say wake word, then your command")
        self._console.print("    [dim]Modes:[/dim]  Say 'go hands free' / 'switch to manual' / 'switch to continuous'")
        self._console.print("    [dim]Help:[/dim]   Say 'help me' for all voice commands")
        self._console.print("    [dim]Exit:[/dim]   Say 'exit' or press Ctrl+C")
        self._console.print()
        self._console.rule()

    def print_transcription(self, text: str, is_command: bool = False, confidence: float = -1.0) -> None:
        kind = "[bold magenta]CMD[/bold magenta]" if is_command else "[bold green]YOU[/bold green]"
        conf_str = ""
        if self._show_confidence and confidence >= 0:
            pct = confidence * 100
            style = "green" if pct >= 80 else "yellow" if pct >= 60 else "red"
            conf_str = f" [{style}][{pct:.0f}% confidence][/{style}]"
        self._console.print(f"\n{kind}: {text}{conf_str}\n")

    def print_confirmation_prompt(self, text: str, timeout_s: float) -> None:
        self._console.print(
            f'\n[bold yellow]Heard:[/bold yellow] "{text}"'
            f"\n[dim]Say 'send' to confirm, 'cancel' to discard "
            f"(auto-sends in {timeout_s:.0f}s)...[/dim]"
        )

    def print_cancelled(self) -> None:
        self._console.print("[bold red]Cancelled.[/bold red] Discarded transcription.\n")

    def print_auto_sent(self) -> None:
        self._console.print("[dim]Auto-confirmed.[/dim]")

    def print_file_list(self, file_list: str) -> None:
        self._console.print(Panel(
            file_list,
            title="[bold]Project Files[/bold]",
            border_style="cyan",
            padding=(0, 1),
        ))

    def print_history(self, history: list) -> None:
        if not history:
            self._console.print("[dim]No voice history yet.[/dim]")
            return
        recent = history[-15:]
        lines = [f"  {i+1}. {entry}" for i, entry in enumerate(recent)]
        self._console.print(Panel(
            "\n".join(lines),
            title="[bold]Recent Voice Inputs[/bold]",
            border_style="cyan",
            padding=(0, 1),
        ))

    def print_help(self, help_text: str) -> None:
        self._console.print(Panel(
            help_text,
            title="[bold]Voice Commands[/bold]",
            border_style="green",
            padding=(0, 1),
        ))
