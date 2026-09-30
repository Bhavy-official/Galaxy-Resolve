"""Component 1: lexicon/regex slot extractor (component, symptom). No LLM. Lexicon in data/slot_lexicon.json."""

from app.models import Slots


def extract_slots(norm_query: str) -> Slots:
    raise NotImplementedError
