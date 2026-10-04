import { useEffect, useState, useCallback } from 'react'

type MetricData = {
  total_requests: number
  cache_hit_rate: number
  latency_p50_ms: number
  latency_p95_ms: number
  avg_cost_usd: number
  recent_traces: TraceRecord[]
}

type TraceRecord = {
  id: string
  timestamp: number
  query: string
  latency_ms: number
  cache_hit: boolean
  model: string
  cost_usd: number
  fallback?: string
  actions_count: number
}

function fmt(n: number | undefined, decimals = 0) {
  if (n === undefined || n === null) return '—'
  return n.toFixed(decimals)
}

function timeAgo(ts: number) {
  const s = Math.floor(Date.now() / 1000 - ts)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

export function MetricsPage() {
  const [data, setData] = useState<MetricData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  const fetchMetrics = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/v1/metrics')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json: MetricData = await res.json()
      setData(json)
      setLastRefresh(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load metrics')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchMetrics() }, [fetchMetrics])

  const cards = data
    ? [
        { label: 'TOTAL REQUESTS', value: String(data.total_requests), sub: 'all time' },
        { label: 'CACHE HIT RATE', value: `${(data.cache_hit_rate * 100).toFixed(1)}%`, sub: 'last 1000 requests' },
        { label: 'P50 LATENCY', value: `${fmt(data.latency_p50_ms)}ms`, sub: 'median response time' },
        { label: 'P95 LATENCY', value: `${fmt(data.latency_p95_ms)}ms`, sub: '95th percentile' },
        { label: 'AVG COST', value: `$${fmt(data.avg_cost_usd, 5)}`, sub: 'per request (LLM)' },
        { label: 'RECENT TRACES', value: String(data.recent_traces.length), sub: 'shown below' },
      ]
    : []

  return (
    <main className="metrics-live-page page-width">
      <div className="demo-heading">
        <div>
          <span className="section-kicker">LIVE TELEMETRY</span>
          <h1>Metrics &amp; <span style={{ color: '#92a8ff' }}>Benchmarks</span></h1>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
          <button className="refresh-btn" onClick={() => void fetchMetrics()} disabled={loading}>
            {loading ? <><span className="button-spinner" style={{ borderTopColor: '#b2b4c0' }} /> Refreshing…</> : '↻ Refresh'}
          </button>
          {lastRefresh && <span style={{ color: '#5d5e67', fontSize: 9, fontFamily: 'var(--galaxy-mono)' }}>Last updated {lastRefresh.toLocaleTimeString()}</span>}
        </div>
      </div>

      {error && (
        <div className="phone-feedback feedback-error" style={{ marginBottom: 24 }}>
          {error} — Is the FastAPI server running on port 8000?
        </div>
      )}

      {!data && !loading && !error && (
        <div className="phone-feedback" style={{ marginBottom: 24 }}>Loading metrics from the API…</div>
      )}

      {data && (
        <>
          <div className="live-metrics-grid">
            {cards.map(c => (
              <div className="live-metric-card reveal" key={c.label}>
                <label>{c.label}</label>
                <strong>{c.value}</strong>
                <span>{c.sub}</span>
              </div>
            ))}
          </div>

          {data.recent_traces.length > 0 && (
            <div className="trace-list" style={{ marginTop: 40 }}>
              <div className="trace-list-header">
                <span>QUERY</span>
                <span>MODEL</span>
                <span>LATENCY</span>
                <span>CACHE</span>
                <span>ACTIONS</span>
              </div>
              {data.recent_traces.slice().reverse().map(t => (
                <div className="trace-list-row" key={t.id}>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.query}>
                    {t.query.length > 45 ? t.query.slice(0, 45) + '…' : t.query}
                    <span style={{ color: '#43444c', fontSize: 9, marginLeft: 6, fontFamily: 'var(--galaxy-mono)' }}>{timeAgo(t.timestamp)}</span>
                  </span>
                  <span style={{ color: '#77788', fontSize: 11, fontFamily: 'var(--galaxy-mono)' }}>{t.model || '—'}</span>
                  <span style={{ fontFamily: 'var(--galaxy-mono)', fontSize: 11 }}>{fmt(t.latency_ms)}ms</span>
                  <span>{t.cache_hit ? <span className="cache-hit-yes">HIT</span> : <span className="cache-hit-no">MISS</span>}</span>
                  <span style={{ fontFamily: 'var(--galaxy-mono)', fontSize: 11 }}>{t.actions_count}</span>
                </div>
              ))}
            </div>
          )}

          {data.total_requests === 0 && (
            <div className="phone-feedback" style={{ marginTop: 24 }}>
              No requests have been made yet. Try the <a href="/demo" style={{ color: '#8ea6ff' }}>live demo</a> first!
            </div>
          )}
        </>
      )}
    </main>
  )
}
