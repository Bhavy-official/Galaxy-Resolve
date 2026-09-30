"""Plan cache: SQLite for plans + paraphrase vectors, in-memory FAISS inner-product index for search.

Each plan is stored under every paraphrase vector (multi-vector cache). Vectors are persisted in SQLite and
the FAISS index is rebuilt from them at startup, so there is a single source of truth on disk.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import faiss
import numpy as np

from app.pipeline.types import Slots

SCHEMA = """
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical TEXT NOT NULL,
    query TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    slots_json TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS vectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES plans(id),
    text TEXT NOT NULL,
    emb BLOB NOT NULL
);
"""


@dataclass
class CachedPlan:
    id: int
    canonical: str
    query: str
    plan: dict[str, Any]
    slots: Slots
    model: str


@dataclass
class VectorHit:
    similarity: float
    plan_id: int
    text: str


class PlanStore:
    def __init__(self, path: Path, dim: int) -> None:
        self.path = Path(path)
        self.dim = dim
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.executescript(SCHEMA)
        self._plans: dict[int, CachedPlan] = {}
        self._rebuild()

    def _rebuild(self) -> None:
        with self._lock:
            self.index = faiss.IndexFlatIP(self.dim)
            self._vec_meta: list[tuple[int, str]] = []
            self._plans = {}
            for pid, canonical, query, plan_json, slots_json, model in self.db.execute(
                "SELECT id, canonical, query, plan_json, slots_json, model FROM plans"
            ):
                self._plans[pid] = CachedPlan(pid, canonical, query, json.loads(plan_json), Slots.from_dict(json.loads(slots_json)), model)
            rows = self.db.execute("SELECT plan_id, text, emb FROM vectors ORDER BY id").fetchall()
            if rows:
                mat = np.vstack([np.frombuffer(r[2], dtype="float32") for r in rows])
                self.index.add(mat)
                self._vec_meta = [(r[0], r[1]) for r in rows]

    @property
    def n_plans(self) -> int:
        return len(self._plans)

    @property
    def n_vectors(self) -> int:
        return self.index.ntotal

    def add(self, canonical: str, query: str, plan: dict[str, Any], slots: Slots, model: str,
            texts: list[str], embs: np.ndarray) -> int:
        embs = np.ascontiguousarray(embs, dtype="float32")
        with self._lock:
            cur = self.db.execute(
                "INSERT INTO plans (canonical, query, plan_json, slots_json, model, created_at) VALUES (?,?,?,?,?,?)",
                (canonical, query, json.dumps(plan, ensure_ascii=False), json.dumps(slots.to_dict()), model, time.time()),
            )
            pid = int(cur.lastrowid)
            self.db.executemany(
                "INSERT INTO vectors (plan_id, text, emb) VALUES (?,?,?)",
                [(pid, t, e.tobytes()) for t, e in zip(texts, embs)],
            )
            self.db.commit()
            self._plans[pid] = CachedPlan(pid, canonical, query, plan, slots, model)
            self.index.add(embs)
            self._vec_meta.extend((pid, t) for t in texts)
        return pid

    def search(self, qvec: np.ndarray, k: int = 8) -> list[VectorHit]:
        with self._lock:
            if self.index.ntotal == 0:
                return []
            sims, idxs = self.index.search(np.ascontiguousarray(qvec.reshape(1, -1), dtype="float32"), min(k, self.index.ntotal))
            return [VectorHit(float(s), self._vec_meta[i][0], self._vec_meta[i][1]) for s, i in zip(sims[0], idxs[0]) if i >= 0]

    def search_many(self, qvecs: np.ndarray, k: int = 8) -> list[VectorHit]:
        """Search with several views of one query; keep each stored vector's best similarity."""
        best: dict[tuple[int, str], VectorHit] = {}
        for v in np.atleast_2d(qvecs):
            for h in self.search(v, k):
                key = (h.plan_id, h.text)
                if key not in best or h.similarity > best[key].similarity:
                    best[key] = h
        return sorted(best.values(), key=lambda h: -h.similarity)[:k]

    def get(self, plan_id: int) -> Optional[CachedPlan]:
        return self._plans.get(plan_id)

    def clear(self) -> None:
        with self._lock:
            self.db.execute("DELETE FROM vectors")
            self.db.execute("DELETE FROM plans")
            self.db.commit()
            self._rebuild()

    def close(self) -> None:
        self.db.close()
