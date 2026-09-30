"""Small, pure text helpers shared across the pipeline."""
from __future__ import annotations

import re

STOPWORDS = frozenset(
    """a an the and or but if then so of on in to at by for with from as is are was were be been being it its
    this that these those your you my me i we our us they them their he she his her there here when while
    will would can could should may might must do does did not no yes up down out over under again also just
    very too into onto about after before once any all some more most other such only own same than which who
    what how why where have has had having am let lets let's please""".split()
)

MINOR_WORDS = frozenset(
    "a an the and or but nor for of on in to at by with from as via per vs into onto".split()
)

# Verbs that start an imperative troubleshooting step.
IMPERATIVE_VERBS = frozenset(
    """tap touch press hold swipe select open navigate go launch enter turn toggle enable disable remove insert
    shine connect disconnect plug unplug charge restart reboot reset back clear check inspect examine ensure
    make try update install uninstall contact visit schedule wipe clean increase decrease adjust set change
    drag search locate place review confirm allow add choose use avoid keep wait reinsert power release scan
    perform find follow return reconnect repeat delete sign provide bring take replace apply save test rotate
    move pin close exit start stop verify switch reach call send access view mirror project give disable
    re-add unlock lock format pair unpair forget boot attempt customize""".split()
)

_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

# Verbs that double as nouns in headings ("Touch Sensitivity", "Power Saving", "Software Update").
_AMBIGUOUS_VERBS = frozenset("touch power charge update back reset restart swipe press tap set lock switch pair "
                             "call start stop scan mirror format boot".split())
_DETERMINERS = frozenset("a an the your my this that its all any".split())


def is_verb_led(phrase: str) -> bool:
    """Heuristic: does a heading start with an imperative verb (vs. a noun phrase)?"""
    words = phrase.lower().split()
    if not words or words[0] not in IMPERATIVE_VERBS | {"force"}:
        return False
    if words[0] not in _AMBIGUOUS_VERBS:
        return True
    return len(words) > 1 and (words[1] in _DETERMINERS or words[1] in {"on", "off", "up", "in", "into", "for"})


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def content_tokens(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in STOPWORDS]


def stem(tok: str) -> str:
    """Very light stemmer: enough to match 'buttons'/'button', 'rotating'/'rotate'."""
    for suf in ("ings", "ing", "ies", "es", "s", "ed"):
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            base = tok[: -len(suf)]
            return base + "y" if suf == "ies" else base
    return tok


def stems(text: str) -> set[str]:
    return {stem(t) for t in content_tokens(text)}


_MODEL_TOKENS = re.compile(
    r"\b(?:techcorp|samsung|galaxy|nexa|ultra|plus|pro|max|lite|fe|[a-z]\d{1,3}[a-z]?(?:\s*/\s*[a-z]?\d{1,3}[a-z]?)?)\b",
    re.I,
)


def normalize_complaint(text: str) -> str:
    """Strip enumeration, quotes and brand/model tokens that dominate short-query embeddings."""
    t = re.sub(r"(^|\s)\d+\.\s+", " ", text)
    t = t.replace('"', " ").replace("“", " ").replace("”", " ")
    t = _MODEL_TOKENS.sub(" ", t)
    t = re.sub(r"\(\s*\)", " ", t)
    return normalize_ws(t)


def word_count(text: str) -> int:
    return len(text.split())


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_for_match(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return normalize_ws(text).lower()


def _keep_case(word: str) -> bool:
    core = re.sub(r"[^A-Za-z]", "", word)
    return len(core) > 1 and any(c.isupper() for c in core[1:])  # Wi-Fi, TechCorp, USB, LDI


def title_case(text: str) -> str:
    words = normalize_ws(text).split(" ")
    out: list[str] = []
    for i, w in enumerate(words):
        if not w:
            continue
        if _keep_case(w):
            out.append(w)
        elif 0 < i < len(words) - 1 and w.lower() in MINOR_WORDS:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def is_title_case(text: str) -> bool:
    words = text.split()
    for i, w in enumerate(words):
        first = next((c for c in w if c.isalnum()), "")
        if not first or first.isdigit():
            continue
        if 0 < i < len(words) - 1 and w.lower() in MINOR_WORDS:
            continue
        if not first.isupper():
            return False
    return bool(words)


def sentence_case(text: str) -> str:
    words = normalize_ws(text).split(" ")
    out: list[str] = []
    for i, w in enumerate(words):
        if _keep_case(w):
            out.append(w)
        elif i == 0:
            out.append(w[:1].upper() + w[1:].lower())
        else:
            out.append(w.lower())
    return " ".join(out)


def is_sentence_case(text: str) -> bool:
    words = text.split()
    if not words or not words[0][:1].isupper():
        return False
    return all(_keep_case(w) or w == w.lower() for w in words[1:])


def ensure_period(text: str) -> str:
    text = text.rstrip()
    text = re.sub(r"[\s,;:]+$", "", text)
    return text if text.endswith((".", "!", "?")) else text + "."


def capitalize_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) offsets of sentences in `text` so spans stay verbatim substrings.

    Splits on newlines, on terminal punctuation followed by whitespace + capital, and on the
    'word.Word' run-ons that appear in scraped support pages.
    """
    spans: list[tuple[int, int]] = []
    for line in re.finditer(r"[^\n]+", text):
        seg_start = line.start()
        line_text = line.group()
        cuts = [
            m.end() for m in re.finditer(r"[.!?](?:\s+(?=[\"'(\[]?[A-Z])|(?=[A-Z][a-z]))", line_text)
        ]
        prev = 0
        for c in cuts + [len(line_text)]:
            piece = line_text[prev:c]
            stripped = piece.strip()
            if stripped:
                lead = len(piece) - len(piece.lstrip())
                s = seg_start + prev + lead
                spans.append((s, s + len(stripped)))
            prev = c
    return spans
