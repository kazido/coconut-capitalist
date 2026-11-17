# Executor guide (read this, then your brief, nothing else)

You are a local coding agent. A planner wrote a **brief** for you (a file in `docs/briefs/`, or in your prompt). Do exactly that and stop.
Ignore the long parts of `CLAUDE.md` unless the brief names a section.

## Rules

1. Work in this folder, on the current branch. Do not create branches or worktrees. Never run `git push`, `git reset --hard`, `git checkout .`
   or anything that deletes work.
2. Touch only the files the brief lists. If you think another file must change, stop and say why in your report.
3. Do not add dependencies, change `pyproject.toml`, `.env`, migrations, or `configs/` unless the brief says so.
4. Copy the style of the code next to yours. Python 3.11+, type hints on new functions, short docstrings, no new abstractions.
5. Game rules live in `cococap/services/` (no Discord objects there); Discord views live in `cococap/screens/`. Numbers live in `configs/*.toml`,
   not in code. Randomness is passed in as a `random.Random`.
6. Tests are real: add or update the tests named in the brief. Never delete or weaken a test to make it pass.

## How to work

1. Read the brief. Open only the files it names (and the "reuse" functions it points to).
2. Make the smallest change that satisfies the brief. Run `scripts/verify.sh` after each file or two.
3. When `scripts/verify.sh` ends with `VERIFY PASSED`, commit with a clear message ending with the line the brief gives.
4. If verification fails: read the FIRST error, fix that, run again. After 3 failed attempts stop and write what you tried.

## Commands

```bash
scripts/verify.sh                       # lint + the tests for the files you changed (what "done" means)
scripts/verify.sh tests/test_foo.py     # exactly these tests
.venv/bin/python -m ruff check . --fix  # lint (and auto-fix simple things)
git diff --stat                         # what you changed
```
Do NOT run the whole test suite (`pytest` with no arguments) unless the brief asks.

## Your final message (keep it short)

- Files changed (from `git diff --stat`).
- The last lines of `scripts/verify.sh`.
- Anything you were unsure about, or did not do, and why.
