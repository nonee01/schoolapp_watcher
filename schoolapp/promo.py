"""Promotion grade-distribution reconstruction.

The portal never lists other students' notes with names — you only ever see
your own note plus aggregate stats and your rank. But its stats endpoints
answer, for ANY hypothetical note you feed them,

    rank(note) = 1 + #{students scoring strictly above `note`}

which is monotonic non-increasing in note. Sweeping `note` across [lo, hi]
therefore recovers the entire (anonymized) grade distribution of the promotion
— every note, no identities. The same sweep works at every level:
`/notes-stat/elemevalsat` (element), `/notes-stat/semsat` (semester moyenne),
and `/notes-stat/anneesat` (année moyenne); only the probe's parameters differ.
"""
from __future__ import annotations

import math
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


def _median(steps: list[tuple[float, int]]) -> float:
    notes: list[float] = []
    for note, count in sorted(steps):
        notes.extend([note] * count)
    if not notes:
        return 0.0
    n = len(notes)
    mid = n // 2
    return notes[mid] if n % 2 else round((notes[mid - 1] + notes[mid]) / 2, 4)


def _int(v):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def histogram_rows(code: str, level: str, eval: str,
                   steps: list[tuple[float, int]], width: float = 1.0) -> list[dict]:
    """Binned distribution: how many students fall in each [low, high) bin
    (top bin closed). Percent is of the recovered total; cumulative is running."""
    if not steps or width <= 0:
        return []
    total = sum(c for _, c in steps)
    lo = math.floor(min(n for n, _ in steps) / width) * width
    hi = math.ceil(max(n for n, _ in steps) / width) * width
    nbins = max(1, round((hi - lo) / width))
    counts = [0] * nbins
    for note, count in steps:
        idx = int((note - lo) / width)
        if idx >= nbins:  # top edge closed
            idx = nbins - 1
        counts[idx] += count
    rows, cumulative = [], 0
    for i, c in enumerate(counts):
        cumulative += c
        rows.append({"code": code, "level": level, "eval": eval,
                     "bin_low": round(lo + i * width, 4),
                     "bin_high": round(lo + (i + 1) * width, 4),
                     "count": c, "percent": round(100 * c / total, 4) if total else 0.0,
                     "cumulative": cumulative})
    return rows


def distribution_rows(code: str, level: str, eval: str,
                      steps: list[tuple[float, int]]) -> list[dict]:
    """Exact reconstructed distribution, best note first. rank_top = the rank of
    the best-scoring student holding that note (1 for the max)."""
    rows, rank = [], 1
    for note, count in sorted(steps, key=lambda s: s[0], reverse=True):
        rows.append({"code": code, "level": level, "eval": eval,
                     "note": f"{note:.2f}", "count": count, "rank_top": rank})
        rank += count
    return rows


def student_rows(code: str, level: str, eval: str,
                 steps: list[tuple[float, int]]) -> list[dict]:
    """One row per student position (anonymized), best = rank 1."""
    rows = []
    for r in expand_to_rows(code, eval, steps):
        rows.append({"code": code, "level": level, "eval": eval,
                     "rank": r["rank"], "note": r["note"]})
    return rows


def summary_row(code: str, level: str, eval: str, steps: list[tuple[float, int]],
                aggregates: dict, your_note=None, your_rank=None,
                au: str = "", filiere: str = "") -> dict:
    """One-row promotion summary combining the free popup aggregates with the
    reconstructed median and recovered count."""
    return {"code": code, "level": level, "eval": eval, "au": au, "filiere": filiere,
            "effectif": _int(aggregates.get("Effectif")),
            "recovered": sum(c for _, c in steps),
            "moyenne_promo": aggregates.get("Moyenne promo", ""),
            "min": aggregates.get("Min", ""), "max": aggregates.get("Max", ""),
            "ecart_type": aggregates.get("Ecart type", ""),
            "median": _median(steps),
            "your_note": your_note or "", "your_rank": your_rank or ""}
