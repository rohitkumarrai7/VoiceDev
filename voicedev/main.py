#!/usr/bin/env python3
"""VoiceDev — Voice-first interface for terminal-based AI coding agents."""

import argparse
import os
import signal
import sys
import time
import threading
from pathlib import Path
from typing import Optional

import numpy as np

from voicedev.config import VoiceDevConfig
from voicedev.audio.capture import AudioCapture
from voicedev.audio.vad import VoiceActivityDetector
from voicedev.audio.noise import reduce_noise
from voicedev.stt.whisper_api import WhisperAPIBackend
from voicedev.stt.faster_whisper import FasterWhisperBackend
from voicedev.stt.groq_whisper import GroqWhisperBackend
from voicedev.stt.base import STTBackend
from voicedev.agent.base import AgentBackend
from voicedev.agent.aider import AiderBackend
from voicedev.commands.router import CommandRouter
from voicedev.tui.display import TUIDisplay
from voicedev.session.logger import SessionLogger

STT_COST_PER_MIN = {
    "groq_whisper": 0.0,
    "whisper_api": 0.006,
    "faster_whisper": 0.0,
}


class WakeWordDetector:
    def __init__(self, phrase: str = "hey dev"):
        self.phrase = phrase.lower()
        self._armed = False

    def process(self, text: str) -> bool:
        if self._armed:
            return True
        text_lower = text.lower().strip()
        if self.phrase in text_lower or text_lower in self.phrase:
            self._armed = True
            return True
        return False

    def disarm(self) -> None:
        self._armed = False

    @property
    def armed(self) -> bool:
        return self._armed


class VoiceDev:
    def __init__(self, config: VoiceDevConfig):
        self.config = config
        self._running = False
        self._paused = False
        self._mode = "PTT"
        self._lock = threading.Lock()

        self._tui = TUIDisplay()
        self._capture = AudioCapture()
        self._vad = VoiceActivityDetector(aggressiveness=config.vad_aggressiveness)
        self._router = CommandRouter()
        self._stt: Optional[STTBackend] = None
        self._agent: Optional[AgentBackend] = None
        self._logger: Optional[SessionLogger] = None
        self._wake = WakeWordDetector(phrase=config.wake_word)

    def _init_stt(self) -> STTBackend:
        if self.config.stt_backend == "groq_whisper":
            backend = GroqWhisperBackend(
                language=self.config.whisper_language,
                model=self.config.groq_whisper_model,
            )
            if not backend.is_available():
                self._tui.console.print("[yellow]GROQ_API_KEY not set. Falling back to faster-whisper.[/yellow]")
                return self._init_faster_whisper()
            return backend
        elif self.config.stt_backend == "whisper_api":
            backend = WhisperAPIBackend(language=self.config.whisper_language)
            if not backend.is_available():
                self._tui.console.print("[yellow]OPENAI_API_KEY not set. Falling back to faster-whisper.[/yellow]")
                return self._init_faster_whisper()
            return backend
        elif self.config.stt_backend == "faster_whisper":
            return self._init_faster_whisper()
        else:
            groq = GroqWhisperBackend(
                language=self.config.whisper_language,
                model=self.config.groq_whisper_model,
            )
            if groq.is_available():
                return groq
            api = WhisperAPIBackend(language=self.config.whisper_language)
            if api.is_available():
                return api
            return self._init_faster_whisper()

    def _init_faster_whisper(self) -> FasterWhisperBackend:
        self._tui.console.print("[dim]Loading local STT model (first run may download ~140MB)...[/dim]")
        return FasterWhisperBackend(model_size=self.config.faster_whisper_model)

    def _init_agent(self) -> AgentBackend:
        return AiderBackend(extra_args=self.config.aider_args)

    def start(self) -> None:
        self.config.ensure_dirs()

        self._stt = self._init_stt()
        self._tui.set_stt_backend(self._stt.name())

        stt_cost = STT_COST_PER_MIN.get(self._stt.name(), 0.0)
        self._tui.set_stt_cost_per_min(stt_cost)

        self._agent = self._init_agent()
        self._agent.start()

        if self.config.session_logging:
            self._logger = SessionLogger(self.config.sessions_dir())
            self._logger.set_stt_backend(self._stt.name())

        self._tui.print_startup_banner(self.config)
        self._tui.print_status()

        self._running = True

        signal.signal(signal.SIGINT, self._handle_signal)

        try:
            if self._mode == "PTT":
                self._run_ptt_loop()
            else:
                self._run_continuous_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def _handle_signal(self, signum, frame):
        self._running = False

    def shutdown(self) -> None:
        self._running = False
        if self._agent:
            self._agent.stop()
        if self._logger:
            self._logger.close()
        self._capture.close()
        self._tui.console.print("[bold cyan]VoiceDev stopped. Session log saved.[/bold cyan]")

    def _process_audio(self, audio: np.ndarray) -> None:
        from voicedev.audio.capture import SAMPLE_RATE
        audio_duration = len(audio) / SAMPLE_RATE

        if self.config.noise_reduction:
            self._tui.set_state(TUIDisplay.STATE_TRANSCRIBING)
            self._tui.print_status()
            audio = reduce_noise(audio)

        start_time = time.time()
        try:
            text = self._stt.transcribe(audio)
        except Exception as e:
            self._tui.console.print(f"[bold red]STT Error: {e}[/bold red]")
            self._tui.set_state(TUIDisplay.STATE_IDLE)
            self._tui.print_status()
            return
        latency_ms = (time.time() - start_time) * 1000

        if not text or not text.strip():
            self._tui.set_state(TUIDisplay.STATE_IDLE)
            self._tui.print_status()
            return

        text = text.strip()

        if self._mode == "Continuous":
            if not self._wake.process(text):
                self._tui.console.print(f"[dim]Wake word required. Heard: '{text}'[/dim]")
                self._tui.set_state(TUIDisplay.STATE_IDLE)
                self._tui.print_status()
                return
            text = text.lower().replace(self._wake.phrase, "").strip()
            if not text:
                self._tui.console.print("[green]Wake word detected. Listening...[/green]")
                self._tui.set_state(TUIDisplay.STATE_LISTENING)
                self._tui.print_status()
                return

        pending = None
        if hasattr(self._agent, "has_pending_prompt"):
            pending = self._agent.has_pending_prompt()

        if pending:
            self._tui.console.print(f"[yellow]Aider asks: {pending}[/yellow]")
            self._tui.console.print(f"[green]Voice responding: {text}[/green]")
            self._tui.record_transcription(text, True, audio_duration, latency_ms)
            if self._logger:
                self._logger.log_entry(f"[prompt response] {text}", True, latency_ms, audio_duration)
            self._agent.respond_to_prompt(text)
            self._tui.set_state(TUIDisplay.STATE_IDLE)
            self._tui.print_status()
            return

        command_result = self._router.route(text)
        is_command = command_result is not None

        self._tui.record_transcription(text, is_command, audio_duration, latency_ms)
        if self._logger:
            self._logger.log_entry(text, is_command, latency_ms, audio_duration)

        self._tui.set_state(TUIDisplay.STATE_SENT)
        self._tui.print_transcription(text, is_command)
        self._tui.print_status()

        if is_command:
            phrase, action = command_result
            self._handle_command(action)
        else:
            self._agent.send_query(text)

        if self._mode == "Continuous":
            self._wake.disarm()

        time.sleep(0.3)
        self._tui.set_state(TUIDisplay.STATE_IDLE)
        self._tui.print_status()

    def _handle_command(self, action: str) -> None:
        if action == "pause":
            self._paused = True
            self._tui.console.print("[yellow]Paused. Say 'start listening' to resume.[/yellow]")
        elif action == "resume":
            self._paused = False
            self._tui.console.print("[green]Resumed.[/green]")
        elif action == "mode_continuous":
            self._mode = "Continuous"
            self._tui.set_mode("Continuous")
            self._tui.console.print("[green]Switched to Continuous (hands-free) mode.[/green]")
            self._tui.console.print(f"[dim]Say your wake word ('{self.config.wake_word}') before each command.[/dim]")
        elif action == "mode_manual":
            self._mode = "PTT"
            self._tui.set_mode("PTT")
            self._tui.console.print("[green]Switched to PTT (push-to-talk) mode.[/green]")
        elif action == "shutdown":
            self._running = False
        elif action in ("Y", "y", "N", "n"):
            if hasattr(self._agent, "respond_to_prompt"):
                self._agent.respond_to_prompt(action)
        else:
            self._agent.send_command(action)

    def _run_ptt_loop(self) -> None:
        import keyboard

        self._tui.console.print("[dim]PTT mode: Hold SPACE to record. Release to send.[/dim]\n")

        while self._running:
            if keyboard.is_pressed("space"):
                if self._paused:
                    time.sleep(0.1)
                    continue

                self._tui.set_state(TUIDisplay.STATE_RECORDING)
                self._tui.print_status()

                audio = self._capture.record_while_key_held("space")

                if len(audio) > 0:
                    self._process_audio(audio)
                else:
                    self._tui.set_state(TUIDisplay.STATE_IDLE)
                    self._tui.print_status()
            else:
                time.sleep(0.05)

    def _run_continuous_loop(self) -> None:
        self._tui.console.print("[dim]Continuous mode: Speak naturally. VAD will detect speech.[/dim]")
        self._tui.console.print(f"[dim]Say '{self.config.wake_word}' before each command.[/dim]\n")

        self._capture.start_stream()

        while self._running:
            if self._paused:
                time.sleep(0.1)
                while self._paused and self._running:
                    time.sleep(0.1)
                if not self._running:
                    break

            self._tui.set_state(TUIDisplay.STATE_LISTENING)
            self._tui.print_status()

            audio = self._vad.detect_speech_segment(
                frame_source=self._capture.read_frame,
                silence_threshold_ms=self.config.silence_threshold_ms,
            )

            if audio is not None and len(audio) > 0:
                self._process_audio(audio)

            time.sleep(0.05)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="voicedev",
        description="VoiceDev — Voice-first interface for terminal coding agents",
    )
    parser.add_argument(
        "--stt",
        choices=["auto", "groq_whisper", "whisper_api", "faster_whisper"],
        default=None,
        help="STT backend to use (default: auto-detect)",
    )
    parser.add_argument(
        "--whisper-model",
        default=None,
        help="faster-whisper model size (default: base.en)",
    )
    parser.add_argument(
        "--mode",
        choices=["ptt", "continuous"],
        default=None,
        help="Input mode: push-to-talk or continuous VAD",
    )
    parser.add_argument(
        "--no-noise-reduction",
        action="store_true",
        help="Disable noise reduction preprocessing",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show session stats and exit",
    )

    args, remaining = parser.parse_known_args()

    return args, remaining


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    search_paths = [
        Path(".env").resolve(),
        Path(__file__).resolve().parent.parent / ".env",
    ]

    for p in search_paths:
        if p.exists():
            load_dotenv(p, override=True)
            return


def main() -> None:
    _load_dotenv()

    args, aider_extra = parse_args()

    overrides = {}
    if args.stt:
        overrides["stt_backend"] = args.stt
    if args.whisper_model:
        overrides["faster_whisper_model"] = args.whisper_model
    if args.no_noise_reduction:
        overrides["noise_reduction"] = False
    if aider_extra:
        overrides["aider_args"] = aider_extra

    config = VoiceDevConfig.load(overrides if overrides else None)
    config.ensure_dirs()

    if not config.config_path().exists():
        config.save()

    app = VoiceDev(config)

    if args.mode == "continuous":
        app._mode = "Continuous"
        app._tui.set_mode("Continuous")

    app.start()


if __name__ == "__main__":
    main()
