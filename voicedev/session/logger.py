import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class SessionLogger:
    def __init__(self, session_dir: Path):
        self._session_dir = session_dir
        self._session_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._filepath = self._session_dir / f"{timestamp}.md"
        self._start_time = time.time()
        self._entries: List[dict] = []
        self._query_count = 0
        self._command_count = 0
        self._total_audio_duration = 0.0
        self._stt_backend = "unknown"
        self._cost_per_min = 0.0
        self._avg_confidence = 0.0
        self._confidence_samples = 0

    @property
    def filepath(self) -> Path:
        return self._filepath

    @property
    def query_count(self) -> int:
        return self._query_count

    def set_stt_backend(self, name: str) -> None:
        self._stt_backend = name
        cost_map = {"groq_whisper": 0.0, "whisper_api": 0.006, "faster_whisper": 0.0}
        self._cost_per_min = cost_map.get(name, 0.0)

    def log_entry(
        self,
        text: str,
        is_command: bool = False,
        latency_ms: float = 0.0,
        audio_duration_s: float = 0.0,
        confidence: float = -1.0,
    ) -> None:
        self._query_count += 1
        if is_command:
            self._command_count += 1
        self._total_audio_duration += audio_duration_s

        if confidence >= 0:
            self._confidence_samples += 1
            self._avg_confidence += (confidence - self._avg_confidence) / self._confidence_samples

        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "text": text,
            "is_command": is_command,
            "latency_ms": round(latency_ms, 1),
            "audio_duration_s": round(audio_duration_s, 2),
            "confidence": round(confidence, 3) if confidence >= 0 else None,
        }
        self._entries.append(entry)
        self._flush()

    def _flush(self) -> None:
        duration = time.time() - self._start_time
        estimated_cost = (self._total_audio_duration / 60.0) * self._cost_per_min

        lines = [
            "# VoiceDev Session Log",
            "",
            f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"- **Duration:** {duration:.0f}s ({duration / 60:.1f} min)",
            f"- **STT Backend:** {self._stt_backend}",
            f"- **Voice queries:** {self._query_count} ({self._command_count} commands)",
            f"- **Total audio:** {self._total_audio_duration:.1f}s",
            f"- **Est. STT cost:** ${estimated_cost:.4f}",
        ]

        if self._confidence_samples > 0:
            lines.append(f"- **Avg. confidence:** {self._avg_confidence * 100:.1f}%")

        lines.extend(["", "## Transcript", ""])

        for i, entry in enumerate(self._entries, 1):
            kind = "command" if entry["is_command"] else "query"
            conf = f", {entry['confidence'] * 100:.0f}% conf" if entry["confidence"] is not None else ""
            lines.append(
                f"{i}. **[{entry['timestamp']}]** ({kind}) `{entry['text']}` "
                f"— {entry['latency_ms']}ms latency, {entry['audio_duration_s']}s audio{conf}"
            )

        self._filepath.write_text("\n".join(lines), encoding="utf-8")

    def close(self) -> None:
        self._flush()
