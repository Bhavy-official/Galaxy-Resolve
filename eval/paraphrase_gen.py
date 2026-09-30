"""Generate extra *unseen* paraphrases with Gemini for hit-rate testing -> eval/paraphrases_llm.json.

Uses a different prompt from the enrich step so the test set does not mirror what was cached.
Without GEMINI_API_KEY this exits cleanly; the hand-written eval/paraphrases.json is always used.
"""
from __future__ import annotations

import json
import sys

from pydantic import BaseModel

from common import EVAL_DIR, siis_rows  # type: ignore[import-not-found]

from app.llm import LLMClient, LLMError


class _Out(BaseModel):
    paraphrases: list[str]


SYSTEM = """You write test inputs for a phone-support search engine.
Given a customer complaint, write 3 messages a different customer with the same problem might send.
Use your own words: vary vocabulary, length and tone, and never copy phrases from the original."""


def main() -> int:
    llm = LLMClient()
    if not llm.available:
        print("GEMINI_API_KEY not set - skipping LLM paraphrase generation (hand-written set still used).")
        return 0
    out = {"positives": [], "negatives": []}
    for row in siis_rows():
        try:
            res, _ = llm.structured(SYSTEM, f"Complaint: {row['original_query']}", _Out, max_tokens=600)
        except LLMError as exc:
            print(f"{row['id']}: {exc}")
            continue
        out["positives"] += [{"row": row["id"], "text": t} for t in res.paraphrases[:3]]
    (EVAL_DIR / "paraphrases_llm.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(out['positives'])} paraphrases; spend ${llm.totals.cost_usd:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
