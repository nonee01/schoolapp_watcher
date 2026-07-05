"""CSV serialization for store resources — flat rows for spreadsheets/Excel.

Works off the plain envelope `data` (dicts/lists) the store hands back, so a
`schoolapp csv` export and an `/api` reader see the same shapes. Stats popups
(MarkStatistics) are pivoted: one row per (element, eval), metrics as columns.
"""
from __future__ import annotations

import csv
import io
from typing import Iterable


def rows_to_csv(rows: list[dict], columns: list[str] | None = None) -> str:
    """Flat resources (elements, modules, semesters, years, absences, courses)."""
    if not rows:
        return ""
    if columns is None:
        columns = list(dict.fromkeys(k for r in rows for k in r if k != "raw"))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: _flat(row.get(c, "")) for c in columns})
    return buf.getvalue()


def stats_to_csv(stats: list[dict]) -> str:
    """Pivot MarkStatistics popups: one row per (element, eval_kind), each metric
    label ('Votre note', 'Moyenne promo', 'Votre classement'…) becoming a column.
    This is the rattrapage/exam ranking data (NoteRAT/NoteEX/NoteCC/MoyElem)."""
    if not stats:
        return ""
    metric_labels: list[str] = []
    for s in stats:
        for row in s.get("rows", []):
            if len(row) >= 2 and row[0] not in metric_labels:
                metric_labels.append(row[0])
    columns = ["element", "eval_kind", "au", "note", *metric_labels]
    flat: list[dict] = []
    for s in stats:
        record = {k: s.get(k, "") for k in ("element", "eval_kind", "au", "note")}
        for row in s.get("rows", []):
            if len(row) >= 2:
                record[row[0]] = row[1]
        flat.append(record)
    return rows_to_csv(flat, columns)


def _flat(value) -> str:
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, (list, tuple)):
        return "; ".join(_flat(v) for v in value)
    if isinstance(value, dict):
        return "; ".join(f"{k}={_flat(v)}" for k, v in value.items())
    return "" if value is None else str(value)
