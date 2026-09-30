"""Rule-based slot extraction (no LLM) and the slot guard used before accepting a cache hit."""
from __future__ import annotations

import re

from app.pipeline.types import Slots

DOMAIN_PATTERNS: dict[str, str] = {
    "display": r"\b(screen|display|pixels?|brightness|resolution|monitor)\b",
    "touch": r"\b(touch(screen)?|taps?|tapping|swip(e|ing)|input|responsive(ness)?)\b",
    "power": r"\b(turn(s|ed)? on|power(s|ed)? on|power button|boot|start(s|ed)? up|charg(e|er|es|ing)|battery|restart)\b",
    "connectivity": r"\b(wi-?fi|bluetooth|internet|network|mobile data|signal|hotspot|carrier|activation)\b",
    "email": r"\b(e-?mails?|gmail|outlook|inbox)\b",
    "data_transfer": r"\b(data transfer|smart switch|transfer(ring)? (my )?(data|files)|back ?up|qr code)\b",
    "mirroring": r"\b(mirror(ing)?|cast(ing)?|smart view|tv)\b",
    "multi_window": r"\b(multi ?window|split screen|pop-?up view|app pairs?|floating (circle|icon|button|bubble)|assistant menu|edge panel)\b",
    "rotation": r"\b(rotat\w*|landscape|portrait|orientation)\b",
    "camera": r"\b(camera|video|photos?|shutter)\b",
    "foldable": r"\b(fold|folds|foldable|inner screen|cover screen|hinge)\b",
    "apps": r"\b(apps?|application|stock price|quick assist)\b",
}

SYMPTOM_PATTERNS: dict[str, str] = {
    "blank": r"\b(blank|black|dark|goes out|went out|white screen|no (image|display|text|picture)|nothing (appears|shows|displays|is visible)|doesn'?t display|won'?t display|can'?t see)\b",
    "flicker": r"\b(flicker\w*|flash\w*|blink\w*|strob\w*)\b",
    "cracked": r"\b(crack\w*|shatter\w*|smash\w*|broken (glass|screen|display))\b",
    "unresponsive": r"\b(unresponsive|not respond\w*|doesn'?t respond|won'?t respond|stopped (working|responding)|frozen|freez\w*|doesn'?t work|not work\w*|won'?t open)\b",
    "lag": r"\b(lag\w*|delay\w*|slow\w*|sluggish)\b",
    "distorted": r"\b(distort\w*|lines|bleed\w*|ink ?blots?|dead pixels?|half (black|dark)|one side|discolou?r\w*)\b",
    "no_power": r"\b((won'?t|doesn'?t|not|fails? to|can'?t) (turn|power|start|boot)( on| up)?|won'?t start|dead phone)\b",
    "no_rotation": r"\b((not|doesn'?t|won'?t) rotat\w*|stuck in (portrait|landscape))\b",
    "size": r"\b(small|doesn'?t fill|shrunk|full size|expand|tiny)\b",
    "remove_feature": r"\b(remove|get rid|turn off|hide|disable)\b",
    "transfer_fail": r"\b((can'?t|unable to|cannot|won'?t)\b.{0,40}\btransfer\w*|transfer\w* (can'?t|won'?t|fail\w*))\b",
    "connection": r"\b((can'?t|not|won'?t|unable to) connect|disconnect\w*|no internet|not responding)\b",
    "drain": r"\b(drain\w*|dies fast|battery (life|dies))\b",
}

TRIGGER_PATTERN = re.compile(
    r"\b(when(ever)?|while|after|every time|each time)\b\s+([^,.;]{3,60})", re.I
)

PROBLEM_SYMPTOMS = frozenset(SYMPTOM_PATTERNS) - {"remove_feature", "size"}

_COMPILED_D = {k: re.compile(v, re.I) for k, v in DOMAIN_PATTERNS.items()}
_COMPILED_S = {k: re.compile(v, re.I) for k, v in SYMPTOM_PATTERNS.items()}


def extract_slots(text: str) -> Slots:
    domains = {k for k, p in _COMPILED_D.items() if p.search(text)}
    symptoms = {k for k, p in _COMPILED_S.items() if p.search(text)}
    m = TRIGGER_PATTERN.search(text)
    return Slots(domains, symptoms, m.group(0).strip() if m else None)


def merge_slots(*items: Slots) -> Slots:
    out = Slots()
    for s in items:
        out.domains |= s.domains
        out.symptoms |= s.symptoms
        out.trigger = out.trigger or s.trigger
    return out


def slots_compatible(query: Slots, plan: Slots) -> bool:
    """Domain and symptom must both agree. An empty side acts as a wildcard (the query didn't say)."""
    if query.domains and plan.domains and not (query.domains & plan.domains):
        return False
    if query.symptoms and plan.symptoms and not (query.symptoms & plan.symptoms):
        return False
    return True
