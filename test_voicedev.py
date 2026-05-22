#!/usr/bin/env python3
"""VoiceDev Integration Test — verify Aider starts and accepts commands."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from voicedev.agent.aider import AiderBackend
from voicedev.commands.router import CommandRouter


def test_aider_found():
    print("=" * 60)
    print("TEST 1: Aider executable resolution")
    print("=" * 60)
    path = AiderBackend._resolve_aider_path()
    if path:
        print(f"PASS: Aider found at: {path}")
        return True
    else:
        print("FAIL: Aider not found")
        print("   Fix: uv tool install aider-chat")
        return False


def test_aider_starts():
    print()
    print("=" * 60)
    print("TEST 2: Aider process starts and accepts stdin")
    print("=" * 60)

    agent = AiderBackend()
    try:
        agent.start()
        time.sleep(3.0)

        if not agent.is_running():
            print("FAIL: Aider process died immediately")
            return False

        print("PASS: Aider process is running")

        print("   Sending: 'Create a hello world Python script'")
        agent.send_query("Create a hello world Python script")
        time.sleep(5.0)

        if agent.is_running():
            print("PASS: Aider accepted input and is still running")
        else:
            print("WARN: Aider exited after receiving input")

        return True
    except Exception as e:
        print(f"FAIL: Exception: {e}")
        return False
    finally:
        print("   Stopping Aider...")
        agent.stop()
        time.sleep(1.0)


def test_command_router():
    print()
    print("=" * 60)
    print("TEST 3: Command router intercepts meta-commands")
    print("=" * 60)

    router = CommandRouter()

    test_cases = [
        ("show diff", True, "/diff"),
        ("undo that", True, "/undo"),
        ("run tests", True, "/run pytest"),
        ("exit", True, "shutdown"),
        ("yes", True, "Y"),
        ("no", True, "N"),
        ("Create a function", False, None),
        ("add file main.py", True, "/add main.py"),
    ]

    all_pass = True
    for text, expected_is_cmd, expected_action in test_cases:
        result = router.route(text)
        is_cmd = result is not None

        if is_cmd != expected_is_cmd:
            print(f"FAIL: '{text}' -- expected is_command={expected_is_cmd}, got {is_cmd}")
            all_pass = False
            continue

        if expected_is_cmd and result:
            _, action = result
            if action != expected_action:
                print(f"FAIL: '{text}' -- expected action='{expected_action}', got '{action}'")
                all_pass = False
                continue

        print(f"PASS: '{text}' -> {'CMD' if is_cmd else 'QUERY'}")

    return all_pass


def test_prompt_detection():
    print()
    print("=" * 60)
    print("TEST 4: Prompt pattern detection")
    print("=" * 60)

    agent = AiderBackend()
    test_lines = [
        ("Accept this change? (Y/n)", True),
        ("Add main.py to the chat? (Y/n)", True),
        ("Run shell command? (Y/n)", True),
        ("Some random code output", False),
        ("Add .aider* to .gitignore (recommended)? (Y)es/(N)o [Yes]:", True),
    ]

    all_pass = True
    for line, expected in test_lines:
        agent._pending_prompt = None
        agent._detect_prompt(line)
        detected = agent.has_pending_prompt() is not None

        if detected != expected:
            print(f"FAIL: '{line[:50]}...' -- expected detected={expected}, got {detected}")
            all_pass = False
        else:
            print(f"PASS: '{line[:50]}...' -> {'PROMPT' if detected else 'NOT PROMPT'}")

    return all_pass


def main():
    print()
    print("=" * 60)
    print("VoiceDev Integration Test Suite")
    print("=" * 60)

    results = []
    results.append(("Aider Found", test_aider_found()))
    results.append(("Aider Starts", test_aider_starts()))
    results.append(("Command Router", test_command_router()))
    results.append(("Prompt Detection", test_prompt_detection()))

    print()
    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    all_passed = all(r[1] for r in results)
    print()
    if all_passed:
        print("ALL TESTS PASSED")
        print()
        print("Run VoiceDev with:")
        print("  $env:PATH = 'C:\\Users\\rohit\\.local\\bin;' + $env:PATH; python -m voicedev.main")
    else:
        print("SOME TESTS FAILED -- fix issues above first.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
