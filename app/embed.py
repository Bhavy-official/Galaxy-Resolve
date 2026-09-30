"""Local models loaded once at startup: bi-encoder embeddings + two cross-encoders."""
from __future__ import annotations

import os
import threading

import numpy as np

from app.config import Settings, settings as default_settings

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


class LocalModels:
    def __init__(self, cfg: Settings = default_settings) -> None:
        self.cfg = cfg
        self._lock = threading.Lock()
        self.embedder = None
        self.reranker = None
        self.paraphrase_ce = None

    @property
    def ready(self) -> bool:
        return self.embedder is not None and self.reranker is not None and self.paraphrase_ce is not None

    def load(self) -> "LocalModels":
        with self._lock:
            if self.ready:
                return self
            import torch
            from sentence_transformers import CrossEncoder, SentenceTransformer

            torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
            self.embedder = SentenceTransformer(self.cfg.embed_model, device="cpu")
            self.reranker = CrossEncoder(self.cfg.rerank_model, device="cpu")
            self.paraphrase_ce = CrossEncoder(
                self.cfg.paraphrase_ce_model, device="cpu", tokenizer_args={"use_fast": False}
            )
            self.encode(["warmup"])
            self.rerank([("warmup", "warmup")])
            self.paraphrase_score([("warmup", "warmup")])
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self.embedder.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype="float32")

    def rerank(self, pairs: list[tuple[str, str]]) -> np.ndarray:
        """Query-passage relevance in [0, 1] (sigmoid of ms-marco logits)."""
        if not pairs:
            return np.zeros(0, dtype="float32")
        logits = np.asarray(self.reranker.predict(pairs, show_progress_bar=False), dtype="float32")
        return 1.0 / (1.0 + np.exp(-logits))

    def paraphrase_score(self, pairs: list[tuple[str, str]]) -> np.ndarray:
        """Semantic-equivalence score in [0, 1] (STS-B cross-encoder)."""
        if not pairs:
            return np.zeros(0, dtype="float32")
        return np.asarray(self.paraphrase_ce.predict(pairs, show_progress_bar=False), dtype="float32")


_shared: LocalModels | None = None


def get_models(cfg: Settings = default_settings) -> LocalModels:
    global _shared
    if _shared is None:
        _shared = LocalModels(cfg)
    return _shared
