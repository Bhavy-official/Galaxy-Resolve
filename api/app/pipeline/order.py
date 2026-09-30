"""Component 9: disruption rank + dependency topological sort (data/dependencies.json), SIIS order tiebreak."""

from app.models import DraftAction


def order(actions: list[DraftAction]) -> list[DraftAction]:
    raise NotImplementedError
