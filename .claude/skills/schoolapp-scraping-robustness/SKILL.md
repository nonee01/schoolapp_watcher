---
name: schoolapp-scraping-robustness
description: Use when editing or creating BeautifulSoup parsers under schoolapp/extractors/ to parse HTML tables from the ENSAM SchoolApp portal.
---

# SchoolApp Scraping Robustness

## Overview
The SchoolApp portal (`schoolapp.ensam-umi.ac.ma`) is an AdminLTE3 based layout containing dynamic tables. Because the server output changes during grade releases or site updates, parsers under [schoolapp/extractors/](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/schoolapp/extractors/) must fail-gracefully and avoid breaking the watcher loop.

## Key Design Patterns

### 1. Handling Missing or Unreleased Grades
* **Placeholder Value**: Unreleased or empty fields are output as `"--"`.
* **Rule**: Map `"--"` to Python `None` (or keep as a placeholder string depending on the schema), but do **not** raise an exception.
* **Preserve State**: If a parse target returns empty due to a network interruption, do not overwrite the cached snapshot with empty arrays. Verify that a page actually loaded before diffing (e.g. check for the presence of elements using `_looks_like_login_page` or specific table wrappers).

### 2. Layout Typo Resiliency
* **Typo Handling**: The portal column header for decisions is literally spelled **`Decesion`** on `/student/notesannee`.
* **Guideline**: When selecting or index-mapping fields, use case-insensitive matches or compile flexible keys:
  ```python
  decision_col = next((i for i, h in enumerate(headers) if "decesion" in h.lower() or "decision" in h.lower()), None)
  ```

### 3. Parsing HTML Tables via `_tables.py`
* Common functions for extracting table headers and body rows are defined in [_tables.py](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/schoolapp/extractors/_tables.py). 
* Do not rewrite standard extraction logic; always extend or inherit from [_tables.py](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/schoolapp/extractors/_tables.py) to maintain consistent snapshot column ordering.
