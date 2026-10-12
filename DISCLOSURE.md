<div align="center">

<br>

# AI AND TOOL DISCLOSURE — GALAXY RESOLVE

### Transparency Statement for the SRM Theme 2: Smart Guided Troubleshooting Engine Submission

*This document discloses all AI tools, language models, third-party libraries, and external services used during the development of Galaxy Resolve.*

<br>

---

### Project Resources

| Resource | Link |
|---|---|
| Project Overview | [README.md](README.md) |
| Presentation Slide Deck | [SRM_Code_Brewers.pdf](submission/SRM_Code_Brewers.pdf) |
| Video Demonstration | [Google Drive — Demo Recording](https://drive.google.com/drive/folders/1mToZ4nGpqT2vQEok5F9KYxQHxP25UocI?usp=sharing) |
| System Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| API Reference | [API.md](API.md) |

---

</div>

## Overview

This document provides full transparency regarding all AI-assisted tools, language model APIs, pre-trained models, and third-party frameworks used in the development and operation of Galaxy Resolve. This disclosure is provided in accordance with the competition guidelines and the spirit of academic integrity.

The project was primarily **designed, built, and evaluated by the team**. AI tooling was used selectively as a productivity aid — similar to how developers use Stack Overflow, documentation search, or a linter — and every line of code was reviewed, understood, and validated by team members.

---

## AI Tools Used During Development

| Tool | Purpose | Scope of Use |
|---|---|---|
| **GitHub Copilot** | Occasional inline code completion suggestions (e.g., boilerplate, regex patterns) | Development aid; all suggestions reviewed and modified by the team |
| **ChatGPT / Gemini (Chat)** | Quick reference queries on library APIs and debugging assistance | Research and reference, not code generation |
| **Google Gemini API** | **Runtime component** — LLM for extracting troubleshooting steps from Samsung support articles at inference time | Core engine cold-path feature (user-facing functionality) |

> The overall system architecture, pipeline design, caching strategy, grounding logic, safety ordering, schema contracts, and evaluation methodology were conceived and implemented by the team. AI tools assisted with specific implementation details and syntax lookups — not with design or logic.

---

## Pre-Trained Models (Runtime)

These models are downloaded from Hugging Face Hub and run **locally on-device** at inference time. They are standard, publicly available, permissively licensed models:

| Model | Source | Use in Galaxy Resolve |
|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | Hugging Face Hub | Dense query and deeplink catalog vectorization |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Hugging Face Hub | Deeplink candidate reranking |
| `cross-encoder/stsb-distilroberta-base` | Hugging Face Hub | Cache borderline verification |

---

## External APIs and Services

| Service | Provider | Purpose |
|---|---|---|
| **Gemini API** | Google DeepMind | Runtime LLM cold-path extraction (requires API key; optional — system runs fully offline without it) |

> No user complaint data is stored externally. The Gemini API call is a transient request used only to process the support article text; it is not retained by the application.

---

## Third-Party Open-Source Libraries

All libraries are permissively licensed (MIT, Apache 2.0, or BSD). Key dependencies:

| Library | License | Purpose |
|---|---|---|
| `fastapi` | MIT | REST API framework and SSE streaming |
| `uvicorn` | BSD | ASGI server |
| `sentence-transformers` | Apache 2.0 | Local SentenceTransformers model loading |
| `rank-bm25` | Apache 2.0 | BM25 lexical search indexing |
| `pydantic` | MIT | Response contract schema validation |
| `openai` | MIT | OpenAI-compatible client for Gemini endpoint |
| `numpy` | BSD | Cosine similarity and vector operations |
| `pytest` | MIT | Automated test suite |
| `react` (v19) | MIT | Frontend web console |
| `vite` | MIT | Frontend build tooling |

The complete dependency list is available in [`requirements.txt`](requirements.txt).

---

## Data Sources

| Dataset | Source | Usage |
|---|---|---|
| Samsung Settings Deeplinks (578 entries) | Compiled from official Samsung One UI documentation | Verified deeplink catalog for action resolution |
| SIIS Support Articles (20 scenarios) | Official Theme 2 competition dataset | Benchmark evaluation and knowledge store |
| Word Frequency Corpus | Public domain unigram frequency lists | Viterbi word segmentation degluer |

---

## Originality Statement

The following components are entirely original work produced by the Galaxy Resolve team:

- The **"LLM Proposes, Code Disposes"** dual-plane architecture and its implementation
- The **three-dimensional Slot Guard** cache validation mechanism (domain × symptom × trigger)
- The **3-Tier SIIS Resolution Strategy** (evaluator-supplied → semantic benchmark match → universal synthesis)
- The **Cross-Domain Mismatch Shield** pipeline gate
- The **Viterbi Scraper Degluer** with Samsung-domain word frequency tuning
- The **Hybrid BM25 + Dense + RRF + Cross-Encoder + Depth-Decay** deeplink retrieval pipeline
- The **Topological Safety DAG** with prerequisite constraint enforcement
- The **Pydantic contract schema validation and zero-URL scrubbing** pipeline
- The **React 19 One UI visualizer** web console with SSE-driven live pipeline streaming
- All test cases, evaluation harness, and benchmark scoring methodology

---

<div align="center">

This disclosure is provided voluntarily and in full transparency.

[README.md](README.md) &nbsp;|&nbsp; [ARCHITECTURE.md](ARCHITECTURE.md) &nbsp;|&nbsp; [HOW_TO_RUN.md](HOW_TO_RUN.md)

</div>