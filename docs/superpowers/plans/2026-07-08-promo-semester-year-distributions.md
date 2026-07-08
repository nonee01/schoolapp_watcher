# Promo Distributions (Semester & Année) + Rich Artifacts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the whole-promotion note reconstruction from elements to semester and année levels, and emit five linked artifacts per evaluation (histogram CSV, exact-distribution CSV, per-student CSV, stats-summary CSV, and a matplotlib histogram PNG), all keyed by the ENSAM code.

**Architecture:** The existing `promo.reconstruct()` bisection sweep is level-agnostic — only the probe closure changes. We add semester/année probes to `client.py` on a shared `_stat_probe` helper, add pure row-builder functions to `promo.py`, isolate matplotlib in a new `plots.py`, and expose three CLI commands (`promo`, `promo-sem`, `promo-year`) that share one artifact emitter.

**Tech Stack:** Python 3.11+, requests, BeautifulSoup, typer, rich, matplotlib (new), pytest.

## Global Constraints

- Python 3.11+; typed code; follow existing module style.
- New runtime dependency: `matplotlib` in `requirements.txt`. Import it **lazily** (inside the plotting function only) so the rest of the tool runs without it.
- Frozen API contracts: `/api/promo/<code>` shape is additive-only; do not change existing response shapes.
- PII rule: test fixtures must contain no real CIN/CNE/email/name/photo. The stat popups used here return only aggregates + the student's own note/rank; craft **synthetic** fixture HTML, never capture real pages.
- Log in from code with `.env` creds; never a browser form. Every probe is rate-limited by `--min-interval` (default 0.25 s).
- Target selection by plain label — **no `au` parameter/flag**. au and filière are auto-resolved from the student's own rows and recorded inside the summary CSV only.
- Semester labels: `S1, S2, S3, S4, …` matched against the `Semestre` column. Année labels: `1A, 2A, …` matched against the `Niveau` column.
- Commit only what each task touches. Never push. Never stage the user's pre-existing uncommitted work.
- Reuse the existing `reconstruct` / `expand_to_rows` — do not reimplement the sweep.

---

### Task 1: Semester & année probes on a shared `_stat_probe` helper

**Files:**
- Modify: `schoolapp/client.py` (refactor `rank_for_note`, add `_stat_probe`, `rank_for_note_sem`, `rank_for_note_year`, `promo_aggregates`)
- Test: `tests/test_promo_probes.py` (create)

**Interfaces:**
- Consumes: existing `parse_mark_statistics`, `_as_int`, `STATS_PATH`, `self._get`.
- Produces:
  - `SchoolAppClient._stat_probe(self, path: str, params: dict) -> dict[str, str]` — returns the popup's label→value dict (e.g. `{"Effectif": "423", "Votre classement": "224", "Moyenne promo": "12.57", "Min": "0.4", "Max": "17.0", "Ecart type": "1.9", "Votre note": "12.57"}`), or `{}` if no stat.
  - `SchoolAppClient.rank_for_note_sem(self, niveau: str, filiere: str, semestre: str, au: str, note: float | str) -> tuple[int, int] | None` — `(rank, effectif)`.
  - `SchoolAppClient.rank_for_note_year(self, niveau: str, filiere: str, au: str, note: float | str) -> tuple[int, int] | None`.
  - `SchoolAppClient.promo_aggregates(self, path: str, params: dict) -> dict[str, str]` — one probe (caller passes `note` in `params`); returns the `_stat_probe` dict.
  - Module constants `SEM_STATS_PATH = "/notes-stat/semsat"`, `YEAR_STATS_PATH = "/notes-stat/anneesat"`.
  - `rank_for_note` (element) keeps its existing signature `(code, eval_kind, au, note) -> tuple[int,int] | None`, now implemented via `_stat_probe`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_promo_probes.py`:

```python
"""Semester & année rank probes reuse the elemstat mechanism."""
import requests
from schoolapp.client import SCHOOLAPP_BASE, SchoolAppClient


def _popup(rank: int, effectif: int) -> str:
    # Synthetic /notes-stat popup: div.stat > p title + a th/td table. No PII.
    return (
        '<div class="stat"><p>Statistiques</p><table>'
        '<tr><th>Votre note</th><td>10.0</td></tr>'
        '<tr><th>Moyenne promo</th><td>12.05</td></tr>'
        '<tr><th>Max</th><td>16.85</td></tr>'
        '<tr><th>Min</th><td>0.25</td></tr>'
        '<tr><th>Ecart type</th><td>1.91</td></tr>'
        f'<tr><th>Effectif</th><td>{effectif}</td></tr>'
        f'<tr><th>Votre classement</th><td>{rank}</td></tr>'
        '</table></div>'
    )


class RankSession:
    """Serves a popup whose rank = 1 + #students strictly above the probed note.
    Distribution: notes [0, 5, 5, 12, 20] over effectif=5."""
    NOTES = [0.0, 5.0, 5.0, 12.0, 20.0]

    def __init__(self):
        self.logged_in = True
        self.calls = []

    def get(self, url, params=None, timeout=None):
        path = url.replace(SCHOOLAPP_BASE, "")
        self.calls.append((path, dict(params or {})))
        note = float(params.get("note", 0))
        rank = 1 + sum(1 for n in self.NOTES if n > note)
        return _Resp(_popup(rank, len(self.NOTES)))

    def post(self, url, data=None, timeout=None):
        return _Resp("<html>bienvenue</html>")


class _Resp:
    def __init__(self, text): self.text, self.status_code, self.headers = text, 200, {"Content-Type": "text/html"}
    def raise_for_status(self): pass


def _client():
    s = RankSession()
    c = SchoolAppClient(session=s)
    c._email, c._password = "e", "p"  # skip login network
    return c, s


def test_rank_for_note_sem_hits_semsat_with_all_params():
    c, s = _client()
    assert c.rank_for_note_sem("1A", "API-MPT", "S1", "2024-2025", 12.0) == (2, 5)
    path, params = s.calls[-1]
    assert path == "/notes-stat/semsat"
    assert params == {"eval": "MoySem", "niveau": "1A", "filiere": "API-MPT",
                      "semestre": "S1", "au": "2024-2025", "note": "12.0"}


def test_rank_for_note_year_hits_anneesat_with_all_params():
    c, s = _client()
    assert c.rank_for_note_year("2A", "API-MPT", "2025-2026", 20.0) == (1, 5)
    path, params = s.calls[-1]
    assert path == "/notes-stat/anneesat"
    assert params == {"eval": "MoyAn", "niveau": "2A", "filiere": "API-MPT",
                      "au": "2025-2026", "note": "20.0"}


def test_rank_is_monotonic_bracketing_the_promotion():
    c, s = _client()
    assert c.rank_for_note_sem("1A", "API-MPT", "S1", "2024-2025", -1)[0] == 6   # below all
    assert c.rank_for_note_sem("1A", "API-MPT", "S1", "2024-2025", 20.5)[0] == 1  # above all


def test_stat_probe_returns_full_aggregate_dict():
    c, s = _client()
    d = c._stat_probe("/notes-stat/semsat",
                      {"eval": "MoySem", "niveau": "1A", "filiere": "API-MPT",
                       "semestre": "S1", "au": "2024-2025", "note": "10"})
    assert d["Effectif"] == "5" and d["Moyenne promo"] == "12.05"
    assert d["Min"] == "0.25" and d["Max"] == "16.85" and d["Ecart type"] == "1.91"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_promo_probes.py -v`
Expected: FAIL — `AttributeError: 'SchoolAppClient' object has no attribute 'rank_for_note_sem'`.

- [ ] **Step 3: Write minimal implementation**

In `schoolapp/client.py`, add the two path constants near `STATS_PATH` (line ~56):

```python
STATS_PATH = "/notes-stat/elemevalsat"
SEM_STATS_PATH = "/notes-stat/semsat"
YEAR_STATS_PATH = "/notes-stat/anneesat"
```

Add `_stat_probe` and rewrite `rank_for_note` on top of it, then add the two new probes. Replace the existing `rank_for_note` method (client.py ~197-214) with:

```python
    def _stat_probe(self, path: str, params: dict) -> dict[str, str]:
        """One GET to a /notes-stat popup with a HYPOTHETICAL note. Returns the
        popup's label→value dict, or {} if the eval is unavailable."""
        html = self._get(path, **{k: str(v) for k, v in params.items()})
        stat = parse_mark_statistics(html)
        if not stat:
            return {}
        return {r[0]: r[1] for r in stat.rows if len(r) >= 2}

    def _rank_effectif(self, d: dict[str, str]) -> tuple[int, int] | None:
        rank, effectif = _as_int(d.get("Votre classement")), _as_int(d.get("Effectif"))
        if rank is None or effectif is None:
            return None
        return rank, effectif

    def rank_for_note(self, code: str, eval_kind: str, au: str,
                      note: float | str) -> tuple[int, int] | None:
        """Element-level probe (see promo.reconstruct). rank = 1 + #above."""
        eval_param = self._EVAL_ALIASES.get(eval_kind.strip().lower(), eval_kind)
        d = self._stat_probe(STATS_PATH, {"eval": eval_param, "codeelem": code.upper(),
                                          "au": au, "note": note})
        return self._rank_effectif(d) if d else None

    def rank_for_note_sem(self, niveau: str, filiere: str, semestre: str, au: str,
                          note: float | str) -> tuple[int, int] | None:
        d = self._stat_probe(SEM_STATS_PATH, {"eval": "MoySem", "niveau": niveau,
                             "filiere": filiere, "semestre": semestre, "au": au, "note": note})
        return self._rank_effectif(d) if d else None

    def rank_for_note_year(self, niveau: str, filiere: str, au: str,
                           note: float | str) -> tuple[int, int] | None:
        d = self._stat_probe(YEAR_STATS_PATH, {"eval": "MoyAn", "niveau": niveau,
                             "filiere": filiere, "au": au, "note": note})
        return self._rank_effectif(d) if d else None

    def promo_aggregates(self, path: str, params: dict) -> dict[str, str]:
        """The constant aggregates (Moyenne promo/Min/Max/Ecart type/Effectif)
        a single popup returns — caller supplies `note` in params."""
        return self._stat_probe(path, params)
```

Note: `_get(path, **params)` passes params as GET query args (see `_get` → `_request(params=...)`). Values are stringified so `note=12.0` serializes as `"12.0"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_promo_probes.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the full suite to confirm no regression**

Run: `pytest tests/test_fetch_all.py -q`
Expected: PASS — the element `rank_for_note` behaviour is unchanged.

- [ ] **Step 6: Commit**

```bash
git add schoolapp/client.py tests/test_promo_probes.py
git commit -m "feat(client): semester & année rank probes on shared _stat_probe"
```

---

### Task 2: Pure artifact row-builders in `promo.py`

**Files:**
- Modify: `schoolapp/promo.py` (add `histogram_rows`, `distribution_rows`, `student_rows`, `summary_row`, `_median`)
- Test: `tests/test_promo.py` (append)

**Interfaces:**
- Consumes: `steps: list[tuple[float, int]]` from `reconstruct`; existing `expand_to_rows`.
- Produces (all pure, no I/O; every row carries `code, level, eval`):
  - `histogram_rows(code, level, eval, steps, width=1.0) -> list[dict]` keys: `code, level, eval, bin_low, bin_high, count, percent, cumulative`.
  - `distribution_rows(code, level, eval, steps) -> list[dict]` keys: `code, level, eval, note, count, rank_top`.
  - `student_rows(code, level, eval, steps) -> list[dict]` keys: `code, level, eval, rank, note`.
  - `summary_row(code, level, eval, steps, aggregates, your_note=None, your_rank=None) -> dict` keys: `code, level, eval, au, filiere, effectif, recovered, moyenne_promo, min, max, ecart_type, median, your_note, your_rank`.
  - `_median(steps) -> float`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_promo.py`:

```python
def _steps():
    # 6 students: notes 2.0×1, 8.0×2, 12.5×2, 19.0×1
    return [(2.0, 1), (8.0, 2), (12.5, 2), (19.0, 1)]


def test_histogram_rows_bins_by_width_with_percent_and_cumulative():
    rows = promo.histogram_rows("S1", "semester", "MoySem", _steps(), width=5.0)
    # bins from floor(2)=0 → ceil(19)=20 in steps of 5: [0,5),[5,10),[10,15),[15,20]
    by_bin = {(r["bin_low"], r["bin_high"]): r for r in rows}
    assert by_bin[(0.0, 5.0)]["count"] == 1   # 2.0
    assert by_bin[(5.0, 10.0)]["count"] == 2  # 8.0×2
    assert by_bin[(10.0, 15.0)]["count"] == 2 # 12.5×2
    assert by_bin[(15.0, 20.0)]["count"] == 1 # 19.0 (top bin closed)
    assert round(by_bin[(5.0, 10.0)]["percent"], 2) == 33.33
    assert rows[-1]["cumulative"] == 6
    assert all(r["code"] == "S1" and r["eval"] == "MoySem" for r in rows)


def test_distribution_rows_are_exact_ground_truth_best_first():
    rows = promo.distribution_rows("S1", "semester", "MoySem", _steps())
    assert [r["note"] for r in rows] == ["19.00", "12.50", "8.00", "2.00"]
    assert [r["count"] for r in rows] == [1, 2, 2, 1]
    assert [r["rank_top"] for r in rows] == [1, 2, 4, 6]  # rank of the best in each note


def test_summary_row_reports_effectif_recovered_and_median():
    aggr = {"Moyenne promo": "10.5", "Min": "2.0", "Max": "19.0",
            "Ecart type": "5.0", "Effectif": "6"}
    row = promo.summary_row("S1", "semester", "MoySem", _steps(), aggr,
                            your_note="12.5", your_rank="3")
    assert row["effectif"] == 6 and row["recovered"] == 6
    assert row["moyenne_promo"] == "10.5" and row["median"] == 10.25
    assert row["your_note"] == "12.5" and row["your_rank"] == "3"


def test_student_rows_carry_level_and_code():
    rows = promo.student_rows("2A", "year", "MoyAn", [(8.0, 1), (15.0, 1)])
    assert rows[0] == {"code": "2A", "level": "year", "eval": "MoyAn",
                       "rank": 1, "note": "15.00"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_promo.py -k "histogram or distribution or summary or student_rows" -v`
Expected: FAIL — `AttributeError: module 'schoolapp.promo' has no attribute 'histogram_rows'`.

- [ ] **Step 3: Write minimal implementation**

Append to `schoolapp/promo.py`:

```python
import math


def _median(steps: list[tuple[float, int]]) -> float:
    notes: list[float] = []
    for note, count in sorted(steps):
        notes.extend([note] * count)
    if not notes:
        return 0.0
    n = len(notes)
    mid = n // 2
    return notes[mid] if n % 2 else round((notes[mid - 1] + notes[mid]) / 2, 4)


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


def _int(v):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_promo.py -v`
Expected: PASS (all, including the pre-existing reconstruct tests).

- [ ] **Step 5: Commit**

```bash
git add schoolapp/promo.py tests/test_promo.py
git commit -m "feat(promo): histogram/distribution/student/summary row builders"
```

---

### Task 3: Histogram PNG plotting (isolated matplotlib)

**Files:**
- Create: `schoolapp/plots.py`
- Modify: `requirements.txt` (add `matplotlib`)
- Test: `tests/test_plots.py` (create)

**Interfaces:**
- Consumes: `histogram_rows` output (list of dicts with `bin_low, bin_high, count`).
- Produces: `plots.histogram_png(bins: list[dict], *, path: str, title: str, subtitle: str = "", mean: float | None = None, your_note: float | None = None) -> str` — writes a PNG to `path`, returns `path`. Raises `RuntimeError` with an install hint if matplotlib is missing.

- [ ] **Step 1: Write the failing test**

Create `tests/test_plots.py`:

```python
import os
import pytest

matplotlib = pytest.importorskip("matplotlib")  # skip cleanly if not installed
from schoolapp import plots


def test_histogram_png_writes_a_nonempty_file(tmp_path):
    bins = [
        {"bin_low": 0.0, "bin_high": 5.0, "count": 1},
        {"bin_low": 5.0, "bin_high": 10.0, "count": 2},
        {"bin_low": 10.0, "bin_high": 15.0, "count": 2},
        {"bin_low": 15.0, "bin_high": 20.0, "count": 1},
    ]
    out = str(tmp_path / "hist.png")
    result = plots.histogram_png(bins, path=out, title="S1 · MoySem",
                                 subtitle="API-MPT 2024-2025", mean=10.5, your_note=12.5)
    assert result == out
    assert os.path.getsize(out) > 0


def test_histogram_png_empty_bins_still_writes(tmp_path):
    out = str(tmp_path / "empty.png")
    plots.histogram_png([], path=out, title="none")
    assert os.path.exists(out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_plots.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'schoolapp.plots'` (or skip if matplotlib absent — then install it first: `pip install matplotlib`).

- [ ] **Step 3: Write minimal implementation**

Create `schoolapp/plots.py`:

```python
"""Histogram rendering for promotion distributions. matplotlib is imported
lazily so the rest of the tool has no hard dependency on it."""
from __future__ import annotations


def histogram_png(bins: list[dict], *, path: str, title: str, subtitle: str = "",
                  mean: float | None = None, your_note: float | None = None) -> str:
    """Render histogram_rows as a bar chart PNG at `path`. Dashed line at the
    promotion mean, solid marker at your note. Returns `path`."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless: no display needed
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - exercised via CLI hint
        raise RuntimeError("matplotlib not installed — run: pip install matplotlib") from exc

    fig, ax = plt.subplots(figsize=(9, 5))
    if bins:
        centers = [(b["bin_low"] + b["bin_high"]) / 2 for b in bins]
        widths = [(b["bin_high"] - b["bin_low"]) * 0.9 for b in bins]
        ax.bar(centers, [b["count"] for b in bins], width=widths,
               color="#4C78A8", edgecolor="white")
        ax.set_xlabel("Note / 20")
        ax.set_ylabel("Nombre d'étudiants")
    if mean is not None:
        ax.axvline(mean, color="#F58518", linestyle="--", linewidth=2, label=f"Moyenne {mean:.2f}")
    if your_note is not None:
        ax.axvline(your_note, color="#54A24B", linestyle="-", linewidth=2, label=f"Vous {your_note:.2f}")
    if mean is not None or your_note is not None:
        ax.legend()
    ax.set_title(title if not subtitle else f"{title}\n{subtitle}", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
```

Add to `requirements.txt` (after `waitress==3.0.1`):

```
matplotlib==3.9.2
```

- [ ] **Step 4: Install matplotlib and run the test**

Run: `pip install matplotlib==3.9.2 && pytest tests/test_plots.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add schoolapp/plots.py tests/test_plots.py requirements.txt
git commit -m "feat(plots): matplotlib histogram PNG (lazy import)"
```

---

### Task 4: Shared artifact emitter + refactor element `promo` to use it

**Files:**
- Modify: `schoolapp/cli.py` (add `_emit_promo_artifacts`, `_promo_reconstruct_eval`; rewrite `promo_cmd` to use them, switching `--out` → `--out-dir`, adding `--bin`/`--no-plot`)
- Test: `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `promo.{reconstruct,histogram_rows,distribution_rows,student_rows,summary_row}`, `plots.histogram_png`, `client.{rank_for_note,promo_aggregates}`, `csvout.rows_to_csv`, `store.save_resource`.
- Produces:
  - `_promo_reconstruct_eval(client, level, eval_param, probe, agg_params, agg_path, resolution) -> tuple[list, dict] | None` — returns `(steps, aggregates)` or `None` if unavailable. `probe` is `Callable[[float], int]`.
  - `_emit_promo_artifacts(code, level, per_eval, out_dir, bin_width, plot, your=None, meta=None) -> list[dict]` — writes 4 CSVs + 1 PNG per eval into `out_dir`, prints paths, persists store, returns summary rows. `per_eval: list[tuple[str, list, dict]]` = `(eval_label, steps, aggregates)`. `your: dict[str, tuple[str,str]] | None` maps eval_label → (your_note, your_rank). `meta: dict[str, tuple[str,str]] | None` maps eval_label → (au, filiere) for the summary.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py` (follow the file's existing runner/import style; adapt `_run`/`runner` to what the file already uses):

```python
def test_promo_element_writes_five_artifacts_keyed_by_code(tmp_path, monkeypatch):
    from schoolapp import cli, promo

    class StubClient:
        def element_grades(self):
            from schoolapp.models import ElementGrade
            return [ElementGrade(code="API421", au="2024-2025")]
        def rank_for_note(self, code, ev, au, note):
            notes = [5.0, 5.0, 12.0, 20.0]
            return 1 + sum(1 for n in notes if n > float(note)), len(notes)
        def promo_aggregates(self, path, params):
            return {"Effectif": "4", "Moyenne promo": "10.5", "Min": "5.0",
                    "Max": "20.0", "Ecart type": "5.0", "Votre note": "12.0",
                    "Votre classement": "2"}

    monkeypatch.setattr(cli, "_library_client", lambda *a, **k: StubClient())
    out = tmp_path / "art"
    result = runner.invoke(cli.app, ["promo", "API421", "--eval", "moy",
                                     "--out-dir", str(out), "--no-plot"])
    assert result.exit_code == 0, result.output
    assert (out / "promo_API421_MoyElem_hist.csv").exists()
    assert (out / "promo_API421_MoyElem_dist.csv").exists()
    assert (out / "promo_API421_MoyElem_students.csv").exists()
    assert (out / "promo_API421_MoyElem_summary.csv").exists()
    text = (out / "promo_API421_MoyElem_students.csv").read_text()
    assert "API421" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -k promo_element_writes -v`
Expected: FAIL — the current `promo` command has no `--out-dir`/`--no-plot` and writes a single CSV.

- [ ] **Step 3: Write minimal implementation**

In `schoolapp/cli.py`, add the helpers above `promo_cmd`:

```python
def _promo_reconstruct_eval(client, agg_path, agg_params, probe, resolution):
    """Return (steps, aggregates) for one eval, or None if the eval is unavailable."""
    from . import promo as promo_mod
    first = client.promo_aggregates(agg_path, {**agg_params, "note": "20"})
    if not first:
        return None
    effectif = int(float(first.get("Effectif", "0") or 0))
    if effectif <= 0:
        return None
    steps = promo_mod.reconstruct(
        lambda n: (probe(n) or (1, effectif))[0], resolution=resolution)
    return steps, first


def _emit_promo_artifacts(code, level, per_eval, out_dir, bin_width, plot, your=None, meta=None):
    """Write 4 CSVs + optional PNG per eval into out_dir; persist store; print paths."""
    from . import promo as promo_mod
    your = your or {}
    meta = meta or {}
    out = Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    summaries, cached = [], {}
    for label, steps, aggr in per_eval:
        yn, yr = your.get(label, ("", ""))
        au, filiere = meta.get(label, ("", ""))
        hist = promo_mod.histogram_rows(code, level, label, steps, width=bin_width)
        dist = promo_mod.distribution_rows(code, level, label, steps)
        studs = promo_mod.student_rows(code, level, label, steps)
        summ = promo_mod.summary_row(code, level, label, steps, aggr,
                                     your_note=yn, your_rank=yr, au=au, filiere=filiere)
        base = out / f"promo_{code}_{label}"
        _write_csv(f"{base}_hist.csv", hist,
                   ["code", "level", "eval", "bin_low", "bin_high", "count", "percent", "cumulative"])
        _write_csv(f"{base}_dist.csv", dist,
                   ["code", "level", "eval", "note", "count", "rank_top"])
        _write_csv(f"{base}_students.csv", studs,
                   ["code", "level", "eval", "rank", "note"])
        _write_csv(f"{base}_summary.csv", [summ],
                   ["code", "level", "eval", "au", "filiere", "effectif", "recovered",
                    "moyenne_promo", "min", "max", "ecart_type", "median", "your_note", "your_rank"])
        if plot:
            try:
                from . import plots
                mean = float(aggr["Moyenne promo"]) if aggr.get("Moyenne promo") else None
                yn_f = float(yn) if yn else None
                png = plots.histogram_png(hist, path=f"{base}_hist.png",
                                          title=f"{code} · {label}",
                                          subtitle=f"{summ['filiere']} {summ['au']}".strip(),
                                          mean=mean, your_note=yn_f)
                log("SUCCESS", f"Wrote {png}")
            except RuntimeError as exc:
                log("WARNING", f"Plot skipped: {exc}")
        summaries.append(summ)
        cached[label] = {"steps": [[n, c] for n, c in steps], "summary": summ,
                         "bins": hist}
    store.save_resource(f"promo/{code.lower()}", cached, source="promo")
    return summaries


def _write_csv(path, rows, columns):
    Path(path).write_text(csvout.rows_to_csv(rows, columns=columns), encoding="utf-8")
    log("SUCCESS", f"Wrote {len(rows)} row(s) → {path}")
```

Rewrite `promo_cmd` — replace `au`/`out` options and the body. New signature and body:

```python
@app.command("promo", rich_help_panel="Live (portal login)")
def promo_cmd(
    ctx: typer.Context,
    code: str = typer.Argument(..., help="Element code, e.g. API421"),
    eval: str = typer.Option("rat,moy,ex,cc", "--eval",
        help="Comma list of evaluations: rat,moy,ex,cc,tp"),
    out_dir: str = typer.Option(".", "--out-dir", "-o", help="Directory for the CSV/PNG artifacts"),
    bin: float = typer.Option(1.0, "--bin", min=0.1, help="Histogram bin width"),
    no_plot: bool = typer.Option(False, "--no-plot", help="Skip the PNG figure"),
    resolution: float = typer.Option(0.01, help="Note granularity to resolve"),
    min_interval: float = typer.Option(0.25, min=0.0,
        help="Seconds between requests — be polite to the school server"),
    email: str | None = typer.Option(None, help="SchoolApp email"),
    password: str | None = typer.Option(None, help="SchoolApp password"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
) -> None:
    """Reconstruct the WHOLE promotion's notes for an ELEMENT (anonymized).

    Writes, per evaluation, a histogram CSV (how many got each mark), the exact
    distribution, per-student rows, a stats summary, and a histogram PNG — all
    named promo_<CODE>_<eval>_*. Fires many rate-limited requests."""
    from . import promo as promo_mod
    from .client import STATS_PATH

    code = code.upper()
    client = _library_client(ctx, email, password, timeout, min_interval=min_interval)
    target = next((g for g in client.element_grades() if g.code.upper() == code), None)
    au = target.au if target else None
    if not au:
        err_console.print(render.error_panel(
            f"Could not resolve the année universitaire for {code}."))
        raise typer.Exit(code=2)

    per_eval, your = [], {}
    for ev in (_split_csv(eval) or ["rat", "moy", "ex", "cc"]):
        eval_param = SchoolAppClient._EVAL_ALIASES.get(ev.strip().lower(), ev)
        label = promo_mod.EVAL_LABELS.get(ev.strip().lower(), eval_param)
        agg_params = {"eval": eval_param, "codeelem": code, "au": au}
        with err_console.status(f"Reconstructing {code} · {label}…"):
            res = _promo_reconstruct_eval(
                client, STATS_PATH, agg_params,
                lambda n, e=ev: client.rank_for_note(code, e, au, n),
                resolution)
        if not res:
            log("WARNING", f"{label} unavailable for {code} — skipping")
            continue
        steps, aggr = res
        per_eval.append((label, steps, aggr))
        your[label] = (aggr.get("Votre note", ""), aggr.get("Votre classement", ""))
        log("SUCCESS", f"{label}: recovered {sum(c for _, c in steps)} notes")

    if not per_eval:
        err_console.print(render.error_panel(f"No promotion data reconstructed for {code}."))
        raise typer.Exit(code=2)
    # element rows carry no filière; au is the resolved element au
    meta = {label: (au, "") for label, _, _ in per_eval}
    _emit_promo_artifacts(code, "element", per_eval, out_dir, bin, not no_plot, your, meta)
```

Ensure `SchoolAppClient` is imported in cli.py (check top imports; it already imports from `.client` — add `SchoolAppClient` if absent). Confirm `Path` and `csvout` are imported (they are).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -k promo -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add schoolapp/cli.py tests/test_cli.py
git commit -m "feat(cli): promo element emits 5 code-keyed artifacts via shared emitter"
```

---

### Task 5: `promo-sem` and `promo-year` commands

**Files:**
- Modify: `schoolapp/cli.py` (add `promo_sem_cmd`, `promo_year_cmd`, `_resolve_sem_row`, `_resolve_year_row`)
- Test: `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `_promo_reconstruct_eval`, `_emit_promo_artifacts`, `client.{semester_results, year_results, rank_for_note_sem, rank_for_note_year, promo_aggregates}`, `SEM_STATS_PATH`, `YEAR_STATS_PATH`.
- Produces: `promo-sem [SEMESTER]`, `promo-year [NIVEAU]` typer commands; helpers `_resolve_sem_row(rows, label) -> SemesterResult | None`, `_resolve_year_row(rows, label) -> YearResult | None` (label match, case-insensitive; `None` label → most recent, i.e. last row).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`:

```python
def test_promo_sem_resolves_label_and_writes_artifacts(tmp_path, monkeypatch):
    from schoolapp import cli
    from schoolapp.models import SemesterResult

    class StubClient:
        def semester_results(self):
            return [SemesterResult(niveau="1A", semestre="S1", au="2024-2025",
                                   moy_sem="12.573", classement="224 / 423",
                                   raw={"Filière": "API-MPT"})]
        def rank_for_note_sem(self, niveau, filiere, semestre, au, note):
            notes = [5.0, 12.0, 12.5, 20.0]
            return 1 + sum(1 for n in notes if n > float(note)), len(notes)
        def promo_aggregates(self, path, params):
            return {"Effectif": "4", "Moyenne promo": "12.57", "Min": "5.0",
                    "Max": "20.0", "Ecart type": "3.0", "Votre note": "12.573",
                    "Votre classement": "224"}

    monkeypatch.setattr(cli, "_library_client", lambda *a, **k: StubClient())
    out = tmp_path / "sem"
    result = runner.invoke(cli.app, ["promo-sem", "S1", "--out-dir", str(out), "--no-plot"])
    assert result.exit_code == 0, result.output
    assert (out / "promo_S1_MoySem_hist.csv").exists()
    assert (out / "promo_S1_MoySem_summary.csv").exists()
    assert "API-MPT" in (out / "promo_S1_MoySem_summary.csv").read_text()


def test_promo_sem_unknown_label_exits_2(tmp_path, monkeypatch):
    from schoolapp import cli
    from schoolapp.models import SemesterResult

    class StubClient:
        def semester_results(self):
            return [SemesterResult(niveau="1A", semestre="S1", au="2024-2025",
                                   raw={"Filière": "API-MPT"})]

    monkeypatch.setattr(cli, "_library_client", lambda *a, **k: StubClient())
    result = runner.invoke(cli.app, ["promo-sem", "S9", "--out-dir", str(tmp_path)])
    assert result.exit_code == 2


def test_promo_year_resolves_label(tmp_path, monkeypatch):
    from schoolapp import cli
    from schoolapp.models import YearResult

    class StubClient:
        def year_results(self):
            return [YearResult(niveau="2A", filiere="API-MPT", au="2025-2026",
                               moy_annee="12.824", classement="125 / 419")]
        def rank_for_note_year(self, niveau, filiere, au, note):
            notes = [5.0, 12.0, 20.0]
            return 1 + sum(1 for n in notes if n > float(note)), len(notes)
        def promo_aggregates(self, path, params):
            return {"Effectif": "3", "Moyenne promo": "12.05", "Min": "5.0",
                    "Max": "20.0", "Ecart type": "3.0", "Votre note": "12.824",
                    "Votre classement": "125"}

    monkeypatch.setattr(cli, "_library_client", lambda *a, **k: StubClient())
    out = tmp_path / "yr"
    result = runner.invoke(cli.app, ["promo-year", "2A", "--out-dir", str(out), "--no-plot"])
    assert result.exit_code == 0, result.output
    assert (out / "promo_2A_MoyAn_dist.csv").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -k "promo_sem or promo_year" -v`
Expected: FAIL — no `promo-sem`/`promo-year` command registered.

- [ ] **Step 3: Write minimal implementation**

In `schoolapp/cli.py` add resolvers + two commands (near `promo_cmd`):

```python
def _resolve_sem_row(rows, label):
    if not rows:
        return None
    if not label:
        return rows[-1]
    return next((r for r in rows if r.semestre.upper() == label.upper()), None)


def _resolve_year_row(rows, label):
    if not rows:
        return None
    if not label:
        return rows[-1]
    return next((r for r in rows if r.niveau.upper() == label.upper()), None)


@app.command("promo-sem", rich_help_panel="Live (portal login)")
def promo_sem_cmd(
    ctx: typer.Context,
    semestre: str | None = typer.Argument(None, help="Semester label, e.g. S1 S2 S3 S4 (default: latest)"),
    out_dir: str = typer.Option(".", "--out-dir", "-o", help="Directory for the CSV/PNG artifacts"),
    bin: float = typer.Option(1.0, "--bin", min=0.1, help="Histogram bin width"),
    no_plot: bool = typer.Option(False, "--no-plot", help="Skip the PNG figure"),
    resolution: float = typer.Option(0.01, help="Note granularity to resolve"),
    min_interval: float = typer.Option(0.25, min=0.0, help="Seconds between requests"),
    email: str | None = typer.Option(None, help="SchoolApp email"),
    password: str | None = typer.Option(None, help="SchoolApp password"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
) -> None:
    """Reconstruct the WHOLE promotion's SEMESTER moyennes (anonymized)."""
    from .client import SEM_STATS_PATH
    client = _library_client(ctx, email, password, timeout, min_interval=min_interval)
    rows = client.semester_results()
    row = _resolve_sem_row(rows, semestre)
    if not row:
        labels = ", ".join(sorted({r.semestre for r in rows})) or "none"
        err_console.print(render.error_panel(
            f"Semester {semestre!r} not found.", hint=f"Available: {labels}"))
        raise typer.Exit(code=2)
    code, filiere = row.semestre.upper(), row.raw.get("Filière", "")
    agg_params = {"eval": "MoySem", "niveau": row.niveau, "filiere": filiere,
                  "semestre": row.semestre, "au": row.au}
    with err_console.status(f"Reconstructing {code} · MoySem…"):
        res = _promo_reconstruct_eval(
            client, SEM_STATS_PATH, agg_params,
            lambda n: client.rank_for_note_sem(row.niveau, filiere, row.semestre, row.au, n),
            resolution)
    if not res:
        err_console.print(render.error_panel(f"No promotion data for {code}."))
        raise typer.Exit(code=2)
    steps, aggr = res
    per_eval = [("MoySem", steps, aggr)]
    _emit_promo_artifacts(code, "semester", per_eval, out_dir, bin, not no_plot,
                          {"MoySem": (aggr.get("Votre note", ""), aggr.get("Votre classement", ""))},
                          {"MoySem": (row.au, filiere)})


@app.command("promo-year", rich_help_panel="Live (portal login)")
def promo_year_cmd(
    ctx: typer.Context,
    niveau: str | None = typer.Argument(None, help="Year label, e.g. 1A 2A (default: latest)"),
    out_dir: str = typer.Option(".", "--out-dir", "-o", help="Directory for the CSV/PNG artifacts"),
    bin: float = typer.Option(1.0, "--bin", min=0.1, help="Histogram bin width"),
    no_plot: bool = typer.Option(False, "--no-plot", help="Skip the PNG figure"),
    resolution: float = typer.Option(0.01, help="Note granularity to resolve"),
    min_interval: float = typer.Option(0.25, min=0.0, help="Seconds between requests"),
    email: str | None = typer.Option(None, help="SchoolApp email"),
    password: str | None = typer.Option(None, help="SchoolApp password"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
) -> None:
    """Reconstruct the WHOLE promotion's ANNÉE moyennes (anonymized)."""
    from .client import YEAR_STATS_PATH
    client = _library_client(ctx, email, password, timeout, min_interval=min_interval)
    rows = client.year_results()
    row = _resolve_year_row(rows, niveau)
    if not row:
        labels = ", ".join(sorted({r.niveau for r in rows})) or "none"
        err_console.print(render.error_panel(
            f"Year {niveau!r} not found.", hint=f"Available: {labels}"))
        raise typer.Exit(code=2)
    code = row.niveau.upper()
    agg_params = {"eval": "MoyAn", "niveau": row.niveau, "filiere": row.filiere, "au": row.au}
    with err_console.status(f"Reconstructing {code} · MoyAn…"):
        res = _promo_reconstruct_eval(
            client, YEAR_STATS_PATH, agg_params,
            lambda n: client.rank_for_note_year(row.niveau, row.filiere, row.au, n),
            resolution)
    if not res:
        err_console.print(render.error_panel(f"No promotion data for {code}."))
        raise typer.Exit(code=2)
    steps, aggr = res
    per_eval = [("MoyAn", steps, aggr)]
    _emit_promo_artifacts(code, "year", per_eval, out_dir, bin, not no_plot,
                          {"MoyAn": (aggr.get("Votre note", ""), aggr.get("Votre classement", ""))},
                          {"MoyAn": (row.au, row.filiere)})
```

The `_emit_promo_artifacts` `meta` parameter (eval_label → (au, filiere)) was
already added in Task 4, so the sem/year commands above just pass it directly —
no further refactor needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -k "promo" -v`
Expected: PASS (element + sem + year).

- [ ] **Step 5: Commit**

```bash
git add schoolapp/cli.py tests/test_cli.py
git commit -m "feat(cli): promo-sem & promo-year whole-promotion reconstruction"
```

---

### Task 6: Docs + full-suite verification

**Files:**
- Modify: `README.md` (extend the "Whole-promotion notes" section)
- Modify: `schoolapp/promo.py` module docstring (mention sem/year levels)

**Interfaces:** none (docs only).

- [ ] **Step 1: Update README**

Replace the "Whole-promotion notes (anonymized)" section body (README.md ~76-88) with:

````markdown
### Whole-promotion notes (anonymized)

```bash
schoolapp promo API421 --eval rat,moy,ex,cc -o out/   # one element
schoolapp promo-sem S1  -o out/                        # a whole semester
schoolapp promo-year 2A -o out/                        # a whole year
```

Recovers **every student's note** across the whole promotion — without names,
which the portal never exposes. It works because the stats endpoint answers
`rank(note)` for any hypothetical note, so sweeping that value traces the full
grade distribution. Endpoints: `/notes-stat/elemevalsat` (element),
`/notes-stat/semsat` (semester), `/notes-stat/anneesat` (année). Target a
semester by its label (`S1`…`S4`) and a year by its niveau (`1A`, `2A`); the
académique year and filière are resolved from your own rows automatically.

Each run writes, per evaluation, into `--out-dir` (default `.`), all keyed by
the code (`API421`, `S1`, `2A`):

| File | Contents |
|------|----------|
| `promo_<code>_<eval>_hist.csv` | binned histogram — how many got each mark (`bin_low,bin_high,count,percent,cumulative`) |
| `promo_<code>_<eval>_dist.csv` | exact reconstructed distribution (`note,count,rank_top`) |
| `promo_<code>_<eval>_students.csv` | one anonymized row per student (`rank,note`) |
| `promo_<code>_<eval>_summary.csv` | effectif, moyenne promo, min/max/écart-type, median, your note/rank |
| `promo_<code>_<eval>_hist.png` | histogram figure (mean + your-note markers); needs matplotlib, `--no-plot` to skip |

Fires many **rate-limited** requests (`--min-interval`, default 0.25 s) — expect
a few minutes per evaluation. `--bin` sets the histogram bin width (default 1.0).
The reconstruction is cached and served at `GET /api/promo/<code>`.
````

- [ ] **Step 2: Update the promo.py module docstring**

Change the first paragraph of `schoolapp/promo.py`'s docstring to note it now covers element, semester (`/notes-stat/semsat`) and année (`/notes-stat/anneesat`) levels via the same `rank(note)` sweep.

- [ ] **Step 3: Run the full test suite**

Run: `pytest -q`
Expected: PASS — all tests (existing + the new probe/promo/plots/cli tests) green.

- [ ] **Step 4: Smoke-check the CLI wiring (no network)**

Run: `schoolapp promo --help && schoolapp promo-sem --help && schoolapp promo-year --help`
Expected: all three show usage with `--out-dir`, `--bin`, `--no-plot` under the "Live (portal login)" panel.

- [ ] **Step 5: Commit**

```bash
git add README.md schoolapp/promo.py
git commit -m "docs(promo): semester & année reconstruction + artifact files"
```

---

## Self-Review Notes

- **Spec coverage:** feasibility/endpoints → Task 1; four output types (hist/dist/students/summary) → Task 2; PNG + matplotlib dep → Task 3; shared emitter + element `-o`→`--out-dir` → Task 4; sem/year commands with label selection (no `au` flag, S1–S4 / 1A–2A) → Task 5; store persistence → Task 4; API read-through unchanged (additive) → covered (no change needed); docs → Task 6.
- **Median definition:** `_median` uses the true middle of the expanded note list (average of two middles for even counts) — matches `test_summary_row` (steps 1+2+2+1=6 → notes[2],notes[3]=8.0,12.5 → 10.25).
- **`rank_top` semantics:** rank of the best student holding a note = 1 + count of all strictly-higher-note students; verified in `test_distribution_rows` (19→1, 12.5→2, 8→4, 2→6).
- **Naming consistency:** `_emit_promo_artifacts(code, level, per_eval, out_dir, bin_width, plot, your=None, meta=None)` is defined once (Task 4) with its final signature; all three call sites (element/sem/year) pass `your` and `meta`. `_promo_reconstruct_eval(client, agg_path, agg_params, probe, resolution)` argument order identical across Tasks 4 & 5.
- **Store key:** `promo/<code lowercased>` (`promo/api421`, `promo/s1`, `promo/2a`) — distinct keys per level, so `/api/promo/<code>` needs no shape change.
