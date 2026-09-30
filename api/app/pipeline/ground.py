"""Component 6: step-level (embedding + shared content term) and action-level grounding."""

from app.models import DraftAction, SiisSentence


def ground(actions: list[DraftAction], sentences: list[SiisSentence]) -> list[DraftAction]:
    raise NotImplementedError
