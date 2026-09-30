"""Pre-warmed no-SIIS lookup table (built offline from the kit). SIIS cache is never pre-warmed."""


def lookup_no_siis(norm_query: str) -> dict | None:
    raise NotImplementedError
