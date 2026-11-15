---
name: finish-feature
description: Wrap up a Coconut Capitalist change safely: lint, run the tests that cover it, write the docs line, and commit with the right attribution without touching unrelated files. Use when a feature or fix is done.
---

# Finish a feature

1. `git status --short`: know exactly which files are yours. Only stage those (`git add <paths>`); use `git add -p`/a filtered patch if a
   file also holds someone else's uncommitted edits. Never `git checkout`/`git stash` over uncommitted work.
2. Lint: `.venv/bin/ruff check .` must say "All checks passed!".
3. Tests: run only the files that cover what changed (`.venv/bin/python -m pytest -q tests/test_x.py`). Run the full suite only if the user asked,
   something they reported is broken, or the change touched shared code (registry models, `User`, nav/ui, db). Say which you ran.
4. Docs: append/refresh a `docs/DESIGN.md` section for a new system or rule; update the "Latest state" part of `docs/HANDOFF.md` and the checklists in
   `CLAUDE.md` if the way of working changed.
5. Commit on `claude/discord-bot-audit-modernize-4dd6c5` with a message that says what the player will notice, ending with the attribution line the
   harness provides. Do NOT push unless the user said so.
6. In the reply: what changed, what was verified, what was not.
