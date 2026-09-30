"""SQLite persistence + single-flight lock per key."""

from app.models import CacheEntry


def put(entry: CacheEntry) -> None:
    raise NotImplementedError
