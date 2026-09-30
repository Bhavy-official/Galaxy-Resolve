"""Enrichment: canonical query, slots {domain, symptom, trigger}, 8-10 paraphrases, topic/title drafts."""
from __future__ import annotations

import random
import re
import zlib
from typing import Literal

from pydantic import BaseModel

from app.cache.slots import DOMAIN_PATTERNS, PROBLEM_SYMPTOMS, SYMPTOM_PATTERNS, extract_slots, merge_slots
from app.llm import LLMClient, Usage
from app.pipeline.textutil import content_tokens, normalize_complaint, normalize_ws
from app.pipeline.types import Enrichment, Slots
from app.pipeline.validators import scrub_urls

Domain = Literal[tuple(DOMAIN_PATTERNS) + ("other",)]  # type: ignore[valid-type]
Symptom = Literal[tuple(SYMPTOM_PATTERNS) + ("other",)]  # type: ignore[valid-type]

MIN_PARA, MAX_PARA = 8, 10

# Topic (goal) + title per dominant symptom; used by rules mode and as a fallback.
SYMPTOM_TOPIC: dict[str, tuple[str, str]] = {
    "cracked": ("Screen Damage", "Screen display damage"),
    "distorted": ("Display Distortion", "Distorted screen display"),
    "blank": ("Blank Screen", "Blank screen recovery"),
    "flicker": ("Screen Flicker", "Screen flicker fix"),
    "no_power": ("Power On", "Device power issue"),
    "unresponsive": ("Touchscreen Response", "Unresponsive screen fix"),
    "lag": ("Touch Lag", "Touch response lag"),
    "no_rotation": ("Screen Rotation", "Screen rotation fix"),
    "transfer_fail": ("Data Transfer", "Data transfer issue"),
    "connection": ("Connection", "Connection issue fix"),
    "drain": ("Battery Drain", "Battery drain fix"),
    "size": ("Display Size", "Display size settings"),
    "remove_feature": ("Feature Removal", "Remove screen shortcut"),
}
SYMPTOM_PRIORITY = ["cracked", "distorted", "flicker", "blank", "no_power", "unresponsive", "lag", "no_rotation",
                    "transfer_fail", "connection", "drain", "size", "remove_feature"]

# Canonical phrasings per symptom broaden the multi-vector cache beyond surface rewrites of one query.
SYMPTOM_PHRASES: dict[str, list[str]] = {
    "blank": ["phone screen went black and shows nothing", "display stays dark", "blank screen on my phone"],
    "flicker": ["screen keeps flickering", "display flashes on and off"],
    "cracked": ["my phone screen is cracked", "broken display glass"],
    "unresponsive": ["touchscreen not responding", "screen doesn't react to touch"],
    "lag": ["touch input is laggy and delayed", "screen responds slowly to taps"],
    "distorted": ["screen looks distorted with lines", "part of the display is black"],
    "no_power": ["phone won't turn on", "device does not power up"],
    "no_rotation": ["screen will not rotate", "auto rotate not working"],
    "transfer_fail": ["can't transfer data to new phone", "data transfer not working"],
    "size": ["screen content looks too small", "display doesn't fill the whole screen"],
    "remove_feature": ["how do I remove the floating button", "turn off the on-screen shortcut menu"],
}

CONFIG_INTENT = re.compile(
    r"\b(how (do|can) i|i want to|i'?d like to|want to|remove|get rid of|set ?up|customi[sz]e|turn (on|off)|enable|disable)\b",
    re.I,
)


class LLMEnrichment(BaseModel):
    canonical_query: str
    domain: Domain  # type: ignore[valid-type]
    symptom: Symptom  # type: ignore[valid-type]
    trigger: str
    topic: str
    title: str
    kind: Literal["Troubleshooting", "Configuration"]
    paraphrases: list[str]


ENRICH_SYSTEM = """You normalize Galaxy/TechCorp device complaints for a troubleshooting cache.
Return:
- canonical_query: one short, neutral sentence stating the problem
- domain, symptom: the best-fitting labels
- trigger: what causes it ("" if none)
- topic: the problem area as a short noun phrase (e.g. "Screen Damage")
- title: a short label for the plan
- kind: Configuration if the user wants to change a setting or feature, else Troubleshooting
- paraphrases: 10 different ways real users would type this same complaint: formal, casual, keyword-only, frustrated, and with typos."""


def _dedupe(texts: list[str], exclude: str) -> list[str]:
    seen = {re.sub(r"\W+", " ", exclude.lower()).strip()}
    out = []
    for t in texts:
        t = normalize_ws(scrub_urls(t))
        k = re.sub(r"\W+", " ", t.lower()).strip()
        if t and k not in seen:
            seen.add(k)
            out.append(t)
    return out


def _typo(text: str, rng: random.Random) -> str:
    words = text.split()
    idx = [i for i, w in enumerate(words) if len(w) > 4]
    for i in rng.sample(idx, min(2, len(idx))):
        w = words[i]
        j = rng.randrange(1, len(w) - 2)
        words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    return " ".join(words)


def rule_paraphrases(query: str, slots: Slots) -> list[str]:
    rng = random.Random(zlib.crc32(query.encode("utf-8")))  # deterministic across processes
    core = normalize_complaint(query)
    core = re.sub(r"^(my|the)\s+", "", core, flags=re.I).rstrip(".")
    keywords = " ".join(dict.fromkeys(content_tokens(core)))
    kw_short = " ".join(keywords.split()[:7])
    variants = [
        f"How can I resolve this issue: my {core}?",
        core.lower(),
        kw_short,
        f"ugh my {core.lower()} again, please help",
        _typo(core.lower(), rng),
        f"{kw_short} fix",
    ]
    for s in SYMPTOM_PRIORITY:
        if s in slots.symptoms:
            variants.extend(SYMPTOM_PHRASES.get(s, []))
    return variants


def pick_topic(slots: Slots, siis_title: str) -> tuple[str, str]:
    for s in SYMPTOM_PRIORITY:
        if s in slots.symptoms:
            return SYMPTOM_TOPIC[s]
    words = [w for w in re.sub(r"[^\w\s-]", " ", siis_title).split() if w.lower() not in {"on", "a", "or", "smartphone", "tablet", "your"}]
    topic = " ".join(words[:2]).title() or "Device"
    return topic, (" ".join(words[:3]).capitalize() or "Device troubleshooting")


def detect_kind(query: str, slots: Slots) -> str:
    if CONFIG_INTENT.search(query) and not (slots.symptoms & (PROBLEM_SYMPTOMS - {"unresponsive"})):
        return "Configuration"
    return "Troubleshooting"


def rules_enrich(query: str, siis_title: str = "") -> Enrichment:
    slots = extract_slots(query)
    topic, title = pick_topic(slots, siis_title)
    paras = _dedupe(rule_paraphrases(query, slots), query)[:MAX_PARA]
    return Enrichment(normalize_ws(query), slots, paras, topic, title, detect_kind(query, slots), "rules")


def llm_enrich(query: str, siis_title: str, llm: LLMClient) -> tuple[Enrichment, Usage]:
    out, usage = llm.structured(ENRICH_SYSTEM, f"Complaint: {query}", LLMEnrichment, max_tokens=1500)
    base = rules_enrich(query, siis_title)
    llm_slots = Slots(
        {out.domain} - {"other"}, {out.symptom} - {"other"}, out.trigger or None
    )
    slots = merge_slots(base.slots, llm_slots, extract_slots(out.canonical_query))
    paras = _dedupe(out.paraphrases, query)
    if len(paras) < MIN_PARA:  # top up deterministically; never trust the count
        paras = _dedupe(paras + base.paraphrases, query)
    return (
        Enrichment(
            canonical=normalize_ws(scrub_urls(out.canonical_query)) or base.canonical,
            slots=slots,
            paraphrases=paras[:MAX_PARA],
            topic=scrub_urls(out.topic) or base.topic,
            title=scrub_urls(out.title) or base.title,
            kind=out.kind,
            source="llm",
        ),
        usage,
    )
