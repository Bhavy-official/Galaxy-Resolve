"""Field validators and repairs. Every output rule is enforced here in code, not in prompts."""
from __future__ import annotations

import re
from typing import Any, Callable

from app.pipeline.textutil import (
    IMPERATIVE_VERBS,
    MINOR_WORDS,
    capitalize_first,
    ensure_period,
    is_sentence_case,
    is_title_case,
    is_verb_led,
    normalize_ws,
    sentence_case,
    title_case,
    word_count,
)

# ---------------------------------------------------------------- URL scrub
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"(?i)\b(?:https?://|www\.)\S*")
_EMAIL = re.compile(r"(?i)\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_DOMAIN = re.compile(
    r"(?i)\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|co|us|uk|in|kr|info|biz|me|ly|gl)\b(?:/\S*)?"
)
_DANGLING = re.compile(r"(?i)\b(?:visit|at|see|go to|check out|on)\s+(?=[.,;:!?]|$)")

URL_LEAK = re.compile(r"(?i)https?://|www\.|\]\(")


def scrub_urls(text: str) -> str:
    if not text:
        return text
    out = _MD_LINK.sub(r"\1", text)
    out = _URL.sub("", out)
    out = _EMAIL.sub("", out)
    out = _DOMAIN.sub("", out)
    out = _DANGLING.sub("", out)
    out = re.sub(r"\(\s*\)", "", out)
    out = re.sub(r"\s+([.,;:!?])", r"\1", out)
    return normalize_ws(out)


def has_url(text: str) -> bool:
    return bool(URL_LEAK.search(text) or _DOMAIN.search(text) or _EMAIL.search(text))


def scrub_tree(obj: Any, skip_keys: frozenset[str] = frozenset({"deeplink"})) -> Any:
    """Recursively scrub every string field except deeplink URIs (which come verbatim from the catalog)."""
    if isinstance(obj, dict):
        return {k: (v if k in skip_keys else scrub_tree(v, skip_keys)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_tree(v, skip_keys) for v in obj]
    if isinstance(obj, str):
        return scrub_urls(obj)
    return obj


# ---------------------------------------------------------------- goal / title
def goal_text(topic: str, kind: str = "Troubleshooting") -> str:
    kind = "Configuration" if kind.lower().startswith("config") else "Troubleshooting"
    topic = title_case(scrub_urls(topic)).strip() or "Device"
    topic = re.sub(r"\s+(Troubleshooting|Configuration)$", "", topic)
    return f"Follow these steps to perform this {topic} {kind}"


GOAL_RE = re.compile(r"^Follow these steps to perform this (.+) (Troubleshooting|Configuration)$")


def enforce_title(draft: str, fallback: str = "Device troubleshooting") -> tuple[str, bool]:
    """Title must be 2-3 words in sentence case. Returns (title, passed_without_repair)."""
    clean = re.sub(r"[^\w\s'-]", " ", scrub_urls(draft or ""))
    words = clean.split()
    ok = 2 <= len(words) <= 3 and is_sentence_case(" ".join(words)) and " ".join(words) == (draft or "").strip()
    if ok:
        return draft.strip(), True
    words = [w for w in words if w.lower() not in MINOR_WORDS] or words
    if len(words) < 2:
        words = (words + fallback.split())[:2] if words else fallback.split()[:3]
    return sentence_case(" ".join(words[:3])), False


def is_valid_title(title: str) -> bool:
    return 2 <= word_count(title) <= 3 and is_sentence_case(title)


# ---------------------------------------------------------------- action name
def enforce_action_name(name: str) -> str:
    name = re.sub(r"^(?:step\s*\d+\s*[:.)-]\s*|\d+\s*[.)-]\s*)", "", scrub_urls(name), flags=re.I)
    name = re.sub(r"[:.;,!?]+$", "", name).strip()
    words = name.split()
    if len(words) > 7:
        words = words[:7]
        while words and words[-1].lower() in MINOR_WORDS:
            words.pop()
    return title_case(" ".join(words)) or "Follow Troubleshooting Steps"


# ---------------------------------------------------------------- description
DESC_MIN, DESC_MAX = 5, 7


def is_valid_description(desc: str) -> bool:
    return bool(desc) and desc.startswith("It will ") and DESC_MIN <= word_count(desc) <= DESC_MAX and not has_url(desc)


_DROPPABLE = {"the", "your", "a", "an", "my", "its"}


def _clip_words(words: list[str]) -> list[str]:
    # shorten by dropping articles/possessives first, then clip without ending on a function word
    i = len(words) - 1
    while len(words) > DESC_MAX and i >= 2:
        if words[i].lower() in _DROPPABLE:
            words.pop(i)
        i -= 1
    words = words[:DESC_MAX]
    while len(words) > DESC_MIN and words[-1].lower().strip(",.") in (MINOR_WORDS | _DROPPABLE):
        words.pop()
    return words


def normalize_description(desc: str) -> str:
    """Light, safe cleanup of a drafted description (punctuation, casing of the lead-in)."""
    d = normalize_ws(scrub_urls(desc or "")).rstrip(".!")
    d = re.sub(r"^it will\b", "It will", d, flags=re.I)
    return d


def _lower_words(text: str) -> list[str]:
    words = re.sub(r"[^\w\s'-]", " ", text).split()
    return [w if (len(w) > 1 and any(c.isupper() for c in w[1:])) else w.lower() for w in words]


def template_description(action_name: str, verb_phrase: str | None = None) -> str:
    """Deterministic fallback: 'It will <verb phrase>' clipped to 5-7 words.

    verb_phrase (e.g. "turn off touch sensitivity", from the matched catalog entry) wins over the action name.
    """
    if verb_phrase:
        body = _lower_words(verb_phrase)
    elif is_verb_led(action_name):
        body = _lower_words(action_name)
    else:
        body = ["help", "with"] + _lower_words(action_name)
    out = _clip_words(["It", "will"] + body)
    filler = ["on", "your", "device"]
    while len(out) < DESC_MIN and filler:
        out.append(filler.pop(0))
    return " ".join(out)


def enforce_description(
    draft: str | None,
    action_name: str,
    repair: Callable[[str, str], str | None] | None = None,
    verb_phrase: str | None = None,
) -> tuple[str, bool]:
    """Validate -> one repair attempt -> template fallback. Returns (description, passed_first_try)."""
    d = normalize_description(draft or "")
    if is_valid_description(d):
        return d, True
    if repair is not None and draft:
        fixed = normalize_description(repair(d, action_name) or "")
        if is_valid_description(fixed):
            return fixed, False
    return template_description(action_name, verb_phrase), False


# ---------------------------------------------------------------- steps
_LEAD = re.compile(
    r"^(?:(?:first|next|then|now|finally|alternatively|additionally|also|afterwards?|simply|just|please|otherwise)\b[\s,]*)+",
    re.I,
)


def normalize_step(step: str) -> str:
    s = scrub_urls(step)
    s = _LEAD.sub("", s)
    s = re.sub(r"\bplease\s+", "", s, flags=re.I)
    s = normalize_ws(s)
    return ensure_period(capitalize_first(s)) if s else ""


def is_valid_step(step: str) -> bool:
    return word_count(step) >= 2 and not has_url(step)


def is_valid_name(name: str) -> bool:
    return bool(name) and is_title_case(name) and not has_url(name)
