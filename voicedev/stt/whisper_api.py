import io
import tempfile
import os
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.io.wavfile import write as write_wav

from voicedev.stt.base import STTBackend


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

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        self._ensure_client()

        if isinstance(audio_data, np.ndarray):
            return self._transcribe_array(audio_data, sample_rate)

        return self._transcribe_bytes(audio_data, sample_rate)

    def _transcribe_array(self, audio: np.ndarray, sample_rate: int) -> str:
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

    def _transcribe_bytes(self, audio: bytes, sample_rate: int) -> str:
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

    def _transcribe_file(self, filepath: str) -> str:
        with open(filepath, "rb") as f:
            transcript = self._client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language=self._language,
                response_format="text",
            )
        return transcript.strip() if transcript else ""
