import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from voicedev.stt.base import STTBackend


class MockSTTBackend(STTBackend):
    def __init__(self, return_text="hello world"):
        self._return_text = return_text

    def transcribe(self, audio_data, sample_rate=16000):
        return self._return_text

    def name(self):
        return "mock"

    def is_available(self):
        return True


class TestSTTBackendInterface:
    def test_mock_backend_implements_interface(self):
        backend = MockSTTBackend()
        assert backend.is_available()
        assert backend.name() == "mock"

    def test_mock_transcribe_returns_text(self):
        backend = MockSTTBackend("test transcription")
        audio = np.zeros(16000, dtype=np.int16)
        result = backend.transcribe(audio)
        assert result == "test transcription"

    def test_mock_transcribe_empty(self):
        backend = MockSTTBackend("")
        audio = np.zeros(16000, dtype=np.int16)
        result = backend.transcribe(audio)
        assert result == ""


class TestWhisperAPIBackend:
    def test_is_available_no_key(self):
        with patch.dict("os.environ", {}, clear=True):
            from voicedev.stt.whisper_api import WhisperAPIBackend

            backend = WhisperAPIBackend()
            assert backend.is_available() is False

    def test_is_available_with_key(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            from voicedev.stt.whisper_api import WhisperAPIBackend

            backend = WhisperAPIBackend()
            assert backend.is_available() is True

    def test_name(self):
        from voicedev.stt.whisper_api import WhisperAPIBackend

        backend = WhisperAPIBackend()
        assert backend.name() == "whisper_api"


class TestFasterWhisperBackend:
    def test_name(self):
        from voicedev.stt.faster_whisper import FasterWhisperBackend

        backend = FasterWhisperBackend()
        assert backend.name() == "faster_whisper"

    def test_is_available(self):
        from voicedev.stt.faster_whisper import FasterWhisperBackend

        backend = FasterWhisperBackend()
        assert isinstance(backend.is_available(), bool)
