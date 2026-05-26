#!/usr/bin/env python3
"""VoiceDev Diagnostic — Check if aider is installed and accessible."""

import os
import shutil
import subprocess
import sys

print("=" * 60)
print("VoiceDev Diagnostic Tool")
print("=" * 60)
print()

print(f"Python executable: {sys.executable}")
print(f"Python version:    {sys.version}")
print(f"Platform:          {sys.platform}")
print()

print("Checking for 'aider' via shutil.which:")
for name in ["aider", "aider.exe", "aider.bat", "aider.cmd"]:
    path = shutil.which(name)
    print(f"  {name:15s} -> {path}")
print()

scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
print(f"Scripts dir: {scripts_dir}")
if os.path.isdir(scripts_dir):
    for name in ["aider", "aider.exe", "aider.bat", "aider.cmd"]:
        candidate = os.path.join(scripts_dir, name)
        if os.path.exists(candidate):
            print(f"    FOUND: {candidate}")
print()

print("Checking 'python -m aider --version':")
try:
    result = subprocess.run(
        [sys.executable, "-m", "aider", "--version"],
        capture_output=True, text=True, timeout=10,
    )
    print(f"  returncode: {result.returncode}")
    print(f"  stdout:     {result.stdout.strip()}")
    print(f"  stderr:     {result.stderr.strip()}")
except Exception as e:
    print(f"  FAILED: {e}")
print()

print("Checking 'import aider':")
try:
    import aider
    print(f"  SUCCESS: aider package at {aider.__file__}")
except ImportError as e:
    print(f"  FAILED: {e}")
print()

print("Checking pexpect:")
try:
    import pexpect
    print(f"  SUCCESS: pexpect {pexpect.__version__}")
except ImportError:
    print("  FAILED: pexpect not installed")
print()

print("Checking agent LLM resolution from environment:")
try:
    from pathlib import Path
    from dotenv import load_dotenv
    for p in [Path(".env"), Path(__file__).resolve().parent / ".env"]:
        if p.exists():
            load_dotenv(p, override=True)
            print(f"  Loaded: {p}")
            break
except ImportError:
    print("  (python-dotenv not installed — using process env only)")

try:
    from voicedev.agent.aider import AiderBackend, LLM_PROVIDERS
    supported = ", ".join(p["name"] for p in LLM_PROVIDERS)
    print(f"  Supported providers: {supported}")
    active = AiderBackend._list_active_providers()
    if active:
        names = [p["name"] for p in active]
        print(f"  Active provider key(s): {', '.join(names)}")
        if len(active) > 1:
            print("  WARNING: multiple agent keys — set VOICEDEV_LLM_PROVIDER")
    llm = AiderBackend._resolve_llm_from_env()
    if llm and "error" in llm:
        print(f"  CONFLICT: {llm['error']}")
    elif llm:
        print(f"  Provider: {llm['provider']}")
        print(f"  Wire:     {llm.get('wire', 'openai_compatible')}")
        print(f"  Model:    {llm['model']}")
        if llm.get("api_base"):
            print(f"  Base:     {llm['api_base']}")
    else:
        print("  NONE — enable ONE provider block in .env.example")
except Exception as e:
    print(f"  FAILED: {e}")
print()

print("=" * 60)
aider_found = any(shutil.which(n) for n in ["aider","aider.exe","aider.bat","aider.cmd"])
try:
    r = subprocess.run([sys.executable,"-m","aider","--version"], capture_output=True, timeout=10)
    module_works = r.returncode == 0
except Exception:
    module_works = False

if not aider_found and not module_works:
    print("Aider is NOT installed.")
    print(f"Fix: {sys.executable} -m pip install aider-chat")
else:
    print("Aider IS installed!")
print("=" * 60)
