"""Component 10: DraftActions -> official Goal objects; score = 0.4 relevance + 0.3 grounding + 0.3 link coverage."""

from app.models import DraftAction, Intent


def compile_goals(intents: list[Intent], actions: list[DraftAction]) -> list[dict]:
    raise NotImplementedError
