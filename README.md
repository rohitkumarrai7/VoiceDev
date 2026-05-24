# VoiceDev — *Speak. Code. Ship.*

VoiceDev is a voice-first interface layer for terminal-based AI coding agents. You speak your intent, it gets transcribed and relayed to the agent, and you stay in flow — no context switching, no typing interruptions. Built for developers who want to stay hands-free while the agent handles the heavy lifting.

**Target Agent:** [Aider](https://aider.chat) — the AI pair programming terminal tool.

---

## Demo Setup Time

**~2 minutes:** Install dependencies, set your API key (optional), run `voicedev`.

---

## Features

- **Voice Activity Detection (VAD):** Automatic speech onset/offset detection via webrtcvad — no button presses needed in continuous mode
- **Push-to-Talk (PTT) Mode:** Hold `Space` to record, release to send
- **Continuous Mode:** Fully hands-free via VAD with configurable wake word detection
- **Wake Word Detection:** On-device ML-based wake word via [openwakeword](https://github.com/dscripka/openWakeWord) (optional), with substring fallback
- **30+ Voice Meta-Commands:** Control VoiceDev and Aider with natural speech — file management, mode switching, git operations, and more
- **Three STT Backends:** Groq Whisper (fastest, free), OpenAI Whisper API (cloud), faster-whisper (local, offline)
- **STT Confidence Scores:** Real-time display of transcription confidence from Whisper model log-probabilities
- **Audio Feedback:** Configurable beep tones on recording start/stop, command recognition, and errors
- **Confirmation Mode:** Optional review step — see the transcription and say "send" or "cancel" before it reaches the agent
- **Noise Cancellation:** Background noise reduction via `noisereduce` before transcription
- **Rich TUI:** Live status panel showing mode, state, confidence, and session stats
- **Session Logging:** Auto-saved Markdown transcripts with timestamps, latency, and confidence tracking
- **Fuzzy Command Matching:** Handles transcription errors gracefully via `rapidfuzz`
- **Auto-Restart:** Automatic Aider recovery with exponential backoff on unexpected crashes
- **Extensible Architecture:** Plugin-style `AgentBackend` and `STTBackend` interfaces for future agent/engine support

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

# Install core dependencies
pip install -r requirements.txt

# Optional: install wake word detection (adds ~50MB model download)
pip install openwakeword>=0.6.0

# Or install as editable package (adds `voicedev` to PATH)
pip install -e .

# Or install with all optional dependencies
pip install -e ".[all]"
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
voicedev --stt groq_whisper
voicedev --stt whisper_api
voicedev --stt faster_whisper
```

### Start in continuous (hands-free) mode

```bash
voicedev --mode continuous
```

### Enable confirmation before sending

```bash
voicedev --confirm
```

### Use a larger local model

```bash
voicedev --whisper-model medium.en
```

### Disable audio feedback beeps

```bash
voicedev --no-feedback
```

### Hide confidence scores

```bash
voicedev --no-confidence
```

### Pass extra arguments to Aider

```bash
voicedev -- --model gpt-4o --no-auto-commits
```

---

## Modes

### PTT Mode (Default)

Hold `Space` to record your voice. Release to transcribe and send to Aider. A beep tone confirms recording start and end.

### Continuous Mode

Say **"switch to continuous"** or start with `--mode continuous`. VAD detects when you start and stop speaking. Say your wake word (default: **"hey dev"**) before each command for fully hands-free operation.

Switch back with **"switch to manual"**.

---

## Voice Meta-Commands

These are intercepted before reaching Aider and control VoiceDev or trigger agent shortcuts:

### Listening Control

| Voice Command | Action |
|---|---|
| `"stop listening"` | Pause voice recording |
| `"start listening"` | Resume voice recording |
| `"switch to continuous"` | Enable hands-free VAD mode |
| `"switch to manual"` | Switch back to PTT mode |

### Aider Commands

| Voice Command | Action |
|---|---|
| `"clear context"` | Sends `/clear` to Aider |
| `"run tests"` | Sends `/run pytest` to Aider |
| `"undo that"` / `"cancel that"` / `"revert that"` | Sends `/undo` to Aider |
| `"show diff"` | Sends `/diff` to Aider |
| `"commit changes"` | Sends `/commit` to Aider |
| `"architect mode"` | Switch Aider to architect mode |
| `"code mode"` | Switch Aider to code mode |
| `"ask mode"` | Switch Aider to ask mode |
| `"show map"` | Show Aider's repository map |
| `"drop all files"` | Drop all files from Aider chat |
| `"reset session"` | Reset Aider session |
| `"git status"` | Show git status via Aider |
| `"show git log"` | Show recent git log |

### File Commands

| Voice Command | Action |
|---|---|
| `"add file [name]"` | Sends `/add [name]` to Aider |
| `"drop file [name]"` | Sends `/drop [name]` to Aider |
| `"list files"` | Lists project files in terminal |
| `"run command [cmd]"` | Sends `/run [cmd]` to Aider |

### VoiceDev Control

| Voice Command | Action |
|---|---|
| `"show status"` | Display session statistics |
| `"show history"` | Show recent voice inputs |
| `"help me"` / `"what can I say"` | List all voice commands |
| `"exit"` / `"quit"` | Graceful shutdown |

### Prompt Responses

| Voice Command | Action |
|---|---|
| `"yes"` / `"accept"` | Accept Aider Y/n prompt |
| `"no"` / `"reject"` | Reject Aider Y/n prompt |

All commands use **fuzzy matching** — slight mispronunciations like "unto that" will still match "undo that".

---

## Confirmation Mode

When enabled (`--confirm` or `confirm_before_send: true` in config), VoiceDev shows the transcription before sending it:

1. You speak your command
2. VoiceDev transcribes and displays: `Heard: "refactor the database module"`
3. You have a configurable window (default 2s) to say **"cancel"** to discard
4. Say **"send"** to confirm immediately, or wait for auto-send

This prevents misheard commands from reaching the agent.

---

## STT Confidence Scores

VoiceDev extracts confidence from Whisper's segment-level log-probabilities and displays it alongside each transcription:

```
YOU: refactor the auth module [92% confidence]
CMD: undo that [87% confidence]
```

Color-coded: green (≥80%), yellow (60-80%), red (<60%). Low confidence is a signal to speak more clearly or repeat. Disable with `--no-confidence`.

---

## Audio Feedback

Short beep tones play on state transitions to give hands-free users immediate feedback without looking at the screen:

| Event | Tone |
|---|---|
| Recording started | High beep (880 Hz) |
| Recording stopped / transcribing | Low beep (440 Hz) |
| Command recognized | Quick high beep (1000 Hz) |
| Query sent successfully | Medium beep (660 Hz) |
| Error occurred | Long low beep (220 Hz) |
| Transcription cancelled | Descending beep (330 Hz) |

Disable with `--no-feedback` or `audio_feedback: false` in config.

---

## Wake Word Detection

In continuous mode, VoiceDev uses wake word detection to distinguish intentional commands from background speech:

- **With openwakeword installed:** Real ML-based on-device detection runs on raw audio frames *before* STT. No API calls wasted on background noise.
- **Without openwakeword:** Falls back to checking for the wake phrase in the STT transcription (substring match).

Install wake word support: `pip install openwakeword>=0.6.0`

---

## Auto-Restart

If Aider crashes unexpectedly, VoiceDev automatically restarts it with exponential backoff:

- Attempt 1: waits 2 seconds
- Attempt 2: waits 4 seconds
- Attempt 3: waits 8 seconds
- After 3 failed restarts: stops and reports the issue

Crashes within 5 seconds of startup are not retried (prevents restart loops from configuration errors).

---

## Configuration

All settings live in `~/.voicedev/config.yaml` (auto-created on first run):

```yaml
stt_backend: auto                   # auto | groq_whisper | whisper_api | faster_whisper
faster_whisper_model: base.en       # Model for local STT
groq_whisper_model: whisper-large-v3-turbo  # Model for Groq STT
whisper_language: en                # Language for transcription
vad_aggressiveness: 2               # 0-3 (higher = more aggressive silence detection)
silence_threshold_ms: 1200          # ms of silence before stopping recording
ptt_key: space                      # Key for push-to-talk
agent: aider                        # Target agent
aider_args: []                      # Extra args passed to aider on launch
wake_word: hey dev                  # Wake word for continuous mode
noise_reduction: true               # Enable noise cancellation
session_logging: true               # Save session transcripts
audio_feedback: true                # Play beep sounds on state changes
confirm_before_send: false          # Review transcription before sending
confirmation_timeout_s: 2.0         # Auto-send timeout (if confirm enabled)
show_confidence: true               # Display STT confidence scores
```

---

## STT Backend Comparison

| Feature | Groq Whisper (Recommended) | OpenAI Whisper API | faster-whisper (local) |
|---|---|---|---|
| **Cost** | Free tier available | $0.006/min (~$0.36/hr) | Free |
| **Speed** | Fastest (~0.3s) | ~1-2s (network) | ~0.3-1s (CPU) |
| **Accuracy** | Best (whisper-large-v3-turbo) | Best | Very Good (base.en) |
| **Confidence** | Yes (verbose_json) | Yes (verbose_json) | Yes (avg_logprob) |
| **Internet** | Required | Required | Not required |
| **Setup** | Groq API key | OpenAI API key | First run downloads model |

---

## Session Logs

Every session is auto-saved to `~/.voicedev/sessions/YYYY-MM-DD_HH-MM-SS.md` with:

- Timestamped voice inputs
- Whether each was a command or agent query
- STT backend used and transcription latency
- Confidence score per transcription
- Average session confidence
- Total session duration and estimated cost

---

## Project Structure

```
voicedev/
├── voicedev/
│   ├── __init__.py              # Package version
│   ├── main.py                  # Entry point, CLI, orchestration
│   ├── config.py                # YAML config loader with defaults
│   ├── audio/
│   │   ├── capture.py           # Microphone capture (sounddevice)
│   │   ├── vad.py               # Voice activity detection (webrtcvad)
│   │   ├── noise.py             # Noise reduction (noisereduce)
│   │   ├── feedback.py          # Audio beep feedback (tone generation)
│   │   └── wakeword.py          # Wake word detection (openwakeword + fallback)
│   ├── stt/
│   │   ├── base.py              # Abstract STT backend + TranscriptionResult
│   │   ├── groq_whisper.py      # Groq Whisper API (with confidence)
│   │   ├── whisper_api.py       # OpenAI Whisper API (with confidence)
│   │   └── faster_whisper.py    # Local faster-whisper (with confidence)
│   ├── agent/
│   │   ├── base.py              # Abstract agent backend
│   │   └── aider.py             # Aider integration (with auto-restart)
│   ├── commands/
│   │   └── router.py            # Voice meta-command routing (30+ commands)
│   ├── tui/
│   │   └── display.py           # Rich TUI status panel
│   └── session/
│       └── logger.py            # Session transcript logger (with confidence)
├── tests/
│   ├── test_vad.py
│   ├── test_commands.py
│   ├── test_stt_mock.py
│   ├── test_config.py
│   └── test_noise.py
├── README.md
├── REPORT.md
├── LICENSE                      # MIT
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
