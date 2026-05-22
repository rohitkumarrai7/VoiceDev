# VoiceDev — *Speak. Code. Ship.*

VoiceDev is a voice-first interface layer for terminal-based AI coding agents. You speak your intent, it gets transcribed and relayed to the agent, and you stay in flow — no context switching, no typing interruptions. Built for developers who want to stay hands-free while the agent handles the heavy lifting.

**Target Agent:** [Aider](https://aider.chat) — the AI pair programming terminal tool.

---

## Demo Setup Time

**~2 minutes:** Install dependencies, set your API key (optional), run `voicedev`.

---

## Features

- **Voice Activity Detection (VAD):** Automatic speech onset/offset detection — no button presses needed in continuous mode
- **Push-to-Talk (PTT) Mode:** Hold `Space` to record, release to send
- **Continuous Mode:** Fully hands-free via VAD with configurable silence threshold
- **Voice Meta-Commands:** Control VoiceDev and Aider with spoken commands (e.g., "run tests", "undo that", "show diff")
- **Dual STT Backend:** Groq Whisper (fast, free tier), OpenAI Whisper API (cloud), or faster-whisper (local, free, offline)
- **Noise Cancellation:** Background noise reduction before transcription
- **Rich TUI:** Live status panel showing mode, state, last transcription, and session stats
- **Session Logging:** Auto-saved Markdown transcripts with timestamps and cost tracking
- **Fuzzy Command Matching:** Handles transcription errors gracefully
- **Extensible Architecture:** Plugin-style `AgentBackend` interface for future agent support

---

## Requirements

- **Python 3.10+**
- **PortAudio** (for microphone input):
  - Ubuntu/Debian: `sudo apt install portaudio19-dev`
  - macOS: `brew install portaudio`
  - Windows: Included with `sounddevice` via pip
- **Aider** (the target coding agent): `pip install aider-chat`
- **Groq API Key** (recommended — fast, free tier; auto-detected from `.env`)
- **OpenAI API Key** (optional — alternative cloud STT; falls back to local model if absent)

---

## Installation

```bash
# Clone or extract the archive
cd voicedev

# Install dependencies
pip install -r requirements.txt

# Or install as editable package (adds `voicedev` to PATH)
pip install -e .
```

---

## Setup

### 1. API Key (Recommended — for Groq Whisper STT)

```bash
# Copy the example env file and add your key
cp .env.example .env
# Edit .env and add: GROQ_API_KEY=gsk_your_key_here
```

Get a free Groq API key at [console.groq.com/keys](https://console.groq.com/keys). Groq's free tier provides fast Whisper STT with generous limits.

If no key is set, VoiceDev automatically uses the **local faster-whisper** backend (free, offline). No configuration needed.

You can also use **OpenAI Whisper API** by setting `OPENAI_API_KEY` in `.env` instead.

### 2. First Run

On first run, VoiceDev auto-creates `~/.voicedev/config.yaml` with sensible defaults.

---

## Usage

### Basic (auto-detects STT backend)

```bash
voicedev
```

### Force a specific STT backend

```bash
voicedev --stt whisper_api
voicedev --stt faster_whisper
```

### Use a larger local model

```bash
voicedev --whisper-model medium.en
```

### Start in continuous (hands-free) mode

```bash
voicedev --mode continuous
```

### Pass extra arguments to Aider

```bash
voicedev -- --model gpt-4o --no-auto-commits
```

### Disable noise reduction

```bash
voicedev --no-noise-reduction
```

---

## Modes

### PTT Mode (Default)

Hold `Space` to record your voice. Release to transcribe and send to Aider.

### Continuous Mode

Say **"switch to continuous"** or start with `--mode continuous`. VAD detects when you start and stop speaking. Fully hands-free after activation.

Switch back with **"switch to manual"**.

---

## Voice Meta-Commands

These are intercepted before reaching Aider and control VoiceDev or trigger agent shortcuts:

| Voice Command | Action |
|---|---|
| `"stop listening"` | Pause voice recording |
| `"start listening"` | Resume voice recording |
| `"switch to continuous"` | Enable hands-free VAD mode |
| `"switch to manual"` | Switch back to PTT mode |
| `"clear context"` | Sends `/clear` to Aider |
| `"run tests"` | Sends `/run pytest` to Aider |
| `"undo that"` | Sends `/undo` to Aider |
| `"show diff"` | Sends `/diff` to Aider |
| `"add file [name]"` | Sends `/add [name]` to Aider |
| `"exit"` | Graceful shutdown |

Commands use fuzzy matching — slight mispronunciations like "unto that" will still match "undo that".

---

## Configuration

All settings live in `~/.voicedev/config.yaml` (auto-created on first run):

```yaml
stt_backend: auto              # auto | groq_whisper | whisper_api | faster_whisper
faster_whisper_model: base.en  # Model for local STT
groq_whisper_model: whisper-large-v3-turbo  # Model for Groq STT
whisper_language: en           # Language for transcription
vad_aggressiveness: 2          # 0-3 (higher = more aggressive silence detection)
silence_threshold_ms: 1200     # ms of silence before stopping recording
ptt_key: space                 # Key for push-to-talk
agent: aider                   # Target agent
aider_args: []                 # Extra args passed to aider on launch
wake_word: hey dev             # Wake word for continuous mode
noise_reduction: true          # Enable noise cancellation
session_logging: true          # Save session transcripts
```

---

## STT Backend Comparison

| Feature | Groq Whisper (Recommended) | OpenAI Whisper API | faster-whisper (local) |
|---|---|---|---|
| **Cost** | Free tier available | $0.006/min (~$0.36/hr) | Free |
| **Speed** | Fastest (~0.3s) | ~1-2s (network) | ~0.3-1s (CPU) |
| **Accuracy** | Best (whisper-large-v3-turbo) | Best | Very Good (base.en) |
| **Internet** | Required | Required | Not required |
| **Setup** | Groq API key | OpenAI API key | First run downloads model |

---

## Session Logs

Every session is auto-saved to `~/.voicedev/sessions/YYYY-MM-DD_HH-MM-SS.md` with:

- Timestamped voice inputs
- Whether each was a command or agent query
- STT backend used and transcription latency
- Total session duration and estimated cost

---

## Project Structure

```
voicedev/
├── voicedev/
│   ├── __init__.py
│   ├── main.py              # Entry point, CLI, orchestration
│   ├── config.py             # YAML config loader
│   ├── audio/
│   │   ├── capture.py        # Microphone capture (sounddevice)
│   │   ├── vad.py            # Voice activity detection (webrtcvad)
│   │   └── noise.py          # Noise reduction (noisereduce)
│   ├── stt/
│   │   ├── base.py           # Abstract STT backend
│   │   ├── whisper_api.py    # OpenAI Whisper API
│   │   └── faster_whisper.py # Local faster-whisper
│   ├── agent/
│   │   ├── base.py           # Abstract agent backend
│   │   └── aider.py          # Aider integration
│   ├── commands/
│   │   └── router.py         # Voice meta-command routing
│   ├── tui/
│   │   └── display.py        # Rich TUI status panel
│   └── session/
│       └── logger.py         # Session transcript logger
├── tests/
│   ├── test_vad.py
│   ├── test_commands.py
│   ├── test_stt_mock.py
│   ├── test_config.py
│   └── test_noise.py
├── README.md
├── REPORT.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
└── config.example.yaml
```

---

## Running Tests

```bash
pip install pytest pytest-mock
pytest tests/ -v
```

---

## License

MIT License. See [LICENSE](LICENSE).
