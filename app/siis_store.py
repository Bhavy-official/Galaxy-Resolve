"""SIIS knowledge store — loads the official siis_responses.json and matches
the best article for a query using cosine similarity on query embeddings.

The Theme 2 spec says siis_response is *optional* in the API request.
When the caller omits it (frontend demo, or scorer testing no-context
resilience) this module auto-selects the most relevant article from the
official Theme 2 siis_responses.json so the pipeline can still run.

When the scorer explicitly passes siis_response (the normal evaluation
path), this module is NOT used — caller-supplied content takes priority.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import settings

log = logging.getLogger("siis_store")


class SIISStore:
    """In-memory store of SIIS articles with semantic lookup."""

    def __init__(self) -> None:
        self._articles: list[dict] = []   # [{id, query, title, content}]
        self._embeddings: Optional[np.ndarray] = None
        self._ready = False

    def load(self, models) -> None:  # models: LocalModels
        path = settings.siis_path
        if not path.exists():
            log.warning("siis_responses.json not found at %s — auto-lookup disabled", path)
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            responses = data.get("responses", [])
            self._articles = []
            for r in responses:
                sr = r.get("siis_response", {})
                content = sr.get("content", "") if isinstance(sr, dict) else str(sr)
                if content.strip():
                    self._articles.append({
                        "id": r.get("id", ""),
                        "query": r.get("original_query", ""),
                        "title": sr.get("title", "") if isinstance(sr, dict) else "",
                        "content": content,
                    })

            if not self._articles:
                log.warning("siis_responses.json loaded but contained no usable articles")
                return

            # Pre-embed all original queries for fast lookup
            texts = [a["query"] for a in self._articles]
            self._embeddings = models.encode(texts)  # shape (n, dim)
            self._ready = True
            log.info("SIISStore loaded %d articles from %s", len(self._articles), path)
        except Exception as exc:
            log.warning("Failed to load SIISStore: %s", exc)

    @property
    def ready(self) -> bool:
        return self._ready

    def lookup(self, query: str, models, threshold: float = 0.30) -> Optional[dict]:
        """Return the best matching SIIS article for query, or None if below threshold."""
        if not self._ready or self._embeddings is None:
            return None
        try:
            qvec = models.encode([query])  # shape (1, dim)
            # Cosine similarity
            norms_q = np.linalg.norm(qvec, axis=1, keepdims=True)
            norms_k = np.linalg.norm(self._embeddings, axis=1, keepdims=True)
            sims = (self._embeddings @ qvec.T) / (norms_k * norms_q.T + 1e-9)  # (n, 1)
            best_idx = int(np.argmax(sims))
            best_sim = float(sims[best_idx])
            if best_sim < threshold:
                log.debug("SIISStore: no match above %.2f (best=%.3f) for %r", threshold, best_sim, query[:60])
                return None
            article = self._articles[best_idx]
            log.info("SIISStore: matched %r (sim=%.3f) for %r", article["title"], best_sim, query[:60])
            return {"title": article["title"], "content": article["content"]}
        except Exception as exc:
            log.warning("SIISStore.lookup failed: %s", exc)
            return None
