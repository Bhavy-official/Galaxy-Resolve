import { Link } from 'react-router-dom'
import {
  IconAlertTriangle,
  IconBolt,
  IconBrain,
  IconCheck,
  IconDeviceMobile,
  IconFileText,
  IconHeadphones,
  IconShieldCheck,
} from '@tabler/icons-react'

const problems = [
  { icon: IconHeadphones, title: 'Manual agent triage', text: '15+ minutes per call. Inconsistent steps across agents. Millions of interactions globally.', index: '01' },
  { icon: IconFileText, title: 'Static knowledge bases', text: 'Dense 1,500-word articles. Users abandon after 2 clicks. Zero in-app actionability.', index: '02' },
  { icon: IconAlertTriangle, title: 'Naive GenAI chatbots', text: 'Hallucinated menu paths. Fabricated deeplinks. Factory Reset before basic checks.', index: '03' },
]

const keyMetrics = [
  { value: '100%', label: 'Schema valid', icon: IconCheck },
  { value: '0', label: 'URL leaks', icon: IconShieldCheck },
  { value: '<25ms', label: 'Cache latency', icon: IconBolt },
  { value: '90%+', label: 'Paraphrase recall', icon: IconBrain },
  { value: '4', label: 'Device domains', icon: IconDeviceMobile },
]

const technologies = [
  { name: 'Python', sym: 'Py' },
  { name: 'FastAPI', sym: 'Fa' },
  { name: 'Gemini', sym: 'G' },
  { name: 'Pydantic', sym: 'P' },
  { name: 'FAISS', sym: 'F' },
  { name: 'BM25', sym: 'B' },
  { name: 'ONNX', sym: 'O' },
  { name: 'SQLite', sym: 'Sq' },
  { name: 'Docker', sym: 'D' },
]

function PipelineArtwork() {
  return (
    <div className="hero-art" aria-label="Troubleshooting pipeline illustration">
      <div className="art-orbit orbit-one" />
      <div className="art-orbit orbit-two" />
      <div className="art-core">
        <span>GR</span>
        <i />
      </div>
      <div className="art-card art-input">
        <span className="art-pulse" /> Galaxy issue{' '}
        <strong>"Screen flickers"</strong>
      </div>
      <div className="art-card art-intent">
        <span className="art-kicker">INTENT MATCHED</span>
        <strong>Display · Flicker</strong>
        <small>confidence 0.98</small>
      </div>
      <div className="art-card art-plan">
        <span className="art-kicker">GROUNDED PLAN</span>
        <strong>3 safe actions</strong>
        <small>2 settings · 1 check</small>
      </div>
      <span className="art-caption">From vague complaint to verified action</span>
    </div>
  )
}

function CacheArtwork() {
  return (
    <div className="visual-panel cache-visual" aria-label="Two-tier semantic cache diagram">
      <div className="cache-query">
        <span>QUERY</span>
        <strong>"battery drains quickly"</strong>
      </div>
      <div className="cache-line" />
      <div className="cache-lanes">
        <div className="cache-lane exact">
          <span>01 / EXACT</span>
          <strong>SHA-256</strong>
          <small>6 ms</small>
        </div>
        <div className="cache-lane semantic">
          <span>02 / SEMANTIC</span>
          <strong>FAISS vector</strong>
          <small>18 ms</small>
        </div>
      </div>
      <div className="cache-guard">
        <span className="guard-dot" /> Near-miss slot guard <span>ON</span>
      </div>
    </div>
  )
}

function RankingArtwork() {
  return (
    <div className="visual-panel ranking-visual" aria-label="Deeplink ranking results illustration">
      <div className="rank-head">
        <span>SETTINGS CATALOG</span>
        <span>578 URIS</span>
      </div>
      <div className="rank-row rank-winner">
        <span className="rank-number">01</span>
        <div><strong>Screen refresh rate</strong><small>Display · Motion smoothness</small></div>
        <span className="rank-score">0.982</span>
      </div>
      <div className="rank-row">
        <span className="rank-number">02</span>
        <div><strong>Screen resolution</strong><small>Display · Clarity</small></div>
        <span className="rank-score">0.841</span>
      </div>
      <div className="rank-row">
        <span className="rank-number">03</span>
        <div><strong>Adaptive brightness</strong><small>Display · Brightness</small></div>
        <span className="rank-score">0.613</span>
      </div>
      <div className="rank-footer">
        <span className="rank-check"><IconCheck size={14} /></span>{' '}
        Cross-encoder reranked <span>leaf screen</span>
      </div>
    </div>
  )
}

export function HomePage() {
  return (
    <main className="home-page">
      {/* ─── Hero ─── */}
      <section className="hero-section">
        <div className="hero-glow" />
        <div className="hero-content page-width">
          <div className="hero-copy">
            <span className="eyebrow hero-eyebrow">
              <span className="eyebrow-dot" /> Samsung PRISM Hackathon 2026{' '}
              <span className="eyebrow-divider">·</span> Theme 2
            </span>
            <h1>Galaxy-<span>Resolve</span></h1>
            <p className="hero-subtitle">
              Transforming vague Galaxy device complaints into one-tap,
              deeplinked troubleshooting plans — powered by grounded GenAI.
            </p>
            <div className="hero-actions">
              <Link className="button-primary" to="/demo">
                Try live demo <span aria-hidden="true">→</span>
              </Link>
              <Link className="button-secondary" to="/features">
                View architecture <span aria-hidden="true">↗</span>
              </Link>
            </div>
            <div className="hero-footnote">
              <span className="hero-footline" /> Deterministic by design. Grounded at every step.
            </div>
          </div>
          <PipelineArtwork />
        </div>
        <a className="scroll-cue" href="#problem" aria-label="Scroll to the problem">
          <span /> Discover the system
        </a>
      </section>

      {/* ─── Problem ─── */}
      <section className="section-block problem-section page-width" id="problem">
        <div className="section-heading reveal">
          <div>
            <span className="section-kicker">THE GAP</span>
            <h2>Troubleshooting should feel <span>effortless.</span></h2>
          </div>
          <p>Today's support experience makes the customer do the hard part.</p>
        </div>
        <div className="problem-grid">
          {problems.map(p => {
            const Icon = p.icon
            return (
              <article className="problem-card reveal" key={p.index}>
                <div className="problem-card-top">
                  <span className="problem-icon"><Icon size={21} stroke={1.6} /></span>
                  <span className="problem-index">{p.index}</span>
                </div>
                <h3>{p.title}</h3>
                <p>{p.text}</p>
              </article>
            )
          })}
        </div>
      </section>

      {/* ─── Solution ─── */}
      <section className="solution-section">
        <div className="page-width solution-inner">
          <div className="section-heading reveal solution-heading">
            <div>
              <span className="section-kicker">THE ENGINE</span>
              <h2>Precision at every step.</h2>
            </div>
            <p>A grounded pipeline that turns intent into safe, actionable device settings.</p>
          </div>

          <article className="solution-row reveal">
            <div className="solution-copy">
              <span className="solution-index">01 / TRUST</span>
              <h3>LLM proposes.<br /><span>Code disposes.</span></h3>
              <p>The AI extracts semantic intent. Deterministic Python enforces every schema rule, deeplink, and safety constraint. Zero hallucination by construction.</p>
              <Link className="text-link" to="/features">Explore the architecture <span>→</span></Link>
            </div>
            <div className="visual-panel code-visual">
              <div className="code-window-top">
                <span /><span /><span />
                <small>grounding.py</small>
              </div>
              <div className="code-lines">
                <div><b>01</b><code><i>intent</i> = extract(query)</code></div>
                <div><b>02</b><code><i>steps</i> = ground(intent, siis)</code></div>
                <div><b>03</b><code><i>assert</i> schema_valid(steps)</code></div>
                <div><b>04</b><code><i>return</i> compile_plan(steps)</code></div>
              </div>
              <div className="code-valid">
                <IconCheck size={15} /> ALL CONSTRAINTS VERIFIED
              </div>
            </div>
          </article>

          <article className="solution-row solution-row-reverse reveal">
            <div className="solution-copy">
              <span className="solution-index">02 / SPEED</span>
              <h3>Sub-25ms<br /><span>semantic cache.</span></h3>
              <p>Two-tier caching with SHA-256 exact match and FAISS vector search. A Near-Miss Slot Guard blocks false hits like "screen black" vs "screen cracked."</p>
              <Link className="text-link" to="/demo">See it in action <span>→</span></Link>
            </div>
            <CacheArtwork />
          </article>

          <article className="solution-row reveal">
            <div className="solution-copy">
              <span className="solution-index">03 / PRECISION</span>
              <h3>The right fix.<br /><span>The exact screen.</span></h3>
              <p>578 masked Settings URIs resolved through BM25, dense embeddings, and cross-encoder reranking with leaf-level specificity.</p>
              <Link className="text-link" to="/features">Explore retrieval <span>→</span></Link>
            </div>
            <RankingArtwork />
          </article>
        </div>
      </section>

      {/* ─── Metrics ─── */}
      <section className="metrics-section page-width reveal" aria-label="Key system metrics">
        <div className="metrics-heading">
          <span className="section-kicker">BUILT TO BE TRUSTED</span>
          <p>Grounded from input to action.</p>
        </div>
        <div className="metric-grid">
          {keyMetrics.map(({ value, label, icon: Icon }) => (
            <div className="metric-item" key={label}>
              <Icon size={18} stroke={1.6} />
              <strong>{value}</strong>
              <span>{label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ─── Stack ─── */}
      <section className="stack-section page-width reveal">
        <div className="stack-heading">
          <span className="section-kicker">THE STACK</span>
          <h2>Lean by design.</h2>
        </div>
        <div className="stack-ribbon">
          {technologies.map(t => (
            <div className="stack-item" key={t.name}>
              <span className="stack-symbol">{t.sym}</span>
              <span>{t.name}</span>
            </div>
          ))}
        </div>
        <p className="stack-caption">
          Single-service Python microservice. Zero Node.js. Boots in &lt; 2 seconds.
        </p>
      </section>
    </main>
  )
}
