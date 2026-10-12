<div align="center">

<br>

# HOW TO RUN — GALAXY RESOLVE

### Complete Setup, Execution, and Evaluation Guide

*Step-by-step instructions for local development, web console, CLI testing, automated evaluation, and Docker deployment.*

<br>

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React%2019-Vite-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![Tests](https://img.shields.io/badge/Tests-101%2F101%20Passing-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](tests/)

<br>

---

### Project Resources

| Resource | Link |
|---|---|
| Presentation Slide Deck | [SRM_Code_Brewers.pdf](submission/SRM_Code_Brewers.pdf) |
| Video Demonstration | [Project — Demo Video](https://drive.google.com/drive/folders/1mToZ4nGpqT2vQEok5F9KYxQHxP25UocI?usp=sharing) |
| Project Overview | [README.md](README.md) |
| System Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| API Reference | [API.md](API.md) |

---

</div>

## Table of Contents

1. [System Prerequisites](#1-system-prerequisites)
2. [Environment Setup and Installation](#2-environment-setup-and-installation)
3. [Configuration and Environment Variables](#3-configuration-and-environment-variables)
4. [Building Indexes and Prewarming Cache](#4-building-indexes-and-prewarming-cache)
5. [Starting the Application Server](#5-starting-the-application-server)
6. [Interactive Web Console](#6-interactive-web-console)
7. [Running the Frontend in Development Mode](#7-running-the-frontend-in-development-mode)
8. [CLI Demo and Quick Testing](#8-cli-demo-and-quick-testing)
9. [Automated Test Suite](#9-automated-test-suite)
10. [Running the Benchmark Evaluation Harness](#10-running-the-benchmark-evaluation-harness)
11. [Docker Deployment](#11-docker-deployment)
12. [Frequently Asked Questions](#12-frequently-asked-questions)

---

## 1. System Prerequisites

Verify that your environment satisfies the following requirements before proceeding:

| Requirement | Minimum | Notes |
|---|---|---|
| **Operating System** | Windows 10/11, macOS, or Linux | Ubuntu 20.04+ recommended for Linux |
| **Python** | 3.10 or 3.11 | Newer versions may work but are not tested |
| **RAM** | 8 GB | Accommodates local SentenceTransformers and Cross-Encoder models |
| **Disk Space** | ~1.5 GB free | For Python dependencies and Hugging Face model cache |
| **Node.js** | 18+ (optional) | Required only for modifying frontend source code |

---

## 2. Environment Setup and Installation

### Step 2.1: Clone the Repository
```bash
git clone https://github.com/Bhavy-official/Galaxy-Resolve.git
cd Galaxy-Resolve
```

### Step 2.2: Create and Activate a Virtual Environment
```bash
# Windows — PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Windows — Command Prompt
python -m venv .venv
.\.venv\Scripts\activate.bat

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2.3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note:** The first installation downloads local Hugging Face models (`all-MiniLM-L6-v2`, `ms-marco-MiniLM-L-6-v2`, `stsb-distilroberta-base`). This may take several minutes on first run. Subsequent startups use the cached models and are fast.

---

## 3. Configuration and Environment Variables

Copy the example configuration file and edit it with your settings:

```bash
cp .env.example .env
```

Open `.env` and configure the following variables:

```ini
# ── LLM Configuration ──────────────────────────────────────────────────────
# Google Gemini API Key — get a free key at https://aistudio.google.com/apikey
# No credit card required. Leave blank to run in fully offline rules mode.
GEMINI_API_KEY=your_gemini_api_key_here

# Pipeline execution mode:
#   auto   = Use Gemini when API key is present; fall back to offline rules automatically
#   rules  = Pure deterministic offline mode (zero API calls, ultra-fast, no key needed)
#   llm    = Require LLM for all cold-path extraction
PIPELINE_MODE=auto

# ── Model Settings ──────────────────────────────────────────────────────────
LLM_MODEL=gemini-2.5-flash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_TIMEOUT_S=10.0
LLM_MAX_RETRIES=1
```

> **Offline Resilience:** If `GEMINI_API_KEY` is not provided or if the network is unavailable, Galaxy Resolve operates completely offline using its deterministic rule engine (`PIPELINE_MODE=rules`). All tests and prewarmed queries execute with full success in this mode.

---

## 4. Building Indexes and Prewarming Cache

These one-time setup steps must be completed before running the server for the first time.

### Step 4.1: Build Catalog Indexes

Generates dense vector embeddings and BM25 lexical indexes for all 578 verified Samsung Settings deeplinks:

```bash
python scripts/build_index.py
```

*Output: Index files written to `data/index/`. Takes approximately 30–60 seconds on first run.*

### Step 4.2: Prewarm the Cache Database

Populates `cache.sqlite3` with precomputed plans and natural language variations for all 20 official benchmark scenarios:

```bash
python scripts/prewarm.py
```

*Output: `cache.sqlite3` is populated with 20+ base plans and 100+ query variations, ensuring sub-30ms response times from the first request.*

---

## 5. Starting the Application Server

Start the FastAPI server with Uvicorn:

```bash
python -m uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

On startup, the server loads the following in sequence:

1. SentenceTransformers dense encoder (`all-MiniLM-L6-v2`)
2. Cross-Encoder reranker models (`ms-marco-MiniLM-L-6-v2`, `stsb-distilroberta-base`)
3. 578-entry deeplink catalog index
4. SIIS Knowledge Store (official benchmark support articles)
5. SQLite vector cache

### Confirm Service Readiness

```bash
curl http://localhost:8000/health
```

**Expected response (`200 OK`):**
```json
{
  "status": "ok",
  "models": true,
  "catalog": true,
  "cache": true,
  "cached_plans": 20,
  "llm": true,
  "total_requests": 0
}
```

| Service | URL |
|---|---|
| Interactive Web Console | http://localhost:8000/ |
| Health Check | http://localhost:8000/health |
| Metrics Dashboard | http://localhost:8000/v1/metrics |

---

## 6. Interactive Web Console

Open a browser and navigate to **http://localhost:8000/**

### Available Pages

**Demo Page (`/demo`)**
- Enter any natural language device complaint (e.g., *"Screen flickers after unlock"*, *"Audio not coming from speaker"*).
- Click any of the **20 official benchmark scenario buttons** to instantly load a test query.
- Watch live pipeline reasoning via Server-Sent Events — each stage streams in real time.
- View the structured troubleshooting plan rendered inside a virtual Samsung Galaxy smartphone frame.
- Expand the **"Response metadata"** panel to inspect raw JSON: latency, model tier, cache status, cost, and token counts.

**Metrics Page (`/metrics`)**
- Rolling request statistics: total requests, cache hit rate, P50 latency, P95 latency, estimated USD cost.
- Recent execution trace history with clickable trace IDs for per-request deep inspection.

**Features Page (`/features`)**
- Visual breakdown of all seven pipeline stages with capability descriptions.

---

## 7. Running the Frontend in Development Mode

> **Note:** This step is only needed if you are developing or modifying the React UI source code. The FastAPI server at `http://localhost:8000/` already serves the compiled production React SPA automatically — no separate frontend server is required for normal use.

```bash
cd frontend
npm install
npm run dev
```

The Vite development server starts at `http://localhost:5173/` and proxies all API calls to `http://localhost:8000`.

To rebuild production assets after making changes:

```bash
cd frontend
npm run build
```

*Compiled output is written to `app/static/dist/`, which FastAPI serves automatically.*

---

## 8. CLI Demo and Quick Testing

Test the engine directly from the terminal using `demo.py`:

```bash
# Run the first official benchmark query
python demo.py

# Run a specific benchmark query by index (0-indexed)
python demo.py 3

# Run with a completely custom user query
python demo.py --query "screen flickers when unlocked"

# Run with a specific query index and verbose output
python demo.py 0 --verbose
```

The CLI outputs a formatted troubleshooting plan, pipeline latency breakdown, model tier, cache status, and token usage.

---

## 9. Automated Test Suite

Galaxy Resolve maintains **101 automated tests** covering all critical modules:

```bash
# Run the complete test suite with verbose output
python -m pytest tests/ -v
```

### Running Specific Test Modules

```bash
# REST API endpoints, SSE streaming, and schema validation
python -m pytest tests/test_api_and_outputs.py -v

# Topological DAG ordering and safety hierarchy
python -m pytest tests/test_ordering.py -v

# Deeplink catalog matching and leaf specificity
python -m pytest tests/test_deeplinks.py -v

# Viterbi word segmentation degluer
python -m pytest tests/test_deglue.py -v

# Cross-domain mismatch detection gate
python -m pytest tests/test_mismatch.py -v

# End-to-end engine execution and slot guards
python -m pytest tests/test_engine.py -v

# Pydantic schema validation and zero-URL scrubbers
python -m pytest tests/test_validators.py -v
```

### Expected Output

```
============================== 101 passed in 12.34s ==============================
```

---

## 10. Running the Benchmark Evaluation Harness

Run the automated evaluation across all 20 official Theme 2 test cases:

```bash
python eval/run_eval.py
```

Output includes per-scenario scores, aggregate precision/recall metrics, and a summary report written to `results.jsonl`.

### Threshold Auto-Tuning

Sweep and optimize cosine similarity, borderline thresholds, and BM25 candidate sizes:

```bash
python eval/run_eval.py --tune
```

*Optimized values are written to `thresholds.json` and automatically applied on subsequent runs.*

---

## 11. Docker Deployment

Build and run Galaxy Resolve as a Docker container:

```bash
# Build the Docker image
docker build -t galaxy-resolve .

# Run on port 8000 (pass your API key as an environment variable)
docker run -p 8000:8000 -e GEMINI_API_KEY="your_key_here" galaxy-resolve

# Run in offline rules mode (no API key required)
docker run -p 8000:8000 -e PIPELINE_MODE="rules" galaxy-resolve
```

Access the application at `http://localhost:8000/`.

---

## 12. Frequently Asked Questions

**Q: Why do I see `fallback: "no_match"` in the response?**

This occurs when the provided reference article is completely unrelated to the user complaint — for example, an appliance manual paired with a Galaxy phone screen query. The Cross-Domain Mismatch Shield rejects the article to prevent hallucinated actions from reaching the user.

**Q: Can Galaxy Resolve run without an internet connection?**

Yes. Set `PIPELINE_MODE=rules` in `.env`. The system uses local SentenceTransformers models, local Cross-Encoders, the SQLite cache, and deterministic parsing — no external API calls are made.

**Q: Where can I view response metadata and execution traces?**

On the `/demo` web page, expand the **"Response metadata"** panel below the terminal log to view raw JSON including latency, model tier, cache status, and cost. You can also query `GET /v1/metrics` or look up a specific request with `GET /v1/trace/{trace_id}`.

**Q: What models does Galaxy Resolve use locally?**

The following Hugging Face models are downloaded automatically on first startup:
- `sentence-transformers/all-MiniLM-L6-v2` — dense embedding encoder for query and catalog vectorization
- `cross-encoder/ms-marco-MiniLM-L-6-v2` — Cross-Encoder reranker for deeplink matching
- `cross-encoder/stsb-distilroberta-base` — Cross-Encoder for borderline cache verification

**Q: How long does the initial setup take?**

Model downloads take 2–5 minutes depending on internet speed. Index building takes approximately 30–60 seconds. All subsequent server starts are fast (under 10 seconds).

---

<div align="center">

For architectural deep-dives, see **[ARCHITECTURE.md](ARCHITECTURE.md)**.
For API schema references, see **[API.md](API.md)**.
For the project overview, see **[README.md](README.md)**.

</div>