"""Promotion grade-distribution reconstruction.

The portal never lists other students' notes with names — you only ever see
your own note plus aggregate stats and your rank. But its per-element stats
endpoint answers, for ANY hypothetical note you feed it,

    rank(note) = 1 + #{students scoring strictly above `note`}

which is monotonic non-increasing in note. Sweeping `note` across [lo, hi]
therefore recovers the entire (anonymized) grade distribution of the promotion
— every note, no identities. This is the "Notes RATT" curve reconstruction.
"""
from __future__ import annotations

from typing import Callable

# alias → the portal's eval parameter (mirrors client._EVAL_ALIASES).
EVAL_LABELS = {
    "rat": "NoteRAT", "noterat": "NoteRAT",
    "moy": "MoyElem", "moyelem": "MoyElem", "moyenne": "MoyElem",
    "ex": "NoteEX", "noteex": "NoteEX",
    "cc": "NoteCC", "notecc": "NoteCC",
    "tp": "NoteTP", "notetp": "NoteTP",
}


def reconstruct(probe: Callable[[float], int], *, lo: float = -2.0, hi: float = 20.5,
                resolution: float = 0.01, max_probes: int = 12000) -> list[tuple[float, int]]:
    """Return [(note, count)] ascending by note — `count` students scored exactly
    `note`. `probe(note)` must return rank = 1 + #{students with note strictly >
    `note`} (as the elemstat endpoint does). Adaptive bisection only probes where
    the rank actually changes, so the cost scales with the number of distinct notes.
    """
    cache: dict[float, int] = {}
    probes = 0

    def rank(v: float) -> int:
        nonlocal probes
        key = round(v, 2)
        if key not in cache:
            cache[key] = probe(key)
            probes += 1
        return cache[key]

    steps: list[tuple[float, int]] = []
    stack = [(round(lo, 2), round(hi, 2), rank(lo), rank(hi))]
    while stack:
        a, b, ra, rb = stack.pop()
        if ra == rb:
            continue  # no students scored in (a, b]
        mid = round((a + b) / 2, 2)
        if b - a <= resolution + 1e-9 or mid <= a or mid >= b or probes >= max_probes:
            steps.append((b, ra - rb))  # (ra - rb) students scored in (a, b] → at b
            continue
        rm = rank(mid)
        stack.append((a, mid, ra, rm))
        stack.append((mid, b, rm, rb))
    steps.sort()
    return steps


def expand_to_rows(element: str, eval_kind: str,
                   steps: list[tuple[float, int]]) -> list[dict]:
    """One row per student position (anonymized): the best note is rank 1."""
    rows: list[dict] = []
    rank = 1
    for note, count in sorted(steps, key=lambda s: s[0], reverse=True):
        for _ in range(count):
            rows.append({"element": element, "eval": eval_kind,
                         "rank": rank, "note": f"{note:.2f}"})
            rank += 1
    return rows
