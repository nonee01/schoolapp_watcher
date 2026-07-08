# Promo distribution: semester & année levels + rich artifacts

**Date:** 2026-07-08
**Branch:** android-native-app
**Status:** design approved, ready for plan

## Problem

`schoolapp promo <CODE>` reconstructs the whole promotion's anonymized note
distribution for one **element** (module element), by sweeping the hypothetical
`note` parameter of the portal's per-element stats endpoint. Two gaps:

1. It only works at the element level. The user wants the same reconstruction at
   the **semester** and **année** levels.
2. The only output is a one-row-per-student CSV. The user wants a CSV of *how
   many people got each mark* ("the distribution"), the exact ground-truth
   distribution, the per-student rows, a stats summary, and a **plotted figure**
   (histogram) — all linked by the ENSAM code.

## Feasibility (proven live)

The portal exposes hypothetical-input ranking endpoints at every level. The
mechanism `rank(note) = 1 + #{students strictly above note}` (monotonic
non-increasing) holds identically — confirmed against the user's real rows.

| Level    | Endpoint                  | GET params                                        |
|----------|---------------------------|---------------------------------------------------|
| Element  | `/notes-stat/elemevalsat` | `eval, codeelem, au, note`                        |
| Semester | `/notes-stat/semsat`      | `eval=MoySem, niveau, filiere, semestre, au, note`|
| Année    | `/notes-stat/anneesat`    | `eval=MoyAn, niveau, filiere, au, note`           |

Every popup also returns free aggregates: `Moyenne promo, Max, Min, Ecart type,
Effectif, Votre classement, Votre note`. Verified: S1 (12.573 → rank 224/423),
2A (12.824 → rank 125/419) — both match the portal's displayed ranking exactly,
note=0 → rank effectif+1, note=20 → rank 1.

## Design

### Target selection (no `au` parameter)

The user identifies a target by its plain label; au and filière are resolved
automatically from the student's own parsed rows.

- Element: `promo API421` (unchanged) — au resolved from `element_grades`.
- Semester: `promo-sem S1` — matched against the `Semestre` column of
  `notessem`; au/filière/niveau taken from that row. Omit the arg → most recent
  semester row.
- Année: `promo-year 2A` — matched against the `Niveau` column of
  `notesannee`; au/filière taken from that row. Omit the arg → most recent year
  row.

If the label matches no row, exit 2 with a panel listing the available labels.

The **code** (the identifier that links every artifact) is the plain label:
`API421`, `S1`, `2A`. au and filière are recorded *inside* the summary CSV, not
in filenames or as flags.

### Components

**`client.py`** — factor the raw stat request into one helper and build the
three level-specific probes on it:

- `_stat_probe(path, params) -> dict[str, str]` — GET the popup, parse via the
  existing `parse_mark_statistics`, return the row dict (`{"Effectif": "423",
  "Votre classement": "224", "Moyenne promo": "12.57", ...}`), or `{}` if the
  eval is unavailable.
- `rank_for_note(code, eval_kind, au, note)` — rewritten on `_stat_probe`
  (element); unchanged public signature/behaviour.
- `rank_for_note_sem(niveau, filiere, semestre, au, note) -> (rank, effectif) | None`
- `rank_for_note_year(niveau, filiere, au, note) -> (rank, effectif) | None`
- `promo_aggregates(path, params) -> dict` — one probe (at note=0) whose
  constant fields (Moyenne promo/Min/Max/Ecart type/Effectif) feed the summary.

**`promo.py`** — keep `reconstruct` and `expand_to_rows`; add pure functions
(no I/O, unit-testable with synthetic `steps`), each stamping the `code`:

- `histogram_rows(code, level, eval, steps, width=1.0) -> list[dict]`
  columns: `code, level, eval, bin_low, bin_high, count, percent, cumulative`.
  Bins span floor(min)…ceil(max) in `width` steps; a note falls in `[low, high)`
  (top bin closed).
- `distribution_rows(code, level, eval, steps) -> list[dict]`
  columns: `code, level, eval, note, count, rank_top` (exact ground truth).
- `student_rows(code, level, eval, steps)` — thin wrapper over `expand_to_rows`,
  adding `code, level` columns.
- `summary_row(code, level, eval, steps, aggregates, your_note=None,
  your_rank=None) -> dict` columns: `code, level, eval, au, filiere, effectif,
  recovered, moyenne_promo, min, max, ecart_type, median*, your_note, your_rank`
  (`median` computed from steps; `recovered` = Σcount).

**`plots.py`** (new — isolates matplotlib):

- `histogram_png(bins, *, path, title, subtitle="", mean=None, your_note=None)`
  — bar chart of `histogram_rows`; dashed line at `mean`, solid marker at
  `your_note` when given. `import matplotlib` is lazy (inside the function) so
  nothing else in the tool depends on it; if absent, raise a clear
  `RuntimeError("matplotlib not installed — pip install matplotlib")` surfaced
  by the CLI as a hint, without aborting the CSV artifacts.
- `matplotlib` added to `requirements.txt`.

**`cli.py`** — one shared emitter, three thin commands:

- `_emit_promo_artifacts(code, level, per_eval, out_dir, bin_width, plot)`:
  for each eval's `steps` writes, into `out_dir` (default `.`):
  `promo_<code>_<eval>_hist.csv`, `_dist.csv`, `_students.csv`, `_summary.csv`,
  and (unless `--no-plot`) `promo_<code>_<eval>_hist.png`. Prints every path;
  returns the summary rows. Persists `store.save_resource("promo/<code>", …)`
  with `{steps, summary, bins}` per eval.
- `promo <CODE>` — element; evals default `rat,moy,ex,cc`. Switches from
  `-o FILE` to `-o/--out-dir DIR` (breaking change to a personal, unpublished
  flag — acceptable). Adds `--bin FLOAT` (default 1.0) and `--no-plot`.
- `promo-sem [SEMESTER]` — eval `MoySem` only.
- `promo-year [NIVEAU]` — eval `MoyAn` only.

All three keep `--resolution`, `--min-interval`, `--timeout`, `--email`,
`--password`, grouped under the existing rich help panel.

**`store.py` / `api.py`** — `/api/promo/<code>` keeps serving the element
payload; the sem/year payloads live under the same `promo/<code>` namespace
(codes `S1`, `2A` are distinct keys), so the existing read-through already
covers them — no endpoint shape change (honours the frozen-contract rule).

### Data flow

```
select target (label → row → niveau/filiere/semestre/au)
  → probe closure (rank_for_note_{sem,year,elem})
  → reconstruct() → steps[(note,count)]
  → {histogram, distribution, student, summary}_rows(code,…)
  → 4 CSVs + 1 PNG in out_dir, all named promo_<code>_<eval>_*
  → store.save_resource("promo/<code>", …)
```

### Error handling

- Unknown label → panel listing available labels, exit 2.
- Eval unavailable (`_stat_probe` → `{}`, e.g. an empty semester) → warn, skip
  that eval, continue.
- matplotlib missing → CSVs still written; a single warning explains how to get
  the PNG; command still exits 0.
- Network/login failures propagate through the existing `_library_client`
  re-auth path; `--min-interval` (default 0.25 s) rate-limits every probe.

### Testing

- `test_promo.py`: `histogram_rows` binning edges (min/max/top-bin-closed,
  width≠1), `distribution_rows`, `summary_row` (median/effectif/recovered) on
  synthetic `steps`. Existing `reconstruct`/`expand_to_rows` tests stay green.
- `test_fetch_all.py` / client tests: `_stat_probe`, `rank_for_note_sem`,
  `rank_for_note_year` against a FakeSession returning canned popup HTML
  (PII-free) for each endpoint; assert correct path + params.
- `test_plots.py`: `histogram_png` writes a non-empty PNG (skip if matplotlib
  absent).
- `test_cli.py`: `promo-sem`/`promo-year` with a stubbed client produce the five
  files in a tmp dir with code-keyed names; unknown label exits 2.
- Manual live check already done for S1 and 2A.

## Out of scope

- Android / plasmoid surfacing of these distributions (separate sub-projects).
- Caching/incremental re-probe across runs.
- Cross-promotion or historical-au comparison plots.

## Standing constraints honoured

PII-free fixtures; log in from code with `.env` creds (never a browser form);
frozen API contracts (additive only); commit only what's asked; never push;
rate-limited probing to be polite to the school server.
