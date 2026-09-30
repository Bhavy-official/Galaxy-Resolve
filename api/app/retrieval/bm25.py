"""BM25 over Screen Graph nodes; message and qna_description weighted above description."""


def search(query: str, k: int = 20) -> list[tuple[str, float]]:
    raise NotImplementedError
