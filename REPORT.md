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

## 4. VAD Design

Voice Activity Detection is the single most important UX feature in VoiceDev. Without it, the user must press a button to start and stop every recording — which defeats the hands-free goal and makes the experience feel like a walkie-talkie rather than a natural conversation.

I chose **webrtcvad** (Google's WebRTC VAD, Python bindings via `webrtcvad-wheels`). It's battle-tested — the same VAD used in Chrome and WebRTC implementations worldwide. It runs in real-time on CPU with negligible overhead, and its Python bindings are straightforward.

**Aggressiveness tuning:** webrtcvad offers levels 0-3, where higher values are more aggressive about filtering non-speech. Level 2 is the sweet spot for typical indoor development environments — it filters out most ambient noise (fans, air conditioning, distant conversations) while reliably detecting speech. Level 0 lets through too much noise; level 3 sometimes clips quiet speech.

**Silence threshold:** The default 1.2 seconds of continuous silence before stopping recording was chosen to match natural speech pauses. People pause between sentences for 0.5-1.0 seconds; 1.2s gives enough margin to avoid cutting off mid-thought while not making the user wait too long after finishing.

**Speech onset detection:** Requiring 3 consecutive voiced frames (90ms at 30ms/frame) before confirming speech onset prevents false triggers from brief noises like keyboard clicks or door slams.

---

## 5. Voice Meta-Commands

A key design insight: not all spoken text should reach the agent. Some utterances control the tool itself — pausing listening, switching modes, triggering shortcuts. These "meta-commands" are intercepted by VoiceDev's command router before reaching the agent.

The command set was designed to be:
- **Natural.** "undo that" rather than "execute undo command"
- **Distinct.** Each phrase is phonetically different enough from normal speech to avoid false positives
- **Aider-aligned.** Commands map directly to Aider's `/slash` vocabulary

**Fuzzy matching** via `rapidfuzz` (Levenshtein-based ratio) is critical because STT isn't perfect. "undo that" might be transcribed as "unto that" or "undo bat" — fuzzy matching with a 75% threshold catches these errors. The threshold was tuned by testing against common transcription errors: too high misses legitimate commands, too low causes false positives on normal speech.

The `"add file [filename]"` command uses prefix matching rather than fuzzy matching, since the filename is variable and should be passed through literally.

---

## 6. Architecture Trade-offs

### stdin injection vs. PTY wrapping

VoiceDev communicates with Aider by writing to the subprocess's stdin pipe. This is simple and reliable — Aider reads from stdin as if the user typed it. The alternative, PTY wrapping (using `pty` or `pexpect`), would allow reading Aider's output programmatically, enabling features like detecting when Aider finishes responding or parsing its output for errors. However, PTY wrapping adds significant complexity, is platform-dependent, and wasn't necessary for the core use case. The agent's output renders directly to the terminal, which is exactly where the user expects to see it.

### Rich TUI without interfering with agent output

The TUI status panel prints discrete updates (state changes, transcriptions) rather than using `rich.live.Live` for a persistent overlay. This was a deliberate choice: Aider owns the terminal's stdout, and a persistent overlay would interfere with its rendering. Instead, VoiceDev prints status updates inline — unobtrusive but informative.

### Threading model

Audio capture runs in a background thread (managed by `sounddevice`'s callback mechanism). VAD processing happens synchronously in the main loop. STT calls are synchronous and blocking — they take 0.3-2s, during which the main loop pauses. This is acceptable because the user is waiting for the transcription result anyway. An async architecture would be more complex without meaningful UX improvement at this scale.

### Noise reduction placement

Noise reduction runs before STT, after VAD confirms a speech segment. This avoids wasting CPU on silence and ensures the STT engine receives the cleanest possible audio. The `noisereduce` library's stationary noise reduction mode is used — it assumes background noise is relatively constant (true for fans, AC, and most office environments) and subtracts the noise profile from the signal.

---

## 7. Limitations

**Simultaneous speech and reading.** If the user speaks while reading Aider's output, they may miss content on screen. This is inherent to a voice-input / visual-output design. A potential mitigation (text-to-speech for agent responses) was explicitly out of scope per the problem statement.

**Keyboard noise triggering VAD.** Mechanical keyboards can produce sounds loud enough to trigger VAD. Noise reduction helps, but in continuous mode, a user who types while the mic is active may generate false recordings. PTT mode avoids this entirely since the user controls when the mic is active.

**Aider subprocess management.** If Aider crashes, VoiceDev detects this via the watchdog thread and prints an error, but doesn't auto-restart it. The user must restart VoiceDev. Auto-restart is a natural future improvement.

**Wake word latency.** The planned wake word detection (via `openwakeword` or `pvporcupine`) adds ~200ms latency to each audio frame in continuous mode. For this release, continuous mode relies on VAD alone — the "hey Dev" wake word is configurable but the actual detection is deferred to a future version that can implement it without degrading the VAD loop's responsiveness.

**Single language.** Both STT backends support multiple languages, but VoiceDev defaults to English. Multi-language support is straightforward to add via the `whisper_language` config option.

---

## 8. Cost Analysis

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

These costs are trivial for a professional tool. A GitHub Copilot subscription costs $10-19/month; VoiceDev's STT cost is a fraction of that.

### Local STT cost

- $0 per query
- ~2GB RAM for the `medium.en` model; ~500MB for `base.en`
- CPU usage during transcription: ~1-2 seconds of CPU time per query

### At scale (hypothetical SaaS)

- 10,000 active users × 100 queries/day × $0.0005/query = $500/day
- Local inference on shared GPU servers could reduce this by 10-50x
- Monthly: $15,000 (cloud) or $300-1,500 (self-hosted)

---

## 9. SaaS Extension Path

VoiceDev's architecture was designed with a clear upgrade path from open-source CLI to SaaS product:

- **Session logs** are already structured Markdown — one parse away from a web dashboard
- **Multi-agent support** is architecturally ready via the `AgentBackend` interface; adding Claude Code or opencode requires implementing one class
- **Voice profiles** (per-project command sets, accent adaptation) can extend the YAML config
- **Team features** (shared session logs, usage analytics) build naturally on the session logging infrastructure
- **Cloud STT proxy** could offer a single API key for teams, with usage tracking and billing

The open-source CLI drives adoption; a Pro tier adds convenience features (cloud STT, web dashboard, search); a Team tier adds collaboration. This is the model that worked for tools like Aider itself, and it aligns with how developer tools grow.

---

## External Services Used

| Service | Purpose | Cost |
|---|---|---|
| Groq Whisper API | Fast cloud speech-to-text (recommended default) | Free tier available |
| OpenAI Whisper API | Cloud speech-to-text (alternative) | $0.006/min |
| faster-whisper | Local speech-to-text (offline fallback) | Free |
| webrtcvad | Voice activity detection | Free (open-source) |
| noisereduce | Audio noise reduction | Free (open-source) |

No paid external services are required. Groq's free tier covers typical developer usage. The tool also works fully offline with faster-whisper.
