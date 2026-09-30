"""Domain and relevance mismatch gate for cross-domain SIIS protection."""
from __future__ import annotations

import re
from app.cache.slots import extract_slots
from app.pipeline.textutil import tokens, STOPWORDS

GENERIC = frozenset(
    """phone galaxy samsung device tablet mobile smartphone ultra plus new old something anything
    nothing problem problems issue issues trouble happens happen happened seems able unable cant
    cannot wont doesnt dont isnt time times way thing things lot really much many like also completely
    totally suddenly always never sometimes often whenever every each""".split()
)

GENERAL_FIX = frozenset(
    """charge charges charged charging charger restart restarts restarted reboot reboots
    update updates updated reset resets support contact service safe mode factory backup""".split()
)


def is_mismatched_article(query: str, article_content: str, article_title: str = "") -> bool:
    """Return True if the article is completely unrelated to the user complaint."""
    if not query or not article_content:
        return False

    q_slots = extract_slots(query)
    q_tokens = [
        t for t in tokens(query)
        if len(t) >= 4 and t.isalpha() and t not in STOPWORDS and t not in GENERIC and t not in GENERAL_FIX
    ]

    # If query has no distinctive terms or slots, we cannot reliably declare a mismatch
    if not q_slots.domains and not q_tokens:
        return False

    combined_article = (article_title + " " + article_content).lower()
    art_tokens = set(tokens(combined_article))

    # 1. Check if any distinctive query token appears in article
    for qt in q_tokens:
        stem = qt[:4]
        if any(at.startswith(stem) for at in art_tokens):
            return False  # Shared substantive word -> not mismatched

    # 2. Check if query domain is represented in article
    if q_slots.domains:
        for domain in q_slots.domains:
            if domain in combined_article or any(at.startswith(domain[:4]) for at in art_tokens):
                return False

    # No domain and no distinctive query word found in article
    return True
