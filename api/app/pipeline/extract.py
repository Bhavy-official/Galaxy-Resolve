"""Component 5: Stage 2 LLM call — actions with cited steps, screen_path, verb, draft description."""

from app.models import DraftAction, Intent, SiisSentence


def extract(intents: list[Intent], sentences: list[SiisSentence]) -> list[DraftAction]:
    raise NotImplementedError
