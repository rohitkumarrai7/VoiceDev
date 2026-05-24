import math
import tempfile
import os

import numpy as np
from scipy.io.wavfile import write as write_wav

from voicedev.stt.base import STTBackend, TranscriptionResult


class WhisperAPIBackend(STTBackend):
    def __init__(self, language: str = "en"):
        self._language = language
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            import openai
            self._client = openai.OpenAI()

    def name(self) -> str:
        return "whisper_api"

    def is_available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY", "").strip())

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
                model="whisper-1",
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
            log_probs = []
            for seg in response.segments:
                lp = getattr(seg, "avg_logprob", None)
                if lp is None and isinstance(seg, dict):
                    lp = seg.get("avg_logprob")
                if lp is not None:
                    log_probs.append(lp)
            if log_probs:
                avg_lp = sum(log_probs) / len(log_probs)
                confidence = max(0.0, min(1.0, math.exp(avg_lp)))
        if hasattr(response, "language"):
            language = response.language or self._language

        return TranscriptionResult(
            text=text,
            confidence=confidence,
            language=language,
            duration_s=duration,
        )
