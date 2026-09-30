"""Local ONNX embeddings (ADR-005) + in-memory vector index. Shared by retrieval, cache and grounding."""


def embed(texts: list[str]) -> list[list[float]]:
    raise NotImplementedError


def search(query: str, k: int = 20) -> list[tuple[str, float]]:
    raise NotImplementedError
