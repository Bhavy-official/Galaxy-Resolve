"""Component 4: split SIIS into sections and numbered sentences; rank sections per intent."""

from app.models import Intent, SiisSentence


def segment(siis_clean: str, intents: list[Intent]) -> list[SiisSentence]:
    raise NotImplementedError
