# Galaxy Resolve — API Specification

This document provides the complete API reference for the **Galaxy Resolve** service.

* **Base URL:** `http://localhost:8000`
* **Default Port:** `8000`
* **Content-Type:** `application/json` (except `/` which serves `text/html` and `/v1/troubleshoot/stream` which serves `text/event-stream`)

---

## 1. Endpoints Overview

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Embedded interactive One UI visualizer console |
| `GET` | `/health` | Service health, readiness, and subsystem status |
| `POST` | `/v1/troubleshoot` | Official single-shot troubleshooting plan generator |
| `POST` | `/v1/troubleshoot/stream` | Server-Sent Events (SSE) streaming reasoning trace |
| `GET` | `/v1/metrics` | Rolling operational performance metrics (P50/P95 latency, hit rate) |
| `GET` | `/v1/trace/{trace_id}` | Detailed execution trace lookup for a specific request |

---

## 2. Health & Readiness

### `GET /health`
Returns `HTTP 200` when all local embedding models, Cross-Encoders, catalog indexes, and cache layers are ready to serve queries. Returns `HTTP 503` during startup or warm-up.

#### Response (`HTTP 200 OK`)
```json
{
  "status": "ok",
  "models": true,
  "catalog": true,
  "cache": true,
  "cached_plans": 20,
  "llm": true,
  "total_requests": 42
}
```

---

## 3. Troubleshooting Endpoints

### `POST /v1/troubleshoot`
The core single-shot troubleshooting endpoint. Accepts a user query and optional Samsung Support (SIIS) context, returning a grounded, ordered, schema-validated plan.

#### Request Headers
```http
Content-Type: application/json
```

#### Request Body
```json
{
  "query": "My phone screen flickers after unlocking",
  "siis_response": {
    "title": "Screen Flickering and Display Issues",
    "content": "To adjust screen refresh rate, navigate to Settings, tap Display, then tap Motion smoothness. Select Standard..."
  }
}
```
*Note: `siis_response` can also be provided as a plain text string.*

#### Response Body (`HTTP 200 OK`)
Conforms strictly to `ContextDeeplinkResponse`:

```json
{
  "contexts": [
    {
      "goal": "Follow these steps to perform this Screen Refresh Rate Configuration",
      "title": "Screen refresh rate",
      "score": 0.95,
      "actions": [
        {
          "actionName": "Motion Smoothness Settings",
          "description": "It will change the screen refresh rate",
          "category": "auto",
          "stepGroups": [
            {
              "steps": [
                "Navigate to Settings.",
                "Tap Display.",
                "Tap Motion smoothness."
              ],
              "actionableDeeplink": {
                "deeplink": "voiceassist://masked/act/aa73a35e8d",
                "description": "Opens Motion smoothness settings page in device Settings.",
                "message": "View Motion Smoothness",
                "originalType": "onClickURL"
              },
              "validationDeeplink": {
                "deeplink": "voiceassist://masked/val/ef6814259a",
                "key": "Motion smoothness",
                "resultType": "str",
                "condition": "equal",
                "value": "Standard"
              }
            }
          ]
        },
        {
          "actionName": "Restart Phone",
          "description": "It will restart your mobile device now",
          "category": "critical",
          "stepGroups": [
            {
              "steps": [
                "Press and hold the Power button.",
                "Tap Restart."
              ],
              "actionableDeeplink": null,
              "validationDeeplink": null
            }
          ]
        }
      ]
    }
  ],
  "meta": {
    "latency_ms": 14.2,
    "cache_hit": true,
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "cost_usd": 0.0,
    "fallback": null,
    "trace_id": "a9b1c2d3"
  }
}
```

---

### `POST /v1/troubleshoot/stream`
Emits real-time pipeline execution progress via Server-Sent Events (SSE). Useful for visualizer dashboards and progress indicators.

#### Request Headers
```http
Content-Type: application/json
Accept: text/event-stream
```

#### Event Format
Each message is emitted as `data: <json>\n\n`:

```text
data: {"stage": "normalize", "message": "Normalizing query & extracting slots..."}

data: {"stage": "llm_enrich", "message": "Enriching problem domain & title..."}

data: {"stage": "grounding", "message": "Verifying sentence grounding from context..."}

data: {"stage": "deeplink_catalog", "message": "Matching target settings to catalog URIs..."}

data: {"stage": "completed", "result": { ... full ContextDeeplinkResponse ... }}
```

*(On a cache hit, emits `{"stage": "cache_hit", "message": "Sub-300ms Cache Hit! Serving cached plan."}` and completes immediately).*

---

## 4. Observability & Metrics Endpoints

### `GET /v1/metrics`
Returns rolling operational statistics calculated over the most recent 1,000 requests.

#### Response (`HTTP 200 OK`)
```json
{
  "total_requests": 150,
  "cache_hit_rate": 0.8267,
  "latency_p50_ms": 16.4,
  "latency_p95_ms": 284.1,
  "avg_cost_usd": 0.000124,
  "recent_traces": [
    {
      "id": "a9b1c2d3",
      "timestamp": 1727715000.12,
      "query": "Battery draining fast when playing games",
      "latency_ms": 14.2,
      "cache_hit": true,
      "model": "sentence-transformers/all-MiniLM-L6-v2",
      "cost_usd": 0.0,
      "fallback": null,
      "actions_count": 2
    }
  ]
}
```

---

### `GET /v1/trace/{trace_id}`
Retrieves detailed metadata for a specific request by its 8-character trace ID.

#### Response (`HTTP 200 OK`)
```json
{
  "id": "a9b1c2d3",
  "timestamp": 1727715000.12,
  "query": "Battery draining fast when playing games",
  "latency_ms": 14.2,
  "cache_hit": true,
  "model": "sentence-transformers/all-MiniLM-L6-v2",
  "cost_usd": 0.0,
  "fallback": null,
  "actions_count": 2
}
```

#### Error Response (`HTTP 404 Not Found`)
```json
{
  "error": "trace not found"
}
```

---

## 5. Web Console

### `GET /`
Serves the self-contained HTML5/CSS3/JavaScript console at `app/static/index.html`. 
Provides an execution trace log and a simulated Galaxy One UI smartphone preview that visually executes `voiceassist://` deep links with interactive toast feedback.
