"""Wake word detection — on-device keyword spotting before STT.

Uses openwakeword when available for real ML-based detection on raw audio
frames. Falls back to post-STT substring matching when the library is absent.
"""

from typing import Optional

import numpy as np

try:
    from openwakeword.model import Model as OWWModel

    _OWW_AVAILABLE = True
except ImportError:
    _OWW_AVAILABLE = False


class WakeWordDetector:
    """Two-tier wake word detector.

    Tier 1 (preferred): openwakeword runs on raw 16 kHz int16 audio chunks
    and fires when its model confidence exceeds *threshold*.

    Tier 2 (fallback): After STT transcription, checks whether the wake
    phrase appears as a substring.
    """

    def __init__(self, phrase: str = "hey dev", threshold: float = 0.5):
        self.phrase = phrase.lower()
        self._threshold = threshold
        self._armed = False
        self._oww_model: Optional[object] = None
        self._use_oww = False

        if _OWW_AVAILABLE:
            try:
                self._oww_model = OWWModel(
                    wakeword_models=["hey_jarvis"],
                    inference_framework="onnx",
                )
                self._use_oww = True
            except Exception:
                self._oww_model = None

    @property
    def backend_name(self) -> str:
        return "openwakeword" if self._use_oww else "substring"

    @property
    def armed(self) -> bool:
        return self._armed

    def detect_audio(self, audio_chunk: np.ndarray) -> bool:
        """Run wake word detection on raw audio (Tier 1).

        Returns True if the wake word was detected in the audio chunk.
        Only works when openwakeword is available.
        """
        if not self._use_oww or self._oww_model is None:
            return False

        try:
            int16 = audio_chunk.astype(np.int16) if audio_chunk.dtype != np.int16 else audio_chunk
            self._oww_model.predict(int16)

            for mdl_name in self._oww_model.prediction_buffer.keys():
                scores = list(self._oww_model.prediction_buffer[mdl_name])
                if scores and max(scores) > self._threshold:
                    self._armed = True
                    self._oww_model.reset()
                    return True
        except Exception:
            pass
        return False

    def detect_text(self, text: str) -> bool:
        """Run wake word detection on transcribed text (Tier 2 fallback).

        Returns True if the text contains the wake phrase or the detector
        is already armed from a previous detection.
        """
        if self._armed:
            return True

        text_lower = text.lower().strip()
        if self.phrase in text_lower or text_lower in self.phrase:
            self._armed = True
            return True
        return False

    def disarm(self) -> None:
        self._armed = False
        if self._use_oww and self._oww_model is not None:
            try:
                self._oww_model.reset()
            except Exception:
                pass
