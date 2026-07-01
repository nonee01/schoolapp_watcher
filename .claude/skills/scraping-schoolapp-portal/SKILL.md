---
name: scraping-schoolapp-portal
description: Use when authenticating against or scraping the ENSAM SchoolApp portal (schoolapp.ensam-umi.ac.ma) — the login/CSRF flow, which route exposes which student data, or the institution-wide catalog POST mechanism.
---

# Scraping the ENSAM SchoolApp Portal

## Overview

SchoolApp is a server-rendered portal (AdminLTE3 + DataTables front end). Auth is a
form login carrying a `_csrf` hidden field; every data page is plain HTML fetched over
one authenticated `requests.Session`. There is no JSON API — you parse tables.

## Login & session (verified)

The portal's CSRF hidden input is named **`_csrf`** (confirmed on the login page).

1. `GET /login` → read `<input name="_csrf">`'s `value`.
2. `POST /login` on the **same session** with `{email, password, _csrf}`.
3. Detect failure / expiry by re-checking for the login page.

Reference implementation: `watcher.py` → `_login`, `_extract_csrf`, `_looks_like_login_page`.
Re-auth rule: on any page that comes back looking like the login page, re-login **once**
and retry; a second failure raises.

```python
SCHOOLAPP_BASE = "https://schoolapp.ensam-umi.ac.ma"
# never type the password into a browser form — read creds from env / resolve_credentials
```

## Surface map (paths)

| Data | Route | Method |
|---|---|---|
| Admin + civil-status (richest PII) | `/index` | GET |
| Elements en cours / full history | `/student/noteselem-encours` · `/student/noteselem` | GET |
| Modules en cours / full history | `/student/notesmod-encours` · `/student/notesmod` | GET |
| Années (annual results + rank) | `/student/notesannee` | GET |
| Semestres | `/student/notessem` | GET |
| Diplôme | `/student/notesdiplome` | GET |
| Mark-statistics popup | `/notes-stat/elemevalsat` | GET (params) |
| Absences · Sanctions | `/student/absence/bilan` · `/student/absence/sanctions` | GET |
| Mes cours (enrollment) | `/student/inscriptioncours` | GET |
| Catalog modules · filières | `/plan-etudes-view/modules` · `/plan-etudes-view/filieres` | **POST** · GET/POST |
| Documents (PDF) | `/student/documents/attestation-scolarite`, relevés linked from notesannee | GET |

Full annotated map (columns, exclusions): spec §1.1–1.2.

## Catalog POST (the non-obvious one)

`/plan-etudes-view/modules` has three jQuery-driven `<select>`s — `niveau` (7), `filiere`
(37), `semestre` (`S1`/`S2`) — that are **not inside a `<form>`**. An `input#valid`
button POSTs to the same URL with those three field names **plus the page CSRF token**,
and the server re-renders the page with a module table
(`CodeMod Intitule Descriptif Niveau Semestre VHMOD CoefMod Seuil Eliminatoire`). Full
product = 7×37×2 = **518 combos**, most empty.

- Read the options with `document.querySelectorAll('select')` — they're JS-built, so
  inspecting `<form>`s returns nothing.
- The CSRF field is `_csrf` like login; confirm the exact name on this page when wiring it.
- When capturing the request in-browser, start network tracking **before** clicking — the
  first click after tracking begins is what records the POST.

## Gotchas

- Site typo: the column is spelled **`Decesion`** on `/student/notesannee`.
- `Classement` looks like `98 / 419`.
- `/student/notesdiplome` renders `"Vous n'avez pas de note de diplome..."` when empty —
  a valid empty state, **not** an error.

## Never

- Don't type the password into the login form via browser automation — log in from code.
- Don't submit `/choixform/...` (choix-filière / mobilité) forms — read the status string only.
- Don't touch `/profil/index` (password / photo write surface).

**Source of truth:** `schoolapp/watcher.py` (login, paths) and the design spec §1.
