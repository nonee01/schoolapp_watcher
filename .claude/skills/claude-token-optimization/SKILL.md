---
name: claude-token-optimization
description: Guidelines for optimizing token usage, managing context, and utilizing specialized plugins/commands to minimize cost and maximize efficiency when using Claude Code CLI with Fable 5.
---

# Claude Code CLI: Fable 5 Token Optimization & Efficiency

## 1. High-Impact Ingestion & Context Rules
* **Avoid full-repository reads**: Never request to view or scan all files if a targeted `grep` or file path is known.
* **Keep terminal output short**: Limit search outputs and run commands with flags that minimize logging (e.g., `git log -n 5`, `pytest -q`, `./gradlew assembleDebug -q`).
* **Do not dump raw logs**: If a command fails, output only the relevant stack trace or error lines, not the entire build log.

## 2. Token Saving Plugins & Tools
* **Install and run `ccusage`**: Use `@ryoppippi/ccusage` to monitor token metrics per command/session:
  ```bash
  npm install -g @ryoppippi/ccusage
  ```
  Check session consumption regularly using `ccusage`.
* **Utilize `CLAUDE.md`**: Define build, test, and style commands in `/home/notadil/Projects/ensam_school/schoolapp_watcher/CLAUDE.md`. This serves as a static memory file, preventing the model from running expensive discovery commands in every new terminal session.

## 3. Communication Efficiency
* **Strict Minimalist Output**: Avoid polite filler, repetitive summaries, and verbose explanations.
* **Direct Answers**: Provide code diffs and file links directly. Let the changes speak for themselves.
* **Interactive commands**: Avoid prompting the user for minor decisions. Group questions together or make technical assumptions aligned with the codebase architecture.

## 4. Gradle & Android Specifics
* **Timeout management**: Gradle builds on MIUI/HyperOS take ~9 minutes initially. Avoid running `./gradlew` repeatedly. Build once, then use `adb install -r` directly to avoid re-triggering heavy Gradle tasks in the terminal:
  ```bash
  adb install -r app/build/outputs/apk/debug/app-debug.apk
  ```
