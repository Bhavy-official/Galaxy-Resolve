"""Tier 1: embed normalized RAW query, ANN over stored original + variations. No LLM on this path."""

from app.models import Slots


def lookup(norm_query: str, slots: Slots, siis_hash: str | None) -> dict | None:
    raise NotImplementedError
