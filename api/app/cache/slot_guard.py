"""Rejects semantic hits whose lexicon slots contradict the query (black vs cracked)."""

from app.models import Slots


def compatible(a: Slots, b: Slots) -> bool:
    raise NotImplementedError
