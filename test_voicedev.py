#!/usr/bin/env python3
"""VoiceDev Integration Test — verify Aider starts and accepts commands."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from voicedev.agent.aider import AiderBackend
from voicedev.commands.router import CommandRouter
from voicedev.stt.base import TranscriptionResult
from voicedev.audio.feedback import AudioFeedback
from voicedev.audio.wakeword import WakeWordDetector


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
        print("   Fix: pip install aider-chat")
        return False


def test_aider_starts():
    print()
    print("=" * 60)
    print("TEST 2: Aider process starts and accepts stdin")
    print("=" * 60)

    agent = AiderBackend(auto_restart=False)
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
    print("TEST 3: Command router (30+ commands)")
    print("=" * 60)

    router = CommandRouter()

    test_cases = [
        ("show diff", True, "/diff"),
        ("undo that", True, "/undo"),
        ("cancel that", True, "/undo"),
        ("run tests", True, "/run pytest"),
        ("commit changes", True, "/commit"),
        ("architect mode", True, "/chat-mode architect"),
        ("list files", True, "list_files"),
        ("show history", True, "show_history"),
        ("help me", True, "help"),
        ("git status", True, "/git status"),
        ("exit", True, "shutdown"),
        ("yes", True, "Y"),
        ("no", True, "N"),
        ("Create a function that parses JSON", False, None),
        ("add file main.py", True, "/add main.py"),
        ("drop file utils.py", True, "/drop utils.py"),
        ("run command ls -la", True, "/run ls -la"),
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

        print(f"PASS: '{text}' -> {'CMD: ' + result[1] if is_cmd else 'QUERY'}")

    return all_pass


def test_prompt_detection():
    print()
    print("=" * 60)
    print("TEST 4: Prompt pattern detection")
    print("=" * 60)

    agent = AiderBackend(auto_restart=False)
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


def test_transcription_result():
    print()
    print("=" * 60)
    print("TEST 5: TranscriptionResult confidence scoring")
    print("=" * 60)

    r = TranscriptionResult(text="hello world", confidence=0.92)
    assert r.has_confidence is True
    assert r.confidence_pct == "92%"
    print(f"PASS: Confidence 0.92 -> {r.confidence_pct}")

    r2 = TranscriptionResult(text="test")
    assert r2.has_confidence is False
    assert r2.confidence_pct == "n/a"
    print(f"PASS: No confidence -> {r2.confidence_pct}")

    return True


def test_audio_feedback():
    print()
    print("=" * 60)
    print("TEST 6: Audio feedback tone generation")
    print("=" * 60)

    fb = AudioFeedback(enabled=False)
    for name in ["start", "stop", "success", "error", "command", "cancel"]:
        tone = fb._get_tone(name)
        assert tone is not None
        assert len(tone) > 0
        print(f"PASS: Tone '{name}' generated ({len(tone)} samples)")

    return True


def test_wake_word():
    print()
    print("=" * 60)
    print("TEST 7: Wake word detection")
    print("=" * 60)

    detector = WakeWordDetector(phrase="hey dev")
    print(f"  Backend: {detector.backend_name}")

    assert detector.detect_text("hey dev start coding") is True
    print("PASS: Detected 'hey dev' in text")

    assert detector.detect_text("anything else") is True
    print("PASS: Armed state passes through")

    detector.disarm()
    assert detector.detect_text("random words") is False
    print("PASS: Disarmed rejects non-wake text")

    return True


def main():
    print()
    print("=" * 60)
    print("VoiceDev Integration Test Suite v0.2")
    print("=" * 60)

    results = []
    results.append(("Aider Found", test_aider_found()))
    results.append(("Aider Starts", test_aider_starts()))
    results.append(("Command Router (30+)", test_command_router()))
    results.append(("Prompt Detection", test_prompt_detection()))
    results.append(("Confidence Scoring", test_transcription_result()))
    results.append(("Audio Feedback", test_audio_feedback()))
    results.append(("Wake Word", test_wake_word()))

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
    else:
        print("SOME TESTS FAILED — fix issues above first.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
