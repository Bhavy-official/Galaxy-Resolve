"""Internal models shared across slices. Frozen contract: change only by team agreement.

Only compiler output reaches the official schema (app/schema.py).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Slots(BaseModel):
    """Deterministic slots from the lexicon. No LLM."""
    component: str | None = None
    symptom: str | None = None


class Intent(BaseModel):
    text: str
    domain: str = "Other"  # Battery | Display | Camera | Performance | Other
    title: str | None = None  # LLM-proposed 2-3 words
    relevance: float = 0.0


class SiisSentence(BaseModel):
    id: str  # "S1", "S2", ...
    section: str
    text: str
    relevance: float = 0.0


class DraftStep(BaseModel):
    text: str
    src_ids: list[str] = Field(default_factory=list)
    grounded: bool = False
    grounding_score: float = 0.0


class LinkTier(str, Enum):
    catalog = "catalog"
    dummy = "dummy"
    manual = "manual"


class LinkDecision(BaseModel):
    tier: LinkTier
    node_id: str | None = None
    entry_id: str | None = None
    confidence: float = 0.0


class DraftAction(BaseModel):
    steps: list[DraftStep]
    screen_path: str | None = None
    intent_verb: str | None = None  # open | enable | disable | set | check | restart | reset | visit
    description: str | None = None
    category: str = "manual"  # auto | manual | critical
    disruption_rank: int = 0
    depends_on: list[str] = Field(default_factory=list)
    link: LinkDecision | None = None
    intent_index: int = 0


class ScreenNode(BaseModel):
    node_id: str
    path: str
    synonyms: list[str] = Field(default_factory=list)
    entries_by_polarity: dict[str, list[str]] = Field(default_factory=dict)  # onURL -> [DL-...]
    validation_by_entry: dict[str, dict] = Field(default_factory=dict)


class CacheEntry(BaseModel):
    key: str
    siis_hash: str | None
    slots: Slots
    plan: dict
    query_texts: list[str] = Field(default_factory=list)  # original + variations
    created_at: float = 0.0
    hits: int = 0


class StageTiming(BaseModel):
    stage: str
    ms: float


class Trace(BaseModel):
    trace_id: str
    timings: list[StageTiming] = Field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    cache_tier: str | None = None  # exact | semantic | None
    model: str | None = None
    fallback: str | None = None  # no_match | no_siis_context | None
