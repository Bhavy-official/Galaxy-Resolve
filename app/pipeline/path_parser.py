"""Steps -> screen paths -> actions. One Action = One Screen; sub-procedures on that screen become StepGroups."""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Optional

from app.pipeline.textutil import IMPERATIVE_VERBS, capitalize_first, ensure_period, title_case
from app.pipeline.types import ActionDraft, CandidateStep, GroupDraft

_VERB_ALT = "|".join(sorted(IMPERATIVE_VERBS, key=len, reverse=True))
_THEN_SPLIT = re.compile(r"(?:,\s*and then\s+|,\s*then\s+|;\s*then\s+|\s+and then\s+)", re.I)
_COMMA_VERB = re.compile(rf",\s+(?:and\s+)?(?=(?:{_VERB_ALT})\b)", re.I)
_SUBORDINATE = re.compile(r"^(if|when|once|after|before|from|on|in|using|with|while|for|to|as)\b", re.I)


def _has_main_verb(clause: str) -> bool:
    """Does a subordinate-led clause already contain its imperative main clause ('If X, remove Y')?"""
    return any(re.match(rf"(?:{_VERB_ALT})\b", part, re.I) for part in re.split(r",\s+", clause)[1:])


_VARIANT = re.compile(r"^(?:on|for) (?:devices|phones|tablets|models)\b", re.I)


def split_compound(step: CandidateStep) -> list[CandidateStep]:
    """'Go to Settings, tap Display, and then tap Navigation bar.' -> three single-interaction steps."""
    text = step.text.rstrip(". ")
    pieces: list[str] = []
    for chunk in _THEN_SPLIT.split(text):
        sub = _COMMA_VERB.split(chunk)
        # Only split at a comma when the left part is itself a complete command (not an "If ..." clause).
        merged: list[str] = []
        for part in sub:
            if merged and _SUBORDINATE.match(merged[-1]) and not _has_main_verb(merged[-1]):
                merged[-1] = f"{merged[-1]}, {part}"
            else:
                merged.append(part)
        pieces.extend(p.strip() for p in merged if p.strip())
    # a fragment that is not itself a command ("charging the device for an hour") stays with its predecessor
    joined: list[str] = []
    for p in pieces:
        if joined and not re.match(rf"(?:{_VERB_ALT})\b", p, re.I) and not _SUBORDINATE.match(p):
            joined[-1] = f"{joined[-1]}, and then {p}"
        else:
            joined.append(p)
    pieces = joined
    if len(pieces) <= 1:
        return [step]
    out = []
    for i, p in enumerate(pieces):
        if not re.search(r"[A-Za-z]{2}", p):
            continue
        out.append(
            replace(
                step,
                text=ensure_period(capitalize_first(p)),
                new_procedure=step.new_procedure and i == 0,
                alternative=step.alternative and i == 0,
            )
        )
    return out or [step]


# ---------------------------------------------------------------- navigation targets
_ROOT = re.compile(
    r"^(?:(?:from|on|in)\s+[^,]+,\s*)?(?:navigate to and open|navigate to|go to|open|launch|access)\s+(?:the\s+)?(.+)$", re.I
)
_TOGGLE = re.compile(r"^(?:tap|touch|select)\s+(?:on\s+)?the\s+switch(?:es)?\s+next\s+to\s+(.+)$", re.I)
_TAP = re.compile(r"^(?:(?:from|on|in)\s+[^,]+,\s*)?(?:tap|select|touch|choose|click)\s+(?:on\s+)?(?:the\s+)?(.+)$", re.I)
_SEARCH = re.compile(r"^(?:from\s+[^,]+,\s*)?search for and select\s+(.+)$", re.I)
_SWIPE_OPEN = re.compile(r"^.*?\bswipe\b.*?\bto (?:open|access) (?:the\s+)?(.+)$", re.I)
_ADJUST = re.compile(r"^(?:adjust|change|set)\s+(?:the\s+)?(.+)$", re.I)
_TRAIL = re.compile(
    r"\s+(?:to (?:confirm|disable|enable|turn|open|check|access|secure|complete|create|save|change|expand|use|see)\b.*"
    r"|when it appears.*|again.*|from there.*|if .*|on the .*|on your .*|as needed.*)$",
    re.I,
)
_SUFFIX = re.compile(r"\s+(?:app|application|menu|page|screen|panel|icon|option|field|button|tab)$", re.I)


def _clean_target(t: str) -> str:
    t = t.strip().rstrip(".")
    t = _TRAIL.sub("", t)
    t = re.sub(r"\s*\((?:the )?[^)]*\)", "", t)  # "(the three vertical dots)"
    t = re.sub(r"^(?:your|the|a|an)\s+", "", t, flags=re.I)
    t = _SUFFIX.sub("", t)
    return t.strip(" ,")


def nav_targets(text: str) -> tuple[list[str], bool]:
    """Screen/setting names a step navigates through, and whether the step is a toggle."""
    t = text.strip().rstrip(".")
    if re.match(r"^(?:touch|press) and hold\b", t, re.I):
        return [], False
    m = _TOGGLE.match(t)
    if m:
        return [_clean_target(m.group(1))], True
    if ">" in t:
        m = _ROOT.match(t) or _TAP.match(t)
        if m:
            parts = [_clean_target(p) for p in re.split(r"\s*>\s*", m.group(1))]
            return [p for p in parts if p], False
    for pat, max_words in ((_SEARCH, 6), (_ROOT, 6), (_TAP, 6), (_SWIPE_OPEN, 6), (_ADJUST, 3)):
        m = pat.match(t)
        if m:
            target = _clean_target(m.group(1))
            return ([target] if target and len(target.split()) <= max_words else []), False
    return [], False


def is_settings_root(path: list[str]) -> bool:
    return bool(path) and re.fullmatch(r"(?:device\s+)?settings", path[0].strip(), re.I) is not None


def direction_of(texts: list[str]) -> Optional[str]:
    joined = " ".join(texts).lower()
    if re.search(r"\b(disable|turn(?:s|ing)? off|switch off|deactivate|to disable)\b", joined):
        return "off"
    if re.search(r"\b(enable|turn(?:s|ing)? on|switch on|activate)\b", joined):
        return "on"
    if re.search(r"\b(adjust|increase|decrease|set to|change the)\b", joined):
        return "update"
    return None


# ---------------------------------------------------------------- grouping
def _procedures(steps: list[CandidateStep]) -> list[tuple[list[CandidateStep], list[str], bool]]:
    """Split one section's steps into procedures: (steps, nav path, starts_with_alternative)."""
    procs: list[tuple[list[CandidateStep], list[str], bool]] = []
    cur: list[CandidateStep] = []
    path: list[str] = []
    alt = False
    for st in steps:
        targets, _ = nav_targets(st.text)
        root = bool(_ROOT.match(st.text.strip())) and bool(targets) and is_settings_root(targets)
        variant = bool(_VARIANT.match(st.text))  # "On devices with a Side button, ..." = alternative procedure
        boundary = st.new_procedure or st.alternative or variant or (root and bool(path))
        if cur and boundary:
            procs.append((cur, path, alt))
            cur, path = [], []
        if not cur:
            alt = st.alternative or variant
        cur.append(st)
        path.extend(targets)
    if cur:
        procs.append((cur, path, alt))
    return procs


def _norm(el: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", el.lower()).strip()


_TERMINAL = {"ok", "yes", "confirm", "done", "allow", "start now", "delete all", "reset", "restart", "apply", "save"}


def strip_terminal(path: list[str]) -> list[str]:
    """Drop trailing confirmation buttons ('OK', 'Delete all') - they are not screens."""
    p = list(path)
    while p and _norm(p[-1]) in _TERMINAL:
        p.pop()
    return p


def _screen_key(path: list[str]) -> tuple[str, ...]:
    p = [_norm(x) for x in strip_terminal(path)]
    return tuple(p[:-1]) if len(p) >= 3 else tuple(p)


def screen_name(group: GroupDraft) -> Optional[str]:
    """Deepest element that names a screen: toggle target, else skip trailing button labels ('Clear cache')."""
    for st in reversed(group.steps):
        targets, toggle = nav_targets(st.text)
        if toggle and targets:
            return targets[-1]
    p = [x for x in strip_terminal(group.path) if not is_settings_root([x])]
    while len(p) > 1 and re.match(rf"(?:{_VERB_ALT})\b", p[-1], re.I):
        p.pop()
    return p[-1] if p else None


def leaf_screen(group: GroupDraft) -> Optional[str]:
    """Most specific screen/setting the group acts on (toggle target, else deepest non-terminal element)."""
    for st in reversed(group.steps):
        targets, toggle = nav_targets(st.text)
        if toggle and targets:
            return targets[-1]
    p = strip_terminal(group.path)
    return p[-1] if p else None


_GERUND = {"restarting": "Restart", "charging": "Charge", "clearing": "Clear", "updating": "Update",
           "resetting": "Reset", "checking": "Check", "using": "Use", "adjusting": "Adjust"}


def action_name_from(section_title: str, purpose: Optional[str], groups: list[GroupDraft], multi: bool) -> str:
    g = next((g for g in groups if g.path), None)
    leaf = leaf_screen(g) if g else None
    if multi and purpose:
        return title_case(purpose)
    words = section_title.split()
    if words and words[0].lower() in _GERUND:
        words[0] = _GERUND[words[0].lower()]
    verb_led = bool(words) and words[0].lower() in IMPERATIVE_VERBS
    if leaf and g is not None and is_settings_root(g.path) and (multi or not verb_led) and not is_settings_root([leaf]):
        toggle = any(nav_targets(s.text)[1] for s in g.steps)
        verb = {"off": "Turn Off", "on": "Turn On"}.get(g.direction or "", "Adjust") if toggle else "Adjust"
        return title_case(f"{verb} {leaf}")
    return title_case(" ".join(words)) if words else "Follow Troubleshooting Steps"


def build_actions(steps: list[CandidateStep], max_steps: int = 8) -> list[ActionDraft]:
    expanded: list[CandidateStep] = [piece for st in steps for piece in split_compound(st)]
    by_section: dict[int, list[CandidateStep]] = {}
    for st in expanded:
        by_section.setdefault(st.section, []).append(st)

    actions: list[ActionDraft] = []
    for sec_idx, sec_steps in by_section.items():
        sec_title = sec_steps[0].section_title
        procs = _procedures(sec_steps)
        # group procedures by screen; alternatives and path-less procedures join the previous action
        buckets: list[tuple[tuple[str, ...], list[GroupDraft], Optional[str]]] = []
        for p_steps, path, alt in procs:
            group = GroupDraft(steps=p_steps[:max_steps], path=path, direction=direction_of([s.text for s in p_steps]))
            key = _screen_key(path) if path else ()
            purpose = next((s.purpose for s in p_steps if s.purpose), None)
            match = next((b for b in buckets if key and b[0] == key), None)
            if match is None and buckets and (alt or not key):
                match = buckets[-1]
            if match is None:
                buckets.append((key, [group], purpose))
            else:
                match[1].append(group)
        multi = len(buckets) > 1
        for key, groups, purpose in buckets:
            actions.append(
                ActionDraft(
                    name=action_name_from(sec_title, purpose, groups, multi),
                    section=sec_idx,
                    section_title=sec_title,
                    groups=groups,
                )
            )
    return actions
