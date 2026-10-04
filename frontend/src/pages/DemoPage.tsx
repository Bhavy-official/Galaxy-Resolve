import { useState } from 'react'
import {
  IconDeviceMobile,
  IconBattery2,
  IconCamera,
  IconGauge,
  IconSettings,
  IconShieldCheck,
  IconFileAlert,
} from '@tabler/icons-react'

// ─── Types ─────────────────────────────────────────────────────────────────

type TraceStage = {
  name: string
  status: 'waiting' | 'running' | 'done'
  latency?: number | string
  summary?: string
}

// Exact schema from Theme 2/schema.py
type ActionableDeeplink = { deeplink: string; description?: string; message?: string }
type ValidationDeeplink = { deeplink: string; key: string; resultType?: string; condition?: string; value?: string }
type StepGroup = {
  steps: string[]
  actionableDeeplink?: ActionableDeeplink | null
  validationDeeplink?: ValidationDeeplink | null
}
type Action = {
  actionName: string
  description: string
  stepGroups: StepGroup[]
  category?: 'auto' | 'manual' | 'critical'
}
type Goal = { goal: string; title: string; actions: Action[]; score: number }
type TroubleshootResult = {
  contexts: Goal[]
  meta?: {
    latency_ms?: number
    cache_hit?: boolean
    model?: string
    cost_usd?: number
    fallback?: string
    trace_id?: string
  }
}

// siis_response is OPTIONAL per Theme 2 spec.
// Frontend sends only {query}. Backend auto-matches the right SIIS article
// from Theme 2/siis_responses.json using semantic similarity.
// If scorer passes explicit siis_response, backend uses that directly.
type Scenario = {
  label: string
  category: string
  icon: typeof IconDeviceMobile
  description: string
  query: string
}

// ─── Official Scenarios — exactly from Theme 2/input.txt ──────────────────

const scenarios: Scenario[] = [
  {
    label: 'Screen flashes → blank (Gmail)',
    category: 'Display', icon: IconDeviceMobile,
    description: 'Tablet screen flashes and goes blank opening email',
    query: 'My TechCorp A15G tablet screen flashes and then goes completely blank whenever I tap to open an email in Gmail, and after it works for a short time it goes blank again.',
  },
  {
    label: 'Blank screen — stock / Quick Assist',
    category: 'Display', icon: IconDeviceMobile,
    description: 'Screen goes blank/white on app usage',
    query: "My Nexa X1 screen turns completely blank or white and no text appears when I search for a stock price or use the Quick Assist app, and it happens with other apps too.",
  },
  {
    label: 'Black screen + Data Transfer blocked',
    category: 'Display', icon: IconFileAlert,
    description: 'Screen black, cannot do data transfer',
    query: "My Nexa Fold X1 screen went completely black, so I can't see or interact with the phone, and I'm unable to use Data Transfer or any other method to transfer my data.",
  },
  {
    label: 'Screen black after one month',
    category: 'Display', icon: IconDeviceMobile,
    description: 'Spontaneous screen failure after a month',
    query: "My TechCorp Nexa A14/A15 screen suddenly went completely black on its own after about a month of use. It doesn't display anything, even when I try to turn it on.",
  },
  {
    label: 'Blank screen — QR scan fails',
    category: 'Display', icon: IconFileAlert,
    description: 'Data Transfer QR code blocked by blank screen',
    query: "My tablet screen stays completely blank when I try to use Data Transfer to scan the QR code for transferring data from my Nexa X1 phone, so the transfer can't proceed.",
  },
  {
    label: 'Screen dark, 3 icons lit only',
    category: 'Display', icon: IconDeviceMobile,
    description: 'Mostly dark screen with partial icons',
    query: "My tablet's screen stays dark and only three app icons are lit while the rest are dark and won't open, so nothing loads on the screen and I can't use the device.",
  },
  {
    label: "Screen doesn't fill display",
    category: 'Display', icon: IconSettings,
    description: 'Screen too small / not full-screen',
    query: "My new smartphone's main screen stays small and doesn't fill the whole display; I can't make it expand to full size and I've never seen this before.",
  },
  {
    label: 'Fold inner screen dead',
    category: 'Display', icon: IconDeviceMobile,
    description: 'Inner foldable screen stopped working',
    query: "My Nexa Fold X1 inner screen stopped working by itself; it shows no image and doesn't respond to touch, while the outer cover screen still works.",
  },
  {
    label: 'Fold screen flickers when opened',
    category: 'Display', icon: IconDeviceMobile,
    description: 'Flicker and blank on fold open',
    query: "My TechCorp Nexa Fold X1 screen flickers and goes blank whenever I open it, so I can't see anything or access the settings, which stops me from using the phone.",
  },
  {
    label: 'Fold screen half black',
    category: 'Display', icon: IconFileAlert,
    description: 'One side of foldable display is dark',
    query: "My Nexa Fold X1 screen is half black—one side of the display is completely dark while the other side works fine, so I can't access the device normally.",
  },
  {
    label: 'Remove floating circle',
    category: 'Settings', icon: IconSettings,
    description: 'Assistive menu / floating ball removal',
    query: "My Nexa X1 has a floating circle that constantly hovers on my screen and gives me quick shortcuts to recent apps, home, back, screen off, volume control, and more; I want to remove it.",
  },
  {
    label: 'Blank after carrier deactivation',
    category: 'Display', icon: IconShieldCheck,
    description: 'Screen blank post carrier deactivation',
    query: "My Nexa X1 screen stays blank and doesn't show any activation message or anything else when I turn it on after the carrier deactivated the old phone.",
  },
  {
    label: 'Totally cracked screen',
    category: 'Hardware', icon: IconFileAlert,
    description: 'Complete screen crack — device unusable',
    query: "My smartphone's screen is completely cracked, it's a total crack and I can't use the device.",
  },
  {
    label: 'Blue/black screen with text on boot',
    category: 'Display', icon: IconDeviceMobile,
    description: 'Boot failure / blue screen of death',
    query: "My Nexa X1 Ultra only shows a blue (or black) screen with tiny text when I try to turn it on, and it won't start up. I tried holding the power button but it doesn't help.",
  },
  {
    label: 'Screen flashes when charging',
    category: 'Display', icon: IconBattery2,
    description: 'Display flicker when plugging in charger',
    query: "My TechCorp X1 Ultra screen flashes extremely quickly (in milliseconds) whenever I plug in a charger, making the display unusable for a short period.",
  },
  {
    label: 'Blank + can\'t use Data Transfer',
    category: 'Display', icon: IconFileAlert,
    description: 'Dark screen with scrolling, data stuck',
    query: '1. "My Nexa X1 screen goes completely blank, just a dark screen with occasional scrolling and no visible content, so I can\'t see anything or use Data Transfer to transfer data."',
  },
  {
    label: 'Multi-issue: crack + touch + dim',
    category: 'Multi-intent', icon: IconFileAlert,
    description: 'Three simultaneous fold screen issues',
    query: '1. "My Nexa Fold X1 screen is cracked again right where it folds." 2. "The touch doesn\'t work on certain parts of the screen." 3. "I can hardly see anything on the display."',
  },
  {
    label: 'Screen distorted on new phone',
    category: 'Display', icon: IconCamera,
    description: 'Display distortion needing diagnostic',
    query: "My Nexa A14 screen looks distorted right after I received the phone, and I need a diagnostic test.",
  },
  {
    label: 'Touch inputs delayed / laggy',
    category: 'Performance', icon: IconGauge,
    description: 'Touch responsiveness and input lag',
    query: "My Nexa X1 screen inputs are delayed and the touch responsiveness is laggy, causing a noticeable delay when I try to interact with the phone.",
  },
  {
    label: 'Screen black — phone still works',
    category: 'Display', icon: IconDeviceMobile,
    description: 'Black screen but phone rings and works',
    query: "My Nexa X1 Ultra screen is completely black and won't turn on, even though the phone powers on, rings, and otherwise works; there is no physical damage.",
  },
]

// ─── Pipeline stages ─────────────────────────────────────────────────────────

const STAGE_NAMES = [
  'Normalizing & Scrubbing Input',
  'Cache Lookup',
  'SIIS Knowledge Matching',
  'Enriching Intent & Domain',
  'Extracting Steps from SIIS',
  'Grounding Verification',
  'Deeplink Catalog Resolution',
  'Compiling & Validating Schema',
]

function stageIndex(value: string): number {
  const s = value.toLowerCase()
  if (s.includes('normal') || s.includes('scrub')) return 0
  if (s.includes('cache')) return 1
  if (s.includes('siis') && s.includes('match')) return 2
  if (s.includes('enrich') || s.includes('intent') || s.includes('domain')) return 3
  if (s.includes('extract') || s.includes('siis')) return 4
  if (s.includes('ground') || s.includes('verif')) return 5
  if (s.includes('deeplink') || s.includes('catalog') || s.includes('retriev')) return 6
  if (s.includes('compil') || s.includes('schema') || s.includes('valid') || s.includes('done') || s.includes('complete')) return 7
  return -1
}

function initialStages(): TraceStage[] {
  return STAGE_NAMES.map(name => ({ name, status: 'waiting' as const }))
}

// ─── Action Card ─────────────────────────────────────────────────────────────

function ActionCard({ action, index }: { action: Action; index: number }) {
  const category = action.category || 'manual'
  const allSteps = action.stepGroups.flatMap(sg => sg.steps)
  const deeplink = action.stepGroups.find(sg => sg.actionableDeeplink?.deeplink)?.actionableDeeplink?.deeplink

  return (
    <article className="action-card" style={{ animationDelay: `${index * 90}ms` }}>
      <div className="action-card-heading">
        <h3>{action.actionName}</h3>
        <span className={`category-badge badge-${category}`}>{category}</span>
      </div>
      {action.description && (
        <p className="action-description">
          {action.description.startsWith('It will') ? action.description : `It will ${action.description}`}
        </p>
      )}
      {allSteps.length > 0 && (
        <ol>{allSteps.map((step, i) => <li key={i}>{step}</li>)}</ol>
      )}
      {deeplink && (
        <a
          className="setting-link"
          href={deeplink}
          target="_blank"
          rel="noreferrer"
          onClick={e => { e.preventDefault(); alert(`Deep link: ${deeplink}`) }}
        >
          Open setting ↗
        </a>
      )}
    </article>
  )
}

// ─── Phone Preview ────────────────────────────────────────────────────────────

function PhoneDemo({
  query, loading, goals, error, message,
}: {
  query: string
  loading: boolean
  goals: Goal[]
  error: string
  message: string
}) {
  const allActions = goals.flatMap(g => g.actions)

  return (
    <section className="phone-column" aria-label="Galaxy troubleshooting app preview">
      <div className="phone-frame">
        <div className="phone-camera" />
        <div className="phone-screen">
          <div className="phone-status">
            <span>9:41</span>
            <span className="phone-status-icons">
              <IconDeviceMobile size={13} />
              <span className="signal-bars"><i /><i /><i /><i /></span>
              <span className="battery-icon"><i /></span>
            </span>
          </div>
          <div className="phone-app-header">
            <span className="app-symbol"><span /></span>
            <div>
              <strong>Galaxy Resolve</strong>
              <small>Device support</small>
            </div>
            <span className="header-menu">···</span>
          </div>
          <div className="phone-content">
            <div className="phone-greeting">
              <span className="phone-mini-label">GALAXY-RESOLVE / PLAN</span>
              <h2>{loading ? 'Building your plan.' : 'Your guided fix.'}</h2>
            </div>
            {query && (
              <div className="phone-issue-preview">
                <span>YOUR ISSUE</span>
                <p>{query}</p>
              </div>
            )}
            <div className="phone-result-heading">
              <span>YOUR PLAN</span>
              {allActions.length > 0 && <span>{allActions.length} ACTIONS</span>}
            </div>
            {error && <div className="phone-feedback feedback-error" role="alert">{error}</div>}
            {!error && message && <div className="phone-feedback" role="status">{message}</div>}
            {!error && loading && allActions.length === 0 && (
              <div className="phone-processing" role="status">
                <span className="button-spinner" /> Grounding your next steps
              </div>
            )}
            {!error && !loading && allActions.length === 0 && !message && (
              <div className="phone-empty">
                <span className="empty-orbit"><IconDeviceMobile size={22} stroke={1.5} /></span>
                <p>Your generated troubleshooting steps will appear here.</p>
              </div>
            )}
            {allActions.map((action, i) => (
              <ActionCard key={`${action.actionName}-${i}`} action={action} index={i} />
            ))}
          </div>
          <div className="phone-home-indicator" />
        </div>
      </div>
      <div className="phone-caption">
        <span className="caption-dot" /> Live product preview
      </div>
    </section>
  )
}

// ─── Trace Panel ─────────────────────────────────────────────────────────────

function TracePanel({
  stages, lines, metadata, loading,
}: {
  stages: TraceStage[]
  lines: string[]
  metadata: TroubleshootResult['meta'] | null
  loading: boolean
}) {
  return (
    <aside className="trace-panel">
      <div className="trace-panel-header">
        <div>
          <span className="trace-overline">LIVE PIPELINE</span>
          <h2>Pipeline trace</h2>
        </div>
        <span className={`stream-indicator ${loading ? 'streaming' : ''}`}>
          <span className="stream-dot" />
          {loading ? 'Streaming' : 'Ready'}
        </span>
      </div>
      <div className="trace-terminal" aria-live="polite">
        <div className="terminal-bar">
          <span /><span /><span />
          <small>galaxy-resolve / trace</small>
        </div>
        <div className="stage-list">
          {stages.map((stage, i) => (
            <div className={`trace-stage stage-${stage.status}`} key={stage.name}>
              <span className="stage-indicator">
                {stage.status === 'done'
                  ? '✓'
                  : stage.status === 'running'
                  ? <span className="stage-spin" />
                  : <b>{String(i + 1).padStart(2, '0')}</b>}
              </span>
              <div className="stage-detail">
                <span>{stage.name}{stage.status === 'running' ? '…' : ''}</span>
                {stage.summary && <small>{stage.summary}</small>}
              </div>
              {stage.latency !== undefined && (
                <span className="stage-latency">
                  {typeof stage.latency === 'number' ? `${stage.latency}ms` : stage.latency}
                </span>
              )}
            </div>
          ))}
        </div>
        {lines.length > 0 && (
          <div className="trace-event-log">
            {lines.slice(-4).map((line, i) => <div key={i}><span>›</span> {line}</div>)}
          </div>
        )}
        {!loading && lines.length === 0 && (
          <p className="terminal-empty">Submit an issue to inspect the live request trace.</p>
        )}
      </div>
      <details className="metadata-disclosure">
        <summary>
          <span>Response metadata</span>
          <span className="metadata-toggle">{metadata ? 'View JSON' : 'Waiting for response'}</span>
        </summary>
        {metadata
          ? <pre>{JSON.stringify(metadata, null, 2)}</pre>
          : <p>Latency, cache tier, model, and cost appear here after a response.</p>}
      </details>
    </aside>
  )
}

// ─── Scenario Section ─────────────────────────────────────────────────────────

function ScenarioSection({ onRun, loading }: { onRun: (s: Scenario) => void; loading: boolean }) {
  const groups = [
    { label: 'OFFICIAL QUERIES 1–8', items: scenarios.slice(0, 8) },
    { label: 'OFFICIAL QUERIES 9–16', items: scenarios.slice(8, 16) },
    { label: 'OFFICIAL QUERIES 17–20', items: scenarios.slice(16) },
  ]
  return (
    <section className="scenario-section">
      <div className="scenario-heading">
        <div>
          <span className="section-kicker">QUICK TESTS</span>
          <h2>Try an official query</h2>
        </div>
        <p>All 20 queries from the Theme 2 evaluation set. Backend auto-matches the SIIS article.</p>
      </div>
      <div className="scenario-groups">
        {groups.map(g => (
          <div className="scenario-group" key={g.label}>
            <span className="scenario-group-label">{g.label}</span>
            <div className="scenario-row">
              {g.items.map(s => {
                const Icon = s.icon
                return (
                  <button
                    key={s.label}
                    className="scenario-button"
                    type="button"
                    title={s.description}
                    onClick={() => onRun(s)}
                    disabled={loading}
                  >
                    <Icon size={15} stroke={1.7} />
                    <span>{s.label}</span>
                    <small>{s.category}</small>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

// ─── Main Demo Page ───────────────────────────────────────────────────────────

export function DemoPage() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [goals, setGoals] = useState<Goal[]>([])
  const [stages, setStages] = useState<TraceStage[]>(initialStages)
  const [lines, setLines] = useState<string[]>([])
  const [metadata, setMetadata] = useState<TroubleshootResult['meta'] | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const applyResult = (result: TroubleshootResult) => {
    if (result.contexts?.length) setGoals(result.contexts)
    if (result.meta) setMetadata(result.meta)
    return result.contexts?.flatMap(g => g.actions).length ?? 0
  }

  const recordSSEEvent = (block: string, actionCount: { n: number }) => {
    const dataText = block
      .split('\n')
      .filter(l => l.startsWith('data:'))
      .map(l => l.slice(5).trim())
      .join('\n')
    if (!dataText) return
    let payload: unknown = dataText
    try { payload = JSON.parse(dataText) } catch { /* plain text ok */ }

    const record = payload && typeof payload === 'object' ? payload as Record<string, unknown> : {}
    const stageVal = String(record.stage ?? record.name ?? record.event ?? '')
    const summary = typeof (record.summary ?? record.message ?? record.detail) === 'string'
      ? String(record.summary ?? record.message ?? record.detail)
      : typeof payload === 'string' ? payload : 'Stage event received'

    setLines(cur => [...cur, summary])

    const idx = stageIndex(stageVal)
    if (idx >= 0) {
      const isRunning = String(record.status ?? '').toLowerCase().includes('start')
        || String(record.status ?? '').toLowerCase().includes('running')
      setStages(cur => cur.map((s, i) =>
        i === idx ? { ...s, status: isRunning ? 'running' : 'done', summary, latency: record.latency_ms as number | undefined } : s
      ))
    }

    if (stageVal.includes('complete') || stageVal.includes('done')) {
      const result = record.result as TroubleshootResult | undefined
      if (result?.contexts) actionCount.n = Math.max(actionCount.n, applyResult(result))
    }
    if (record.contexts) {
      actionCount.n = Math.max(actionCount.n, applyResult(record as unknown as TroubleshootResult))
    }
  }

  // Per Theme 2 spec: siis_response is OPTIONAL in the API contract.
  // Frontend intentionally omits it — backend auto-matches the right
  // SIIS article from siis_responses.json via semantic similarity.
  // Scorer evaluation path: scorer passes explicit siis_response → backend uses it directly.
  const submit = async (selectedQuery = query) => {
    const trimmed = selectedQuery.trim()
    if (!trimmed || loading) return
    setQuery(trimmed)
    setLoading(true)
    setError('')
    setMessage('')
    setGoals([])
    setMetadata(null)
    setStages(initialStages())
    setLines([])

    // Only send query — siis_response handled server-side
    const body = JSON.stringify({ query: trimmed })

    try {
      const res = await fetch('/v1/troubleshoot/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream, application/json' },
        body,
      })

      // Fallback to non-stream endpoint if SSE not available
      if (!res.ok || !res.headers.get('content-type')?.includes('text/event-stream')) {
        const fallback = await fetch('/v1/troubleshoot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body,
        })
        if (!fallback.ok) throw new Error(`API returned ${fallback.status}`)
        const data: TroubleshootResult = await fallback.json()
        const n = applyResult(data)
        if (n === 0) {
          const reason = data.meta?.fallback
          setMessage(
            reason === 'no_siis_context'
              ? 'No matching knowledge article found for this query. Try one of the official scenarios below.'
              : reason === 'no_match'
              ? 'Engine found an article but could not ground actions for this query.'
              : 'API responded but returned no structured actions.'
          )
        }
        setLines(['Response received from troubleshooting API.'])
        return
      }

      if (!res.body) throw new Error('No readable body in streaming response.')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      const actionCount = { n: 0 }
      let lastMeta: TroubleshootResult['meta'] | null = null

      while (true) {
        const { value, done } = await reader.read()
        buffer += decoder.decode(value, { stream: !done })
        const blocks = buffer.split(/\r?\n\r?\n/)
        buffer = blocks.pop() ?? ''
        blocks.forEach(b => {
          const dataLine = b.split('\n').find(l => l.startsWith('data:'))
          if (dataLine) {
            try {
              const parsed = JSON.parse(dataLine.slice(5).trim()) as Record<string, unknown>
              if (parsed.stage === 'completed' && parsed.result) {
                lastMeta = (parsed.result as TroubleshootResult).meta ?? null
              }
            } catch { /* ignore */ }
          }
          recordSSEEvent(b, actionCount)
        })
        if (done) break
      }
      if (buffer.trim()) recordSSEEvent(buffer, { n: 0 })

      setStages(cur => cur.map(s => s.status === 'running' ? { ...s, status: 'done' } : s))
      if (actionCount.n === 0) {
        const reason = lastMeta?.fallback
        setMessage(
          reason === 'no_siis_context'
            ? 'No matching knowledge article found. Try one of the 20 official scenarios below.'
            : reason === 'no_match'
            ? 'Engine found an article but could not ground actions for this query.'
            : 'Stream complete — try one of the official test queries above.'
        )
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to reach the troubleshooting API.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="demo-page page-width">
      <div className="demo-heading">
        <div>
          <span className="section-kicker">INTERACTIVE SYSTEM DEMO</span>
          <h1>From issue to <span>action.</span></h1>
        </div>
        <p>Describe a Galaxy device issue. The engine auto-matches the right knowledge article and resolves it end-to-end.</p>
      </div>
      <div className="demo-workbench">
        <div className="demo-left-column">
          <section className="demo-controls" aria-label="Troubleshooting controls">
            <span className="section-kicker">DESCRIBE AN ISSUE</span>
            <label className="issue-label" htmlFor="issue-input">Galaxy device issue</label>
            <textarea
              id="issue-input"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Describe your Galaxy device issue in your own words..."
              rows={3}
              onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void submit() }}
            />
            <button
              className="resolve-button"
              type="button"
              onClick={() => void submit()}
              disabled={loading || !query.trim()}
            >
              {loading
                ? <><span className="button-spinner" /> Resolving</>
                : <>Resolve issue <span>→</span></>}
            </button>
          </section>

          <ScenarioSection onRun={s => void submit(s.query)} loading={loading} />
          <TracePanel stages={stages} lines={lines} metadata={metadata} loading={loading} />
        </div>

        <PhoneDemo query={query} loading={loading} goals={goals} error={error} message={message} />
      </div>
    </main>
  )
}
