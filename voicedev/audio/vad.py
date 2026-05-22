from typing import Optional

import numpy as np
import webrtcvad


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 2, sample_rate: int = 16000, frame_duration_ms: int = 30):
        self._vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)

    def set_aggressiveness(self, level: int) -> None:
        self._vad.set_mode(level)

    def is_speech(self, frame: np.ndarray) -> bool:
        if len(frame) < self.frame_size:
            return False
        pcm_bytes = frame[: self.frame_size].astype(np.int16).tobytes()
        return self._vad.is_speech(pcm_bytes, self.sample_rate)

    def detect_speech_segment(
        self,
        frame_source,
        silence_threshold_ms: int = 1200,
        speech_onset_frames: int = 3,
        max_duration_s: float = 30.0,
    ) -> Optional[np.ndarray]:
        silence_frames_needed = int(silence_threshold_ms / self.frame_duration_ms)
        max_total_frames = int(max_duration_s * 1000 / self.frame_duration_ms)

        frames = []
        voiced_count = 0
        silence_count = 0
        speaking = False
        total = 0

        while total < max_total_frames:
            frame = frame_source()
            if frame is None:
                break

            total += 1
            is_voiced = self.is_speech(frame)

            if not speaking:
                if is_voiced:
                    voiced_count += 1
                    frames.append(frame)
                    if voiced_count >= speech_onset_frames:
                        speaking = True
                else:
                    voiced_count = 0
                    frames = []
            else:
                frames.append(frame)
                if is_voiced:
                    silence_count = 0
                else:
                    silence_count += 1
                    if silence_count >= silence_frames_needed:
                        break

        if not frames:
            return None
        return np.concatenate(frames)
