"""Component 7 (offline): strip description boilerplate, drop appliances (manual list), read polarity from message when originalType is null."""


def load_clean_catalog(path: str) -> list[dict]:
    raise NotImplementedError


def polarity(entry: dict) -> str | None:
    raise NotImplementedError
