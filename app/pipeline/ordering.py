"""Rule-based action category + stable disruption sort (auto -> manual -> critical) + dependency ordering."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Optional

from app.config import settings
from app.pipeline.types import ActionDraft

CRITICAL = re.compile(
    r"\b(factory (?:data )?reset|reset (?:your |the )?(?:device|phone|tablet|settings)|restart|reboot|safe mode|"
    r"firmware|software update|update (?:the |your )?(?:device )?software|wipe|erase all|recovery (?:mode|menu)|"
    r"force (?:a )?restart|power off|delete all)\b",
    re.I,
)

CRITICAL_KINDS: tuple[tuple[str, int, re.Pattern], ...] = (
    ("factory reset", 3, re.compile(r"\bfactory (?:data )?reset\b|\bwipe\b|\berase all\b|\bdelete all\b", re.I)),
    ("software update", 2, re.compile(r"\bsoftware updates?\b|\bupdate (?:the |your )?(?:device |phone |tablet )?software\b|\bsystem update|\bfirmware update\b", re.I)),
    ("safe mode", 1, re.compile(r"\bsafe mode\b", re.I)),
    ("restart", 0, re.compile(r"\b(?:force )?restart(?:ing|s|ed)?\b(?! (?:the |your )?(?:\w+ )?app\b)|\breboot|\bturn (?:it|the (?:device|phone)|your (?:device|phone)) off and (?:back )?on\b", re.I)),
)

RANK = {"auto": 0, "manual": 1, "critical": 2}


def critical_rank(action: ActionDraft) -> int:
    text = f"{action.name} " + " ".join(s.text for g in action.groups for s in g.steps)
    for _, rank, pat in CRITICAL_KINDS:
        if pat.search(text):
            return rank
    return 0



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


def _load_dependencies() -> list[dict[str, str]]:
    dep_file = Path(settings.data_dir) / "dependencies.json"
    if dep_file.exists():
        try:
            return json.loads(dep_file.read_text(encoding="utf-8")).get("edges", [])
        except Exception:
            pass
    return [
        {"before": "backup", "after": "factory reset"},
        {"before": "safe mode", "after": "uninstall in safe mode"},
        {"before": "safe mode", "after": "in safe mode"},
        {"before": "charge", "after": "force restart"},
    ]


def _matches_concept(action: ActionDraft, concept: str) -> bool:
    text = f"{action.name} " + " ".join(s.text for g in action.groups for s in g.steps)
    text = text.lower()
    if concept == "backup":
        return "backup" in text or "smart switch" in text or "back up" in text
    if concept == "factory reset":
        return "factory" in text or "wipe" in text or "reset to factory" in text
    if concept == "safe mode":
        return "safe mode" in text
    if concept == "uninstall in safe mode" or concept == "in safe mode":
        return "safe mode" in text and ("uninstall" in text or "delete" in text or "remove" in text)
    if concept == "charge":
        return "charge" in text or "plug in" in text or "power source" in text
    if concept == "force restart":
        return "force restart" in text or "restart" in text or "reboot" in text
    return concept in text


def apply_categories(actions: list[ActionDraft]) -> list[ActionDraft]:
    for a in actions:
        a.category = categorize(a)
        if a.category == "manual":  # manual actions never carry an actionable deeplink
            for g in a.groups:
                g.actionable, g.validation, g.dl_kind = None, None, "none"

    # Step 1: Base disruption sort (auto -> manual -> critical, critical sub-ranked restart < safe mode < update < reset)
    ordered = sorted(
        actions,
        key=lambda a: (RANK[a.category], critical_rank(a) if a.category == "critical" else 0)
    )

    # Step 2: Apply topological prerequisite edges
    edges = _load_dependencies()
    for edge in edges:
        before_concept = edge["before"]
        after_concept = edge["after"]

        before_idx = next((i for i, a in enumerate(ordered) if _matches_concept(a, before_concept)), None)
        after_idx = next((i for i, a in enumerate(ordered) if _matches_concept(a, after_concept)), None)

        if before_idx is not None and after_idx is not None and before_idx > after_idx:
            # Move before_action to just before after_action
            item = ordered.pop(before_idx)
            ordered.insert(after_idx, item)

    return ordered

