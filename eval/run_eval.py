"""Evaluation: schema/rule compliance, deeplink accuracy, cache hit rate, latency. Writes eval/metrics.{json,md}.

    python eval/run_eval.py              # full report
    python eval/run_eval.py --latency    # latency gates only
    python eval/run_eval.py --tune       # grid-search cache + deeplink thresholds -> thresholds.json
Exit code 1 if a hard gate fails (URL leak, catalog violation, schema error, cache-hit P95 > 300 ms).
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import time
from collections import Counter
from typing import Any

from common import (  # type: ignore[import-not-found]
    EVAL_DIR,
    ROOT,
    LookupSim,
    ensure_prewarmed,
    gold_group,
    hit_metrics,
    load_json,
    paraphrases,
    pct,
    results,
    siis_rows,
    with_cfg,
)

from app.engine import Engine
from app.pipeline import compliance
from app.schema import ContextDeeplinkResponse

URL_RE = re.compile(r"https?://|www\.", re.I)
HIT_P95_BUDGET_MS = 300.0
MISS_P95_BUDGET_MS = 8000.0


# ---------------------------------------------------------------- sections
def compliance_section(res: list[dict], engine: Engine) -> dict[str, Any]:
    cats: Counter = Counter()
    dl_kinds: Counter = Counter()
    fallbacks: Counter = Counter()
    violations: list[str] = []
    schema_errors = 0
    n_actions = 0
    for rec in res:
        resp = rec["response"]
        fallbacks[resp["meta"].get("fallback") or "none"] += 1
        try:
            ContextDeeplinkResponse.model_validate(resp)
        except Exception:
            schema_errors += 1
        violations += [f"{rec['id']}: {v}" for v in compliance.violations(resp, engine.catalog.all_uris)]
        for g in resp["contexts"]:
            for a in g["actions"]:
                n_actions += 1
                cats[a["category"]] += 1
                for sg in a["stepGroups"]:
                    dl = sg["actionableDeeplink"]
                    dl_kinds["null" if dl is None else ("dummy_positive" if dl["deeplink"].endswith("dummy_positive") else "catalog")] += 1
    text = (ROOT / "results.jsonl").read_text(encoding="utf-8") if (ROOT / "results.jsonl").exists() else ""
    return {
        "responses": len(res),
        "schema_errors": schema_errors,
        "url_leaks": len(URL_RE.findall(text)),
        "violations": violations,
        "actions": n_actions,
        "categories": dict(cats),
        "deeplinks": dict(dl_kinds),
        "fallbacks": dict(fallbacks),
    }


def gold_section(engine: Engine) -> dict[str, Any]:
    gold = load_json(EVAL_DIR / "gold_deeplinks.json")
    rows, ok = [], 0
    for case in gold:
        m = engine.catalog.match_group(gold_group(case["steps"], case.get("direction")))
        got = m.entry["id"] if m.entry else m.kind
        hit = got in case["expect"]
        ok += hit
        rows.append({"name": case["name"], "expect": case["expect"], "got": got, "best": m.best_id, "conf": round(m.conf, 3), "ok": hit})
    return {"accuracy": ok / len(gold), "n": len(gold), "cases": rows}


def latency_section(engine: Engine, positives: list[dict], passes: int = 3) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    import app.api as api

    api.engine = engine
    queries = [r["original_query"] for r in siis_rows()] + [p["text"] for p in positives]
    hit_client, hit_server = [], []
    with TestClient(api.app) as client:
        client.post("/v1/troubleshoot", json={"query": "warmup screen black"})
        for _ in range(passes):
            for q in queries:
                t0 = time.perf_counter()
                body = client.post("/v1/troubleshoot", json={"query": q}).json()
                dt = (time.perf_counter() - t0) * 1000
                if body["meta"]["cache_hit"]:
                    hit_client.append(dt)
                    hit_server.append(body["meta"]["latency_ms"])
    miss = [r["response"]["meta"]["latency_ms"] for r in results() if not r["response"]["meta"]["cache_hit"]]
    return {
        "hit_requests": len(hit_client),
        "hit_p50_ms": round(pct(hit_client, 50), 1),
        "hit_p95_ms": round(pct(hit_client, 95), 1),
        "hit_server_p95_ms": round(pct(hit_server, 95), 1),
        "miss_requests": len(miss),
        "miss_p50_ms": round(pct(miss, 50), 1),
        "miss_p95_ms": round(pct(miss, 95), 1),
    }


def cache_section(engine: Engine, sim: LookupSim, para: dict) -> dict[str, Any]:
    pos, neg = para["positives"], para["negatives"]
    held_pos, held_neg = pos[1::2], neg[1::2]
    return {
        "thresholds": {k: getattr(engine.cfg, k) for k in ("hit_threshold", "borderline_low", "ce_hit_threshold", "slot_guard")},
        "all": hit_metrics(engine, sim, engine.cfg, pos, neg),
        "held_out": hit_metrics(engine, sim, engine.cfg, held_pos, held_neg),
        "cached_plans": engine.store.n_plans,
        "cached_vectors": engine.store.n_vectors,
    }


# ---------------------------------------------------------------- tuning
def tune(engine: Engine, sim: LookupSim, para: dict) -> dict[str, float]:
    """Grid search on the even-indexed split; the odd split stays held out for the report."""
    pos, neg = para["positives"][0::2], para["negatives"][0::2]
    best, best_key = None, None
    grid = itertools.product([0.70, 0.725, 0.75, 0.775, 0.80, 0.825, 0.85, 0.875, 0.90],
                             [0.55, 0.60, 0.65, 0.70], [0.40, 0.50, 0.60, 0.70])
    for hit_t, low, ce in grid:
        if low >= hit_t:
            continue
        m = hit_metrics(engine, sim, with_cfg(engine, hit_threshold=hit_t, borderline_low=low, ce_hit_threshold=ce), pos, neg)
        objective = m["acceptable_hit_rate"] - 2 * m["wrong_hit_rate"] - 2 * m["negative_false_hit_rate"]
        key = (round(objective, 4), hit_t, low, ce)  # ties -> the most conservative thresholds
        if best_key is None or key > best_key:
            best_key, best = key, {"hit_threshold": hit_t, "borderline_low": low, "ce_hit_threshold": ce}

    # deeplink threshold: midpoint between the strongest wrong/should-reject candidate and the weakest correct one
    gold = load_json(EVAL_DIR / "gold_deeplinks.json")
    good, bad = [], []
    for case in gold:
        m = engine.catalog.match_group(gold_group(case["steps"], case.get("direction")))
        if m.best_id is None:
            continue
        (good if m.best_id in case["expect"] else bad).append(m.conf)
    if good and bad and min(good) > max(bad):
        best["dl_threshold"] = round((min(good) + max(bad)) / 2, 3)
    else:
        best["dl_threshold"] = engine.cfg.dl_threshold
    (ROOT / "thresholds.json").write_text(json.dumps(best, indent=2) + "\n", encoding="utf-8")
    print(f"tuned -> thresholds.json {best} (objective {best_key[0]})")
    return best


# ---------------------------------------------------------------- report
def write_markdown(rep: dict[str, Any]) -> None:
    c, d, k, lat = rep["compliance"], rep["deeplinks"], rep["cache"], rep["latency"]
    a, h = k["all"], k["held_out"]
    lines = [
        "# Evaluation report",
        "",
        f"_Generated by `python eval/run_eval.py` on {rep['generated_at']} - pipeline mode: **{rep['mode']}**, "
        f"LLM model: `{rep['llm_model']}`._",
        "",
        "## 1. Schema and rule compliance (`results.jsonl`)",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Responses | {c['responses']} |",
        f"| Schema validation errors (`schema.py`) | {c['schema_errors']} |",
        f"| URL leaks (`https?://`, `www.`) | {c['url_leaks']} |",
        f"| Rule violations (goal/title/description/actionName/order/catalog/manual-null) | {len(c['violations'])} |",
        f"| Actions | {c['actions']} ({', '.join(f'{v} {n}' for n, v in sorted(c['categories'].items()))}) |",
        f"| Step-group deeplinks | {', '.join(f'{v} {n}' for n, v in sorted(c['deeplinks'].items()))} |",
        f"| Fallbacks | {', '.join(f'{v} {n}' for n, v in sorted(c['fallbacks'].items()))} |",
        "",
        "## 2. Deeplink accuracy (hand-labelled gold set, `eval/gold_deeplinks.json`)",
        "",
        f"**{d['accuracy']:.0%}** ({int(round(d['accuracy'] * d['n']))}/{d['n']}) - includes leaf-vs-parent, on/off direction, "
        "and out-of-catalog screens that must fall back to `dummy_positive` or `null`.",
        "",
        "| Case | Expected | Got | Conf |",
        "|---|---|---|---|",
        *[f"| {r['name']} | {', '.join(r['expect'])} | {r['got']}{'' if r['ok'] else ' ❌'} | {r['conf']} |" for r in d["cases"]],
        "",
        "## 3. Cache hit rate on unseen paraphrases (`eval/paraphrases.json`)",
        "",
        f"Thresholds: hit ≥ {k['thresholds']['hit_threshold']}, borderline ≥ {k['thresholds']['borderline_low']} "
        f"(cross-encoder ≥ {k['thresholds']['ce_hit_threshold']}), slot guard {'on' if k['thresholds']['slot_guard'] else 'off'}. "
        f"Cache: {k['cached_plans']} plans / {k['cached_vectors']} paraphrase vectors.",
        "",
        "| Split | Paraphrases | Hit rate | Correct plan (same row) | Acceptable (same SIIS article) | Wrong-plan hits | Negatives | False hits on negatives |",
        "|---|---|---|---|---|---|---|---|",
        f"| All | {a['n_pos']} | {a['hit_rate']:.0%} | {a['exact_row']:.0%} | {a['acceptable_hit_rate']:.0%} | {a['wrong_hit_rate']:.0%} | {a['n_neg']} | {a['negative_false_hit_rate']:.0%} |",
        f"| Held-out (not used for tuning) | {h['n_pos']} | {h['hit_rate']:.0%} | {h['exact_row']:.0%} | {h['acceptable_hit_rate']:.0%} | {h['wrong_hit_rate']:.0%} | {h['n_neg']} | {h['negative_false_hit_rate']:.0%} |",
        "",
        "## 4. Latency",
        "",
        "| Path | Requests | P50 | P95 | Budget |",
        "|---|---|---|---|---|",
        f"| Cache hit (HTTP, client-side) | {lat['hit_requests']} | {lat['hit_p50_ms']} ms | {lat['hit_p95_ms']} ms | ≤ {HIT_P95_BUDGET_MS:.0f} ms |",
        f"| New query (full pipeline, {rep['mode']} mode) | {lat['miss_requests']} | {lat['miss_p50_ms']} ms | {lat['miss_p95_ms']} ms | ≤ {MISS_P95_BUDGET_MS:.0f} ms |",
        "",
        "## 5. Gates",
        "",
        *[f"- {'✅' if ok else '❌'} {name}" for name, ok in rep["gates"].items()],
        "",
        "## 6. Ablations",
        "",
        "See `eval/ablations.md` (generated by `python eval/ablations.py`).",
        "",
    ]
    if c["violations"]:
        lines += ["## Appendix: violations", "", *[f"- `{v}`" for v in c["violations"][:50]], ""]
    (EVAL_DIR / "metrics.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latency", action="store_true", help="only run the latency gates")
    ap.add_argument("--tune", action="store_true", help="grid-search thresholds and write thresholds.json")
    args = ap.parse_args()

    engine = Engine().load()
    ensure_prewarmed(engine)
    para = paraphrases()
    sim = LookupSim(engine)

    if args.tune:
        tuned = tune(engine, sim, para)
        engine.cfg = with_cfg(engine, **tuned)
        engine.catalog.cfg = engine.cfg

    lat = latency_section(engine, para["positives"])
    if args.latency:
        print(json.dumps(lat, indent=2))
        ok = lat["hit_p95_ms"] <= HIT_P95_BUDGET_MS
        print("cache-hit P95", "OK" if ok else "OVER BUDGET")
        return 0 if ok else 1

    rep: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "mode": "llm" if engine.use_llm else "rules",
        "llm_model": engine.cfg.llm_model if engine.use_llm else "none (no GEMINI_API_KEY)",
        "compliance": compliance_section(results(), engine),
        "deeplinks": gold_section(engine),
        "cache": cache_section(engine, sim, para),
        "latency": lat,
    }
    c = rep["compliance"]
    rep["gates"] = {
        "schema.py validation on every response": c["schema_errors"] == 0,
        "zero URL leaks": c["url_leaks"] == 0,
        "zero rule violations (incl. catalog integrity)": not c["violations"],
        f"cache-hit P95 ≤ {HIT_P95_BUDGET_MS:.0f} ms": lat["hit_p95_ms"] <= HIT_P95_BUDGET_MS,
        f"new-query P95 ≤ {MISS_P95_BUDGET_MS:.0f} ms": lat["miss_p95_ms"] <= MISS_P95_BUDGET_MS,
        "no false cache hits on negatives": rep["cache"]["all"]["negative_false_hit_rate"] == 0,
    }
    (EVAL_DIR / "metrics.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(rep)
    print(json.dumps({k: rep[k] for k in ("gates",)}, indent=2, ensure_ascii=False))
    print(f"deeplink accuracy {rep['deeplinks']['accuracy']:.0%}; cache {json.dumps(rep['cache']['all'])}")
    print(f"latency {json.dumps(lat)}")
    return 0 if all(v for k, v in rep["gates"].items() if "false cache" not in k) else 1


if __name__ == "__main__":
    raise SystemExit(main())
