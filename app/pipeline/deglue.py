"""Viterbi word degluer and scraper run-on text repair."""
from __future__ import annotations

import math
import re
from functools import lru_cache

# Punctuation missing space repair: "reasons.restart" -> "reasons. restart"
_GLUED_PUNCT = re.compile(r"(?<=[a-z]{2})([.!?;,])([A-Za-z])(?=[a-z])")
_RUN = re.compile(r"[a-z]{15,}")

# Core unigram frequencies for common technical/Galaxy troubleshooting vocabulary
COMMON_WORDS = (
    "the of and to a in for is on that by this with i you it not or be are from at as your all have new more "
    "an was we will home can us about if my has but our one other do no make time see up then back also screen "
    "device phone settings tap display restart reboot safe mode power battery charging charge touch reset "
    "wifi network data bluetooth app apps clear storage cache sound volume button key volume volume camera "
    "notification notifications lock security biometrics finger face pin password accounts cloud google samsung "
    "switch smart update software version system factory backup restore recovery enter select press hold swipe "
    "open navigate go launch turn toggle enable disable remove insert connect disconnect plug unplug check inspect "
    "examine ensure try install uninstall clean increase decrease adjust set change drag search locate place review "
    "confirm allow add choose use avoid keep wait reinsert release scan perform find follow return repeat delete"
).split()

_WORD_COST = {w: -math.log((i + 1) / len(COMMON_WORDS)) for i, w in enumerate(COMMON_WORDS)}
_MAX_WORD_LEN = 20


@lru_cache(maxsize=1024)
def split_glued_run(s: str) -> str:
    """Viterbi dynamic programming word segmentation for glued runs."""
    n = len(s)
    if n <= 3:
        return s

    cost = [0.0] + [float("inf")] * n
    prev = [0] * (n + 1)

    for i in range(1, n + 1):
        for j in range(max(0, i - _MAX_WORD_LEN), i):
            word = s[j:i]
            c = _WORD_COST.get(word, 9.0 + (len(word) * 0.5))
            if cost[j] + c < cost[i]:
                cost[i] = cost[j] + c
                prev[i] = j

    words = []
    curr = n
    while curr > 0:
        words.append(s[prev[curr]:curr])
        curr = prev[curr]
    words.reverse()
    return " ".join(words)


def deglue(text: str) -> str:
    """Repair missing spaces in scraped technical articles."""
    if not text:
        return ""
    # 1. Add space after punctuation if glued
    repaired = _GLUED_PUNCT.sub(r"\1 \2", text)

    # 2. Segment abnormal run-ons of lowercase letters > 15 chars
    def _repl(m: re.Match) -> str:
        run = m.group(0)
        # Avoid splitting common long technical words like 'telecommunications'
        if run in _WORD_COST:
            return run
        return split_glued_run(run)

    return _RUN.sub(_repl, repaired)
