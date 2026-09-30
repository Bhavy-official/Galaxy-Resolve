"""Rule-based action category + stable disruption sort (auto -> manual -> critical)."""
from __future__ import annotations

import re

from app.pipeline.types import ActionDraft

CRITICAL = re.compile(
    r"\b(factory (?:data )?reset|reset (?:your |the )?(?:device|phone|tablet|settings)|restart|reboot|safe mode|"
    r"firmware|software update|update (?:the |your )?(?:device )?software|wipe|erase all|recovery (?:mode|menu)|"
    r"force (?:a )?restart|power off|delete all)\b",
    re.I,
)
RANK = {"auto": 0, "manual": 1, "critical": 2}


def categorize(action: ActionDraft) -> str:
    text = " ".join([action.name] + [s.text for g in action.groups for s in g.steps])
    if CRITICAL.search(action.name) or CRITICAL.search(text) and _mostly_critical(action):
        return "critical"
    if any(g.actionable for g in action.groups):
        return "auto"
    return "manual"


def _mostly_critical(action: ActionDraft) -> bool:
    steps = [s.text for g in action.groups for s in g.steps]
    hits = sum(1 for s in steps if CRITICAL.search(s))
    return hits >= max(1, len(steps) // 2)


def apply_categories(actions: list[ActionDraft]) -> list[ActionDraft]:
    for a in actions:
        a.category = categorize(a)
        if a.category == "manual":  # manual actions never carry an actionable deeplink
            for g in a.groups:
                g.actionable, g.validation, g.dl_kind = None, None, "none"
    return sorted(actions, key=lambda a: RANK[a.category])  # sorted() is stable
