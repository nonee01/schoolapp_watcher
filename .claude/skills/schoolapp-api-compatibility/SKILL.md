---
name: schoolapp-api-compatibility
description: Use when editing schoolapp/api.py, refactoring the watcher's snapshot/store, or changing the s4_snapshot.json format — the existing endpoints feed the KDE plasmoid and the native Android app, whose response shapes must not change.
---

# SchoolApp API Back-Compat Contract

## Overview

`schoolapp/api.py` is a **read-through cache server**: the watcher writes snapshots, the
API serves them (no per-request scraping for GET endpoints). Several endpoints are
consumed by **external clients you cannot redeploy in lockstep** — the KDE plasmoid
(`plasmoid/`) and the native Android app (`android/`, `mobile/`). Treat their response
contracts as **frozen**.

## Frozen endpoints (don't change shape)

| Endpoint | Top-level response keys |
|---|---|
| `GET /api/status` | `watcher, last_check, next_check, poll_interval, server_time` |
| `GET /api/grades/<sem>` | `semester, modules[]` → each `{code,title,coef,seuil,moy,partial,validated, elements[]}`; element `{code,title,cc,ex,tp,moy,estimated,validated,dec}` |
| `GET /api/absences` | `absences[]` → `{element,title,date,seance,justified,remarks}`; `sanctions{}` |
| `GET /api/modules` | `modules[]` → `{code,title,au,moy,dec}` |
| `GET /api/semesters` | `semesters[]` |
| `GET /api/history` | `history[]` (accepts `?limit=`) |
| `POST /api/check`, `/api/watcher/pause`, `/api/watcher/resume` | action endpoints |

## Rules

1. **Additive only.** New data → **new** endpoints (`/api/profile`, `/api/years`,
   `/api/all`, …). Never repurpose or rename an existing key.
2. **Keep the snapshot source working.** Existing reads go through
   `_load_snapshot(_snapshot_path("S4", None))` against `s4_snapshot.json`. If you later
   migrate an endpoint onto the new per-resource store, the emitted JSON must stay
   **byte-compatible** (same keys, same types, same defaults like `"--"`).
3. **Auth unchanged.** Every endpoint stays behind `_auth()` (`X-API-Key` vs `API_KEY`).
4. **Don't remove keys.** Adding a field to an object is usually safe; removing/renaming
   one breaks a consumer that reads it positionally or by name.

## Before changing a shape, check who reads it

```bash
grep -RniE '/api/(grades|absences|modules|semesters|status|history)' plasmoid/ android/ mobile/
```

If a consumer reads the key you're touching, it breaks silently — there's no shared types.

## Verify you didn't break it (golden responses)

```bash
KEY=$(grep -m1 '^API_KEY=' .env | cut -d= -f2-)
for e in status grades/S4 absences modules semesters; do
  curl -s -H "X-API-Key: $KEY" localhost:8787/api/$e > /tmp/after-$(echo $e | tr / _).json
done
# diff against a /tmp/before-*.json set captured before your change
```

**Source of truth:** `schoolapp/api.py`; design spec §7 (storage/back-compat) and §8.1.
