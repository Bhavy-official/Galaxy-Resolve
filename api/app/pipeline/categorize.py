"""Component 8: keyword overrides for critical/manual; auto only via the tiered link decision."""

from app.models import DraftAction


def categorize(actions: list[DraftAction]) -> list[DraftAction]:
    raise NotImplementedError
