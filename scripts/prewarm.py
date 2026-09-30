"""Run every provided query offline through the full pipeline, fill the cache, and write results.jsonl.

    python scripts/prewarm.py            # keep existing cache entries
    python scripts/prewarm.py --reset    # clear the cache first
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.pipeline.enrich import rules_enrich  # noqa: E402


def load_rows() -> list[dict]:
    raw = json.loads(settings.siis_path.read_text(encoding="utf-8"))
    return raw["responses"] if isinstance(raw, dict) else raw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="clear the plan cache before prewarming")
    ap.add_argument("--out", default=str(settings.results_path))
    args = ap.parse_args()

    engine = Engine().load()
    if args.reset:
        engine.store.clear()
    rows = load_rows()
    t0 = time.perf_counter()
    with open(args.out, "w", encoding="utf-8") as f:
        for row in rows:
            q = row["original_query"]
            resp = engine.troubleshoot(q, row.get("siis_response"), use_cache=False)
            # 8-10 deterministic, diverse variations per query (official scoring: 5 pts)
            variations = rules_enrich(q, (row.get("siis_response") or {}).get("title", "")).paraphrases
            f.write(json.dumps({"id": row["id"], "query": q, "query_variations": variations,
                                "response": resp}, ensure_ascii=False) + "\n")
            m = resp["meta"]
            n = sum(len(g["actions"]) for g in resp["contexts"])
            print(f"{row['id']:<7} actions={n} fallback={m['fallback']} model={m['model']} "
                  f"cost=${m['cost_usd']:.4f} {m['latency_ms']:.0f}ms"
                  + (f" VIOLATIONS={len(m['violations'])}" if m.get("violations") else ""))
    print(f"prewarmed {len(rows)} queries in {time.perf_counter() - t0:.1f}s; cache now "
          f"{engine.store.n_plans} plans / {engine.store.n_vectors} vectors; LLM spend ${engine.llm.totals.cost_usd:.4f}")


if __name__ == "__main__":
    main()