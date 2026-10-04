"""Central configuration. Thresholds live here (overridable by env or thresholds.json), never inline."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Tuned values written by eval/run_eval.py --tune take precedence over defaults; env overrides both.
_TUNED: dict = {}
_tuned_path = ROOT / "thresholds.json"
if _tuned_path.exists():
    _TUNED = json.loads(_tuned_path.read_text(encoding="utf-8"))


def _num(name: str, default: float) -> float:
    return float(os.getenv(name.upper(), _TUNED.get(name, default)))


def _str(name: str, default: str) -> str:
    return os.getenv(name.upper(), default)


@dataclass(frozen=True)
class Settings:
    data_dir: Path = ROOT / "data"
    deeplinks_path: Path = ROOT / "data" / "deeplinks.json"
    siis_path: Path = ROOT / "data" / "siis_responses.json"
    index_dir: Path = ROOT / "data" / "index"
    cache_db: Path = Path(_str("cache_db", str(ROOT / "cache.sqlite3")))
    results_path: Path = ROOT / "results.jsonl"

    # Local models (fast path must never call an LLM).
    embed_model: str = _str("embed_model", "sentence-transformers/all-MiniLM-L6-v2")
    rerank_model: str = _str("rerank_model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    paraphrase_ce_model: str = _str("paraphrase_ce_model", "cross-encoder/stsb-distilroberta-base")

    # LLM (Google Gemini — Muse Spark)
    llm_model: str = _str("llm_model", "gemini-3.8-flash")
    llm_base_url: str = _str("llm_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")
    llm_timeout_s: float = _num("llm_timeout_s", 25.0)
    llm_max_retries: int = int(_num("llm_max_retries", 2))
    # auto = use LLM when credentials exist, else deterministic rules; rules = never call LLM; llm = require LLM
    pipeline_mode: str = _str("pipeline_mode", "auto")

    # Cache thresholds
    hit_threshold: float = _num("hit_threshold", 0.80)
    borderline_low: float = _num("borderline_low", 0.68)
    ce_hit_threshold: float = _num("ce_hit_threshold", 0.62)
    slot_guard: bool = _str("slot_guard", "1") not in ("0", "false", "False")

    # Deeplink thresholds
    dl_threshold: float = _num("dl_threshold", 0.85)
    dl_nonsettings_margin: float = _num("dl_nonsettings_margin", 0.10)
    dl_candidates: int = int(_num("dl_candidates", 20))
    rrf_k: int = int(_num("rrf_k", 60))

    # Plan shape limits
    max_actions: int = int(_num("max_actions", 6))
    max_steps_per_group: int = int(_num("max_steps_per_group", 8))
    extra: dict = field(default_factory=dict)


settings = Settings()
