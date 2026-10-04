# Galaxy Resolve — System Architecture & Design

This document details the engineering design, module contracts, and execution pipelines of **Galaxy Resolve**, built for the Samsung PRISM GenAI Hackathon (Theme 2: Smart Guided Troubleshooting Engine).

---

## 1. Architectural Philosophy: *"LLM Proposes, Code Disposes"*

Support troubleshooting engines face a fundamental challenge: LLMs are proficient at semantic interpretation, but prone to hallucinations, non-deterministic phrasing, and latency spikes.

Galaxy Resolve adheres to the **"LLM proposes, code disposes"** doctrine:
1. **The LLM is strictly an extractor**: It identifies component entities, symptoms, section relevance, and draft action labels.
2. **Deterministic Python code controls all output contracts**:
   * Word count limits (Title: 2–3 words; Description: 5–7 words starting with `"It will "`).
   * Deeplink mapping: URIs are never written by an LLM; they are matched via hybrid retrieval against a verified 578-entry catalog.
   * Disruption ordering: Actions are sorted auto $\to$ manual $\to$ critical.
   * Safety dependencies: Prerequisite actions (like backup before factory reset) are enforced via a directed acyclic graph (DAG).
   * URL scrubbers: 100% elimination of external links and domain suffixes.

---

## 2. End-to-End Execution Flow

```text
                                 [ User Complaint + SIIS Context ]
                                                │
                                                ▼
                                    ┌───────────────────────┐
                                    │ Input Normalization   │
                                    │ & Slot Extraction     │
                                    └───────────┬───────────┘
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     │                                                     │
                     ▼                                                     ▼
      ┌─────────────────────────────┐                       ┌─────────────────────────────┐
      │  Fast Path: Vector Cache    │                       │  Cold Path: Mismatch Gate   │
      │  - Dense Cosine (>= 0.80)   │                       │  - Distinctive word check   │
      │  - Slot Guard Validation    │                       │  - Reject unrelated SIIS    │
      │  - Borderline Cross-Encoder │                       └──────────────┬──────────────┘
      └──────────────┬──────────────┘                                      │
                     │ (Hit: < 30ms)                                       ▼
                     │                                      ┌─────────────────────────────┐
                     │                                      │  Viterbi Scraper Degluer    │
                     │                                      │  - Repair missing spaces    │
                     │                                      └──────────────┬──────────────┘
                     │                                                     │
                     │                                                     ▼
                     │                                      ┌─────────────────────────────┐
                     │                                      │  Dual Extraction Engine     │
                     │                                      │  - Gemini / Structured LLM  │
                     │                                      │  - Deterministic Rules Fall │
                     │                                      └──────────────┬──────────────┘
                     │                                                     │
                     │                                                     ▼
                     │                                      ┌─────────────────────────────┐
                     │                                      │  Grounding Verifier         │
                     │                                      │  - Token overlap with span  │
                     │                                      └──────────────┬──────────────┘
                     │                                                     │
                     │                                                     ▼
                     │                                      ┌─────────────────────────────┐
                     │                                      │  Hybrid Deeplink Matcher    │
                     │                                      │  - BM25 + Dense + RRF       │
                     │                                      │  - Cross-Encoder + Specific │
                     │                                      └──────────────┬──────────────┘
                     │                                                     │
                     │                                                     ▼
                     │                                      ┌─────────────────────────────┐
                     │                                      │  Topological DAG Sorter     │
                     │                                      │  - auto -> manual -> crit   │
                     │                                      │  - data/dependencies.json   │
                     │                                      └──────────────┬──────────────┘
                     │                                                     │
                     │                                                     ▼
                     │                                      ┌─────────────────────────────┐
                     │                                      │  Schema Compiler & Scrub    │
                     │                                      │  - Pydantic contract check  │
                     │                                      │  - Zero external URL scrub  │
                     │                                      └──────────────┬──────────────┘
                     │                                                     │
                     └──────────────────────────┬──────────────────────────┘
                                                │
                                                ▼
                                  [ ContextDeeplinkResponse ]
```

---

## 3. Core Subsystems

### 3.1 Fast Path: Vector Cache & Slot Guards (`app/cache/`)
* **Storage (`app/cache/store.py`):** Backed by SQLite (`cache.sqlite3`), storing precomputed plans, canonical representations, query variations, and dense vector embeddings (`all-MiniLM-L6-v2`).
* **Slot Guard (`app/cache/slots.py`):** Before returning a cache hit, validates that domain (`battery`, `display`, `camera`), symptom (`drain`, `flicker`, `black`), and triggers match. Prevents cross-domain cache collisions (e.g. matching a battery query to a display fix).
* **Borderline Cross-Encoder:** If vector cosine similarity falls into the borderline region ($0.68 \le \text{sim} < 0.80$), a Cross-Encoder (`stsb-distilroberta-base`) evaluates semantic equivalence, preventing false-positive cache hits.

### 3.2 Mismatched SIIS Protection Gate (`app/pipeline/mismatch.py`)
* Evaluates whether the provided reference article has substantive relevance to the user complaint.
* Compares distinct content tokens and domain slots between the query and article content.
* If a completely unrelated guide is supplied (e.g. washing machine instructions for a phone camera bug), the engine immediately halts with:
  ```json
  {"contexts": [], "meta": {"fallback": "no_match"}}
  ```
  preventing hallucinated actions from reaching the user.

### 3.3 Viterbi Dynamic Programming Word Degluer (`app/pipeline/deglue.py`)
* Scraped technical articles often feature joined words without spacing (e.g., `enteryourcurrentpin,passwordorpattern`).
* Uses a Viterbi unigram dynamic programming algorithm with negative log word costs to segment runs $> 15$ characters into constituent dictionary words.
* Runs on demand during sentence parsing, preserving the verbatim source span references needed for grounding verification.

### 3.4 Extraction & Grounding (`app/pipeline/extract.py`, `app/pipeline/grounding.py`)
* **Dual Execution:**
  * **LLM Mode (`llm_extract`):** Calls Gemini via structured output (`LLMExtraction`) with section-bounded candidate steps, verbatim source spans, and section labels.
  * **Rules Mode (`rules_extract`):** Deterministic sentence classifier filtering imperative verb-led instructions, stripping modals (*"you should"*), and splitting compound procedures.
* **Grounding Gate:** Cross-references each step's content tokens against the source document. Steps that introduce unsupported claims are discarded.

### 3.5 Hybrid Deeplink Catalog Matcher (`app/pipeline/deeplinks.py`)
* Matches target settings screens against the 578 entries in `data/deeplinks.json`.
* **Three-Tier Hybrid Retrieval:**
  1. **BM25 Lexical Search:** Matches specific screen and setting terminology.
  2. **Dense Vector Cosine:** Semantic matching using `sentence-transformers/all-MiniLM-L6-v2`.
  3. **Reciprocal Rank Fusion (RRF):** Merges rank lists.
* **Cross-Encoder Reranking (`ms-marco-MiniLM-L-6-v2`):** Computes deep attention across the top candidate pairs.
* **Depth Decay Specificity:** Exponentially penalizes generic parent screens in favor of granular leaf menus:
  $$\text{weight}_d = 0.85^{n - 1 - d}$$

### 3.6 Topological Dependency Sorter & Safety Ordering (`app/pipeline/ordering.py`)
* **Disruption Categories:**
  * `auto`: Actionable settings screen with deep link.
  * `manual`: External / physical intervention (no actionable link).
  * `critical`: Disruptive operations (Restart, Safe Mode, Update, Reset).
* **Critical Sub-Ranking:**
  1. `restart` (least disruptive critical)
  2. `safe mode`
  3. `software update`
  4. `factory reset` (destructive — always ordered last)
* **Topological Prerequisites (`data/dependencies.json`):**
  Enforces prerequisite DAG edges:
  * `backup` $\to$ `factory reset`
  * `safe mode` $\to$ `uninstall in safe mode`
  * `charge` $\to$ `force restart`

### 3.7 Contract Compiler & URL Scrubbing (`app/pipeline/validators.py`)
* Programmatically formats fields:
  * `goal`: Strict syntax: `Follow these steps to perform this <Topic> Troubleshooting`.
  * `title`: Exactly 2–3 words in Sentence case.
  * `description`: Exactly 5–7 words starting with `"It will "`.
* **Zero Absolute URL Leak:** Regex scrubbers strip all `http://`, `https://`, `www.`, markdown links, domain suffixes (`.com`, `.org`), and email addresses.

### 3.8 Observability & Real-Time Streaming (`app/api.py`)
* **Server-Sent Events (SSE):** `POST /v1/troubleshoot/stream` streams live stage events (`normalize`, `cache_hit`, `llm_enrich`, `grounding`, `deeplink_catalog`, `completed`) to the web visualizer.
* **In-Memory Rolling Deque:** Maintains the last 1,000 requests, calculating real-time P50 and P95 latencies, cache hit rates, and request costs exposed at `GET /v1/metrics`.
* **Per-Request Tracing:** Assigns unique 8-character trace IDs accessible at `GET /v1/trace/{trace_id}`.

### 3.9 SIIS Knowledge Store & Auto-Matching (`app/siis_store.py`)

The Theme 2 specification defines `siis_response` as **optional** in the API contract:

```json
POST /v1/troubleshoot
{
  "query": "phone swipe gestures wrong direction after app install",
  "siis_response": "<optional raw text context>"
}
```

Two execution paths exist depending on whether `siis_response` is provided:

| Caller Scenario | `siis_response` in request | Engine behaviour |
|---|---|---|
| **Scorer / evaluator** | Provided (from `siis_responses.json`) | Engine uses caller content directly — highest priority |
| **Frontend demo** | Omitted | `SIISStore` auto-matches the best article via cosine similarity |
| **Unknown query** | Omitted, no match found | Returns `contexts: []` with `fallback: "no_siis_context"` |

**SIISStore implementation:**
* Loads all 20 Samsung support articles from `data/siis_responses.json` at startup.
* Pre-embeds the original query for each article using `all-MiniLM-L6-v2`.
* On lookup: encodes the incoming query, computes cosine similarity, returns best article above threshold `0.30`.
* Gracefully degrades if the file is missing — explicit caller-supplied SIIS still works.

---

## 4. Data Assets

| File | Description |
|---|---|
| `data/deeplinks.json` | 578 verified Samsung deeplinks (`voiceassist://masked/act/...`) with descriptions and validation rules |
| `data/siis_responses.json` | 20 official Samsung SIIS support articles paired with original queries |
| `data/input.txt` | 20 official evaluation queries from the Theme 2 evaluation set |
| `data/samples/sample_1.json` | Reference input/output pair illustrating the correct response schema |
| `data/schema_reference.py` | Pydantic schema from Theme 2 spec — defines the exact output contract |
| `data/dependencies.json` | Topological prerequisite edges for safety ordering |
| `data/index/` | Pre-built BM25 + dense vector indexes for the deeplink catalog |
