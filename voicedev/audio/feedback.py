"""Audio feedback — play short beep tones for state transitions."""

import threading
from typing import Optional

import numpy as np

SAMPLE_RATE = 16000

_TONES = {
    "start": (880, 0.08),
    "stop": (440, 0.08),
    "success": (660, 0.06),
    "error": (220, 0.15),
    "command": (1000, 0.05),
    "cancel": (330, 0.12),
}


def _generate_tone(freq: float, duration: float, volume: float = 0.3) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    envelope = np.ones_like(t)
    fade = int(SAMPLE_RATE * 0.005)
    if fade > 0 and len(envelope) > fade * 2:
        envelope[:fade] = np.linspace(0, 1, fade)
        envelope[-fade:] = np.linspace(1, 0, fade)
    wave = volume * np.sin(2 * np.pi * freq * t) * envelope
    return (wave * 32767).astype(np.int16)


class AudioFeedback:
    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._cache: dict = {}

    def _get_tone(self, name: str) -> Optional[np.ndarray]:
        if name not in self._cache:
            params = _TONES.get(name)
            if params is None:
                return None
            self._cache[name] = _generate_tone(*params)
        return self._cache[name]

    def play(self, tone_name: str) -> None:
        if not self._enabled:
            return
        audio = self._get_tone(tone_name)
        if audio is None:
            return
        threading.Thread(target=self._play_async, args=(audio,), daemon=True).start()

    @staticmethod
    def _play_async(audio: np.ndarray) -> None:
        try:
            import sounddevice as sd
            sd.play(audio, samplerate=SAMPLE_RATE, blocking=True)
        except Exception:
            pass

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
