import subprocess
import sys
import threading
import time
import shutil
from typing import List, Optional

from voicedev.agent.base import AgentBackend


class AiderBackend(AgentBackend):
    def __init__(self, extra_args: Optional[List[str]] = None):
        self._extra_args = extra_args or []
        self._process: Optional[subprocess.Popen] = None
        self._watchdog: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        aider_path = shutil.which("aider")
        if aider_path is None:
            print("[VoiceDev] ERROR: 'aider' not found on PATH. Install it with: pip install aider-chat")
            print("[VoiceDev] Falling back to echo mode (voice input will be printed but not sent to an agent).")
            self._running = True
            return

        cmd = [aider_path] + self._extra_args
        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=None,
                stderr=None,
                bufsize=1,
                text=True,
            )
            self._running = True
            self._watchdog = threading.Thread(target=self._watch_process, daemon=True)
            self._watchdog.start()
            print(f"[VoiceDev] Aider started (PID {self._process.pid})")
        except FileNotFoundError:
            print("[VoiceDev] ERROR: Could not launch aider. Falling back to echo mode.")
            self._running = True

    def _watch_process(self) -> None:
        if self._process is None:
            return
        self._process.wait()
        self._running = False
        print("[VoiceDev] Aider process exited.")

    def send_query(self, text: str) -> None:
        if self._process is None or not self._running:
            print(f"[VoiceDev] (echo) {text}")
            return
        try:
            self._process.stdin.write(text + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError):
            print("[VoiceDev] ERROR: Lost connection to aider process.")
            self._running = False

    def send_command(self, command: str) -> None:
        if not command.startswith("/"):
            command = "/" + command
        self.send_query(command)

    def stop(self) -> None:
        self._running = False
        if self._process is not None:
            try:
                self._process.stdin.write("/exit\n")
                self._process.stdin.flush()
                time.sleep(0.5)
            except (BrokenPipeError, OSError):
                pass
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

    def is_running(self) -> bool:
        return self._running
