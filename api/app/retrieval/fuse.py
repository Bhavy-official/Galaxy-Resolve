"""Reciprocal rank fusion of BM25 and dense results."""


def rrf(*ranked: list[tuple[str, float]], k: int = 60) -> list[tuple[str, float]]:
    raise NotImplementedError
