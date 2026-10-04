# Galaxy Resolve

> **Smart Guided Troubleshooting Engine for Samsung Galaxy Devices**  
> *Transforming vague user complaints into grounded, ordered, schema-compliant troubleshooting plans with direct Samsung Settings deeplinks.*

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-Passing%20(94%2F94)-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()

---

## Overview

When Galaxy device users encounter issues, their natural language descriptions are often vague or symptom-driven (*"My phone screen flickers after unlocking"*, *"Battery draining fast while playing games"*, *"Touch gestures going wrong direction"*). 

**Galaxy Resolve** is a high-performance troubleshooting engine that bridges the gap between natural language complaints and actionable device resolutions. Operating on the core architectural principle of **"LLM proposes, code disposes"**, it uses semantic extraction where understanding is needed, but enforces schema compliance, grounding, deeplink matching, and safety ordering through deterministic code.

### Core Highlights

* **Sub-300ms Fast Path**: SQLite vector cache with slot guards (domain, symptom, trigger) and Cross-Encoder borderline verification serves repeated and paraphrased queries in $< 30\text{ ms}$.
* **SIIS Store Auto-Matching**: When `siis_response` is omitted from API calls (e.g. custom user queries in web UI or tests), semantic vector similarity auto-selects the best-matching support article from the official dataset so custom queries work seamlessly.
* **Zero URL Leaks**: Deterministic URL scrubbers and catalog verifiers ensure exactly 0 external web links leak into output; all actionable links map strictly to the verified 578-entry catalog (`voiceassist://masked/act/...`).
* **100% Schema Conformance**: Validated against Pydantic schema contracts (`ContextDeeplinkResponse`), enforcing strict linguistic rules (goal phrasing, 2–3 word titles, 5–7 word descriptions starting with *"It will "*).
* **Viterbi Scraper Degluing**: Dynamic programming word segmentation automatically repairs concatenated text from scraped support articles (e.g. `enteryourcurrentpin,passwordorpattern`).
* **Topological Dependency Ordering**: Respects prerequisite dependency graphs (`data/dependencies.json`) and safety hierarchy (auto $\to$ manual $\to$ critical; restart $\to$ safe mode $\to$ software update $\to$ factory reset).
* **Cross-Domain Mismatch Protection**: Guards against irrelevant support articles (e.g. appliance manuals paired with phone queries) by returning `contexts: []` with `fallback: "no_match"`.
* **Zero-Node Embedded Dashboard**: A lightweight, modern dark-mode web console with a simulated Samsung Galaxy device frame served directly by FastAPI at `GET /` with live Server-Sent Events (SSE) streaming.

---

## System Architecture

```text
                        ┌──────────────────────────────────────┐
                        │      Incoming Complaint / Query      │
                        └──────────────────┬───────────────────┘
                                           │
                        ┌──────────────────▼───────────────────┐
                        │     Input Scrubbing & Slot Normalization
                        └──────────────────┬───────────────────┘
                                           │
                 ┌─────────────────────────┴─────────────────────────┐
                 ▼ (Fast Path < 30ms)                                ▼ (Cold Path)
      ┌───────────────────────┐                           ┌───────────────────────┐
      │  Vector + Slot Cache  │                           │ Mismatched SIIS Check │
      │  Exact & Cross-Encoder│                           │ (Reject Irrelevant)   │
      └──────────┬────────────┘                           └───────────┬───────────┘
                 │ (Hit)                                              │ (Pass)
                 │                                        ┌───────────▼───────────┐
                 │                                        │ Viterbi Word Degluer  │
                 │                                        └───────────┬───────────┘
                 │                                                    │
                 │                                        ┌───────────▼───────────┐
                 │                                        │ Extraction & Grounding│
                 │                                        │ (Gemini / Rules)      │
                 │                                        └───────────┬───────────┘
                 │                                                    │
                 │                                        ┌───────────▼───────────┐
                 │                                        │ Hybrid Deeplink Match │
                 │                                        │ BM25 + Dense + RRF    │
                 │                                        └───────────┬───────────┘
                 │                                                    │
                 │                                        ┌───────────▼───────────┐
                 │                                        │ Dependency Sort (DAG) │
                 │                                        │ & Severity Ranking    │
                 │                                        └───────────┬───────────┘
                 │                                                    │
                 │                                        ┌───────────▼───────────┐
                 │                                        │ Schema Validator      │
                 │                                        │ & Contract Compiler   │
                 │                                        └───────────┬───────────┘
                 │                                                    │
                 └─────────────────────────┬──────────────────────────┘
                                           │
                        ┌──────────────────▼───────────────────┐
                        │  Grounded ContextDeeplinkResponse    │
                        └──────────────────────────────────────┘
```

---

## Quick Start

### 1. Requirements
* Python 3.10 or higher
* Recommended: Virtual environment (`venv` or `conda`)

### 2. Setup
```bash
# Clone the repository
git clone https://github.com/Bhavy-official/Galaxy-Resolve.git
cd Galaxy-Resolve

# Install dependencies
pip install -r requirements.txt

# Build local vector and search indexes (one-time setup)
python scripts/build_index.py

# Prewarm the cache database with baseline kit queries
python scripts/prewarm.py
```

### 3. Run Server
```bash
python -m uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

* **Interactive Web Console**: Open [http://localhost:8000/](http://localhost:8000/) in your browser.
* **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
* **Metrics Dashboard**: [http://localhost:8000/v1/metrics](http://localhost:8000/v1/metrics)

---

## API Summary

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web UI with execution trace and simulated Galaxy device |
| `GET` | `/health` | Service readiness, models, catalog, and cache status |
| `POST` | `/v1/troubleshoot` | Official single-shot troubleshooting plan resolution |
| `POST` | `/v1/troubleshoot/stream` | Server-Sent Events (SSE) streaming reasoning trace |
| `GET` | `/v1/metrics` | Rolling 1,000-request operational latency & hit metrics |
| `GET` | `/v1/trace/{trace_id}` | Detailed execution trace lookup for a specific request |

For complete payload specifications and response schemas, see [API.md](API.md).

---

## Testing & Quality Assurance

Galaxy Resolve maintains an exhaustive automated test suite covering all critical path modules:

```bash
# Run the full test suite
python -m pytest tests/ -v
```

**Test Coverage Summary:**
* `tests/test_api_and_outputs.py`: REST contracts, schema validation, streaming events, and metrics.
* `tests/test_ordering.py`: Critical severity ranking and topological prerequisite resolution.
* `tests/test_deglue.py`: Viterbi word segmentation and punctuation spacing.
* `tests/test_mismatch.py`: Domain mismatch gating for cross-domain articles.
* `tests/test_deeplinks.py`: Verbatim catalog URI extraction and leaf specificity.
* `tests/test_engine.py`: End-to-end LLM execution, offline rules degradation, and slot guards.
* `tests/test_validators.py`: Word count bounds, "It will" prefix enforcement, and zero-URL scrubbing.

---

## Project Structure

```text
Galaxy-Resolve/
├── app/
│   ├── api.py               # FastAPI routes, SSE streaming, metrics window
│   ├── config.py            # Central configuration & environment variables
│   ├── embed.py             # SentenceTransformers & CrossEncoder local models
│   ├── engine.py            # Core pipeline orchestrator (fast/cold path)
│   ├── llm.py               # Google Gemini client with OpenAI-compatible fallback
│   ├── schema.py            # Official Pydantic response contract models
│   ├── siis_store.py        # SIIS knowledge store auto-matching for custom/omitted queries
│   ├── static/              # Embedded One UI visualizer console (HTML5/CSS3/JS)
│   ├── cache/               # SQLite vector store, slot guards, caching logic
│   └── pipeline/            # Extraction, grounding, degluing, ordering, deeplinks
├── data/
│   ├── deeplinks.json       # 578-entry Samsung settings deeplink catalog
│   ├── dependencies.json    # Prerequisite DAG edges for action ordering
│   └── siis_responses.json  # Reference support articles & benchmark queries
├── eval/                    # Evaluation harness and scoring scripts
├── scripts/
│   ├── build_index.py       # Catalog vector & BM25 index builder
│   └── prewarm.py           # Prewarm cache with diverse variations
├── tests/                   # Pytest test suite (94+ unit tests)
├── ARCHITECTURE.md          # In-depth architectural specification
├── HOW_TO_RUN.md            # Detailed setup, execution, and eval guide
└── API.md                   # Complete REST & SSE endpoint reference
```

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.
