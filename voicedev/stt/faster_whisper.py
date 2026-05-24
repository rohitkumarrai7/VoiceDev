import math

import numpy as np

from voicedev.stt.base import STTBackend, TranscriptionResult


class FasterWhisperBackend(STTBackend):
    def __init__(self, model_size: str = "base.en", device: str = "cpu", compute_type: str = "int8"):
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )

    def name(self) -> str:
        return "faster_whisper"

    def is_available(self) -> bool:
        try:
            from faster_whisper import WhisperModel
            return True
        except ImportError:
            return False

    def transcribe(self, audio_data, sample_rate: int = 16000) -> TranscriptionResult:
        self._ensure_model()

        if isinstance(audio_data, bytes):
            audio_data = np.frombuffer(audio_data, dtype=np.int16)

        float_audio = audio_data.astype(np.float32) / 32768.0

        segments_gen, info = self._model.transcribe(
            float_audio,
            beam_size=5,
            language="en",
        )

        segments = list(segments_gen)
        text = " ".join(seg.text for seg in segments).strip()

        confidence = -1.0
        if segments:
            log_probs = [seg.avg_logprob for seg in segments if hasattr(seg, "avg_logprob")]
            if log_probs:
                avg_lp = sum(log_probs) / len(log_probs)
                confidence = max(0.0, min(1.0, math.exp(avg_lp)))

        duration = getattr(info, "duration", 0.0) or 0.0
        language = getattr(info, "language", "en") or "en"

        return TranscriptionResult(
            text=text,
            confidence=confidence,
            language=language,
            duration_s=float(duration),
        )
