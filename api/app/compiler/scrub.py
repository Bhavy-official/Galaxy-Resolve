"""Zero-URL guard: removes http(s), www., domains, emails, markdown links from every string."""


def scrub(text: str) -> str:
    raise NotImplementedError


def has_leak(text: str) -> bool:
    raise NotImplementedError
