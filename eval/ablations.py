"""Ablation table for metrics.md -> eval/ablations.md

  A. Deeplink retrieval components (gold set): BM25 / dense / RRF / +rerank / full (leaf + precision + threshold)
  B. Cache fast path: full vs no-slot-guard vs no-cross-encoder vs single-vector vs no-normalization
  C. Pipeline: rules vs hybrid (LLM extract + code) vs full-LLM (LLM writes the whole plan); LLM rows need a key
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import replace
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel

from common import (  # type: ignore[import-not-found]
    EVAL_DIR,
    LookupSim,
    ensure_prewarmed,
    gold_group,
    hit_metrics,
    load_json,
    paraphrases,
    pct,
    siis_rows,
    with_cfg,
)

from app.engine import Engine
from app.llm import LLMClient, LLMError
from app.pipeline import compliance
from app.pipeline.deeplinks import DUMMY_URI, Catalog
from app.pipeline.path_parser import is_settings_root, strip_terminal
from app.pipeline.validators import scrub_tree


# ---------------------------------------------------------------- A. retrieval
def retrieval_ablation(cat: Catalog) -> list[dict[str, Any]]:
    gold = load_json(EVAL_DIR / "gold_deeplinks.json")

    def run(pick) -> float:
        ok = 0
        for case in gold:
            g = gold_group(case["steps"], case.get("direction"))
            ok += pick(g) in case["expect"]
        return ok / len(gold)

    def query_of(g) -> tuple[str, list[str]]:
        from app.pipeline.path_parser import leaf_screen

        path = [p for p in strip_terminal(g.path) if not is_settings_root([p])]
        leaf = leaf_screen(g)
        el = list(dict.fromkeys([*path, leaf] if leaf else path))
        return " ".join(el), el

    def bm25(g):
        q, _ = query_of(g)
        if not q:
            return "none"
        from app.pipeline.textutil import content_tokens, stem

        s = cat.bm25.get_scores([stem(t) for t in content_tokens(q)])
        return cat.entries[int(np.argmax(s))]["id"]

    def dense(g):
        q, _ = query_of(g)
        return cat.entries[int(np.argmax(cat.emb @ cat.models.encode([q])[0]))]["id"] if q else "none"

    def rrf(g):
        q, _ = query_of(g)
        return cat.entries[cat.candidates(q, cat.cfg.dl_candidates)[0]]["id"] if q else "none"

    def rerank_only(g):
        q, _ = query_of(g)
        if not q:
            return "none"
        idxs = cat.candidates(q, cat.cfg.dl_candidates)
        rel = cat.models.rerank([(q, cat.docs[i]) for i in idxs])
        return cat.entries[idxs[int(np.argmax(rel))]]["id"]

    def full_no_threshold(g):
        q, el = query_of(g)
        if not q:
            return "none"
        s = cat.score_candidates(q, el, g.direction, cat.candidates(q, cat.cfg.dl_candidates))
        return cat.entries[s[0][0]]["id"]

    def full(g):
        m = cat.match_group(g)
        return m.entry["id"] if m.entry else m.kind

    return [
        {"variant": "BM25 only", "accuracy": run(bm25)},
        {"variant": "Dense only (MiniLM)", "accuracy": run(dense)},
        {"variant": "Hybrid RRF (BM25 + dense)", "accuracy": run(rrf)},
        {"variant": "RRF + cross-encoder rerank", "accuracy": run(rerank_only)},
        {"variant": "+ leaf specificity + key precision + direction (no threshold)", "accuracy": run(full_no_threshold)},
        {"variant": "Full (with confidence threshold -> dummy_positive / null)", "accuracy": run(full)},
    ]


# ---------------------------------------------------------------- B. cache
class VariantSim(LookupSim):
    def __init__(self, engine: Engine, single_vector: bool = False, normalize: bool = True) -> None:
        super().__init__(engine)
        self.single_vector, self.normalize = single_vector, normalize

    def _query(self, q: str):
        if q not in self._q:
            from app.cache.slots import extract_slots
            from app.pipeline.textutil import normalize_complaint

            norm = normalize_complaint(q)
            views = [q, norm] if self.normalize and norm and norm != q else [q]
            hits = self.engine.store.search_many(self.engine.models.encode(views), k=200 if self.single_vector else 10)
            if self.single_vector:  # only the original query's vector per plan (no paraphrase multi-vector)
                hits = [h for h in hits if h.text == self.engine.store.get(h.plan_id).query][:10]
            self._q[q] = (hits, extract_slots(q))
        return self._q[q]


def cache_ablation(engine: Engine) -> list[dict[str, Any]]:
    para = paraphrases()
    pos, neg = para["positives"], para["negatives"]
    base = LookupSim(engine)
    rows = [
        ("Full (multi-vector + normalization + slot guard + cross-encoder)", base, engine.cfg),
        ("No slot guard", base, with_cfg(engine, slot_guard=False)),
        ("No cross-encoder (embedding threshold only)", base, with_cfg(engine, ce_hit_threshold=9.0)),
        ("No slot guard, embedding threshold 0.70", base, with_cfg(engine, slot_guard=False, hit_threshold=0.70, ce_hit_threshold=9.0)),
        ("Single vector per plan (no paraphrases)", VariantSim(engine, single_vector=True), engine.cfg),
        ("No query-side brand/model normalization", VariantSim(engine, normalize=False), engine.cfg),
    ]
    return [{"variant": name, **hit_metrics(engine, sim, cfg, pos, neg)} for name, sim, cfg in rows]


# ---------------------------------------------------------------- C. pipeline
class FLStepGroup(BaseModel):
    steps: list[str]
    deeplink_id: Optional[str] = None


class FLAction(BaseModel):
    actionName: str
    description: str
    category: str
    stepGroups: list[FLStepGroup]


class FLPlan(BaseModel):
    goal: str
    title: str
    score: float
    actions: list[FLAction]


FULL_LLM_SYSTEM = """You write a complete device troubleshooting plan from a support article.
Rules: goal = "Follow these steps to perform this <Topic> Troubleshooting"; title 2-3 words sentence case;
actionName Title Case, one screen per action; description starts with "It will" and has 5-7 words;
steps are imperative, one interaction each, only from the article, no URLs;
category auto (has a deeplink) / manual (no deeplink) / critical (reset, restart, safe mode, update) with critical last;
deeplink_id must be one of the candidate ids, "DUMMY" for a Settings screen with no candidate, or null."""


def full_llm_plan(engine: Engine, query: str, siis: dict) -> dict[str, Any]:
    """Ablation baseline: the LLM does everything (no grounding, path parser, retrieval ranking or validators)."""
    cands = engine.catalog.candidates(f"{query} {siis.get('title', '')}", 40)
    cand_text = "\n".join(f"{engine.catalog.entries[i]['id']}: {engine.catalog.docs[i][:160]}" for i in cands)
    user = f"Complaint: {query}\n\nArticle:\n{siis.get('content', '')}\n\nDeeplink candidates:\n{cand_text}"
    plan, _ = engine.llm.structured(FULL_LLM_SYSTEM, user, FLPlan, max_tokens=4096)
    actions = []
    for a in plan.actions:
        groups = []
        for g in a.stepGroups:
            e = engine.catalog.by_id.get(g.deeplink_id or "")
            dl = None
            if g.deeplink_id == "DUMMY":
                dl = {"deeplink": DUMMY_URI, "description": "Opens the relevant screen in Settings", "message": "Open the relevant Settings screen"}
            elif e is not None:
                dl = {"deeplink": e["deeplink"], "description": e["description"], "message": e["message"]}
            elif g.deeplink_id:
                dl = {"deeplink": f"invalid:{g.deeplink_id}", "description": "", "message": ""}
            groups.append({"steps": g.steps, "actionableDeeplink": dl, "validationDeeplink": None})
        cat = a.category if a.category in ("auto", "manual", "critical") else "manual"
        actions.append({"actionName": a.actionName, "description": a.description, "stepGroups": groups, "category": cat})
    return {"contexts": [{"goal": plan.goal, "title": plan.title, "score": max(0.0, min(1.0, plan.score)), "actions": actions}]}


def pipeline_ablation(engine: Engine) -> list[dict[str, Any]]:
    rows = siis_rows()
    out = []
    has_llm = LLMClient.has_credentials()

    def measure(name: str, fn) -> None:
        lat, cost, viol, ok = [], 0.0, 0, 0
        for r in rows:
            t0 = time.perf_counter()
            before = engine.llm.totals.cost_usd
            try:
                resp = fn(r)
            except LLMError as exc:
                out.append({"variant": name, "note": f"failed: {exc}"})
                return
            lat.append((time.perf_counter() - t0) * 1000)
            cost += engine.llm.totals.cost_usd - before
            v = compliance.violations(scrub_tree(resp) if name.startswith("Full-LLM") else resp, engine.catalog.all_uris)
            raw_v = compliance.violations(resp, engine.catalog.all_uris)
            viol += len(raw_v)
            ok += not raw_v and bool(resp.get("contexts"))
            _ = v
        out.append({
            "variant": name, "fully_compliant": f"{ok}/{len(rows)}", "violations": viol,
            "p50_ms": round(pct(lat, 50)), "p95_ms": round(pct(lat, 95)), "cost_usd_per_query": round(cost / len(rows), 5),
        })

    rules = Engine(replace(engine.cfg, pipeline_mode="rules"), models=engine.models, store=engine.store).load()
    rules.llm.client = None
    measure("Rules only (no LLM)", lambda r: rules.troubleshoot(r["original_query"], r["siis_response"], use_cache=False, write_cache=False))
    if has_llm:
        hybrid = Engine(replace(engine.cfg, pipeline_mode="auto"), models=engine.models, store=engine.store).load()
        measure("Hybrid (LLM extract/enrich + code) - production", lambda r: hybrid.troubleshoot(r["original_query"], r["siis_response"], use_cache=False, write_cache=False))
        measure("Full-LLM (LLM writes whole plan)", lambda r: full_llm_plan(hybrid, r["original_query"], r["siis_response"]))
    else:
        out.append({"variant": "Hybrid (LLM extract/enrich + code) - production", "note": "n/a: set GEMINI_API_KEY"})
        out.append({"variant": "Full-LLM (LLM writes whole plan)", "note": "n/a: set GEMINI_API_KEY"})
    return out


RATE_COLS = {"accuracy", "hit_rate", "acceptable_hit_rate", "wrong_hit_rate", "negative_false_hit_rate"}


def table(rows: list[dict[str, Any]], cols: list[str]) -> list[str]:
    def fmt(c: str, v: Any) -> str:
        return f"{v:.0%}" if c in RATE_COLS and isinstance(v, float) else str(v)

    return ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols),
            *["| " + " | ".join(fmt(c, r.get(c, "")) for c in cols) + " |" for r in rows]]


def main() -> int:
    engine = Engine().load()
    ensure_prewarmed(engine)
    a = retrieval_ablation(engine.catalog)
    b = cache_ablation(engine)
    c = pipeline_ablation(engine)
    md = [
        "# Ablations", "", "_Generated by `python eval/ablations.py`._", "",
        "## A. Deeplink retrieval (gold set)", "", *table(a, ["variant", "accuracy"]), "",
        "## B. Cache fast path (unseen paraphrases + negatives)", "",
        *table(b, ["variant", "hit_rate", "acceptable_hit_rate", "wrong_hit_rate", "negative_false_hit_rate"]), "",
        "## C. Pipeline (20 provided queries, cache bypassed)", "",
        *table(c, ["variant", "fully_compliant", "violations", "p50_ms", "p95_ms", "cost_usd_per_query", "note"]), "",
    ]
    (EVAL_DIR / "ablations.md").write_text("\n".join(md), encoding="utf-8")
    (EVAL_DIR / "ablations.json").write_text(json.dumps({"retrieval": a, "cache": b, "pipeline": c}, indent=2), encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
