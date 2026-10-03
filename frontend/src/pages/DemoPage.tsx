import { useState } from 'react'
import {
  IconBattery2,
  IconCamera,
  IconDeviceMobile,
  IconGauge,
  IconSettings,
  IconShieldCheck,
} from '@tabler/icons-react'

// ─── Types ─────────────────────────────────────────────────────────────────

type TraceStage = {
  name: string
  status: 'waiting' | 'running' | 'done'
  latency?: number | string
  summary?: string
}

// Exact schema from app/schema.py
type ActionableDeeplink = { deeplink: string; description?: string }
type StepGroup = { steps: string[]; actionableDeeplink?: ActionableDeeplink }
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
    cache_tier?: string
    model?: string
    cost_usd?: number
    fallback?: string
    trace_id?: string
  }
}

type Scenario = { label: string; category: string; icon: typeof IconDeviceMobile; description: string; query: string; siis?: string }

// ─── Bundled SIIS snippets (Samsung-style support articles) ─────────────────

const SIIS_BATTERY = `Battery Life Optimization — Samsung Galaxy
If your Galaxy device battery drains quickly, especially during gaming or when the phone feels warm, follow these steps:
1. Open Settings and tap Battery and Device Care.
2. Tap Battery, then select Power saving mode to reduce background usage.
3. Go back and tap Background usage limits. Enable Put unused apps to sleep.
4. Go to Settings > Display and lower Screen brightness or enable Adaptive brightness.
5. Tap Screen timeout and set it to 30 seconds or less.
6. Go to Settings > Location and switch to Battery saving mode.
7. Open Device Care and tap Optimize Now to clear cache and background processes.`

const SIIS_DISPLAY = `Screen Flickering After Software Update — Samsung Galaxy
If your screen flickers or shows display issues after a software update:
1. Restart your device by holding the Power button and selecting Restart.
2. Go to Settings > Display and turn off Motion smoothness or set it to Standard.
3. Open Settings > Display > Screen mode and select Natural or Basic.
4. Go to Settings > Accessibility > Visibility enhancements and disable Flash notifications.
5. Clear the system cache: Power off the device, then boot into Recovery Mode by holding Volume Up + Power. Select Wipe cache partition.
6. If flickering persists, go to Settings > General management > Reset > Reset all settings.`

const SIIS_CAMERA = `Camera Blurry in Low Light — Samsung Galaxy
To fix blurry photos taken in low-light conditions:
1. Open the Camera app and tap the Settings gear icon.
2. Under Shooting methods, enable Shooting methods > Voice commands or Timer to stabilise shots.
3. Tap Scene optimizer and make sure it is turned On.
4. Switch to Night mode by swiping to More in the camera modes list, then select Night.
5. Tap the ISO setting and select Auto or a lower ISO value to reduce grain.
6. Go to Settings > Apps > Camera > Storage and clear cache to fix any corruption.
7. For consistent sharpness, wipe the rear camera lens gently with a microfibre cloth.`

const SIIS_PERF = `Phone Running Slow After Update — Samsung Galaxy
If your Galaxy phone feels sluggish after a software update:
1. Go to Settings > Battery and Device Care and tap Optimize Now.
2. Tap Memory and then Clean Now to free RAM.
3. Go to Settings > Apps, sort by size, and uninstall or disable unused apps.
4. Open Settings > General management > Reset > Reset all settings (this preserves your data).
5. Go to Settings > Developer options and set Window animation scale, Transition animation scale, and Animator duration scale all to 0.5x.
6. Restart the phone in Safe Mode (hold Power, then long-press Power off) to check if a third-party app is the cause.`

const SIIS_GESTURE = `Swipe Gestures Wrong Direction — Samsung Galaxy
If navigation gestures feel reversed or unresponsive after installing an app:
1. Go to Settings > Display > Navigation bar.
2. Make sure Swipe gestures is selected (not Button navigation).
3. Tap Swipe options and toggle Swipe from sides and bottom.
4. Under Gesture hints, enable Show button to hide keyboard to confirm gestures are active.
5. If an app overrides gestures, go to Settings > Display > Navigation bar > Gesture conflict apps and disable the conflicting app.
6. Restart your device to apply changes.`

const SIIS_FLOATING = `Remove the Floating Circle (One-handed mode ball) — Samsung Galaxy
The floating circle (assistive touch ball) appears when One-handed mode or Assistive Touch is enabled:
1. Go to Settings > Advanced features > One-handed mode.
2. Toggle One-handed mode off.
3. If the circle persists, go to Settings > Accessibility > Interaction and dexterity > Assistive menu.
4. Turn off Assistive menu.
5. Restart your device to ensure the overlay is cleared.`

const SIIS_DEAD = `Phone Won't Turn On — Samsung Galaxy
If your Galaxy phone is unresponsive and will not turn on:
1. Press and hold the Power button and Volume Down button simultaneously for 10 seconds to force restart.
2. Connect the phone to the original charger and wait 15 minutes before trying again.
3. If no charging indicator appears, try a different cable and adapter.
4. Boot into Recovery Mode (hold Volume Up + Power) and select Wipe cache partition.
5. If the device still doesn't respond, visit a Samsung Service Centre for a battery or hardware check.`

const SIIS_MISMATCHED = `How to Set Up Samsung Pay — Samsung Galaxy
Samsung Pay lets you make contactless payments using your Galaxy device:
1. Open the Samsung Pay app.
2. Sign in with your Samsung account.
3. Tap Add card and scan or enter your credit or debit card details.
4. Complete bank verification via SMS or call.
5. To pay, swipe up from the bottom of the screen anywhere and hold near the payment terminal.`

// ─── Scenarios ──────────────────────────────────────────────────────────────

const scenarios: Scenario[] = [
  { label: 'Screen flickers after update', category: 'Display', icon: IconDeviceMobile, description: 'Standard display troubleshooting', query: 'Screen flickers after update', siis: SIIS_DISPLAY },
  { label: 'Battery drains fast when hot', category: 'Battery', icon: IconBattery2, description: 'Thermal and battery intent', query: 'Battery drains fast when hot', siis: SIIS_BATTERY },
  { label: 'Camera blurry in low light', category: 'Camera', icon: IconCamera, description: 'Camera settings retrieval', query: 'Camera blurry in low light', siis: SIIS_CAMERA },
  { label: 'Phone slow after update', category: 'Performance', icon: IconGauge, description: 'Performance domain routing', query: 'Phone slow after update', siis: SIIS_PERF },
  { label: 'Swipe gestures wrong direction', category: 'Multi-step', icon: IconDeviceMobile, description: 'Multi-step intent grounding', query: 'Swipe gestures wrong direction after app install', siis: SIIS_GESTURE },
  { label: 'Screen black AND battery drains', category: 'Multi-intent', icon: IconBattery2, description: 'Two independent device intents', query: 'Screen black AND battery drains', siis: SIIS_BATTERY },
  { label: 'my fone iz ded cant trun on!!!', category: 'Typo test', icon: IconDeviceMobile, description: 'Noisy input and frustrated phrasing', query: 'my fone iz ded cant trun on!!!', siis: SIIS_DEAD },
  { label: 'Remove the floating circle', category: 'Settings', icon: IconSettings, description: 'Configuration intent resolution', query: 'How do I remove the floating circle?', siis: SIIS_FLOATING },
  { label: 'No SIIS Context', category: 'Fallback', icon: IconShieldCheck, description: 'Empty article handling — expects fallback', query: 'Battery drains fast', siis: '' },
  { label: 'Mismatched Article', category: 'Safety', icon: IconShieldCheck, description: 'Irrelevant context rejection', query: 'Battery drains fast when hot', siis: SIIS_MISMATCHED },
  { label: 'Repeated Query (cache)', category: 'Cache', icon: IconGauge, description: 'Run twice to check cache reuse', query: 'Screen flickers after update', siis: SIIS_DISPLAY },
  { label: 'Near-Miss Confusion', category: 'Slot guard', icon: IconShieldCheck, description: 'Black vs. cracked screen distinction', query: 'screen cracked', siis: SIIS_DISPLAY },
]

// ─── Pipeline stages ─────────────────────────────────────────────────────────

const STAGE_NAMES = [
  'Normalizing & Scrubbing URLs',
  'Cache Lookup',
  'Enriching Intent & Domain',
  'Extracting Steps from SIIS',
  'Grounding Verification',
  'Deeplink Catalog Resolution',
  'Compiling & Validating Schema',
  'Done',
]

function stageIndex(value: string): number {
  const s = value.toLowerCase()
  if (s.includes('normal') || s.includes('scrub')) return 0
  if (s.includes('cache')) return 1
  if (s.includes('enrich') || s.includes('intent') || s.includes('domain')) return 2
  if (s.includes('extract') || s.includes('siis')) return 3
  if (s.includes('ground') || s.includes('verif')) return 4
  if (s.includes('deeplink') || s.includes('catalog') || s.includes('retriev')) return 5
  if (s.includes('compil') || s.includes('schema') || s.includes('valid')) return 6
  if (s.includes('done') || s.includes('complete') || s.includes('finish')) return 7
  return -1
}

function initialStages(): TraceStage[] {
  return STAGE_NAMES.map(name => ({ name, status: 'waiting' }))
}

// ─── Action Card ─────────────────────────────────────────────────────────────

function ActionCard({ action, index }: { action: Action; index: number }) {
  const category = action.category || 'manual'
  // Flatten steps from stepGroups
  const allSteps = action.stepGroups.flatMap(sg => sg.steps)
  // Get first valid deeplink from stepGroups
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
          onClick={e => { e.preventDefault(); alert(`Simulated deep link: ${deeplink}`) }}
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
                {stage.status === 'done' ? '✓' : stage.status === 'running' ? <span className="stage-spin" /> : <b>{String(i + 1).padStart(2, '0')}</b>}
              </span>
              <div className="stage-detail">
                <span>{stage.name}{stage.status === 'running' ? '…' : ''}</span>
                {stage.summary && <small>{stage.summary}</small>}
              </div>
              {stage.latency !== undefined && (
                <span className="stage-latency">{typeof stage.latency === 'number' ? `${stage.latency}ms` : stage.latency}</span>
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
    { label: 'STANDARD', items: scenarios.slice(0, 4) },
    { label: 'EDGE CASES', items: scenarios.slice(4, 8) },
    { label: 'SAFETY & CACHE', items: scenarios.slice(8) },
  ]
  return (
    <section className="scenario-section">
      <div className="scenario-heading">
        <div>
          <span className="section-kicker">QUICK TESTS</span>
          <h2>Try a scenario</h2>
        </div>
        <p>Run a ready-made test in the Galaxy preview.</p>
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

// ─── Keyword-based SIIS auto-matcher ─────────────────────────────────────────

const SIIS_CATALOG: Array<{ keywords: string[]; article: string; label: string }> = [
  { keywords: ['battery', 'drain', 'charge', 'power', 'thermal', 'hot', 'heat', 'warm'], article: SIIS_BATTERY, label: 'Battery & Power' },
  { keywords: ['screen', 'flicker', 'display', 'blank', 'black', 'bright', 'dim', 'blink', 'refresh'], article: SIIS_DISPLAY, label: 'Display & Screen' },
  { keywords: ['camera', 'photo', 'blurry', 'blur', 'dark', 'low light', 'picture', 'focus', 'lens'], article: SIIS_CAMERA, label: 'Camera' },
  { keywords: ['slow', 'lag', 'performance', 'sluggish', 'freeze', 'hang', 'ram', 'memory', 'speed'], article: SIIS_PERF, label: 'Performance' },
  { keywords: ['swipe', 'gesture', 'navigation', 'gesture bar', 'back gesture'], article: SIIS_GESTURE, label: 'Gestures & Navigation' },
  { keywords: ['floating', 'circle', 'ball', 'assistive', 'one-hand', 'one hand', 'bubble'], article: SIIS_FLOATING, label: 'Floating Circle / Assistive Touch' },
  { keywords: ['dead', 'wont turn', "won't turn", 'not turning', 'not on', "can't turn", 'cant turn', 'unresponsive', 'boot', 'ded', 'fone'], article: SIIS_DEAD, label: "Phone Won't Turn On" },
]

function autoMatchSiis(q: string): { article: string; label: string } | null {
  const lower = q.toLowerCase()
  let bestScore = 0
  let bestMatch: { article: string; label: string } | null = null
  for (const entry of SIIS_CATALOG) {
    const score = entry.keywords.filter(k => lower.includes(k)).length
    if (score > bestScore) { bestScore = score; bestMatch = entry }
  }
  return bestScore > 0 ? bestMatch : null
}

// ─── Main Demo Page ───────────────────────────────────────────────────────────

export function DemoPage() {
  const [query, setQuery] = useState('')
  const [siis, setSiis] = useState('')
  const [autoSiisLabel, setAutoSiisLabel] = useState<string | null>(null)
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
      const isRunning = String(record.status ?? '').toLowerCase().includes('start') || String(record.status ?? '').toLowerCase().includes('running')
      setStages(cur => cur.map((s, i) => i === idx ? { ...s, status: isRunning ? 'running' : 'done', summary, latency: record.latency_ms as number | undefined } : s))
    }

    // If it's the completed event with result data
    if (stageVal.includes('complete') || stageVal.includes('done')) {
      const result = record.result as TroubleshootResult | undefined
      if (result?.contexts) {
        actionCount.n = Math.max(actionCount.n, applyResult(result))
      }
    }
    // Also try direct parse if result is inline
    if (record.contexts) {
      actionCount.n = Math.max(actionCount.n, applyResult(record as unknown as TroubleshootResult))
    }
  }

  const submit = async (selectedQuery = query, selectedSiis = siis) => {
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

    // Auto-match a SIIS article when the user typed a custom query without providing one
    let effectiveSiis = selectedSiis.trim()
    if (!effectiveSiis) {
      const match = autoMatchSiis(trimmed)
      if (match) {
        effectiveSiis = match.article
        setSiis(match.article)
        setAutoSiisLabel(match.label)
      } else {
        setAutoSiisLabel(null)
      }
    } else {
      setAutoSiisLabel(null)
    }

    const siisPayload = effectiveSiis ? { content: effectiveSiis } : null

    try {
      const res = await fetch('/v1/troubleshoot/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream, application/json' },
        body: JSON.stringify({ query: trimmed, siis_response: siisPayload }),
      })

      // Fallback to non-stream endpoint
      if (!res.ok || !res.headers.get('content-type')?.includes('text/event-stream')) {
        const fallback = await fetch('/v1/troubleshoot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: trimmed, siis_response: siisPayload }),
        })
        if (!fallback.ok) throw new Error(`API returned ${fallback.status}`)
        const data: TroubleshootResult = await fallback.json()
        const n = applyResult(data)
        if (n === 0) {
          const reason = data.meta?.fallback
          setMessage(reason === 'no_siis_context'
            ? 'No SIIS article provided — paste a Samsung Support article in the context box.'
            : reason === 'no_match'
            ? 'Engine could not ground actions from the provided article for this query.'
            : 'API responded but returned no structured actions.')
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
          // Capture meta from completed event before recordSSEEvent
          const dataLine = b.split('\n').find(l => l.startsWith('data:'))
          if (dataLine) {
            try {
              const parsed = JSON.parse(dataLine.slice(5).trim()) as Record<string, unknown>
              if (parsed.stage === 'completed' && parsed.result) {
                const r = parsed.result as TroubleshootResult
                lastMeta = r.meta ?? null
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
        setMessage(reason === 'no_siis_context'
          ? 'No SIIS article provided — paste a Samsung Support article in the context box below.'
          : reason === 'no_match'
          ? 'Engine could not ground actions from the provided article for this query.'
          : 'Stream complete — no actions matched. Try adding or changing the context article.')
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
        <p>Describe a Galaxy issue. Follow the grounded pipeline as it resolves.</p>
      </div>
      <div className="demo-workbench">
        <div className="demo-left-column">
          {/* Input controls */}
          <section className="demo-controls" aria-label="Troubleshooting controls">
            <span className="section-kicker">DESCRIBE AN ISSUE</span>
            <label className="issue-label" htmlFor="issue-input">Galaxy device issue</label>
            <textarea
              id="issue-input"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Describe your Galaxy issue..."
              rows={3}
              onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void submit() }}
            />
            <details style={{ marginTop: '10px' }}>
              <summary style={{ fontSize: '12px', color: 'var(--color-muted, #8fa3b8)', cursor: 'pointer', userSelect: 'none', marginBottom: '6px' }}>
                SIIS Context Article
                {autoSiisLabel
                  ? <span style={{ marginLeft: '6px', color: '#34d399', fontWeight: 600 }}>✓ Auto-matched: {autoSiisLabel}</span>
                  : <span style={{ opacity: 0.6 }}> (auto-matched from query, or paste your own)</span>
                }
              </summary>
              <textarea
                id="siis-input"
                value={siis}
                onChange={e => { setSiis(e.target.value); setAutoSiisLabel(null) }}
                placeholder="Paste a Samsung Support article here... or type a query and the engine will auto-match one."
                rows={5}
                style={{ marginTop: '6px', fontSize: '12px', opacity: 0.85 }}
              />
            </details>
            <button
              className="resolve-button"
              type="button"
              onClick={() => void submit()}
              disabled={loading || !query.trim()}
            >
              {loading ? <><span className="button-spinner" /> Resolving</> : <>Resolve issue <span>→</span></>}
            </button>
          </section>

          <ScenarioSection onRun={s => { setSiis(s.siis ?? ''); void submit(s.query, s.siis ?? '') }} loading={loading} />
          <TracePanel stages={stages} lines={lines} metadata={metadata} loading={loading} />
        </div>

        <PhoneDemo query={query} loading={loading} goals={goals} error={error} message={message} />
      </div>
    </main>
  )
}
