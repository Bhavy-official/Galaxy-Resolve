"""Internal (non-contract) data structures passed between pipeline stages."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Section:
    idx: int
    title: str
    text: str
    start: int  # offset of text within the cleaned content


@dataclass
class CandidateStep:
    text: str
    span: str
    section: int
    section_title: str
    purpose: Optional[str] = None  # "clear the app's cache" when introduced by "To clear the app's cache:"
    new_procedure: bool = False  # forced procedure boundary (a "To X:" line preceded it)
    alternative: bool = False  # sentence began with "Alternatively"
    grounding: float = 1.0


@dataclass
class Slots:
    domains: set[str] = field(default_factory=set)
    symptoms: set[str] = field(default_factory=set)
    trigger: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"domains": sorted(self.domains), "symptoms": sorted(self.symptoms), "trigger": self.trigger}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Slots":
        return cls(set(d.get("domains", [])), set(d.get("symptoms", [])), d.get("trigger"))


@dataclass
class Enrichment:
    canonical: str
    slots: Slots
    paraphrases: list[str]
    topic: str
    title: str
    kind: str  # "Troubleshooting" | "Configuration"
    source: str = "rules"


@dataclass
class GroupDraft:
    steps: list[CandidateStep]
    path: list[str]
    direction: Optional[str] = None  # on | off | update | None
    actionable: Optional[dict[str, Any]] = None
    validation: Optional[dict[str, Any]] = None
    dl_kind: str = "none"  # catalog | dummy | none
    dl_conf: float = 0.0
    dl_id: Optional[str] = None


@dataclass
class ActionDraft:
    name: str
    section: int
    section_title: str
    groups: list[GroupDraft]
    description: Optional[str] = None
    desc_ok: bool = False  # drafted description passed validation on the first try
    from_llm_label: bool = False
    verb_phrase: Optional[str] = None  # "turn off touch sensitivity" - basis for template descriptions
    category: str = "manual"
    relevance: float = 0.0
