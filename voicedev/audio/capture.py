import queue
import threading
from typing import Optional

import numpy as np
import sounddevice as sd


SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_DURATION_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)
DTYPE = "int16"


class AudioCapture:
    def __init__(self, sample_rate: int = SAMPLE_RATE, frame_duration_ms: int = FRAME_DURATION_MS):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        self._frame_queue: queue.Queue = queue.Queue()
        self._recording = False
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            pass
        frame = indata[:, 0].copy()
        self._frame_queue.put(frame)

    def start_stream(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=self.frame_size,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._recording = True

    def stop_stream(self) -> None:
        with self._lock:
            if self._stream is not None:
                self._recording = False
                self._stream.stop()
                self._stream.close()
                self._stream = None

    def read_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def is_streaming(self) -> bool:
        return self._recording

    def record_while_key_held(self, key: str = "space") -> np.ndarray:
        import keyboard

        frames = []
        self.start_stream()
        keyboard.wait(key)
        while keyboard.is_pressed(key):
            frame = self.read_frame(timeout=0.5)
            if frame is not None:
                frames.append(frame)
        self.stop_stream()

        if not frames:
            return np.array([], dtype=np.int16)
        return np.concatenate(frames)

    def close(self) -> None:
        self.stop_stream()
