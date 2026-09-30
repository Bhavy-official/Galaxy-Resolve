"""Grounding validator: a step survives only if its span is in the SIIS text and the span supports the step."""
from __future__ import annotations

import difflib

from app.pipeline.textutil import normalize_for_match, sentence_spans, stems
from app.pipeline.types import CandidateStep

# Words an imperative rewrite may add without the source saying them.
_FREE = {
    "tap", "touch", "select", "open", "go", "navigate", "press", "hold", "swipe", "device", "phone", "tablet",
    "settings", "screen", "button", "icon", "app", "check", "try", "make", "sure", "ensure", "turn", "use", "step",
    "again", "confirm", "enable", "disable", "switch", "option", "menu", "find", "locate",
}

SPAN_FUZZY_MIN = 0.88
SUPPORT_MIN = 0.6


def locate_span(span: str, content: str) -> tuple[bool, str]:
    """Is `span` (modulo whitespace/quotes/case) in content? Falls back to the best fuzzy sentence match."""
    n_span, n_content = normalize_for_match(span), normalize_for_match(content)
    if n_span and n_span in n_content:
        return True, span
    best, best_ratio = "", 0.0
    for s, e in sentence_spans(content):
        cand = content[s:e]
        r = difflib.SequenceMatcher(None, n_span, normalize_for_match(cand)).ratio()
        if r > best_ratio:
            best, best_ratio = cand, r
    return best_ratio >= SPAN_FUZZY_MIN, best


def support(step: str, span: str) -> float:
    step_stems = stems(step) - _FREE
    if not step_stems:
        return 1.0
    return len(step_stems & stems(span)) / len(step_stems)


def ground_steps(steps: list[CandidateStep], content: str) -> tuple[list[CandidateStep], list[CandidateStep]]:
    kept, dropped = [], []
    for st in steps:
        found, span = locate_span(st.span, content)
        score = support(st.text, span) if found else 0.0
        if found and score >= SUPPORT_MIN:
            st.span, st.grounding = span, score
            kept.append(st)
        else:
            st.grounding = score
            dropped.append(st)
    return kept, dropped
