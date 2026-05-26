import os
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from voicedev.agent.base import AgentBackend

_TRUTHY = frozenset({"1", "true", "yes", "on"})
OPENROUTER_DEFAULT_MODEL = "openrouter/qwen/qwen-2.5-coder-32b-instruct:free"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
MINIMAX_DEFAULT_MODEL = "minimax/minimax-m2.7"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
MINIMAX_API_BASE = "https://api.minimaxi.chat/v1"

# Each provider is selected when its API key env is set; no fixed priority.
# If multiple keys are set, use VOICEDEV_LLM_PROVIDER or legacy VOICEDEV_USE_* flags.
LLM_PROVIDERS: List[Dict[str, Any]] = [
    {
        "name": "openrouter",
        "keys": ["OPENROUTER_API_KEY", "QWEN3_API_KEY"],
        "base": OPENROUTER_API_BASE,
        "model_envs": ["AIDER_MODEL", "QWEN3_MODEL"],
        "fallback_model": OPENROUTER_DEFAULT_MODEL,
        "normalize": "openrouter",
    },
    {
        "name": "openai",
        "keys": ["OPENAI_API_KEY"],
        "base": None,
        "model_envs": ["AIDER_MODEL"],
        "fallback_model": OPENAI_DEFAULT_MODEL,
        "normalize": None,
    },
    {
        "name": "minimax",
        "keys": ["MINIMAX_API_KEY"],
        "base": MINIMAX_API_BASE,
        "model_envs": ["AIDER_MODEL", "MINIMAX_MODEL"],
        "fallback_model": MINIMAX_DEFAULT_MODEL,
        "normalize": None,
    },
]

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

    MAX_RESTARTS = 3
    RESTART_BACKOFF_BASE = 2.0

    def __init__(self, extra_args: Optional[List[str]] = None, auto_restart: bool = True):
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
        self._auto_restart = auto_restart
        self._restart_count = 0
        self._last_start_time = 0.0
        self._on_restart_cb = None
        self._resolved_llm: Optional[Dict[str, str]] = None

    def set_on_restart(self, callback) -> None:
        self._on_restart_cb = callback

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
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return sys.executable
        except Exception:
            pass

        return None

    @staticmethod
    def _env_truthy(name: str) -> bool:
        return os.environ.get(name, "").lower().strip() in _TRUTHY

    @staticmethod
    def _normalize_openrouter_model(model: str) -> str:
        model = model.strip()
        if not model:
            return model
        if model.startswith("openrouter/"):
            return model
        return f"openrouter/{model}"

    @staticmethod
    def _provider_has_key(provider: Dict[str, Any]) -> bool:
        for key_name in provider["keys"]:
            if os.environ.get(key_name, "").strip():
                return True
        return False

    @staticmethod
    def _provider_api_key(provider: Dict[str, Any]) -> str:
        override_key = os.environ.get("AIDER_API_KEY", "").strip()
        if override_key:
            return override_key
        for key_name in provider["keys"]:
            value = os.environ.get(key_name, "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _model_for_provider(provider: Dict[str, Any]) -> str:
        for env_name in provider["model_envs"]:
            value = os.environ.get(env_name, "").strip()
            if value:
                return value
        return provider["fallback_model"]

    @staticmethod
    def _list_active_providers() -> List[Dict[str, Any]]:
        return [p for p in LLM_PROVIDERS if AiderBackend._provider_has_key(p)]

    @staticmethod
    def _provider_by_name(name: str) -> Optional[Dict[str, Any]]:
        name = name.lower().strip()
        for provider in LLM_PROVIDERS:
            if provider["name"] == name:
                return provider
        return None

    @staticmethod
    def _resolve_provider_conflict(
        active: List[Dict[str, Any]], extra_args: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        extra_args = extra_args or []

        explicit = os.environ.get("VOICEDEV_LLM_PROVIDER", "").strip().lower()
        if explicit:
            chosen = AiderBackend._provider_by_name(explicit)
            if chosen and chosen in active:
                return chosen

        if AiderBackend._env_truthy("VOICEDEV_USE_MINIMAX"):
            chosen = AiderBackend._provider_by_name("minimax")
            if chosen and chosen in active:
                return chosen

        if AiderBackend._env_truthy("VOICEDEV_USE_QWEN3"):
            chosen = AiderBackend._provider_by_name("openrouter")
            if chosen and chosen in active:
                return chosen

        if any("minimax" in arg.lower() for arg in extra_args):
            chosen = AiderBackend._provider_by_name("minimax")
            if chosen and chosen in active:
                return chosen

        return None

    @staticmethod
    def _format_provider_conflict(active: List[Dict[str, Any]]) -> str:
        names = [p["name"] for p in active]
        keys = []
        for provider in active:
            for key_name in provider["keys"]:
                if os.environ.get(key_name, "").strip():
                    keys.append(key_name)
        key_list = ", ".join(sorted(set(keys)))
        return (
            f"Multiple agent API keys set ({key_list}). "
            f"Active providers: {', '.join(names)}. "
            "Set VOICEDEV_LLM_PROVIDER=minimax|openrouter|openai "
            "or comment out the keys you are not using."
        )

    @staticmethod
    def _build_llm_config(provider: Dict[str, Any]) -> Dict[str, str]:
        override_base = os.environ.get("AIDER_API_BASE", "").strip()
        api_key = AiderBackend._provider_api_key(provider)
        api_base = override_base or provider["base"]
        model = AiderBackend._model_for_provider(provider)

        if provider["normalize"] == "openrouter":
            model = AiderBackend._normalize_openrouter_model(model)

        result: Dict[str, str] = {
            "provider": provider["name"],
            "api_key": api_key,
            "model": model,
        }
        if api_base:
            result["api_base"] = api_base
        return result

    @staticmethod
    def _resolve_llm_from_env(extra_args: Optional[List[str]] = None) -> Optional[Dict[str, str]]:
        extra_args = extra_args or []
        active = AiderBackend._list_active_providers()

        if len(active) == 0:
            override_key = os.environ.get("AIDER_API_KEY", "").strip()
            if override_key:
                openrouter = AiderBackend._provider_by_name("openrouter")
                if openrouter:
                    return AiderBackend._build_llm_config(openrouter)
            return None

        if len(active) == 1:
            return AiderBackend._build_llm_config(active[0])

        chosen = AiderBackend._resolve_provider_conflict(active, extra_args)
        if not chosen:
            return {"error": AiderBackend._format_provider_conflict(active)}

        return AiderBackend._build_llm_config(chosen)

    def _build_cmd(self, aider_path: str) -> List[str]:
        if aider_path == sys.executable:
            base = [sys.executable, "-m", "aider"]
        else:
            base = [aider_path]

        auto_flags = [
            "--no-pretty", "--no-gitignore", "--no-auto-commits",
            "--yes-always", "--map-tokens", "256", "--no-auto-lint",
        ]
        for flag in auto_flags:
            if flag not in self._extra_args:
                base.append(flag)

        llm = self._resolve_llm_from_env(self._extra_args)
        self._resolved_llm = llm

        has_api_key_in_extra = any(
            arg == "--openai-api-key" for arg in self._extra_args
        )
        has_base_in_extra = any(
            arg == "--openai-api-base" for arg in self._extra_args
        )
        model_in_extra = any(arg.startswith("--model") for arg in self._extra_args)

        if llm and "error" not in llm:
            if not has_api_key_in_extra:
                base.extend(["--openai-api-key", llm["api_key"]])
            if llm.get("api_base") and not has_base_in_extra:
                base.extend(["--openai-api-base", llm["api_base"]])
            if not model_in_extra and llm.get("model"):
                base.extend(["--model", llm["model"]])

        base.extend(self._extra_args)
        return base

    def _log_llm_config(self) -> None:
        model_in_extra = any(arg.startswith("--model") for arg in self._extra_args)
        if self._resolved_llm and "error" in self._resolved_llm:
            print(f"\n[VoiceDev] ERROR: {self._resolved_llm['error']}\n")
        elif self._resolved_llm:
            print(
                f"[VoiceDev] Aider LLM: {self._resolved_llm['provider']} "
                f"({self._resolved_llm['model']})"
            )
        elif not model_in_extra:
            print(
                "\n[VoiceDev] WARNING: No agent LLM configured in .env.\n"
                "[VoiceDev] Enable ONE provider block in .env.example "
                "(MiniMax, OpenRouter/Qwen, or OpenAI).\n"
                "[VoiceDev] Without this, Aider may use a broken default model.\n"
            )

    def start(self) -> None:
        self._last_start_time = time.time()
        self._resolved_llm = self._resolve_llm_from_env(self._extra_args)
        self._log_llm_config()

        aider_path = self._resolve_aider_path()

        if aider_path is None:
            print("\n[VoiceDev] WARNING: 'aider' not found.")
            print("[VoiceDev] Install with: pip install aider-chat  OR  uv tool install aider-chat")
            print("[VoiceDev] Running in echo mode — voice input will be displayed but not sent to an agent.\n")
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
        print(f"[VoiceDev] Launching: {cmd_str}")

        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["TERM"] = "dumb"

            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=None,
                stderr=None,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                env=env,
            )
            self._running = True
            self._use_pexpect = False

            self._reader_thread = threading.Thread(target=self._watchdog_windows, daemon=True)
            self._reader_thread.start()

            time.sleep(2.0)
            print(f"[VoiceDev] Aider started (PID {self._process.pid})")

        except Exception as e:
            print(f"[VoiceDev] ERROR launching aider: {e}")
            self._running = True

    def _watchdog_windows(self) -> None:
        if self._process is None:
            return
        try:
            self._process.wait()
        except Exception:
            pass

        if self._auto_restart and self._attempt_restart():
            return

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

            self._reader_thread = threading.Thread(target=self._read_output_pexpect, daemon=True)
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
            restarted = self._auto_restart and self._attempt_restart()
            if not restarted:
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

            self._reader_thread = threading.Thread(target=self._read_output_subprocess, daemon=True)
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
            restarted = self._auto_restart and self._attempt_restart()
            if not restarted:
                self._running = False
                print("[VoiceDev] Aider process exited.")

    def _attempt_restart(self) -> bool:
        uptime = time.time() - self._last_start_time
        if uptime < 5.0:
            return False
        if self._restart_count >= self.MAX_RESTARTS:
            print(f"[VoiceDev] Aider crashed {self._restart_count} times. Giving up.")
            return False

        self._restart_count += 1
        delay = self.RESTART_BACKOFF_BASE ** self._restart_count
        print(f"[VoiceDev] Aider exited unexpectedly. Restarting in {delay:.0f}s "
              f"(attempt {self._restart_count}/{self.MAX_RESTARTS})...")
        time.sleep(delay)

        if self._on_restart_cb:
            try:
                self._on_restart_cb(self._restart_count)
            except Exception:
                pass

        self._process = None
        self._child = None
        self.start()
        return self._running

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
            else:
                print(f"[VoiceDev] (echo) {text}")
        except (BrokenPipeError, OSError, ValueError) as e:
            print(f"[VoiceDev] ERROR sending to aider: {e}")
            self._running = False

    def stop(self) -> None:
        self._auto_restart = False
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
                        capture_output=True, timeout=5,
                    )
                else:
                    self._process.terminate()
                    self._process.wait(timeout=3)
            except Exception:
                pass
            self._process = None

    def is_running(self) -> bool:
        return self._running
