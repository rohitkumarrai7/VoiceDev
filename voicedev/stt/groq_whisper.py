import json
import tempfile
import os

import numpy as np
from scipy.io.wavfile import write as write_wav

from voicedev.stt.base import STTBackend, TranscriptionResult


class GroqWhisperBackend(STTBackend):
    def __init__(self, language: str = "en", model: str = "whisper-large-v3-turbo"):
        self._language = language
        self._model = model
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from groq import Groq

            api_key = os.environ.get("GROQ_API_KEY", "")
            self._client = Groq(api_key=api_key)

    def name(self) -> str:
        return "groq_whisper"

    def is_available(self) -> bool:
        return bool(os.environ.get("GROQ_API_KEY", "").strip())

    def transcribe(self, audio_data, sample_rate: int = 16000) -> TranscriptionResult:
        self._ensure_client()

        if isinstance(audio_data, np.ndarray):
            return self._transcribe_array(audio_data, sample_rate)
        return self._transcribe_bytes(audio_data, sample_rate)

    def _transcribe_array(self, audio: np.ndarray, sample_rate: int) -> TranscriptionResult:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            try:
                int_audio = audio.astype(np.int16) if audio.dtype != np.int16 else audio
                write_wav(tmp.name, sample_rate, int_audio)
                return self._transcribe_file(tmp.name)
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass

    def _transcribe_bytes(self, audio: bytes, sample_rate: int) -> TranscriptionResult:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            try:
                tmp.write(audio)
                tmp.flush()
                return self._transcribe_file(tmp.name)
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass

    def _transcribe_file(self, filepath: str) -> TranscriptionResult:
        with open(filepath, "rb") as f:
            response = self._client.audio.transcriptions.create(
                model=self._model,
                file=f,
                language=self._language,
                response_format="verbose_json",
            )

        text = ""
        confidence = -1.0
        duration = 0.0
        language = self._language

        if hasattr(response, "text"):
            text = response.text.strip()
        if hasattr(response, "duration"):
            duration = float(response.duration or 0)
        if hasattr(response, "segments") and response.segments:
            log_probs = [s.get("avg_logprob", s.avg_logprob if hasattr(s, "avg_logprob") else -1)
                         for s in response.segments
                         if hasattr(s, "avg_logprob") or (isinstance(s, dict) and "avg_logprob" in s)]
            if log_probs:
                import math
                avg_logprob = sum(log_probs) / len(log_probs)
                confidence = max(0.0, min(1.0, math.exp(avg_logprob)))
        if hasattr(response, "language"):
            language = response.language or self._language

        return TranscriptionResult(
            text=text,
            confidence=confidence,
            language=language,
            duration_s=duration,
        )
