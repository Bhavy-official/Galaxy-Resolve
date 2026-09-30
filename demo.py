"""Interactive demo: run the troubleshooting engine on the provided queries.

Usage:
    python demo.py                  # first provided query
    python demo.py 3                # 4th provided query (0-based)
    python demo.py --query "my screen flickers"   # custom query (rules mode, needs SIIS text)

Requires: pip install -r requirements.txt, then python scripts/build_index.py (once).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.engine import Engine  # noqa: E402

CAT_ICON = {"auto": "⚡", "manual": "✋", "critical": "⚠️"}


def show(resp: dict) -> None:
    meta = resp.get("meta", {})
    print(f"\n  latency: {meta.get('latency_ms', 0):.0f} ms   cache_hit: {meta.get('cache_hit')}   "
          f"model: {meta.get('model')}   cost: ${meta.get('cost_usd', 0):.5f}")
    if meta.get("fallback"):
        print(f"  fallback: {meta['fallback']}")
    for ctx in resp.get("contexts", []):
        print(f"\n  GOAL: {ctx.get('goal')}")
        for a in ctx.get("actions", []):
            icon = CAT_ICON.get(a.get("category"), "•")
            print(f"\n  {icon} [{a.get('category')}] {a.get('actionName')}  (score {a.get('score', 0):.2f})")
            print(f"     {a.get('description')}  — {a.get('title')}")
            for i, s in enumerate(a.get("steps", []), 1):
                print(f"       {i}. {s}")
            dl = (a.get("actionableDeeplink") or {})
            if dl.get("deeplink"):
                print(f"     ↳ deeplink: {dl['deeplink']}")
    print()


def main() -> None:
    rows = json.loads(settings.siis_path.read_text(encoding="utf-8"))["responses"]
    if "--query" in sys.argv:
        q = sys.argv[sys.argv.index("--query") + 1]
        siis = None
    else:
        idx = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0
        row = rows[idx % len(rows)]
        q, siis = row["original_query"], row.get("siis_response")
        print(f"Query {idx}: {q}")

    engine = Engine().load()
    resp = engine.troubleshoot(q, siis)
    print(f"\nQuery: {q}")
    show(resp)


if __name__ == "__main__":
    main()
