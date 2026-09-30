"""Component 7 (offline): cluster entries into ScreenNodes (shared validation deeplink or near-identical description)."""

from app.models import ScreenNode


def build_nodes(entries: list[dict]) -> list[ScreenNode]:
    raise NotImplementedError
