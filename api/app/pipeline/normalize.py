"""Component 1: normalize query, scrub URLs/emails from SIIS, compute siis_hash. No LLM."""


def normalize_query(query: str) -> str:
    raise NotImplementedError


def clean_siis(siis: dict | str | None) -> tuple[str, str | None]:
    """Return (siis_clean, siis_hash)."""
    raise NotImplementedError
