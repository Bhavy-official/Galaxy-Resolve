"""Shared helpers for eval scripts."""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.cache.slots import extract_slots, slots_compatible  # noqa: E402
from app.config import Settings, settings  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.pipeline.path_parser import direction_of, nav_targets  # noqa: E402
from app.pipeline.textutil import normalize_complaint  # noqa: E402
from app.pipeline.types import CandidateStep, GroupDraft  # noqa: E402

EVAL_DIR = ROOT / "eval"


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def siis_rows() -> list[dict[str, Any]]:
    return load_json(settings.siis_path)["responses"]


def results(path: Path = settings.results_path) -> list[dict[str, Any]]:
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def paraphrases() -> dict[str, Any]:
    data = load_json(EVAL_DIR / "paraphrases.json")
    extra = EVAL_DIR / "paraphrases_llm.json"
    if extra.exists():
        more = load_json(extra)
        data["positives"] += more.get("positives", [])
        data["negatives"] += more.get("negatives", [])
    return data


def gold_group(steps: list[str], direction: Optional[str] = None) -> GroupDraft:
    path = [x for t in steps for x in nav_targets(t)[0]]
    return GroupDraft([CandidateStep(t, t, 0, "") for t in steps], path, direction or direction_of(steps))


def pct(values: list[float], q: float) -> float:
    return float(np.percentile(values, q)) if values else float("nan")


def ensure_prewarmed(engine: Engine) -> None:
    if engine.store.n_plans:
        return
    for row in siis_rows():
        engine.troubleshoot(row["original_query"], row["siis_response"], use_cache=False)


class LookupSim:
    """Re-implements Engine.lookup with swappable thresholds and memoized model calls (for tuning/ablation)."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._q: dict[str, tuple[Any, Any]] = {}
        self._ce: dict[tuple[str, str], float] = {}

    def _query(self, q: str):
        if q not in self._q:
            norm = normalize_complaint(q)
            vecs = self.engine.models.encode([q, norm] if norm and norm != q else [q])
            self._q[q] = (self.engine.store.search_many(vecs, k=10), extract_slots(q))
        return self._q[q]

    def _ce_score(self, q: str, t: str) -> float:
        if (q, t) not in self._ce:
            self._ce[(q, t)] = float(self.engine.models.paraphrase_score([(q, t)])[0])
        return self._ce[(q, t)]

    def lookup(self, q: str, cfg: Settings) -> Optional[int]:
        hits, qslots = self._query(q)
        borderline = []
        seen: set[int] = set()
        for h in hits:
            if h.similarity < cfg.borderline_low:
                break
            if h.plan_id in seen:
                continue
            plan = self.engine.store.get(h.plan_id)
            if plan is None or (cfg.slot_guard and not slots_compatible(qslots, plan.slots)):
                continue
            seen.add(h.plan_id)
            if h.similarity >= cfg.hit_threshold:
                return h.plan_id
            borderline.append((h.plan_id, h.text))
        if borderline:
            scored = [(self._ce_score(q, t), pid) for pid, t in borderline[:3]]
            best = max(scored)
            if best[0] >= cfg.ce_hit_threshold:
                return best[1]
        return None


def hit_metrics(engine: Engine, sim: LookupSim, cfg: Settings, positives: list[dict], negatives: list[str]) -> dict[str, float]:
    rows = {r["original_query"]: r for r in siis_rows()}
    by_id = {r["id"]: r for r in siis_rows()}
    correct = same_doc = wrong = hits = 0
    for p in positives:
        pid = sim.lookup(p["text"], cfg)
        if pid is None:
            continue
        hits += 1
        plan = engine.store.get(pid)
        src = rows.get(plan.query)
        if src is None:
            wrong += 1
        elif src["id"] == p["row"]:
            correct += 1
        elif src["siis_response"]["title"] == by_id[p["row"]]["siis_response"]["title"]:
            same_doc += 1  # identical underlying SIIS article -> equivalent plan
        else:
            wrong += 1
    neg_hits = sum(1 for n in negatives if sim.lookup(n, cfg) is not None)
    n_pos, n_neg = max(1, len(positives)), max(1, len(negatives))
    return {
        "hit_rate": hits / n_pos,
        "exact_row": correct / n_pos,
        "acceptable_hit_rate": (correct + same_doc) / n_pos,
        "wrong_hit_rate": wrong / n_pos,
        "negative_false_hit_rate": neg_hits / n_neg,
        "n_pos": len(positives),
        "n_neg": len(negatives),
    }


def with_cfg(engine: Engine, **kw: Any) -> Settings:
    return replace(engine.cfg, **kw)
