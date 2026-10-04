import { Link } from 'react-router-dom'
import {
  IconBolt,
  IconBrain,
  IconCheck,
  IconDatabase,
  IconFilter,
  IconLanguage,
  IconShieldCheck,
  IconZoomCode,
} from '@tabler/icons-react'

const features = [
  {
    icon: IconLanguage,
    title: 'Query Normalization',
    desc: 'Spell correction, URL scrubbing, and slot extraction converts noisy natural language into a clean canonical form before any LLM call.',
  },
  {
    icon: IconBolt,
    title: 'Two-Tier Semantic Cache',
    desc: 'SHA-256 exact-match (6 ms) followed by FAISS vector search (≤25 ms). Near-Miss Slot Guard blocks category-crossing false hits.',
  },
  {
    icon: IconBrain,
    title: 'LLM Intent Enrichment',
    desc: 'Gemini extracts domain, sub-domain, and goal from the query. Falls back to deterministic rules when the API is unavailable or rate-limited.',
  },
  {
    icon: IconZoomCode,
    title: 'SIIS Grounding',
    desc: 'Cross-encoder verifies each extracted step against the Samsung Support article text. Hallucinated steps that lack textual evidence are dropped.',
  },
  {
    icon: IconDatabase,
    title: 'Deeplink Catalog (578 URIs)',
    desc: 'BM25 + dense embedding hybrid retrieval with cross-encoder reranking resolves every action to the leaf-level Settings screen URI.',
  },
  {
    icon: IconFilter,
    title: 'Schema Validation',
    desc: 'Every compiled plan is validated against the Pydantic ContextDeeplinkResponse schema. Invalid actions are repaired or dropped — never surfaced.',
  },
  {
    icon: IconShieldCheck,
    title: 'Safety Constraints',
    desc: 'Factory Reset is blocked unless the plan has ≥3 preceding safe actions. No external URLs are ever injected into deeplinks.',
  },
  {
    icon: IconCheck,
    title: 'Deterministic Fallback',
    desc: 'Pure rule-based extraction (zero API calls, <50 ms) is always available. The engine gracefully degrades when Gemini is unavailable.',
  },
]

const pipelineSteps = [
  { num: '01', label: 'NORMALIZE' },
  { num: '02', label: 'CACHE' },
  { num: '03', label: 'ENRICH' },
  { num: '04', label: 'EXTRACT' },
  { num: '05', label: 'GROUND' },
  { num: '06', label: 'DEEPLINK' },
  { num: '07', label: 'VALIDATE' },
]

export function FeaturesPage() {
  return (
    <main className="features-page page-width">
      <div className="demo-heading">
        <div>
          <span className="section-kicker">SYSTEM ARCHITECTURE</span>
          <h1>Features &amp; <span style={{ color: '#92a8ff' }}>Architecture</span></h1>
        </div>
        <p>A 7-stage grounded pipeline from vague complaint to verified action.</p>
      </div>

      {/* Pipeline diagram */}
      <section style={{ marginBottom: 48 }}>
        <div className="pipeline-diagram">
          {pipelineSteps.map((step, i) => (
            <div key={step.num} style={{ display: 'flex', alignItems: 'center' }}>
              <div className="pipeline-step">
                <div className="pipeline-step-dot">{step.num}</div>
                <span>{step.label}</span>
              </div>
              {i < pipelineSteps.length - 1 && <span className="pipeline-arrow">→</span>}
            </div>
          ))}
        </div>
      </section>

      {/* Feature cards */}
      <div className="features-grid">
        {features.map(f => {
          const Icon = f.icon
          return (
            <article className="feature-card reveal" key={f.title}>
              <div className="feature-icon"><Icon size={22} stroke={1.6} /></div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </article>
          )
        })}
      </div>

      {/* Architecture note */}
      <section style={{ marginTop: 64, padding: '32px', border: '1px solid rgb(255 255 255 / 8%)', borderRadius: 14, background: 'linear-gradient(145deg, rgb(255 255 255 / 3%), rgb(255 255 255 / 1%))' }}>
        <span className="section-kicker">TRUST MODEL</span>
        <h2 style={{ margin: '13px 0 16px', fontSize: 'clamp(24px,3vw,34px)', fontWeight: 560, letterSpacing: '-0.05em' }}>
          LLM proposes. <span style={{ color: '#899fff' }}>Code disposes.</span>
        </h2>
        <p style={{ color: '#8b8b93', fontSize: 13, lineHeight: 1.85, maxWidth: 680, margin: '0 0 24px' }}>
          The AI is used only for semantic extraction — never for generating deeplinks or schema values.
          Every deeplink URI comes from the verified catalog. Every schema field is validated by Pydantic.
          Hallucination is structurally impossible for the output format.
        </p>
        <Link className="button-primary" to="/demo" style={{ display: 'inline-flex' }}>
          Try the live demo <span aria-hidden="true">→</span>
        </Link>
      </section>
    </main>
  )
}
