"""Component 7 (runtime): step -> node -> entry by polarity; tiered link decision (catalog / dummy / manual)."""

from app.models import DraftAction, LinkDecision


def resolve(action: DraftAction) -> LinkDecision:
    raise NotImplementedError
