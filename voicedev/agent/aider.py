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
        re.compile(r"\[Yes/no/all", re.IGNORECASE),
        re.compile(r"Add \.aider\* to \.gitignore", re.IGNORECASE),
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
        self._is_windows = sys.platform == "win32"

    @staticmethod
    def _resolve_aider_path() -> Optional[str]:
        for name in ["aider", "aider.exe", "aider.bat", "aider.cmd"]:
            path = shutil.which(name)
            if path:
                print(f"[VoiceDev] Found aider via PATH: {path}")
                return path

        uv_bin = os.path.join(os.path.expanduser("~"), ".local", "bin")
        for name in ["aider", "aider.exe", "aider.bat"]:
            candidate = os.path.join(uv_bin, name)
            if os.path.exists(candidate):
                print(f"[VoiceDev] Found aider in uv bin: {candidate}")
                return candidate

        scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
        for name in ["aider.exe", "aider.bat", "aider.cmd"]:
            candidate = os.path.join(scripts_dir, name)
            if os.path.exists(candidate):
                print(f"[VoiceDev] Found aider in Scripts: {candidate}")
                return candidate

        try:
            result = subprocess.run(
                [sys.executable, "-m", "aider", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                print("[VoiceDev] Found aider as Python module")
                return sys.executable
        except Exception:
            pass

        return None

    def _build_cmd(self, aider_path: str) -> List[str]:
        if aider_path == sys.executable:
            base = [sys.executable, "-m", "aider"]
        else:
            base = [aider_path]

        auto_flags = ["--no-pretty", "--no-gitignore", "--no-auto-commits", "--yes-always", "--map-tokens", "256"]
        for flag in auto_flags:
            if flag not in self._extra_args:
                base.append(flag)

        minimax_key = os.environ.get("MINIMAX_API_KEY", "")
        if minimax_key:
            base.append("--openai-api-key")
            base.append(minimax_key)
            base.append("--openai-api-base")
            base.append("https://api.minimaxi.chat/v1")

        model_in_extra = any(
            arg.startswith("--model") for arg in self._extra_args
        )
        if not model_in_extra:
            base.append("--model")
            base.append("minimax/minimax-m2.5")

        base.extend(self._extra_args)
        return base

    def start(self) -> None:
        aider_path = self._resolve_aider_path()

        if aider_path is None:
            print("\n[VoiceDev] ERROR: 'aider' not found.")
            print("[VoiceDev] Install with one of:")
            print("[VoiceDev]   uv tool install aider-chat")
            print("[VoiceDev]   pip install aider-chat")
            print("[VoiceDev] Falling back to echo mode.\n")
            self._running = True
            return

        if self._is_windows:
            self._start_windows_mode(aider_path)
        elif PEXPECT_AVAILABLE:
            self._start_with_pexpect(aider_path)
        else:
            self._start_with_subprocess(aider_path)

    def _start_windows_mode(self, aider_path: str) -> None:
        cmd = self._build_cmd(aider_path)
        cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        print(f"[VoiceDev] Launching (Windows console mode): {cmd_str}")

        try:
            kwargs = {
                "stdin": subprocess.PIPE,
                "stdout": None,
                "stderr": None,
                "text": True,
                "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP,
            }

            self._process = subprocess.Popen(cmd, **kwargs)
            self._running = True
            self._use_pexpect = False

            self._reader_thread = threading.Thread(
                target=self._watchdog_windows, daemon=True
            )
            self._reader_thread.start()

            time.sleep(2.0)

            print(f"[VoiceDev] Aider started (PID {self._process.pid}, Windows console mode)")
            print("[VoiceDev] Aider output renders directly on terminal below")
            print("[VoiceDev] Speak your commands while holding SPACE\n")

        except Exception as e:
            print(f"[VoiceDev] ERROR: Could not launch aider: {e}")
            self._running = True

    def _watchdog_windows(self) -> None:
        if self._process is None:
            return
        try:
            self._process.wait()
        except Exception:
            pass
        self._running = False
        print("\n[VoiceDev] Aider process exited.")

    def _start_with_pexpect(self, aider_path: str) -> None:
        cmd_list = self._build_cmd(aider_path)
        cmd_str = subprocess.list2cmdline(cmd_list)

        try:
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
            print(f"[VoiceDev] Aider started (PID {pid}, pexpect/PTY mode)")
        except Exception as e:
            print(f"[VoiceDev] pexpect failed ({e}), falling back to subprocess...")
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
            print("[VoiceDev] ERROR: Could not launch aider.")
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
        elif normalized in ("all", "accept all"):
            response = "a"
        elif normalized in ("skip",):
            response = "s"

        self._send_raw(response)

    def clear_pending_prompt(self) -> None:
        with self._lock:
            self._pending_prompt = None

    def send_query(self, text: str) -> None:
        if not self._running:
            print(f"[VoiceDev] (echo, agent not running) {text}")
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
            else:
                print(f"[VoiceDev] (echo, no channel) {text}")
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
                if self._is_windows:
                    subprocess.run(
                        ["taskkill", "/PID", str(self._process.pid), "/T", "/F"],
                        capture_output=True,
                        timeout=5,
                    )
                else:
                    self._process.terminate()
                    self._process.wait(timeout=3)
            except Exception:
                pass
            self._process = None

    def is_running(self) -> bool:
        return self._running
