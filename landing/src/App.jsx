const GITHUB_URL = "https://github.com/rohitkumarrai7/VoiceDev";
const DOWNLOAD_URL = "/downloads/VoiceDev-v0.3.0.zip";

const FEATURES = [
  {
    title: "Hands-Free Mode",
    desc: "VAD listens continuously. Smart filter rejects noise, filler words, and low-confidence junk.",
  },
  {
    title: "Reliable PTT",
    desc: "Hold Space to record, release to send. Predictable default for real coding sessions.",
  },
  {
    title: "Three STT Backends",
    desc: "Groq Whisper (fast), OpenAI Whisper API, or local faster-whisper — auto-detected.",
  },
  {
    title: "30+ Voice Commands",
    desc: "Undo, commit, git status, mode switch, file add/drop — fuzzy-matched for STT errors.",
  },
  {
    title: "Confidence Scores",
    desc: "Color-coded transcription confidence so you know when to repeat before sending.",
  },
  {
    title: "Session Logs",
    desc: "Markdown transcripts with latency, confidence, and cost tracking per session.",
  },
];

const FLOW = [
  { step: "1", label: "Mic", detail: "sounddevice capture" },
  { step: "2", label: "VAD + Filter", detail: "webrtcvad + smart gate" },
  { step: "3", label: "STT", detail: "Whisper transcription" },
  { step: "4", label: "Router", detail: "commands vs queries" },
  { step: "5", label: "Aider", detail: "stdin to agent" },
];

const SETUP_STEPS = [
  { cmd: "pip install -r requirements.txt", note: "Core dependencies" },
  { cmd: "cp .env.example .env", note: "GROQ_API_KEY (STT) + OPENROUTER_API_KEY (Aider)" },
  { cmd: "pip install aider-chat", note: "Target coding agent" },
  { cmd: "voicedev", note: "PTT default — hold Space" },
  { cmd: "voicedev --mode hands_free", note: "Zero-touch hands-free" },
];

const COMMANDS = [
  { phrase: "go hands free", action: "Switch to hands-free VAD" },
  { phrase: "switch to manual", action: "Back to PTT mode" },
  { phrase: "undo that", action: "Aider /undo" },
  { phrase: "commit changes", action: "Aider /commit" },
  { phrase: "run tests", action: "Aider /run pytest" },
  { phrase: "show diff", action: "Aider /diff" },
  { phrase: "list files", action: "List project files" },
  { phrase: "help me", action: "Show all commands" },
  { phrase: "stop listening", action: "Pause microphone" },
  { phrase: "exit", action: "Graceful shutdown" },
];

function TerminalDemo() {
  return (
    <div className="terminal" aria-label="VoiceDev demo preview">
      <div className="terminal-bar">
        <span className="dot red" />
        <span className="dot yellow" />
        <span className="dot green" />
        <span className="terminal-title">voicedev — PTT mode</span>
      </div>
      <pre className="terminal-body">
        <code>
{`VoiceDev | LISTENING | STT: groq_whisper | Mode: HandsFree

YOU: refactor the auth module [92% confidence]
     → sent to Aider

CMD: run tests [87% confidence]
     → /run pytest

Filtered: low confidence (7%) — ". ."
     → discarded (not sent)`}
        </code>
      </pre>
    </div>
  );
}

export default function App() {
  return (
    <div className="page">
      <header className="header">
        <a href="#" className="logo">
          <span className="logo-mark">VD</span>
          VoiceDev
        </a>
        <nav className="nav">
          <a href="#features">Features</a>
          <a href="#how">How it works</a>
          <a href="#setup">Setup</a>
          <a href="#commands">Commands</a>
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
            GitHub
          </a>
        </nav>
      </header>

      <main>
        <section className="hero">
          <div className="hero-content">
            <p className="eyebrow">Voice interface for terminal coding agents</p>
            <h1>
              Speak. <span className="accent">Code.</span> Ship.
            </h1>
            <p className="hero-lead">
              VoiceDev wraps Aider with speech-to-text, voice activity detection,
              and 30+ meta-commands — so you stay hands-free while the agent does
              the heavy lifting.
            </p>
            <div className="hero-cta">
              <a className="btn btn-primary" href={DOWNLOAD_URL} download>
                Download ZIP
              </a>
              <a
                className="btn btn-secondary"
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
              >
                View on GitHub
              </a>
            </div>
            <ul className="hero-meta">
              <li>Demo setup ~2 min</li>
              <li>MIT licensed</li>
              <li>No secrets in archive</li>
              <li>Works offline with local STT</li>
            </ul>
          </div>
          <TerminalDemo />
        </section>

        <section id="features" className="section">
          <h2>Built for hands-free developers</h2>
          <p className="section-lead">
            Three input modes, smart audio filtering, and deep Aider integration.
          </p>
          <div className="grid features-grid">
            {FEATURES.map((f) => (
              <article key={f.title} className="card">
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="how" className="section section-alt">
          <h2>How it works</h2>
          <p className="section-lead">
            Your voice flows through a pipeline before reaching the agent.
          </p>
          <div className="flow">
            {FLOW.map((item, i) => (
              <div key={item.step} className="flow-item">
                <div className="flow-step">{item.step}</div>
                <div className="flow-label">{item.label}</div>
                <div className="flow-detail">{item.detail}</div>
                {i < FLOW.length - 1 && <div className="flow-arrow">→</div>}
              </div>
            ))}
          </div>
        </section>

        <section id="setup" className="section">
          <h2>Quick start</h2>
          <p className="section-lead">
            Extract the zip, install dependencies, add an API key (optional), and run.
          </p>
          <ol className="setup-list">
            {SETUP_STEPS.map((s) => (
              <li key={s.cmd} className="setup-item">
                <code>{s.cmd}</code>
                <span>{s.note}</span>
              </li>
            ))}
          </ol>
          <p className="setup-note">
            Without any API key, VoiceDev falls back to local{" "}
            <strong>faster-whisper</strong> — fully offline.
          </p>
        </section>

        <section id="commands" className="section section-alt">
          <h2>Voice command cheat sheet</h2>
          <p className="section-lead">
            Fuzzy matching handles minor STT errors — say it naturally.
          </p>
          <div className="commands-table-wrap">
            <table className="commands-table">
              <thead>
                <tr>
                  <th>Say this</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {COMMANDS.map((c) => (
                  <tr key={c.phrase}>
                    <td>
                      <code>&quot;{c.phrase}&quot;</code>
                    </td>
                    <td>{c.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="section trust">
          <h2>Submission-ready</h2>
          <div className="trust-grid">
            <div className="trust-item">
              <strong>Archive</strong>
              <p>Source + README + REPORT + LICENSE. Under 1 MB. No binaries or secrets.</p>
            </div>
            <div className="trust-item">
              <strong>Cost</strong>
              <p>Groq Whisper free tier recommended. Local STT is $0. Agent LLM billed separately.</p>
            </div>
            <div className="trust-item">
              <strong>Target agent</strong>
              <p>
                <a href="https://aider.chat" target="_blank" rel="noopener noreferrer">
                  Aider
                </a>{" "}
                — stdin integration, slash commands, auto-restart on crash.
              </p>
            </div>
          </div>
          <div className="cta-bottom">
            <a className="btn btn-primary" href={DOWNLOAD_URL} download>
              Download VoiceDev v0.3.0
            </a>
          </div>
        </section>
      </main>

      <footer className="footer">
        <p>
          VoiceDev — MIT License · Built for P1 Voice Input Interface assignment
        </p>
        <p>
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
            github.com/rohitkumarrai7/VoiceDev
          </a>
        </p>
      </footer>
    </div>
  );
}
