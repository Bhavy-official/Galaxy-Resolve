"""Component 3: Stage 1 LLM call — intents, domain, title, 12 candidate variations; lexical-diversity filter."""

from app.models import Intent


def enrich(norm_query: str) -> tuple[list[Intent], list[str]]:
    """Return (intents, 8-10 filtered variations)."""
    raise NotImplementedError
