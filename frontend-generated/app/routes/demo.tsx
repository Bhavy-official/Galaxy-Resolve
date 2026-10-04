import {
  IconBattery2,
  IconCamera,
  IconDeviceMobile,
  IconGauge,
  IconSettings,
  IconShieldCheck,
} from "@tabler/icons-react";
import { useState } from "react";

import { GalaxyShell } from "@/components/galaxy-shell";
import { galaxyApiUrl } from "@/lib/galaxy-api";

type TraceStage = {
  name: string;
  status: "waiting" | "running" | "done";
  latency?: number | string;
  summary?: string;
};

type ActionResult = Record<string, unknown>;

type Scenario = {
  label: string;
  category: string;
  icon: typeof IconDeviceMobile;
  description: string;
  query: string;
};

const stageNames = [
  "Normalizing & Scrubbing URLs",
  "Cache Lookup",
  "Enriching Intent & Domain",
  "Extracting Steps from SIIS",
  "Grounding Verification",
  "Deeplink Catalog Resolution",
  "Compiling & Validating Schema",
  "Done",
];

const scenarios: Scenario[] = [
  {
    label: "Screen flickers after update",
    category: "Display",
    icon: IconDeviceMobile,
    description: "Standard display troubleshooting",
    query: "Screen flickers after update",
  },
  {
    label: "Battery drains fast when hot",
    category: "Battery",
    icon: IconBattery2,
    description: "Thermal and battery intent",
    query: "Battery drains fast when hot",
  },
  {
    label: "Camera blurry in low light",
    category: "Camera",
    icon: IconCamera,
    description: "Camera settings retrieval",
    query: "Camera blurry in low light",
  },
  {
    label: "Phone slow after update",
    category: "Performance",
    icon: IconGauge,
    description: "Performance domain routing",
    query: "Phone slow after update",
  },
  {
    label: "Swipe gestures wrong direction",
    category: "Multi-step",
    icon: IconDeviceMobile,
    description: "Multi-step intent grounding",
    query: "Swipe gestures wrong direction after app install",
  },
  {
    label: "Screen black AND battery drains",
    category: "Multi-intent",
    icon: IconBattery2,
    description: "Two independent device intents",
    query: "Screen black AND battery drains",
  },
  {
    label: "my fone iz ded cant trun on!!!",
    category: "Typo test",
    icon: IconDeviceMobile,
    description: "Noisy input and frustrated phrasing",
    query: "my fone iz ded cant trun on!!!",
  },
  {
    label: "Remove the floating circle",
    category: "Settings",
    icon: IconSettings,
    description: "Configuration intent resolution",
    query: "How do I remove the floating circle?",
  },
  {
    label: "No SIIS Context",
    category: "Fallback",
    icon: IconShieldCheck,
    description: "Empty article handling",
    query: "No SIIS Context",
  },
  {
    label: "Mismatched Article",
    category: "Safety",
    icon: IconShieldCheck,
    description: "Irrelevant context rejection",
    query: "Mismatched Article",
  },
  {
    label: "Repeated Query",
    category: "Cache",
    icon: IconGauge,
    description: "Run twice to check cache reuse",
    query: "Screen flickers after update",
  },
  {
    label: "Near-Miss Confusion",
    category: "Slot guard",
    icon: IconShieldCheck,
    description: "Black vs. cracked screen distinction",
    query: "screen cracked",
  },
];

function initialStages(): TraceStage[] {
  return stageNames.map((name) => ({ name, status: "waiting" }));
}

function stageIndex(value: string) {
  const stage = value.toLowerCase();
  if (stage.includes("normal") || stage.includes("scrub")) return 0;
  if (stage.includes("cache")) return 1;
  if (
    stage.includes("enrich") ||
    stage.includes("intent") ||
    stage.includes("domain")
  )
    return 2;
  if (stage.includes("extract") || stage.includes("siis")) return 3;
  if (stage.includes("ground") || stage.includes("verif")) return 4;
  if (
    stage.includes("deeplink") ||
    stage.includes("catalog") ||
    stage.includes("retriev")
  )
    return 5;
  if (
    stage.includes("compil") ||
    stage.includes("schema") ||
    stage.includes("valid")
  )
    return 6;
  if (
    stage.includes("done") ||
    stage.includes("complete") ||
    stage.includes("finish")
  )
    return 7;
  return -1;
}

function extractActions(data: unknown): ActionResult[] {
  if (!data || typeof data !== "object") return [];
  const record = data as Record<string, unknown>;
  const output = (record.result ??
    record.response ??
    record.plan ??
    record) as Record<string, unknown>;
  const actions =
    output && typeof output === "object"
      ? (output.actions ?? output.steps ?? output.troubleshooting_steps)
      : undefined;
  if (Array.isArray(actions))
    return actions.filter(
      (item): item is ActionResult => !!item && typeof item === "object",
    );
  return [];
}

function getMetadata(data: unknown) {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  if (record.metadata && typeof record.metadata === "object")
    return record.metadata;
  const keys = [
    "latency_ms",
    "cache_hit",
    "cache_tier",
    "model",
    "cost_usd",
    "fallback",
  ];
  if (keys.some((key) => key in record))
    return Object.fromEntries(keys.map((key) => [key, record[key] ?? null]));
  return null;
}

function stageSummary(payload: unknown) {
  if (typeof payload === "string") return payload;
  if (!payload || typeof payload !== "object") return "Stage event received";
  const data = payload as Record<string, unknown>;
  const summary = data.summary ?? data.message ?? data.detail ?? data.status;
  return typeof summary === "string" ? summary : "Stage event received";
}

function safeDeepLink(value: unknown) {
  if (typeof value !== "string" || !value.trim()) return undefined;
  if (/^(settings|samsung|intent):/i.test(value)) return value;
  try {
    const url = new URL(value, window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}

function resultName(action: ActionResult, index: number) {
  const value = action.name ?? action.title ?? action.action;
  return typeof value === "string"
    ? value
    : `Troubleshooting step ${index + 1}`;
}

function resultCategory(action: ActionResult) {
  const value = String(
    action.category ?? action.type ?? "manual",
  ).toLowerCase();
  if (value.includes("critical")) return "critical";
  if (value.includes("auto")) return "auto";
  return "manual";
}

function actionSteps(action: ActionResult) {
  const value = action.steps ?? action.instructions;
  if (Array.isArray(value))
    return value.map((step) =>
      typeof step === "string" ? step : JSON.stringify(step),
    );
  return typeof action.instruction === "string" ? [action.instruction] : [];
}

function ActionCard({
  action,
  index,
}: {
  action: ActionResult;
  index: number;
}) {
  const category = resultCategory(action);
  const description =
    typeof action.description === "string" ? action.description : "";
  const deepLink = safeDeepLink(
    action.deeplink ?? action.deep_link ?? action.url,
  );
  const steps = actionSteps(action);
  return (
    <article
      className="action-card"
      style={{ animationDelay: `${index * 90}ms` }}
    >
      <div className="action-card-heading">
        <h3>{resultName(action, index)}</h3>
        <span className={`category-badge badge-${category}`}>{category}</span>
      </div>
      {description && (
        <p className="action-description">
          {description.startsWith("It will")
            ? description
            : `It will ${description}`}
        </p>
      )}
      {steps.length > 0 && (
        <ol>
          {steps.map((step, stepIndex) => (
            <li key={`${stepIndex}-${step}`}>{step}</li>
          ))}
        </ol>
      )}
      {category === "auto" && deepLink && (
        <a
          className="setting-link"
          href={deepLink}
          target="_blank"
          rel="noreferrer"
        >
          Open setting <span>↗</span>
        </a>
      )}
    </article>
  );
}

function TracePanel({
  stages,
  lines,
  metadata,
  loading,
}: {
  stages: TraceStage[];
  lines: string[];
  metadata: unknown;
  loading: boolean;
}) {
  return (
    <aside className="trace-panel">
      <div className="trace-panel-header">
        <div>
          <span className="trace-overline">LIVE PIPELINE</span>
          <h2>Pipeline trace</h2>
        </div>
        <span className={`stream-indicator ${loading ? "streaming" : ""}`}>
          <i />
          {loading ? "Streaming" : "Ready"}
        </span>
      </div>
      <div className="trace-terminal" aria-live="polite">
        <div className="terminal-bar">
          <span />
          <span />
          <span />
          <small>galaxy-resolve / trace</small>
        </div>
        <div className="stage-list">
          {stages.map((stage, index) => (
            <div
              className={`trace-stage stage-${stage.status}`}
              key={stage.name}
            >
              <span className="stage-indicator">
                {stage.status === "done" ? (
                  "✓"
                ) : stage.status === "running" ? (
                  <i />
                ) : (
                  <b>{String(index + 1).padStart(2, "0")}</b>
                )}
              </span>
              <div className="stage-detail">
                <span>
                  {stage.name}
                  {stage.status === "running" ? "…" : ""}
                </span>
                {stage.summary && <small>{stage.summary}</small>}
              </div>
              {stage.latency !== undefined && (
                <span className="stage-latency">
                  {typeof stage.latency === "number"
                    ? `${stage.latency}ms`
                    : stage.latency}
                </span>
              )}
            </div>
          ))}
        </div>
        {lines.length > 0 && (
          <div className="trace-event-log">
            {lines.slice(-4).map((line, index) => (
              <div key={`${index}-${line}`}>
                <span>›</span> {line}
              </div>
            ))}
          </div>
        )}
        {!loading && lines.length === 0 && (
          <p className="terminal-empty">
            Submit an issue to inspect the live request trace.
          </p>
        )}
      </div>
      <details className="metadata-disclosure">
        <summary>
          <span>Response metadata</span>
          <span className="metadata-toggle">
            {metadata ? "View JSON" : "Waiting for response"}
          </span>
        </summary>
        {metadata ? (
          <pre>{JSON.stringify(metadata, null, 2)}</pre>
        ) : (
          <p>
            Latency, cache tier, model, and cost appear here after a response.
          </p>
        )}
      </details>
    </aside>
  );
}

function PhoneDemo({
  query,
  loading,
  actions,
  error,
  message,
}: {
  query: string;
  loading: boolean;
  actions: ActionResult[];
  error: string;
  message: string;
}) {
  return (
    <section
      className="phone-column"
      aria-label="Galaxy troubleshooting app preview"
    >
      <div className="phone-frame">
        <div className="phone-camera" />
        <div className="phone-screen">
          <div className="phone-status">
            <span>9:41</span>
            <span className="phone-status-icons">
              <IconDeviceMobile size={13} />
              <span className="signal-bars">
                <i />
                <i />
                <i />
                <i />
              </span>
              <span className="battery-icon">
                <i />
              </span>
            </span>
          </div>
          <div className="phone-app-header">
            <span className="app-symbol">
              <span />
            </span>
            <div>
              <strong>Galaxy Resolve</strong>
              <small>Device support</small>
            </div>
            <span className="header-menu">···</span>
          </div>
          <div className="phone-content">
            <div className="phone-greeting">
              <span className="phone-mini-label">GALAXY-RESOLVE / PLAN</span>
              <h2>{loading ? "Building your plan." : "Your guided fix."}</h2>
            </div>
            {query && (
              <div className="phone-issue-preview">
                <span>YOUR ISSUE</span>
                <p>{query}</p>
              </div>
            )}
            <div className="phone-result-heading">
              <span>YOUR PLAN</span>
              {actions.length > 0 && <span>{actions.length} ACTIONS</span>}
            </div>
            {error && (
              <div className="phone-feedback feedback-error" role="alert">
                {error}
              </div>
            )}
            {!error && message && (
              <div className="phone-feedback" role="status">
                {message}
              </div>
            )}
            {!error && loading && actions.length === 0 && (
              <div className="phone-processing" role="status">
                <span className="button-spinner" /> Grounding your next steps
              </div>
            )}
            {!error && !loading && actions.length === 0 && !message && (
              <div className="phone-empty">
                <span className="empty-orbit">
                  <IconDeviceMobile size={22} stroke={1.5} />
                </span>
                <p>Your generated troubleshooting steps will appear here.</p>
              </div>
            )}
            {actions.map((action, index) => (
              <ActionCard
                key={`${resultName(action, index)}-${index}`}
                action={action}
                index={index}
              />
            ))}
          </div>
          <div className="phone-home-indicator" />
        </div>
      </div>
      <div className="phone-caption">
        <span className="caption-dot" /> Live product preview
      </div>
    </section>
  );
}

function DemoControls({
  query,
  setQuery,
  onSubmit,
  loading,
}: {
  query: string;
  setQuery: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
}) {
  return (
    <section className="demo-controls" aria-label="Troubleshooting controls">
      <span className="section-kicker">DESCRIBE AN ISSUE</span>
      <label className="issue-label" htmlFor="issue-input">
        Galaxy device issue
      </label>
      <textarea
        id="issue-input"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Describe your Galaxy issue..."
        rows={3}
      />
      <button
        className="resolve-button"
        type="button"
        onClick={onSubmit}
        disabled={loading || !query.trim()}
      >
        {loading ? (
          <>
            <span className="button-spinner" /> Resolving
          </>
        ) : (
          <>
            Resolve issue <span>→</span>
          </>
        )}
      </button>
    </section>
  );
}

function ScenarioSection({
  onRun,
  loading,
}: {
  onRun: (scenario: Scenario) => void;
  loading: boolean;
}) {
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
        <div className="scenario-group">
          <span className="scenario-group-label">STANDARD</span>
          <div className="scenario-row">
            {scenarios.slice(0, 4).map((scenario) => (
              <ScenarioButton
                key={scenario.label}
                scenario={scenario}
                onChoose={() => onRun(scenario)}
                disabled={loading}
              />
            ))}
          </div>
        </div>
        <div className="scenario-group">
          <span className="scenario-group-label">EDGE CASES</span>
          <div className="scenario-row">
            {scenarios.slice(4, 8).map((scenario) => (
              <ScenarioButton
                key={scenario.label}
                scenario={scenario}
                onChoose={() => onRun(scenario)}
                disabled={loading}
              />
            ))}
          </div>
        </div>
        <div className="scenario-group">
          <span className="scenario-group-label">SAFETY & CACHE</span>
          <div className="scenario-row">
            {scenarios.slice(8).map((scenario) => (
              <ScenarioButton
                key={scenario.label}
                scenario={scenario}
                onChoose={() => onRun(scenario)}
                disabled={loading}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export function meta() {
  return [
    { title: "Live Demo — Galaxy-Resolve" },
    {
      name: "description",
      content:
        "Try grounded Galaxy troubleshooting and inspect the live pipeline trace.",
    },
  ];
}

export default function DemoRoute() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [actions, setActions] = useState<ActionResult[]>([]);
  const [stages, setStages] = useState<TraceStage[]>(initialStages);
  const [lines, setLines] = useState<string[]>([]);
  const [metadata, setMetadata] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const applyPayload = (payload: unknown) => {
    const nextActions = extractActions(payload);
    const nextMetadata = getMetadata(payload);
    if (nextActions.length > 0) setActions(nextActions);
    if (nextMetadata) setMetadata(nextMetadata);
    return nextActions.length;
  };

  let receivedActionCount = 0;
  const recordEvent = (eventBlock: string) => {
    const eventName = eventBlock
      .split("\n")
      .find((line) => line.startsWith("event:"))
      ?.slice(6)
      .trim();
    const dataText = eventBlock
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim())
      .join("\n");
    if (!dataText) return;
    let payload: unknown = dataText;
    try {
      payload = JSON.parse(dataText);
    } catch {
      /* Plain-text SSE events are valid. */
    }
    if (
      eventName &&
      payload &&
      typeof payload === "object" &&
      !Array.isArray(payload)
    ) {
      payload = { ...(payload as Record<string, unknown>), event: eventName };
    }
    const record =
      payload && typeof payload === "object"
        ? (payload as Record<string, unknown>)
        : {};
    const stageValue = String(
      record.stage ?? record.name ?? record.event ?? eventName ?? "",
    );
    const index = stageIndex(stageValue);
    const summary = stageSummary(payload);
    setLines((current) => [...current, summary]);
    if (index >= 0) {
      const isRunning =
        String(record.status ?? "")
          .toLowerCase()
          .includes("start") ||
        String(record.status ?? "")
          .toLowerCase()
          .includes("running");
      setStages((current) =>
        current.map((stage, stageNumber) =>
          stageNumber === index
            ? {
                ...stage,
                status: isRunning ? "running" : "done",
                latency: (record.latency_ms ?? record.latency) as
                  | number
                  | string
                  | undefined,
                summary,
              }
            : stage,
        ),
      );
    }
    if (Object.keys(record).length > 0)
      receivedActionCount = Math.max(receivedActionCount, applyPayload(record));
  };

  const submit = async (selectedQuery = query) => {
    const trimmed = selectedQuery.trim();
    if (!trimmed || loading) return;
    setQuery(trimmed);
    setLoading(true);
    setError("");
    setMessage("");
    setActions([]);
    setMetadata(null);
    setStages(initialStages());
    setLines([]);

    try {
      const response = await fetch(galaxyApiUrl("/v1/troubleshoot/stream"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream, application/json",
        },
        body: JSON.stringify({ query: trimmed }),
      });

      if (
        (response.status === 404 || response.status === 405) &&
        !response.ok
      ) {
        const standard = await fetch(galaxyApiUrl("/v1/troubleshoot"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({ query: trimmed }),
        });
        if (!standard.ok)
          throw new Error(`Troubleshooting API returned ${standard.status}.`);
        const payload = await standard.json();
        const actionCount = applyPayload(payload);
        if (actionCount === 0)
          setMessage(
            "The API responded, but did not return structured troubleshooting actions.",
          );
        setLines([
          "Streaming endpoint unavailable; standard request completed.",
        ]);
        return;
      }
      if (!response.ok)
        throw new Error(`Troubleshooting API returned ${response.status}.`);

      if (
        !response.headers.get("content-type")?.includes("text/event-stream")
      ) {
        const payload = await response.json();
        const actionCount = applyPayload(payload);
        if (actionCount === 0)
          setMessage(
            "The API responded, but did not return structured troubleshooting actions.",
          );
        setLines(["Response received from the troubleshooting API."]);
        return;
      }

      if (!response.body)
        throw new Error(
          "The streaming response did not include a readable body.",
        );
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const blocks = buffer.split(/\r?\n\r?\n/);
        buffer = blocks.pop() ?? "";
        blocks.forEach(recordEvent);
        if (done) break;
      }
      if (buffer.trim()) recordEvent(buffer);
      setStages((current) =>
        current.map((stage) =>
          stage.status === "running" ? { ...stage, status: "done" } : stage,
        ),
      );
      if (receivedActionCount === 0)
        setMessage(
          "Stream complete. Structured actions will appear here when returned by the API.",
        );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to reach the troubleshooting API.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <GalaxyShell>
      <main className="demo-page page-width">
        <div className="demo-heading">
          <div>
            <span className="section-kicker">INTERACTIVE SYSTEM DEMO</span>
            <h1>
              From issue to <span>action.</span>
            </h1>
          </div>
          <p>
            Describe a Galaxy issue. Follow the grounded pipeline as it
            resolves.
          </p>
        </div>
        <div className="demo-workbench">
          <div className="demo-left-column">
            <DemoControls
              query={query}
              setQuery={setQuery}
              onSubmit={() => void submit()}
              loading={loading}
            />
            <ScenarioSection
              onRun={(scenario) => void submit(scenario.query)}
              loading={loading}
            />
            <TracePanel
              stages={stages}
              lines={lines}
              metadata={metadata}
              loading={loading}
            />
          </div>
          <PhoneDemo
            query={query}
            loading={loading}
            actions={actions}
            error={error}
            message={message}
          />
        </div>
      </main>
    </GalaxyShell>
  );
}

function ScenarioButton({
  scenario,
  onChoose,
  disabled,
}: {
  scenario: Scenario;
  onChoose: () => void;
  disabled: boolean;
}) {
  const Icon = scenario.icon;
  return (
    <button
      className="scenario-button"
      type="button"
      title={scenario.description}
      onClick={onChoose}
      disabled={disabled}
    >
      <Icon size={15} stroke={1.7} />
      <span>{scenario.label}</span>
      <small>{scenario.category}</small>
    </button>
  );
}
