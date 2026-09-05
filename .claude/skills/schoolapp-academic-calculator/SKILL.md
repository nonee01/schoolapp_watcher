---
name: schoolapp-academic-calculator
description: Use when editing the weighted average calculation algorithms under schoolapp/calculator.py or presets.py, or changing how S3/S4 semester modules are evaluated.
---

# SchoolApp Academic Calculator Rules

## Overview
The CLI provides an interactive weighted calculator ([schoolapp/calculator.py](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/schoolapp/calculator.py)) to evaluate student module averages and semesters using coefficients and threshold limits. These algorithms mirror the engineering evaluation rules of ENSAM.

## Core Formulae

### 1. Module Average Computation
A module is comprised of elements (e.g., CC, Exam, TP). The module average $M$ is computed using element coefficients ($C_i$) and grades ($G_i$):
$$M = \frac{\sum (G_i \times C_i)}{\sum C_i}$$
* **Threshold Validation**: If an element's grade falls below the eliminating threshold (Seuil Éliminatoire, usually $G_e < 5.0$ or $6.0$), the module is marked as **Eliminated** regardless of the calculated average.
* **Validation Bar**: A module is validated if $M \ge 12.0$ (standard engineering validation baseline).

### 2. Implementation Rules
* **Presets Config**: Hardcoded element coefficients and modules are defined in [presets.py](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/schoolapp/presets.py) and within [schoolapp/semesters/](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/schoolapp/semesters/).
* **JSON Inputs**: The calculator can ingest raw grades from a `marks.json` file. Ensure that custom parsed keys (e.g. `API411.cc`) match the pattern `[ModuleCode].[ElementType]`.
* **Tests**: Validate all calculator logic against unit tests in [CalculatorTest.kt](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/android/app/src/test/java/ma/ensam/schoolapp/CalculatorTest.kt) and [calculator.py](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/schoolapp/calculator.py)'s Python counterpart tests to ensure parity between CLI and Android app logic.
