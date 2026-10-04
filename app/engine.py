"""Pipeline orchestrator: cache fast path -> (miss) enrich + extract -> ground -> parse -> link -> order -> validate."""
from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor

from app.siis_store import SIISStore
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel

from app.cache.slots import extract_slots, merge_slots, slots_compatible
from app.cache.store import CachedPlan, PlanStore
from app.config import Settings, settings as default_settings
from app.embed import LocalModels, get_models
from app.llm import LLMClient, LLMError, Usage
from app.pipeline import compliance
from app.pipeline.deeplinks import Catalog
from app.pipeline.enrich import llm_enrich, rules_enrich
from app.pipeline.extract import (
    LLMSectionLabel,
    clean_content,
    is_numbered_procedure,
    llm_extract,
    parse_sections,
    rules_extract,
)
from app.pipeline.grounding import ground_steps
from app.pipeline.ordering import apply_categories
from app.pipeline.path_parser import build_actions, screen_name
from app.pipeline.textutil import is_verb_led, normalize_complaint
from app.pipeline.types import ActionDraft, CandidateStep, Enrichment, Section
from app.pipeline.validators import (
    enforce_action_name,
    enforce_description,
    enforce_title,
    goal_text,
    is_valid_description,
    is_valid_step,
    normalize_description,
    normalize_step,
    scrub_tree,
)
from app.schema import ContextDeeplinkResponse

log = logging.getLogger("engine")


class _Repair(BaseModel):
    index: int
    description: str


class _RepairBatch(BaseModel):
    descriptions: list[_Repair]


REPAIR_SYSTEM = """Rewrite each action description so it starts with "It will" and has 5 to 7 words in total.
Keep the meaning. Return one item per input index."""


class Engine:
    def __init__(
        self,
        cfg: Settings = default_settings,
        llm: Optional[LLMClient] = None,
        models: Optional[LocalModels] = None,
        store: Optional[PlanStore] = None,
    ) -> None:
        self.cfg = cfg
        self.llm = llm if llm is not None else LLMClient(cfg)
        self.models = models or get_models(cfg)
        self.store = store
        self.catalog: Optional[Catalog] = None
        self.siis_store: SIISStore = SIISStore()
        self._pool = ThreadPoolExecutor(max_workers=4)

    # ------------------------------------------------------------ lifecycle
    def load(self) -> "Engine":
        self.models.load()
        self.catalog = Catalog(self.cfg.deeplinks_path, self.models, self.cfg)
        if self.store is None:
            dim = int(self.models.encode(["dim"]).shape[1])
            self.store = PlanStore(self.cfg.cache_db, dim)
        # Load official SIIS knowledge base for auto-lookup when caller omits siis_response
        self.siis_store.load(self.models)
        return self

    @property
    def ready(self) -> bool:
        return self.models.ready and self.catalog is not None and self.store is not None

    @property
    def use_llm(self) -> bool:
        return self.llm.available and self.cfg.pipeline_mode != "rules"

    # ------------------------------------------------------------ public entry
    def troubleshoot(
        self, query: str, siis: Optional[dict[str, Any]] = None, use_cache: bool = True, write_cache: bool = True
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        query = (query or "").strip()
        if use_cache and query:
            hit = self.lookup(query)
            if hit is not None:
                plan, sim = hit
                return self._respond(plan.plan, t0, cache_hit=True, model=plan.model, similarity=sim)
        content = (siis or {}).get("content") or ""
        if not content.strip():
            if siis is None:
                # Caller did not supply siis_response (optional per spec).
                # Auto-lookup the best matching article from the official SIIS knowledge base.
                auto = self.siis_store.lookup(query, self.models) if self.siis_store.ready else None
                if auto:
                    siis = auto
                    content = auto["content"]
                    log.info("Auto-matched SIIS article %r for query %r", auto.get("title"), query[:60])
                else:
                    return self._respond({"contexts": []}, t0, cache_hit=False, model="none", fallback="no_siis_context")
            else:
                return self._respond({"contexts": []}, t0, cache_hit=False, model="none", fallback="no_siis_context")

        from app.pipeline.mismatch import is_mismatched_article
        if is_mismatched_article(query, content, (siis or {}).get("title") or ""):
            return self._respond({"contexts": []}, t0, cache_hit=False, model="none", fallback="no_match")

        resp, info = self.generate(query, siis or {})

        if write_cache and resp["contexts"] and not info["violations"]:
            self._write_cache(query, resp, info)
        return self._respond(resp, t0, cache_hit=False, **info["meta"])

    # ------------------------------------------------------------ fast path (no LLM)
    def lookup(self, query: str) -> Optional[tuple[CachedPlan, float]]:
        norm = normalize_complaint(query)
        vecs = self.models.encode([query, norm] if norm and norm != query else [query])
        qslots = extract_slots(query)
        borderline: list[tuple[CachedPlan, float, str]] = []
        seen: set[int] = set()
        for h in self.store.search_many(vecs, k=10):
            if h.similarity < self.cfg.borderline_low:
                break
            if h.plan_id in seen:
                continue
            plan = self.store.get(h.plan_id)
            if plan is None or (self.cfg.slot_guard and not slots_compatible(qslots, plan.slots)):
                continue
            seen.add(h.plan_id)
            if h.similarity >= self.cfg.hit_threshold:
                return plan, h.similarity
            borderline.append((plan, h.similarity, h.text))
        if borderline:  # cross-encoder decides borderline scores
            borderline = borderline[:3]
            scores = self.models.paraphrase_score([(query, t) for _, _, t in borderline])
            best = int(np.argmax(scores))
            if scores[best] >= self.cfg.ce_hit_threshold:
                return borderline[best][0], borderline[best][1]
        return None

    # ------------------------------------------------------------ slow path
    def generate(self, query: str, siis: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        usage = Usage(model=self.llm.model if self.use_llm else "rules")
        degraded: list[str] = []
        content, title = siis.get("content") or "", siis.get("title") or ""
        sections = parse_sections(content, title)

        # [0] enrich and [1] extract are independent -> run concurrently
        enrich_f = self._pool.submit(self._enrich, query, title, usage, degraded)
        steps, labels = self._extract(query, content, sections, usage, degraded)
        enrichment: Enrichment = enrich_f.result()

        kept, dropped = ground_steps(steps, content)
        meta = {
            "model": usage.model if usage.calls else "rules",
            "cost_usd": round(usage.cost_usd, 6),
            "tokens": {"input": usage.input_tokens, "output": usage.output_tokens},
            "mode": "llm" if self.use_llm and not degraded else ("rules" if not self.use_llm else "degraded"),
            "grounding": {"kept": len(kept), "dropped": len(dropped)},
        }
        if degraded:
            meta["degraded"] = degraded
        if not kept:
            return {"contexts": []}, {"violations": [], "meta": {**meta, "fallback": "no_match"}, "enrichment": enrichment}

        actions = self._assemble(query, kept, labels, usage)
        if not actions:
            return {"contexts": []}, {"violations": [], "meta": {**meta, "fallback": "no_match"}, "enrichment": enrichment}

        title_text, title_ok = enforce_title(enrichment.title)
        passes = [title_ok] + [a.desc_ok for a in actions]  # LLM drafts that passed without repair
        pass_rate = sum(passes) / len(passes) if self.use_llm else 1.0
        plan_text = " ".join([a.name for a in actions] + [s.text for a in actions for g in a.groups for s in g.steps][:20])
        q_emb, p_emb = self.models.encode([query, plan_text])
        relevance = float(q_emb @ p_emb)
        score = round(max(0.0, min(1.0, (1 + relevance) / 2 * pass_rate)), 2)

        goal = {
            "goal": goal_text(enrichment.topic, enrichment.kind),
            "title": title_text,
            "score": score,
            "actions": [self._action_dict(a) for a in actions],
        }
        resp = scrub_tree({"contexts": [goal]})
        ContextDeeplinkResponse.model_validate(resp)  # contract check (raises on drift)
        errs = compliance.violations(resp, self.catalog.all_uris)
        meta.update({"cost_usd": round(usage.cost_usd, 6), "tokens": {"input": usage.input_tokens, "output": usage.output_tokens}})
        if usage.calls:
            meta["model"] = usage.model
        if errs:
            log.warning("plan failed compliance, not caching: %s", errs[:5])
            meta["violations"] = errs
        return resp, {"violations": errs, "meta": meta, "enrichment": enrichment}

    # ------------------------------------------------------------ stages
    def _enrich(self, query: str, title: str, usage: Usage, degraded: list[str]) -> Enrichment:
        if self.use_llm:
            try:
                e, u = llm_enrich(query, title, self.llm)
                usage.add(u)
                return e
            except LLMError as exc:
                log.warning("enrich LLM failed, using rules: %s", exc)
                degraded.append("enrich")
        return rules_enrich(query, title)

    def _extract(
        self, query: str, content: str, sections: list[Section], usage: Usage, degraded: list[str]
    ) -> tuple[list[CandidateStep], dict[int, LLMSectionLabel]]:
        if self.use_llm:
            try:
                steps, labels, u = llm_extract(query, sections, self.llm)
                usage.add(u)
                return steps, labels
            except LLMError as exc:
                log.warning("extract LLM failed, using rules: %s", exc)
                degraded.append("extract")
        return rules_extract(self._relevant_sections(query, content, sections)), {}

    def _relevant_sections(self, query: str, content: str, sections: list[Section]) -> list[Section]:
        """Rules mode has no LLM to judge relevance: keep numbered procedures whole, else the closest
        sections among those that actually contain steps."""
        with_steps = {st.section for st in rules_extract(sections)}
        sections = [s for s in sections if s.idx in with_steps]
        if is_numbered_procedure(content) or len(sections) <= 2:
            return sections
        embs = self.models.encode([query] + [f"{s.title}. {s.text[:600]}" for s in sections])
        sims = embs[1:] @ embs[0]
        best = float(sims.max())
        keep = {i for i, s in enumerate(sims) if s >= max(0.2, best - 0.12)}
        top = sorted(keep, key=lambda i: -sims[i])[:4]
        return [sections[i] for i in sorted(top)]

    def _assemble(self, query: str, steps: list[CandidateStep], labels: dict[int, LLMSectionLabel], usage: Usage) -> list[ActionDraft]:
        actions = build_actions(steps, self.cfg.max_steps_per_group)
        per_section: dict[int, int] = {}
        for a in actions:
            per_section[a.section] = per_section.get(a.section, 0) + 1
        out: list[ActionDraft] = []
        for a in actions:
            for g in a.groups:
                seen: set[str] = set()
                clean = []
                for st in g.steps:
                    st.text = normalize_step(st.text)
                    if is_valid_step(st.text) and st.text.lower() not in seen:
                        seen.add(st.text.lower())
                        clean.append(st)
                g.steps = clean
            a.groups = [g for g in a.groups if g.steps]
            if not a.groups:
                continue
            lab = labels.get(a.section)
            if lab and per_section[a.section] == 1:
                a.name, a.description, a.from_llm_label = lab.action_name, lab.description, True
            a.name = enforce_action_name(a.name)
            out.append(a)

        # relevance to the query decides which actions survive the cap
        if out:
            texts = [f"{a.name}. " + " ".join(s.text for g in a.groups for s in g.steps) for a in out]
            embs = self.models.encode([query] + texts)
            for a, sim in zip(out, embs[1:] @ embs[0]):
                a.relevance = float(sim)
            if len(out) > self.cfg.max_actions:
                keep = set(sorted(range(len(out)), key=lambda i: -out[i].relevance)[: self.cfg.max_actions])
                out = [a for i, a in enumerate(out) if i in keep]

        for a in out:
            for g in a.groups:
                m = self.catalog.match_group(g)
                g.dl_kind, g.dl_conf, g.actionable, g.validation = m.kind, m.conf, m.actionable, m.validation
                g.dl_id = m.entry["id"] if m.entry else None
            self._label_from_deeplink(a)
        out = self._drop_conflicting_toggles(out)
        out = apply_categories(out)
        self._finalize_descriptions(out, usage)
        return out

    _OT_VERB = {"onurl": ("Turn On", "turn on {}"), "offurl": ("Turn Off", "turn off {}"),
                "onclickurl": ("Open", "open the {} settings"), "updateurl": ("Adjust", "adjust the {} setting")}

    def _label_from_deeplink(self, a: ActionDraft) -> None:
        """Name/verb phrase from the matched catalog entry when the section heading is not an action."""
        g = next((g for g in a.groups if g.dl_kind == "catalog"), None)
        if g is not None:
            e = self.catalog.by_id[g.dl_id]
            key = (e.get("validation") or {}).get("key") or re.sub(r"^(enable|disable|view|adjust)\s+", "", e.get("message") or "", flags=re.I)
            key = re.sub(r"\s*\([^)]*\)", "", key).strip()
            verb, phrase = self._OT_VERB.get((e.get("originalType") or "").lower(), ("Open", "open the {} settings"))
            a.verb_phrase = phrase.format(key.lower() if not any(c.isupper() for c in key[1:]) else key)
            if not a.from_llm_label and (not is_verb_led(a.name) or a.name.startswith(("Adjust ", "Turn ", "Open "))):
                a.name = enforce_action_name(f"{verb} {key}")
            return
        g = next((g for g in a.groups if g.dl_kind == "dummy"), None)
        if g is not None:
            screen = screen_name(g) or "relevant"
            a.verb_phrase = f"open the {screen} settings"

    @staticmethod
    def _drop_conflicting_toggles(actions: list[ActionDraft]) -> list[ActionDraft]:
        """Two actions driving the same setting (enable vs disable) confuse users: keep the more relevant one."""
        best: dict[str, ActionDraft] = {}
        for a in actions:
            for g in a.groups:
                key = (g.validation or {}).get("key")
                if key and (key not in best or a.relevance > best[key].relevance):
                    best[key] = a
        losers = {id(a) for a in actions for g in a.groups
                  if (g.validation or {}).get("key") and best[(g.validation or {})["key"]] is not a}
        return [a for a in actions if id(a) not in losers]

    def _finalize_descriptions(self, actions: list[ActionDraft], usage: Usage) -> None:
        """Validate -> one batched LLM repair -> template fallback. a.description=None marks 'did not pass first try'."""
        drafts = {i: normalize_description(a.description or "") for i, a in enumerate(actions)}
        failing = [i for i, d in drafts.items() if d and not is_valid_description(d)]
        repaired: dict[int, str] = {}
        if failing and self.use_llm:
            prompt = "\n".join(f"{i}: {drafts[i]} (action: {actions[i].name})" for i in failing)
            try:
                out, u = self.llm.structured(REPAIR_SYSTEM, prompt, _RepairBatch, max_tokens=800)
                usage.add(u)
                repaired = {r.index: r.description for r in out.descriptions}
            except LLMError as exc:
                log.warning("description repair failed: %s", exc)
        for i, a in enumerate(actions):
            a.desc_ok = is_valid_description(drafts[i])
            a.description, _ = enforce_description(
                drafts[i] if a.desc_ok else repaired.get(i, ""), a.name, verb_phrase=a.verb_phrase
            )

    @staticmethod
    def _action_dict(a: ActionDraft) -> dict[str, Any]:
        return {
            "actionName": a.name,
            "description": a.description,
            "stepGroups": [
                {"steps": [s.text for s in g.steps], "actionableDeeplink": g.actionable, "validationDeeplink": g.validation}
                for g in a.groups
            ],
            "category": a.category,
        }

    # ------------------------------------------------------------ cache + response
    def _write_cache(self, query: str, resp: dict[str, Any], info: dict[str, Any]) -> None:
        e: Enrichment = info["enrichment"]
        texts = list(dict.fromkeys([query, normalize_complaint(query), e.canonical, *e.paraphrases]))
        embs = self.models.encode(texts)
        slots = merge_slots(extract_slots(query), extract_slots(e.canonical), e.slots)
        self.store.add(e.canonical, query, resp, slots, info["meta"].get("model", "rules"), texts, embs)

    @staticmethod
    def _respond(plan: dict[str, Any], t0: float, cache_hit: bool, model: str, fallback: Optional[str] = None,
                 similarity: Optional[float] = None, **extra: Any) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "cache_hit": cache_hit,
            "model": model,
            "cost_usd": extra.pop("cost_usd", 0.0),
            "fallback": fallback if fallback else (None if plan.get("contexts") else "no_match"),
        }
        if similarity is not None:
            meta["similarity"] = round(similarity, 4)
        meta.update({k: v for k, v in extra.items() if k != "fallback"})
        if extra.get("fallback"):
            meta["fallback"] = extra["fallback"]
        return {"contexts": plan.get("contexts", []), "meta": meta}
