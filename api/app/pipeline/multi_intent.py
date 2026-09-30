"""Component 11: dedupe actions across Goals; keep each in its most relevant Goal; drop empty Goals."""

from app.models import DraftAction, Intent


def dedupe_across_goals(intents: list[Intent], actions: list[DraftAction]) -> list[DraftAction]:
    raise NotImplementedError
