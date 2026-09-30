"""Deeplink catalog + hybrid retrieval (BM25 + dense, RRF, cross-encoder rerank, leaf preference).

Matching uses description / message / qna_description / validation key - never the masked URI.
URIs are only ever copied verbatim from the catalog; anything else is `voiceassist://dummy_positive` or null.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
from rank_bm25 import BM25Okapi

from app.config import Settings, settings as default_settings
from app.embed import LocalModels
from app.pipeline.path_parser import is_settings_root, leaf_screen, screen_name, strip_terminal
from app.pipeline.textutil import content_tokens, stem, stems, title_case
from app.pipeline.types import GroupDraft

DUMMY_URI = "voiceassist://dummy_positive"
DEPTH_DECAY = 0.85  # weight of a path element one level shallower than the leaf
_GENERIC = {"settings", "setting", "device", "view", "page", "open", "opens", "via", "enable", "enables", "disable",
            "disables", "update", "updates", "adjust", "specified", "value", "screen", "check", "configure"}


@dataclass
class DeeplinkMatch:
    kind: str  # catalog | dummy | none
    conf: float
    entry: Optional[dict[str, Any]] = None
    actionable: Optional[dict[str, Any]] = None
    validation: Optional[dict[str, Any]] = None
    query: str = ""
    best_id: Optional[str] = None  # top-scoring catalog candidate, even when rejected by the threshold


def _doc_text(e: dict[str, Any]) -> str:
    key = (e.get("validation") or {}).get("key") or ""
    return " . ".join(x for x in (key, e.get("message") or "", e.get("description") or "", e.get("qna_description") or "") if x)


def _focus_text(e: dict[str, Any]) -> str:
    """The parts that name the concrete setting (used for leaf/parent matching)."""
    key = (e.get("validation") or {}).get("key") or ""
    desc = re.sub(r"\b(opens|the|settings? page|in device settings|on the device|via device settings|"
                  r"to a specified value|enables|disables|updates)\b", " ", (e.get("description") or "").lower())
    return f"{key} {desc}"


class Catalog:
    def __init__(self, path: Path, models: LocalModels, cfg: Settings = default_settings) -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = raw["deeplinks"] if isinstance(raw, dict) else raw
        self.cfg = cfg
        self.models = models
        self.dummy = next((e for e in entries if e["deeplink"] == DUMMY_URI), None)
        self.entries = [e for e in entries if e["deeplink"] != DUMMY_URI]
        self.uris = {e["deeplink"] for e in entries}
        self.all_uris = self.uris | {(e.get("validation") or {}).get("deeplink") for e in entries} - {None}
        self.by_id = {e["id"]: e for e in self.entries}
        self.docs = [_doc_text(e) for e in self.entries]
        self.focus_stems = [stems(_focus_text(e)) - _GENERIC for e in self.entries]
        self.key_stems = [
            stems(re.sub(r"\([^)]*\)", " ", (e.get("validation") or {}).get("key") or e.get("message") or "")) - _GENERIC
            for e in self.entries
        ]
        self.bm25 = BM25Okapi([[stem(t) for t in content_tokens(d)] for d in self.docs])
        self.emb = self._load_or_build_embeddings(path)

    def _load_or_build_embeddings(self, path: Path) -> np.ndarray:
        digest = hashlib.sha1(("\n".join(self.docs) + self.cfg.embed_model).encode("utf-8")).hexdigest()[:16]
        cache = self.cfg.index_dir / f"deeplinks_{digest}.npy"
        if cache.exists():
            return np.load(cache)
        emb = self.models.encode(self.docs)
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache, emb)
        return emb

    def is_valid_uri(self, uri: Optional[str]) -> bool:
        return uri is None or uri == DUMMY_URI or uri in self.uris

    # ------------------------------------------------------------ retrieval
    def candidates(self, query: str, k: int) -> list[int]:
        q_tokens = [stem(t) for t in content_tokens(query)]
        bm = self.bm25.get_scores(q_tokens) if q_tokens else np.zeros(len(self.entries))
        dense = self.emb @ self.models.encode([query])[0]
        rank_bm = np.argsort(-bm)[: k * 2]
        rank_dn = np.argsort(-dense)[: k * 2]
        rrf: dict[int, float] = {}
        for ranks in (rank_bm, rank_dn):
            for r, idx in enumerate(ranks):
                rrf[int(idx)] = rrf.get(int(idx), 0.0) + 1.0 / (self.cfg.rrf_k + r + 1)
        return [i for i, _ in sorted(rrf.items(), key=lambda kv: -kv[1])[:k]]

    def score_candidates(
        self, query: str, elements: list[str], direction: Optional[str], idxs: list[int]
    ) -> list[tuple[int, float]]:
        """elements: screen path from root to leaf (Settings root removed).

        specificity = max over path elements of depth_weight * coverage, so a candidate that only names a
        parent menu ("Display") scores below one that names the leaf ("Navigation bar").
        """
        if not idxs:
            return []
        rel = self.models.rerank([(query, self.docs[i]) for i in idxs])
        el_stems = [stems(x) - _GENERIC for x in elements]
        n = len(el_stems)
        weights = [DEPTH_DECAY ** (n - 1 - d) for d in range(n)]
        query_st = stems(query) - _GENERIC
        scored = []
        for i, r in zip(idxs, rel):
            e, focus, key = self.entries[i], self.focus_stems[i], self.key_stems[i]
            specificity = max(
                (w * len(st & focus) / len(st) for st, w in zip(el_stems, weights) if st), default=0.0
            )
            # squared: every qualifier the query didn't ask for ("Auto factory reset") costs a lot
            key_prec = (len(key & query_st) / len(key)) ** 2 if key else 0.0
            s = 0.4 * float(r) + 0.3 * specificity + 0.3 * key_prec
            ot = (e.get("originalType") or "").lower()
            if direction == "on" and ot == "offurl" or direction == "off" and ot == "onurl":
                s -= 0.25
            elif direction in ("on", "off") and ot == f"{direction}url":
                s += 0.05
            elif direction is None and ot == "onclickurl":
                s += 0.03
            if not ot:  # status getters ("Retrieves ...") are not actionable screens
                s -= 0.1
            scored.append((i, s))
        return sorted(scored, key=lambda t: -t[1])

    def match_group(self, group: GroupDraft, context: str = "") -> DeeplinkMatch:
        path = [p for p in strip_terminal(group.path) if not is_settings_root([p])]
        leaf = leaf_screen(group)
        if not path and not leaf:
            return DeeplinkMatch("none", 0.0)
        elements = list(dict.fromkeys([*path, leaf] if leaf else path))
        # Full screen path, no verb: direction is scored separately against originalType.
        query = " ".join(elements)
        scored = self.score_candidates(query, elements, group.direction, self.candidates(query, self.cfg.dl_candidates))
        best_i, best_s = scored[0] if scored else (-1, 0.0)
        best_s = float(max(0.0, min(1.0, best_s)))
        settings_path = is_settings_root(group.path)
        need = self.cfg.dl_threshold + (0.0 if settings_path else self.cfg.dl_nonsettings_margin)
        best_id = self.entries[best_i]["id"] if best_i >= 0 else None
        if best_i >= 0 and best_s >= need:
            e = self.entries[best_i]
            return DeeplinkMatch("catalog", best_s, e, actionable_payload(e), validation_payload(e), query, best_id)
        screen = screen_name(group)
        if settings_path and screen:  # the steps clearly open a real Settings screen that the catalog lacks
            return DeeplinkMatch("dummy", best_s, None, dummy_payload(screen), None, query, best_id)
        return DeeplinkMatch("none", best_s, query=query, best_id=best_id)


def actionable_payload(e: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"deeplink": e["deeplink"], "description": e.get("description") or "", "message": e.get("message") or ""}
    if e.get("originalType"):
        out["originalType"] = e["originalType"]
    return out


def validation_payload(e: dict[str, Any]) -> Optional[dict[str, Any]]:
    v = e.get("validation")
    if not v or not v.get("deeplink") or not v.get("key"):
        return None
    out = {"deeplink": v["deeplink"], "key": v["key"]}
    for k in ("resultType", "condition", "value"):
        if v.get(k) is not None:
            out[k] = v[k]
    return out


def dummy_payload(screen: str) -> dict[str, Any]:
    """Placeholder entry: description/message are written by code, 5-7 words, naming the concrete screen."""
    words = re.sub(r"[^\w\s'-]", " ", screen).split() or ["Relevant"]
    for n in (len(words), 3, 2, 1):
        name = title_case(" ".join(words[:n]))
        for d, m in ((f"Opens the {name} screen in Settings", f"Open the {name} screen in Settings"),
                     (f"Opens {name} in device Settings", f"Open {name} in device Settings"),
                     (f"Opens the {name} settings screen", f"Open the {name} settings screen")):
            if 5 <= len(d.split()) <= 7 and 5 <= len(m.split()) <= 7:
                return {"deeplink": DUMMY_URI, "description": d, "message": m, "originalType": "placeholder"}
    return {"deeplink": DUMMY_URI, "description": "Opens the relevant screen in Settings",
            "message": "Open the relevant screen in Settings", "originalType": "placeholder"}
