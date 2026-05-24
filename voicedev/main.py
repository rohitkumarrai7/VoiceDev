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
from voicedev.audio.capture import AudioCapture, SAMPLE_RATE
from voicedev.audio.vad import VoiceActivityDetector
from voicedev.audio.noise import reduce_noise
from voicedev.audio.feedback import AudioFeedback
from voicedev.audio.wakeword import WakeWordDetector
from voicedev.stt.whisper_api import WhisperAPIBackend
from voicedev.stt.faster_whisper import FasterWhisperBackend
from voicedev.stt.groq_whisper import GroqWhisperBackend
from voicedev.stt.base import STTBackend, TranscriptionResult
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

MODE_PTT = "PTT"
MODE_HANDS_FREE = "HandsFree"
MODE_CONTINUOUS = "Continuous"


class VoiceDev:
    def __init__(self, config: VoiceDevConfig):
        self.config = config
        self._running = False
        self._paused = False
        self._mode = MODE_PTT
        self._lock = threading.Lock()

        self._tui = TUIDisplay()
        self._capture = AudioCapture()
        self._vad = VoiceActivityDetector(aggressiveness=config.vad_aggressiveness)
        self._router = CommandRouter()
        self._feedback = AudioFeedback(enabled=config.audio_feedback)
        self._wake = WakeWordDetector(phrase=config.wake_word)
        self._stt: Optional[STTBackend] = None
        self._agent: Optional[AgentBackend] = None
        self._logger: Optional[SessionLogger] = None

        self._filler_set = {w.lower().strip() for w in config.filler_words}

    # ── STT / Agent init ─────────────────────────────────────

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
        backend = AiderBackend(extra_args=self.config.aider_args)
        backend.set_on_restart(self._on_agent_restart)
        return backend

    def _on_agent_restart(self, attempt: int) -> None:
        self._tui.console.print(f"[bold yellow]Aider restarting (attempt {attempt})...[/bold yellow]")
        self._feedback.play("error")

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        self.config.ensure_dirs()

        self._stt = self._init_stt()
        self._tui.set_stt_backend(self._stt.name())
        self._tui.set_show_confidence(self.config.show_confidence)
        self._tui.set_wake_backend(self._wake.backend_name)

        stt_cost = STT_COST_PER_MIN.get(self._stt.name(), 0.0)
        self._tui.set_stt_cost_per_min(stt_cost)

        self._agent = self._init_agent()
        self._agent.start()

        if self.config.session_logging:
            self._logger = SessionLogger(self.config.sessions_dir())
            self._logger.set_stt_backend(self._stt.name())

        self._tui.print_startup_banner(self.config, self._mode)
        self._tui.print_status()

        self._running = True
        signal.signal(signal.SIGINT, self._handle_signal)

        try:
            self._dispatch_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def _dispatch_loop(self) -> None:
        while self._running:
            if self._mode == MODE_PTT:
                self._run_ptt_loop()
            elif self._mode == MODE_HANDS_FREE:
                self._run_hands_free_loop()
            elif self._mode == MODE_CONTINUOUS:
                self._run_continuous_loop()
            else:
                self._run_ptt_loop()

    def _handle_signal(self, signum, frame):
        self._running = False

    def shutdown(self) -> None:
        self._running = False
        if self._agent:
            self._agent.stop()
        if self._logger:
            self._logger.close()
        self._capture.close()
        self._feedback.play("stop")
        self._tui.console.print("[bold cyan]VoiceDev stopped. Session log saved.[/bold cyan]")

    # ── Smart filtering ───────────────────────────────────────

    def _is_garbage(
        self,
        audio: np.ndarray,
        result: TranscriptionResult,
        strict: bool = True,
    ) -> Optional[str]:
        """Return a rejection reason string, or None if the audio is good."""
        text = (result.text or "").strip()
        if not text:
            return "empty transcription"

        if not any(ch.isalnum() for ch in text):
            return "no words detected"

        if result.has_confidence and result.confidence < self.config.min_confidence:
            return f"low confidence ({result.confidence_pct} < {int(self.config.min_confidence*100)}%)"

        if not strict:
            return None

        audio_duration = len(audio) / SAMPLE_RATE
        if audio_duration < self.config.min_audio_duration_s:
            return f"too short ({audio_duration:.1f}s < {self.config.min_audio_duration_s}s)"

        text_lower = text.lower().strip().rstrip(".!?,;:")
        if text_lower in self._filler_set:
            return f"filler word ('{text_lower}')"

        return None

    # ── Audio processing pipeline ─────────────────────────────

    def _process_audio(self, audio: np.ndarray, apply_smart_filter: bool = False) -> None:
        audio_duration = len(audio) / SAMPLE_RATE

        if self.config.noise_reduction:
            self._tui.set_state(TUIDisplay.STATE_TRANSCRIBING)
            self._tui.print_status()
            audio = reduce_noise(audio)

        self._feedback.play("stop")

        start_time = time.time()
        try:
            result: TranscriptionResult = self._stt.transcribe(audio)
        except Exception as e:
            self._tui.console.print(f"[bold red]STT Error: {e}[/bold red]")
            self._feedback.play("error")
            self._tui.set_state(TUIDisplay.STATE_IDLE)
            self._tui.print_status()
            return
        latency_ms = (time.time() - start_time) * 1000

        text = result.text.strip() if result.text else ""
        confidence = result.confidence

        reason = self._is_garbage(audio, result, strict=apply_smart_filter)
        if reason:
            self._tui.console.print(f"[dim]Filtered: {reason} — '{text}'[/dim]")
            self._tui.set_state(TUIDisplay.STATE_IDLE)
            self._tui.print_status()
            return

        if self._mode == MODE_CONTINUOUS and self.config.require_wake_word:
            if not self._wake.detect_text(text):
                self._tui.console.print(f"[dim]Wake word required. Heard: '{text}'[/dim]")
                self._tui.set_state(TUIDisplay.STATE_IDLE)
                self._tui.print_status()
                return
            text = text.lower().replace(self._wake.phrase, "").strip()
            if not text:
                self._tui.console.print("[green]Wake word detected. Listening...[/green]")
                self._feedback.play("command")
                self._tui.set_state(TUIDisplay.STATE_LISTENING)
                self._tui.print_status()
                return

        if self.config.confirm_before_send:
            confirmed = self._confirm_transcription(text)
            if not confirmed:
                self._feedback.play("cancel")
                self._tui.print_cancelled()
                self._tui.set_state(TUIDisplay.STATE_IDLE)
                self._tui.print_status()
                return

        pending = None
        if hasattr(self._agent, "has_pending_prompt"):
            pending = self._agent.has_pending_prompt()

        if pending:
            self._tui.console.print(f"[yellow]Aider asks: {pending}[/yellow]")
            self._tui.console.print(f"[green]Voice responding: {text}[/green]")
            self._tui.record_transcription(text, True, audio_duration, latency_ms, confidence)
            if self._logger:
                self._logger.log_entry(f"[prompt response] {text}", True, latency_ms, audio_duration, confidence)
            self._agent.respond_to_prompt(text)
            self._feedback.play("success")
            self._tui.set_state(TUIDisplay.STATE_IDLE)
            self._tui.print_status()
            return

        command_result = self._router.route(text)
        is_command = command_result is not None

        self._tui.record_transcription(text, is_command, audio_duration, latency_ms, confidence)
        if self._logger:
            self._logger.log_entry(text, is_command, latency_ms, audio_duration, confidence)

        self._tui.set_state(TUIDisplay.STATE_SENT)
        self._tui.print_transcription(text, is_command, confidence)
        self._tui.print_status()

        if is_command:
            phrase, action = command_result
            self._feedback.play("command")
            self._handle_command(action)
        else:
            self._feedback.play("success")
            self._agent.send_query(text)

        if self._mode == MODE_CONTINUOUS:
            self._wake.disarm()

        time.sleep(0.3)
        self._tui.set_state(TUIDisplay.STATE_IDLE)
        self._tui.print_status()

    # ── Confirmation ──────────────────────────────────────────

    def _confirm_transcription(self, text: str) -> bool:
        self._tui.set_state(TUIDisplay.STATE_CONFIRMING)
        self._tui.print_confirmation_prompt(text, self.config.confirmation_timeout_s)

        deadline = time.time() + self.config.confirmation_timeout_s
        while time.time() < deadline:
            if not self._running:
                return False

            if self._mode == MODE_PTT:
                import keyboard
                if keyboard.is_pressed(self.config.ptt_key):
                    quick_audio = self._capture.record_while_key_held(self.config.ptt_key)
                    if len(quick_audio) > 0:
                        try:
                            quick_result = self._stt.transcribe(quick_audio)
                            word = quick_result.text.lower().strip()
                        except Exception:
                            word = ""
                        if word in ("cancel", "no", "stop", "discard", "not that", "wrong"):
                            return False
                        if word in ("send", "yes", "go", "confirm", "ok"):
                            return True
            time.sleep(0.1)

        self._tui.print_auto_sent()
        return True

    # ── Command handling ──────────────────────────────────────

    def _handle_command(self, action: str) -> None:
        if action == "pause":
            self._paused = True
            self._tui.console.print("[yellow]Paused. Say 'start listening' to resume.[/yellow]")
        elif action == "resume":
            self._paused = False
            self._tui.console.print("[green]Resumed.[/green]")
        elif action == "mode_continuous":
            self._switch_mode(MODE_CONTINUOUS)
        elif action == "mode_hands_free":
            self._switch_mode(MODE_HANDS_FREE)
        elif action == "mode_manual":
            self._switch_mode(MODE_PTT)
        elif action == "shutdown":
            self._running = False
        elif action in ("Y", "y", "N", "n"):
            if hasattr(self._agent, "respond_to_prompt"):
                self._agent.respond_to_prompt(action)
        elif action == "list_files":
            file_list = CommandRouter.list_project_files()
            self._tui.print_file_list(file_list)
        elif action == "show_status":
            self._tui.print_status()
        elif action == "show_history":
            self._tui.print_history(self._router.history)
        elif action == "help":
            self._tui.print_help(CommandRouter.get_help_text())
        else:
            self._agent.send_command(action)

    def _switch_mode(self, new_mode: str) -> None:
        old_mode = self._mode
        self._mode = new_mode
        self._tui.set_mode(new_mode)

        if new_mode == MODE_PTT:
            self._tui.console.print("[green]Switched to PTT mode. Hold SPACE to record, release to send.[/green]")
            if self._capture.is_streaming:
                self._capture.stop_stream()
        elif new_mode == MODE_HANDS_FREE:
            self._tui.console.print("[green]Switched to Hands-Free mode. Just speak — no button, no wake word.[/green]")
            if not self._capture.is_streaming:
                self._capture.start_stream()
            self._capture.drain_queue()
        elif new_mode == MODE_CONTINUOUS:
            self._tui.console.print("[green]Switched to Continuous mode (wake word required).[/green]")
            self._tui.console.print(f"[dim]Say '{self.config.wake_word}' before each command.[/dim]")
            if not self._capture.is_streaming:
                self._capture.start_stream()
            self._capture.drain_queue()

    # ── PTT loop (hold-to-record, most reliable default) ──────

    def _run_ptt_loop(self) -> None:
        import keyboard

        self._tui.console.print("[dim]PTT mode: Hold SPACE to record. Release to send.[/dim]\n")

        while self._running and self._mode == MODE_PTT:
            if keyboard.is_pressed(self.config.ptt_key):
                if self._paused:
                    time.sleep(0.1)
                    continue

                self._feedback.play("start")
                self._tui.set_state(TUIDisplay.STATE_RECORDING)
                self._tui.print_status()

                audio = self._capture.record_while_key_held(self.config.ptt_key)

                if len(audio) > 0:
                    self._process_audio(audio, apply_smart_filter=False)
                else:
                    self._tui.set_state(TUIDisplay.STATE_IDLE)
                    self._tui.print_status()
            else:
                time.sleep(0.05)

    # ── Hands-Free loop (VAD, no wake word, smart filter) ─────

    def _run_hands_free_loop(self) -> None:
        self._tui.console.print("[dim]Hands-Free mode: Just speak naturally. Smart filter removes noise.[/dim]")
        self._tui.console.print("[dim]Say 'stop listening' to pause, 'switch to manual' for PTT.[/dim]\n")

        if not self._capture.is_streaming:
            self._capture.start_stream()
        self._capture.drain_queue()

        while self._running and self._mode == MODE_HANDS_FREE:
            if self._paused:
                time.sleep(0.1)
                while self._paused and self._running and self._mode == MODE_HANDS_FREE:
                    time.sleep(0.1)
                if not self._running or self._mode != MODE_HANDS_FREE:
                    break
                self._capture.drain_queue()

            self._tui.set_state(TUIDisplay.STATE_LISTENING)
            self._tui.print_status()

            audio = self._vad.detect_speech_segment(
                frame_source=self._capture.read_frame,
                silence_threshold_ms=self.config.silence_threshold_ms,
            )

            if audio is not None and len(audio) > 0:
                self._feedback.play("start")
                self._process_audio(audio, apply_smart_filter=True)

            time.sleep(0.05)

    # ── Continuous loop (VAD + wake word) ─────────────────────

    def _run_continuous_loop(self) -> None:
        self._tui.console.print("[dim]Continuous mode: Speak naturally. VAD will detect speech.[/dim]")
        self._tui.console.print(f"[dim]Say '{self.config.wake_word}' before each command.[/dim]\n")

        if not self._capture.is_streaming:
            self._capture.start_stream()
        self._capture.drain_queue()

        while self._running and self._mode == MODE_CONTINUOUS:
            if self._paused:
                time.sleep(0.1)
                while self._paused and self._running and self._mode == MODE_CONTINUOUS:
                    time.sleep(0.1)
                if not self._running or self._mode != MODE_CONTINUOUS:
                    break
                self._capture.drain_queue()

            self._tui.set_state(TUIDisplay.STATE_LISTENING)
            self._tui.print_status()

            audio = self._vad.detect_speech_segment(
                frame_source=self._capture.read_frame,
                silence_threshold_ms=self.config.silence_threshold_ms,
            )

            if audio is not None and len(audio) > 0:
                self._feedback.play("start")
                self._process_audio(audio, apply_smart_filter=True)

            time.sleep(0.05)


# ── CLI ───────────────────────────────────────────────────────

def parse_args():
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
        choices=["ptt", "hands_free", "continuous"],
        default=None,
        help="Input mode: ptt (hold space), hands_free (zero-touch), continuous (wake word)",
    )
    parser.add_argument(
        "--no-noise-reduction",
        action="store_true",
        help="Disable noise reduction preprocessing",
    )
    parser.add_argument(
        "--no-feedback",
        action="store_true",
        help="Disable audio feedback beeps",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Enable confirmation before sending to agent",
    )
    parser.add_argument(
        "--no-confidence",
        action="store_true",
        help="Hide STT confidence scores",
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
    if args.no_feedback:
        overrides["audio_feedback"] = False
    if args.confirm:
        overrides["confirm_before_send"] = True
    if args.no_confidence:
        overrides["show_confidence"] = False
    if aider_extra:
        overrides["aider_args"] = aider_extra

    config = VoiceDevConfig.load(overrides if overrides else None)
    config.ensure_dirs()

    if not config.config_path().exists():
        config.save()

    app = VoiceDev(config)

    if args.mode == "hands_free":
        app._mode = MODE_HANDS_FREE
        app._tui.set_mode(MODE_HANDS_FREE)
    elif args.mode == "continuous":
        app._mode = MODE_CONTINUOUS
        app._tui.set_mode(MODE_CONTINUOUS)
        config.require_wake_word = True

    app.start()


if __name__ == "__main__":
    main()
