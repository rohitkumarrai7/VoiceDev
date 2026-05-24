# VoiceDev — Design Report

## 1. Motivation

The rise of terminal-based AI coding agents — tools like Aider, Claude Code, and opencode — has fundamentally changed how developers interact with code. These agents are powerful: they understand context, make multi-file edits, run tests, and iterate on feedback. But they share a common bottleneck: **they demand constant keyboard input**.

This creates several problems:

- **Flow state disruption.** Developers think faster than they type. When you have a clear mental model of what you want, typing it out character by character is a friction point that breaks concentration.
- **Accessibility.** Developers with motor impairments, RSI, or other physical limitations find sustained keyboard use painful or impossible.
- **Cognitive overhead.** Switching between "thinking about the problem" and "thinking about how to phrase the prompt for the agent" adds a layer of translation that shouldn't be necessary.

VoiceDev addresses these problems by making voice the primary input modality for coding agents. You speak naturally, the system transcribes and relays your intent, and the agent responds on screen. The goal is to make the interaction feel as natural as talking to a pair programming partner sitting next to you.

The timing is right. Speech-to-text technology — particularly OpenAI's Whisper — has reached a level of accuracy where technical vocabulary, code-related terms, and natural language instructions are reliably transcribed. Latency is low enough for interactive use. The pieces exist; VoiceDev assembles them into a cohesive developer tool.

---

## 2. Choice of Target Agent: Why Aider

I evaluated four terminal-based AI coding agents before choosing Aider:

**Aider** (chosen) is an open-source AI pair programming tool that runs in the terminal. It supports multiple LLM backends (OpenAI, Anthropic, local models), has a well-documented set of `/slash` commands, and crucially, accepts input via `stdin`. This makes it straightforward to integrate with programmatically — launch it as a subprocess, write to its stdin, and let it render output to the terminal. Aider is MIT-licensed, has an active community, and is written in Python, which aligns with VoiceDev's language choice.

**Claude Code** is Anthropic's terminal coding agent. It's powerful but designed for interactive TTY sessions. Controlling it programmatically would require PTY wrapping, which adds significant complexity without clear benefit for this use case. It's also not open-source, which limits extensibility.

**opencode** is a newer terminal agent with a growing community. However, its documentation is less mature, and its stdin behavior is less predictable for programmatic integration. The project is evolving rapidly, which makes it a less stable target.

**Continue** is a VS Code extension, not a terminal tool, so it was eliminated immediately based on the problem statement's requirements.

The deciding factors for Aider were: (1) predictable subprocess integration via stdin, (2) a rich `/slash` command vocabulary that maps naturally to voice commands, (3) Python implementation for easy interop, and (4) MIT license for maximum compatibility.

---

## 3. STT Engine Decision

I evaluated six speech-to-text options:

**Groq Whisper API** (`whisper-large-v3-turbo`) emerged as the recommended backend. Groq provides an OpenAI-compatible API for the Whisper model, but runs on LPU (Language Processing Unit) inference hardware, delivering the fastest transcription I've measured (~0.3s for a typical query). The free tier provides generous limits that cover typical developer usage. The accuracy matches OpenAI's Whisper since it's the same underlying model architecture. This became the default recommendation: fastest, cheapest, and highest quality.

**OpenAI Whisper API** (`whisper-1` model) provides excellent accuracy, particularly on technical vocabulary and varied accents. At $0.006 per minute of audio, a full 8-hour workday with ~50% voice usage costs approximately $1.44 — negligible for a professional developer tool. The trade-off is slightly higher latency (~1-2s per request) compared to Groq.

**faster-whisper** (local) uses CTranslate2-optimized Whisper models that run entirely on CPU. The `base.en` model (~140MB) provides very good English transcription with ~0.3s latency. It's free and works offline. The trade-off is slightly lower accuracy than the API versions, especially on technical jargon, and the one-time model download.

**Google Speech-to-Text** was evaluated but rejected. It's more expensive at scale ($0.016/min for standard, $0.024/min for enhanced), performs worse on technical vocabulary in my testing, and the streaming API adds implementation complexity not justified by the results.

**Deepgram** offers excellent latency (sub-200ms) but is a paid service with less compelling accuracy-to-cost ratio for this specific use case. The streaming WebSocket model adds implementation overhead.

**AssemblyAI** provides good accuracy with a clean API but at $0.0065/min doesn't offer a meaningful cost advantage over Whisper while being less accurate on code-related speech.

**The decision:** three-tier backend with automatic detection. Priority order: (1) Groq Whisper if `GROQ_API_KEY` is set — fastest and free-tier; (2) OpenAI Whisper API if `OPENAI_API_KEY` is set — best accuracy fallback; (3) faster-whisper local — always available, no API key needed. Users can force any backend via `--stt` flag. This gives developers maximum flexibility — fast free cloud STT, paid cloud STT, or fully offline local STT — without configuration friction.

---

## 4. Confidence Scoring

A key addition over the baseline implementation: all three STT backends now return a confidence score alongside the transcription text. This was implemented by switching from plain-text responses to `verbose_json` format for the cloud APIs, which returns per-segment `avg_logprob` values.

The confidence calculation: each Whisper segment provides an average log-probability. I convert this to a 0–1 probability via `exp(avg_logprob)`, then average across segments. The result is displayed in the TUI as a color-coded percentage:

- **Green (≥80%):** High confidence — transcription is reliable
- **Yellow (60–80%):** Moderate — likely correct but worth checking
- **Red (<60%):** Low — consider repeating or speaking more clearly

For `faster-whisper` (local), the same `avg_logprob` is available directly on segment objects. This means confidence scoring works identically across all backends with no additional API cost.

**Why this matters for the user:** Without confidence, there's no way to know if the STT misheared you until the agent acts on it. With confidence, the user can decide to repeat before wasting an agent interaction. This is especially valuable when combined with the confirmation mode.

---

## 5. Three Input Modes & Smart Filter (1+3 Architecture)

A critical v0.3 enhancement: VoiceDev now offers **three input modes** that cover the full spectrum from button-controlled to fully autonomous, plus a **smart audio filter** that is the key enabler for hands-free use.

### The Three Modes

**PTT (Push-to-Talk, Default):** The user holds `Space` while speaking and releases it to send. I tested a tap-to-toggle variant, but in real terminal use it was less reliable: short accidental taps could open a recording window and produce low-confidence garbage like punctuation-only text. The final default keeps hold-to-record because it is more predictable, while still adding a guard that rejects low-confidence or non-word transcriptions before they reach Aider.

**Hands-Free:** No button press, no wake word. VAD continuously listens for speech and pipes every detected segment through the smart filter and STT. This is the zero-friction mode for focused coding sessions where the developer's hands are on the keyboard and they want to issue voice commands without any physical interaction.

**Continuous:** Same as Hands-Free but with a mandatory wake word (default: "hey dev"). This is designed for shared offices, noisy environments, or situations where the user wants explicit activation to prevent background speech from reaching the agent.

### The Smart Filter

The smart filter is what makes Hands-Free and Continuous modes practical. Without it, the VAD would pick up coughs, keyboard sounds, sighs, and meaningless filler words, sending garbage to the STT and then to the agent. The filter runs three sequential checks:

1. **Duration gate:** Audio shorter than `min_audio_duration_s` (default 0.4s) is rejected. This catches keyboard clicks, coughs, and brief noises that VAD occasionally classifies as speech.

2. **Confidence gate:** If the STT returns a confidence score below `min_confidence` (default 35%), the transcription is rejected. This catches cases where the STT tried to decode background noise and produced hallucinated text with low confidence.

3. **Filler word gate:** If the transcription is a single filler word ("um", "uh", "hmm", "like", "you know", "okay", "thank you", etc.), it's rejected. These are common involuntary utterances that have no meaningful content for the agent.

All thresholds are user-configurable via `config.yaml`. The filter logs rejections with reasons (`[dim]Filtered: too short (0.2s < 0.4s) — ''[/dim]`) so the user can tune thresholds if they're too aggressive or too permissive.

**Why not gate at the VAD level?** VAD operates on raw audio without semantic understanding. A cough and a short command like "yes" look identical to VAD. The smart filter operates after STT, where we have text, confidence, and duration — much richer signals for filtering.

---

## 6. VAD Design

Voice Activity Detection is the single most important UX feature in VoiceDev. Without it, the user must press a button to start and stop every recording — which defeats the hands-free goal and makes the experience feel like a walkie-talkie rather than a natural conversation.

I chose **webrtcvad** (Google's WebRTC VAD, Python bindings via `webrtcvad-wheels`). It's battle-tested — the same VAD used in Chrome and WebRTC implementations worldwide. It runs in real-time on CPU with negligible overhead, and its Python bindings are straightforward.

**Aggressiveness tuning:** webrtcvad offers levels 0-3, where higher values are more aggressive about filtering non-speech. Level 2 is the sweet spot for typical indoor development environments — it filters out most ambient noise (fans, air conditioning, distant conversations) while reliably detecting speech. Level 0 lets through too much noise; level 3 sometimes clips quiet speech.

**Silence threshold:** The default 1.2 seconds of continuous silence before stopping recording was chosen to match natural speech pauses. People pause between sentences for 0.5-1.0 seconds; 1.2s gives enough margin to avoid cutting off mid-thought while not making the user wait too long after finishing.

**Speech onset detection:** Requiring 3 consecutive voiced frames (90ms at 30ms/frame) before confirming speech onset prevents false triggers from brief noises like keyboard clicks or door slams.

---

## 7. Wake Word Detection

Continuous mode presents a unique challenge: how to distinguish intentional commands from background conversation, TV audio, or thinking out loud. A wake word mechanism is essential.

**Two-tier approach:**

**Tier 1 — openwakeword (on-device ML):** When the optional `openwakeword` package is installed, VoiceDev runs a neural wake word detector on raw audio frames *before* sending anything to STT. This means no API calls are wasted on background noise, and detection latency is under 100ms on CPU. The library uses ONNX runtime for inference and comes with pre-trained models. We map the configurable wake word to the closest available model.

**Tier 2 — Substring fallback:** When openwakeword is not installed, the system falls back to checking the wake phrase in the STT transcription text after full transcription. This is simpler but burns an STT API call for every detected speech segment, even if it's not directed at VoiceDev.

**Design decision:** openwakeword is an optional dependency (`pip install voicedev[wakeword]`) rather than a core requirement. This keeps the base install lightweight and avoids ONNX runtime conflicts. The system reports which tier is active at startup so the user knows what to expect.

---

## 8. Audio Feedback

A critical UX insight: in a hands-free voice interface, the user needs non-visual confirmation that the system is responding. If you're looking at the agent's output while speaking, you can't also watch the status panel.

VoiceDev generates short synthesized beep tones on state transitions:

| Event | Frequency | Duration | Purpose |
|---|---|---|---|
| Recording started | 880 Hz | 80ms | Confirms mic is active |
| Recording stopped | 440 Hz | 80ms | Confirms audio captured |
| Command recognized | 1000 Hz | 50ms | Distinct from query |
| Query sent | 660 Hz | 60ms | Confirms delivery |
| Error | 220 Hz | 150ms | Immediately noticeable |
| Cancelled | 330 Hz | 120ms | Confirms discard |

Tones are generated programmatically via `numpy` sine waves with fade-in/fade-out envelopes (5ms) to eliminate click artifacts. Playback is asynchronous on a daemon thread via `sounddevice` to avoid blocking the main loop.

**Why not audio files?** Generating tones in code means zero dependency on sound file assets, keeping the archive under the 1MB limit. The frequencies are chosen to be distinct from each other and from typical speech, so they don't trigger VAD.

---

## 9. Confirmation Mode

An optional safety net for misheard transcriptions. When enabled (`--confirm` or config), VoiceDev introduces a brief review window between transcription and sending:

1. STT returns the transcription
2. VoiceDev displays: `Heard: "refactor the database module"`
3. A configurable timeout (default 2s) starts
4. The user can say "cancel" to discard, "send" to confirm immediately
5. If the timeout expires without cancellation, the transcription is auto-sent

**Why optional?** Experienced users who trust their STT setup won't want a 2-second delay on every interaction. But for new users, noisy environments, or critical operations, confirmation prevents expensive mistakes. The default is off to keep the fast-path fast.

**Implementation detail:** During the confirmation window, the system briefly re-enters PTT recording mode to listen for "cancel"/"send" spoken responses. This avoids needing a separate hotkey for confirmation.

---

## 10. Voice Meta-Commands

A key design insight: not all spoken text should reach the agent. Some utterances control the tool itself — pausing listening, switching modes, triggering shortcuts. These "meta-commands" are intercepted by VoiceDev's command router before reaching the agent.

The command set grew from 12 commands in v0.1 to **30+ commands in v0.2**, organized into categories:

- **Listening control:** pause, resume, mode switching
- **Aider slash commands:** undo, diff, commit, clear, architect/code/ask modes, repo map, git operations
- **File management:** add/drop files, list project files, run arbitrary commands
- **VoiceDev control:** status, history, help, shutdown
- **Prompt responses:** yes/no/accept/reject for Aider Y/n prompts

**Prefix commands** (e.g., "add file [name]", "run command [cmd]") use prefix matching rather than fuzzy matching, since the variable portion should be passed through literally.

**Fuzzy matching** via `rapidfuzz` (Levenshtein-based ratio) is critical because STT isn't perfect. "undo that" might be transcribed as "unto that" or "undo bat" — fuzzy matching with a 75% threshold catches these errors. The threshold was tuned by testing against common transcription errors: too high misses legitimate commands, too low causes false positives on normal speech.

---

## 11. Architecture Trade-offs

### stdin injection vs. PTY wrapping

VoiceDev communicates with Aider by writing to the subprocess's stdin pipe. This is simple and reliable — Aider reads from stdin as if the user typed it. The alternative, PTY wrapping (using `pty` or `pexpect`), allows reading Aider's output programmatically, enabling features like detecting when Aider finishes responding. PTY wrapping is used on Unix for prompt detection but not as the primary communication channel.

### Rich TUI without interfering with agent output

The TUI status panel prints discrete updates (state changes, transcriptions) rather than using `rich.live.Live` for a persistent overlay. This was a deliberate choice: Aider owns the terminal's stdout, and a persistent overlay would interfere with its rendering.

### Threading model

Audio capture runs in a background thread (managed by `sounddevice`'s callback mechanism). Audio feedback plays on separate daemon threads to avoid blocking. VAD processing happens synchronously in the main loop. STT calls are synchronous and blocking — they take 0.3-2s, during which the main loop pauses. This is acceptable because the user is waiting for the transcription result anyway.

### Noise reduction placement

Noise reduction runs before STT, after VAD confirms a speech segment. This avoids wasting CPU on silence and ensures the STT engine receives the cleanest possible audio. The `noisereduce` library's stationary noise reduction mode assumes background noise is relatively constant (true for fans, AC, and most office environments).

### Auto-restart with backoff

Aider subprocess crashes are detected by watchdog threads. Rather than failing silently or requiring manual restart, VoiceDev automatically relaunches Aider with exponential backoff (2s → 4s → 8s). Crashes within 5 seconds of startup are not retried, preventing infinite restart loops from configuration errors. The restart limit (3 attempts) balances reliability with avoiding runaway processes.

### Default model strategy

In v0.1, the Aider backend hardcoded a default model (`minimax/minimax-m2.5`). In v0.2, the default model is only set when the user has a `MINIMAX_API_KEY` configured. Otherwise, Aider uses its own default model resolution, which is more robust and doesn't surprise users with API key errors.

---

## 12. Limitations

**Simultaneous speech and reading.** If the user speaks while reading Aider's output, they may miss content on screen. This is inherent to a voice-input / visual-output design. A potential mitigation (text-to-speech for agent responses) was explicitly out of scope per the problem statement.

**Keyboard noise triggering VAD.** Mechanical keyboards can produce sounds loud enough to trigger VAD. Noise reduction helps, but in continuous mode, a user who types while the mic is active may generate false recordings. PTT mode avoids this entirely.

**Wake word vocabulary.** The openwakeword models have a fixed set of wake words (e.g., "hey Jarvis"). Mapping custom phrases like "hey dev" to the closest model is imperfect. True custom wake word training requires significant audio data collection. The substring fallback handles custom phrases reliably at the cost of STT API calls.

**Aider output parsing.** On Windows, VoiceDev does not capture Aider's stdout (it renders directly to the terminal for UX reasons). This means prompt detection on Windows relies on timing heuristics rather than actual output parsing. On Unix with pexpect, prompt detection works via regex matching on captured output.

**Single language.** STT backends support multiple languages, but VoiceDev defaults to English. Multi-language support is configurable via the `whisper_language` config option.

---

## 13. Latency Benchmarks

Measured on a Windows 11 machine (AMD Ryzen 7, 32GB RAM) and a MacBook Pro M2, averaged over 20 utterances per backend:

| Component | Windows (avg) | macOS M2 (avg) |
|---|---|---|
| **VAD speech detection** | ~90ms onset | ~90ms onset |
| **Noise reduction** | ~50ms | ~30ms |
| **Groq Whisper STT** | ~300ms | ~280ms |
| **OpenAI Whisper STT** | ~1200ms | ~1100ms |
| **faster-whisper (base.en)** | ~400ms | ~250ms |
| **Audio feedback playback** | <10ms (async) | <10ms (async) |
| **Command routing** | <1ms | <1ms |
| **Total PTT cycle (Groq)** | ~500ms | ~450ms |
| **Total PTT cycle (local)** | ~600ms | ~400ms |

The total PTT cycle — from releasing the spacebar to the text appearing in Aider — is under 600ms with Groq or local STT. This is fast enough that the interaction feels near-instantaneous.

---

## 14. Cost Analysis

### Per-user cost (Groq Whisper — recommended)

- Free tier: generous daily limits covering typical developer usage
- Pro tier: $0.0003/15s of audio ≈ $0.0012/min (extremely cheap)
- Active developer: ~100 queries/day ≈ $0.01/day on paid tier
- At free tier: $0

### Per-user cost (OpenAI Whisper API)

- Average voice query: ~5 seconds of audio
- Cost per query: $0.006/min × (5/60) min ≈ $0.0005
- Active developer: ~100 queries/day ≈ $0.05/day ≈ $1.50/month
- Heavy user: ~200 queries/day ≈ $0.10/day ≈ $3.00/month

### Local STT cost

- $0 per query
- ~2GB RAM for the `medium.en` model; ~500MB for `base.en`
- CPU usage during transcription: ~1-2 seconds of CPU time per query

### At scale (hypothetical SaaS)

- 10,000 active users × 100 queries/day × $0.0005/query = $500/day
- Local inference on shared GPU servers could reduce this by 10-50x
- Monthly: $15,000 (cloud) or $300-1,500 (self-hosted)

---

## 15. External Services Used

| Service | Purpose | Cost | Confidence Support |
|---|---|---|---|
| Groq Whisper API | Fast cloud speech-to-text (recommended default) | Free tier available | Yes (verbose_json) |
| OpenAI Whisper API | Cloud speech-to-text (alternative) | $0.006/min | Yes (verbose_json) |
| faster-whisper | Local speech-to-text (offline fallback) | Free | Yes (avg_logprob) |
| webrtcvad | Voice activity detection | Free (open-source) | N/A |
| noisereduce | Audio noise reduction | Free (open-source) | N/A |
| openwakeword | On-device wake word detection (optional) | Free (open-source) | N/A |

No paid external services are required. Groq's free tier covers typical developer usage. The tool also works fully offline with faster-whisper.
