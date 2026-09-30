# How to Run Galaxy Resolve

This guide provides practical, step-by-step instructions for installing, configuring, indexing, running, and evaluating the **Galaxy Resolve** troubleshooting engine.

---

## 1. Prerequisites & Environment Setup

* **Python:** Version `3.10` or higher
* **Git:** Installed and available in PATH
* **Hardware:** Modern multi-core CPU (8GB+ RAM recommended for local embedding models)

### Create Virtual Environment
```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 2. Configuration & API Keys

Create a `.env` file in the project root (or copy from `.env.example`):

```ini
# Google Gemini API Key (Required for LLM mode)
GEMINI_API_KEY=your_actual_gemini_api_key_here

# Pipeline mode:
# 'auto'   = Use Gemini LLM when API key exists, otherwise fall back to deterministic rules
# 'rules'  = Pure deterministic offline rules mode (zero API calls, ultra-fast)
# 'llm'    = Require LLM for cold path extraction
PIPELINE_MODE=auto

# Optional overrides (default paths and models)
LLM_MODEL=gemini-3.8-flash
HIT_THRESHOLD=0.80
BORDERLINE_LOW=0.68
CE_HIT_THRESHOLD=0.62
SLOT_GUARD=1
```

> **Note:** If `GEMINI_API_KEY` is not provided or if network fails, Galaxy Resolve automatically falls back to its deterministic rule engine (`rules_extract` + `rules_enrich`).

---

## 3. Build Indexes & Prewarm Cache

Before starting the server for the first time, build the local search indexes and prewarm the cache database.

### Step 3.1: Build Catalog Indexes
Builds the BM25 index and computes dense embeddings for the 578 catalog deeplinks using `sentence-transformers/all-MiniLM-L6-v2`:
```bash
python scripts/build_index.py
```
*Creates vector and keyword index files in `data/index/`.*

### Step 3.2: Prewarm the Cache
Populates `cache.sqlite3` with precomputed plans and high-coverage paraphrases for baseline support queries:
```bash
python scripts/prewarm.py
```
*Creates `cache.sqlite3` and writes baseline solutions to `results.jsonl`.*

---

## 4. Running the Application

### Start the FastAPI Server
```bash
python -m uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

When started, the service will load the local embedding models, Cross-Encoders, catalog index, and SQLite cache into memory.

### Verify Health Status
Once booted, verify the service readiness:
```bash
curl http://localhost:8000/health
```
**Expected Response:**
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

---

## 5. Using the User Interface

Open your web browser and navigate to:
👉 **[http://localhost:8000/](http://localhost:8000/)**

The embedded dark-mode console features:
1. **Query Input:** Enter natural language Galaxy complaints (e.g. *"My battery drains fast when playing games"*).
2. **SIIS Support Text (Optional):** Paste or supply official Samsung Support article content.
3. **Real-Time Execution Trace (SSE):** Displays live stages (`normalize`, `cache_hit` / `llm_enrich`, `grounding`, `deeplink_catalog`, `completed`).
4. **Interactive Galaxy Phone Frame:** Renders the resulting plan inside a simulated One UI smartphone frame with category badges (`AUTO`, `MANUAL`, `CRITICAL`) and clickable `voiceassist://...` setting simulation buttons.

---

## 6. CLI Demo Tool

For quick command-line testing without a browser:

```bash
# Run on the first sample query from dataset
python demo.py

# Run on the 4th query (0-indexed)
python demo.py 3

# Run on a custom query
python demo.py --query "screen flickers when unlocked"
```

---

## 7. Running Tests & Quality Verification

Run the comprehensive unit test suite:
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific functional suites
python -m pytest tests/test_api_and_outputs.py -v   # API contracts & metrics
python -m pytest tests/test_ordering.py -v          # Topological dependency sorting
python -m pytest tests/test_deglue.py -v            # Viterbi word segmentation
python -m pytest tests/test_mismatch.py -v          # Cross-domain mismatch protection
python -m pytest tests/test_deeplinks.py -v         # Deeplink catalog matching
```

---

## 8. Running the Evaluation Harness

To run the full evaluation suite and measure schema conformance, grounding accuracy, and latency across test cases:

```bash
python eval/run_eval.py
```
To tune confidence and similarity thresholds:
```bash
python eval/run_eval.py --tune
```
