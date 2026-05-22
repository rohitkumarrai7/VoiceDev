from typing import Optional

import numpy as np


def reduce_noise(audio: np.ndarray, sample_rate: int = 16000, prop_decrease: float = 0.8) -> np.ndarray:
    try:
        import noisereduce

        if len(audio) < sample_rate:
            return audio

        float_audio = audio.astype(np.float32) / 32768.0
        reduced = noisereduce.reduce_noise(
            y=float_audio,
            sr=sample_rate,
            prop_decrease=prop_decrease,
            stationary=True,
        )
        result = (reduced * 32768.0).astype(np.int16)
        return result
    except Exception:
        return audio
