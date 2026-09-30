"""Step extraction from SIIS text. Every candidate step carries the verbatim source span it came from.

Two extractors produce the same `CandidateStep` list:
  * `llm_extract`  - Gemini picks query-relevant steps and quotes their spans (structured output).
  * `rules_extract` - deterministic sentence classifier (offline mode + ablation baseline).
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel

from app.llm import LLMClient, Usage
from app.pipeline.textutil import (
    IMPERATIVE_VERBS,
    capitalize_first,
    ensure_period,
    normalize_ws,
    sentence_spans,
)
from app.pipeline.types import CandidateStep, Section
from app.pipeline.validators import scrub_urls

# ---------------------------------------------------------------- sections
_HEADING = re.compile(r"^\s*(#{1,6})\s*(.*?)\s*$")
_PREFIX = re.compile(r"^[^\n]{0,400}?\(\s*[^()\n]{0,300}\):\s*")  # "Smartphone,... Title ( Smartphone,...): "
_SKIP_SECTIONS = re.compile(r"^glossary:?$", re.I)  # everything after it is definitions, not steps


def clean_content(content: str) -> str:
    return _PREFIX.sub("", content or "", count=1)




def clean_heading(title: str) -> str:
    title = re.sub(r"^(?:step\s*\d+\s*[:.)-]\s*|\d+\s*[.)-]\s*)", "", title.strip(), flags=re.I)
    return title.strip(" :#")


def parse_sections(content: str, doc_title: str = "") -> list[Section]:
    text = clean_content(content)
    sections: list[Section] = []
    cur_title, cur_start, buf_start = clean_heading(doc_title) or "Overview", 0, 0
    lines = list(re.finditer(r"[^\n]*\n?", text))

    def flush(end: int) -> None:
        body = text[buf_start:end]
        if body.strip() and not _SKIP_SECTIONS.match(cur_title):
            sections.append(Section(len(sections), cur_title, body, buf_start))

    for m in lines:
        line = m.group()
        h = _HEADING.match(line.rstrip("\n"))
        if h and line.strip():
            flush(m.start())
            heading = clean_heading(h.group(2))
            cur_title = heading or cur_title
            buf_start = m.end()
        elif line.strip() and _SKIP_SECTIONS.match(line.strip()):
            flush(m.start())
            cur_title = line.strip()
            buf_start = m.end()
    flush(len(text))
    return sections


def is_numbered_procedure(content: str) -> bool:
    return len(re.findall(r"^\s*#{1,6}\s*(?:step\s*)?\d+\s*[:.]", clean_content(content), re.I | re.M)) >= 2


# ---------------------------------------------------------------- rule-based sentence -> imperative
_LEAD = re.compile(
    r"^(?:(?:first|next|then|now|finally|alternatively|additionally|also|afterwards?|simply|just|please|otherwise|"
    r"once connected|if prompted)\b[\s,]*)+",
    re.I,
)
_LETS = re.compile(r"^let'?s\s+(?:try to\s+)?", re.I)
_MODAL = re.compile(
    r"\b(?:it is (?:recommended|advisable|best|important) to|we recommend(?: that you)?|you (?:should|can|may|must|"
    r"will need to|need to|may need to|might need to|could)(?: also| still| always| even)?|please|be sure to)\s+",
    re.I,
)
_CONDITIONAL = re.compile(r"^(if|when|once|after|before|from|on|in|using|with|while|for|to)\b", re.I)
_NOT_STEP = re.compile(r"\?|^(i |i'm|we |here'?s|this |these |it |there |that |note\b)", re.I)
_PURPOSE_LINE = re.compile(r"^\s*(to [^:]{3,80}):\s*$", re.I)
_FILLER = re.compile(
    r"\b(we|us|these steps|following steps|this guide|troubleshooting (steps|guide)|our (website|guide)|"
    r"provided links?|links?|check out|some steps|resolve this)\b",
    re.I,
)
MAX_STEP_WORDS = 35


def _first_word(text: str) -> str:
    m = re.match(r"[A-Za-z][A-Za-z'-]*", text)
    return m.group().lower() if m else ""


def _starts_imperative(text: str) -> bool:
    w = _first_word(text)
    return w in IMPERATIVE_VERBS and not re.match(r"^(touch|press|set|use|access|check)\w*\s+(is|are|was|will)\b", text, re.I)


from app.pipeline.deglue import deglue


def to_imperative(sentence: str) -> Optional[str]:
    """Return an imperative step derived from `sentence`, or None if it is not an instruction."""
    s = normalize_ws(sentence)
    if any(len(w) > 25 for w in s.split()):
        s = deglue(s)
    words = s.split()
    if len(words) < 2 or len(words) > MAX_STEP_WORDS or _NOT_STEP.search(s) or _FILLER.search(s):
        return None

    s = _LEAD.sub("", s)
    s = _LETS.sub("", s)
    # "Label: Do something" -> keep conditional labels ("On devices with a Power button"), drop the rest.
    lab = re.match(r"^([^:]{2,60}):\s+(.+)$", s)
    if lab and len(lab.group(1).split()) <= 8:
        label, rest = lab.group(1), _LEAD.sub("", lab.group(2))
        rest_imp = to_imperative(rest)
        if rest_imp:
            if re.match(r"^(on|for|if|when|with)\b", label, re.I):
                return ensure_period(f"{capitalize_first(label)}, {rest_imp[0].lower()}{rest_imp[1:]}")
            return rest_imp
        return None
    # "To do X, tap Y" -> "Tap Y"
    purpose = re.match(r"^to [^,]{3,80},\s+(.+)$", s, re.I)
    if purpose and _starts_imperative(_MODAL.sub("", purpose.group(1))):
        return ensure_period(capitalize_first(_MODAL.sub("", purpose.group(1))))
    if _starts_imperative(s):
        return ensure_period(capitalize_first(_MODAL.sub("", s)))
    if _CONDITIONAL.match(s):
        # find a comma after which an (optionally modal-prefixed) imperative clause starts
        for m in re.finditer(r",\s+", s):
            rest = _MODAL.sub("", s[m.end():], count=1) if _MODAL.match(s[m.end():]) else s[m.end():]
            rest = _LEAD.sub("", rest)
            if _starts_imperative(rest):
                return ensure_period(capitalize_first(f"{s[:m.start()]}, {rest}"))
        return None
    mm = _MODAL.search(s)
    if mm and _starts_imperative(s[mm.end():]) and mm.start() < 40:
        return ensure_period(capitalize_first(s[mm.end():]))
    return None


def rules_extract(sections: list[Section]) -> list[CandidateStep]:
    steps: list[CandidateStep] = []
    for sec in sections:
        purpose: Optional[str] = None
        pending_boundary = False
        for start, end in sentence_spans(sec.text):
            raw = sec.text[start:end]
            pm = _PURPOSE_LINE.match(raw)
            if pm:
                purpose = pm.group(1)[3:].strip()
                if _FILLER.search(purpose) or re.search(r"\b(this|the) (issue|problem)\b", purpose, re.I):
                    purpose = None
                pending_boundary = True
                continue
            imp = to_imperative(raw)
            if not imp:
                continue
            steps.append(
                CandidateStep(
                    text=imp,
                    span=raw,
                    section=sec.idx,
                    section_title=sec.title,
                    purpose=purpose,
                    new_procedure=pending_boundary,
                    alternative=bool(re.match(r"^\s*alternatively\b", raw, re.I)),
                )
            )
            pending_boundary = False
    return steps


# ---------------------------------------------------------------- LLM extraction
class LLMStep(BaseModel):
    section_id: int
    text: str
    source_span: str


class LLMSectionLabel(BaseModel):
    section_id: int
    action_name: str
    description: str


class LLMExtraction(BaseModel):
    steps: list[LLMStep]
    labels: list[LLMSectionLabel]


EXTRACT_SYSTEM = """You turn TechCorp support articles into device troubleshooting steps.
You receive a user complaint and the article split into numbered sections.
Select only the steps that help with the complaint, in article order.
For each step:
- section_id: the section it comes from
- text: an imperative instruction describing one physical interaction (one tap, one press, one swipe)
- source_span: the exact sentence(s) copied verbatim from the article that support the step
Never add a step that is not in the article.
For each section you used, give an action_name (the feature or screen it acts on) and a one-line description of what the action achieves, starting with "It will"."""


def build_extract_prompt(query: str, sections: list[Section]) -> str:
    parts = [f"User complaint: {query}", "", "Article sections:"]
    for s in sections:
        parts.append(f"<section id={s.idx} title=\"{s.title}\">\n{s.text.strip()}\n</section>")
    return "\n".join(parts)


def llm_extract(
    query: str, sections: list[Section], llm: LLMClient
) -> tuple[list[CandidateStep], dict[int, LLMSectionLabel], Usage]:
    out, usage = llm.structured(EXTRACT_SYSTEM, build_extract_prompt(query, sections), LLMExtraction, max_tokens=4096)
    by_id = {s.idx: s for s in sections}
    steps: list[CandidateStep] = []
    for st in out.steps:
        sec = by_id.get(st.section_id)
        if sec is None:
            continue
        steps.append(
            CandidateStep(
                text=scrub_urls(st.text),  # LLMs inject "visit samsung.com/support" from pretraining
                span=st.source_span,
                section=sec.idx,
                section_title=sec.title,
                alternative=bool(re.match(r"^\s*alternatively\b", st.source_span, re.I)),
            )
        )
    labels = {lab.section_id: lab for lab in out.labels if lab.section_id in by_id}
    return steps, labels, usage
