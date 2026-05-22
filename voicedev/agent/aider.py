import os
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import List, Optional

from voicedev.agent.base import AgentBackend

try:
    import pexpect
    from pexpect.popen_spawn import PopenSpawn

    PEXPECT_AVAILABLE = True
except ImportError:
    PEXPECT_AVAILABLE = False


class AiderBackend(AgentBackend):
    PROMPT_PATTERNS = [
        re.compile(r"Accept this change\?", re.IGNORECASE),
        re.compile(r"Add .* to the chat\?", re.IGNORECASE),
        re.compile(r"Run shell command\?", re.IGNORECASE),
        re.compile(r"Undo that change\?", re.IGNORECASE),
        re.compile(r"\(Y/n", re.IGNORECASE),
        re.compile(r"\(y/N", re.IGNORECASE),
        re.compile(r"\[Y/n", re.IGNORECASE),
        re.compile(r"\[y/N", re.IGNORECASE),
        re.compile(r"\[Yes/No", re.IGNORECASE),
    ]

    def __init__(self, extra_args: Optional[List[str]] = None):
        self._extra_args = extra_args or []
        self._child = None
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._pending_prompt: Optional[str] = None
        self._output_buffer: List[str] = []
        self._use_pexpect = False

    @staticmethod
    def _resolve_aider_path() -> Optional[str]:
        for name in ["aider", "aider.exe", "aider.bat", "aider.cmd"]:
            path = shutil.which(name)
            if path:
                return path

        uv_bin = os.path.join(os.path.expanduser("~"), ".local", "bin")
        for name in ["aider", "aider.exe", "aider.bat"]:
            candidate = os.path.join(uv_bin, name)
            if os.path.exists(candidate):
                return candidate

        scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
        for name in ["aider.exe", "aider.bat", "aider.cmd"]:
            candidate = os.path.join(scripts_dir, name)
            if os.path.exists(candidate):
                return candidate

        try:
            result = subprocess.run(
                [sys.executable, "-m", "aider", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return sys.executable
        except Exception:
            pass

        return None

    def start(self) -> None:
        aider_path = self._resolve_aider_path()

        if aider_path is None:
            print("\n[VoiceDev] ERROR: 'aider' not found.")
            print("[VoiceDev] Install with: pip install aider-chat")
            print("[VoiceDev] Falling back to echo mode.\n")
            self._running = True
            return

        if PEXPECT_AVAILABLE:
            self._start_with_pexpect(aider_path)
        else:
            self._start_with_subprocess(aider_path)

    def _build_cmd(self, aider_path: str) -> List[str]:
        if aider_path == sys.executable:
            return [sys.executable, "-m", "aider"] + self._extra_args
        return [aider_path] + self._extra_args

    def _start_with_pexpect(self, aider_path: str) -> None:
        cmd_list = self._build_cmd(aider_path)
        cmd_str = subprocess.list2cmdline(cmd_list)

        try:
            if sys.platform == "win32":
                self._child = PopenSpawn(
                    cmd_str, timeout=None, encoding="utf-8", codec_errors="replace"
                )
            else:
                self._child = pexpect.spawn(
                    cmd_str, timeout=None, encoding="utf-8", codec_errors="replace"
                )

            self._running = True
            self._use_pexpect = True

            self._reader_thread = threading.Thread(
                target=self._read_output_pexpect, daemon=True
            )
            self._reader_thread.start()
            time.sleep(1.5)

            pid = getattr(self._child, "pid", "unknown")
            print(f"[VoiceDev] Aider started (PID {pid}, pexpect mode)")
        except Exception as e:
            print(f"[VoiceDev] pexpect failed ({e}), trying subprocess...")
            self._start_with_subprocess(aider_path)

    def _read_output_pexpect(self) -> None:
        try:
            while self._running and self._child is not None:
                try:
                    self._child.expect(r"\r?\n", timeout=0.5)
                    line = (self._child.before or "").strip()
                except pexpect.TIMEOUT:
                    continue
                except pexpect.EOF:
                    break
                except Exception:
                    time.sleep(0.1)
                    continue

                if line:
                    with self._lock:
                        self._output_buffer.append(line)
                        if len(self._output_buffer) > 200:
                            self._output_buffer = self._output_buffer[-200:]
                    print(line, flush=True)
                    self._detect_prompt(line)
        except Exception:
            pass
        finally:
            self._running = False
            print("[VoiceDev] Aider process exited.")

    def _start_with_subprocess(self, aider_path: str) -> None:
        cmd = self._build_cmd(aider_path)

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
            )
            self._running = True
            self._use_pexpect = False

            self._reader_thread = threading.Thread(
                target=self._read_output_subprocess, daemon=True
            )
            self._reader_thread.start()

            print(f"[VoiceDev] Aider started (PID {self._process.pid}, subprocess mode)")
        except FileNotFoundError:
            print("[VoiceDev] ERROR: Could not launch aider. Falling back to echo mode.")
            self._running = True

    def _read_output_subprocess(self) -> None:
        try:
            while self._running and self._process is not None:
                line = self._process.stdout.readline()
                if not line:
                    if self._process.poll() is not None:
                        break
                    time.sleep(0.1)
                    continue
                line = line.strip()
                if line:
                    with self._lock:
                        self._output_buffer.append(line)
                        if len(self._output_buffer) > 200:
                            self._output_buffer = self._output_buffer[-200:]
                    print(line, flush=True)
                    self._detect_prompt(line)
        except Exception:
            pass
        finally:
            self._running = False
            print("[VoiceDev] Aider process exited.")

    def _detect_prompt(self, line: str) -> None:
        for pattern in self.PROMPT_PATTERNS:
            if pattern.search(line):
                with self._lock:
                    self._pending_prompt = line
                return

    def has_pending_prompt(self) -> Optional[str]:
        with self._lock:
            return self._pending_prompt

    def respond_to_prompt(self, response: str) -> None:
        with self._lock:
            self._pending_prompt = None

        normalized = response.lower().strip()
        if normalized in ("yes", "yep", "yeah", "sure", "accept", "ok"):
            response = "y"
        elif normalized in ("no", "nope", "nah", "reject", "deny"):
            response = "n"

        self._send_raw(response)

    def clear_pending_prompt(self) -> None:
        with self._lock:
            self._pending_prompt = None

    def send_query(self, text: str) -> None:
        if not self._running:
            print(f"[VoiceDev] (echo) {text}")
            return

        if self._use_pexpect and self._child is None:
            print(f"[VoiceDev] (echo) {text}")
            return

        if not self._use_pexpect and self._process is None:
            print(f"[VoiceDev] (echo) {text}")
            return

        self._send_raw(text)

    def send_command(self, command: str) -> None:
        if not command.startswith("/"):
            command = "/" + command
        self.send_query(command)

    def _send_raw(self, text: str) -> None:
        try:
            if self._use_pexpect and self._child is not None:
                self._child.sendline(text)
            elif self._process is not None and self._process.stdin is not None:
                self._process.stdin.write(text + "\n")
                self._process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as e:
            print(f"[VoiceDev] ERROR sending to aider: {e}")
            self._running = False

    def stop(self) -> None:
        self._running = False
        self.clear_pending_prompt()

        if self._use_pexpect and self._child is not None:
            try:
                self._child.sendline("/exit")
                time.sleep(0.5)
            except Exception:
                pass
            try:
                self._child.terminate(force=True)
            except Exception:
                pass
            try:
                self._child.close(force=True)
            except Exception:
                pass
            self._child = None

        if self._process is not None:
            try:
                if self._process.stdin is not None:
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
            except Exception:
                pass
            self._process = None

    def is_running(self) -> bool:
        return self._running
