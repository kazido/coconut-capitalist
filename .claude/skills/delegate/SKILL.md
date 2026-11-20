---
name: delegate
description: How the lead maps a change with graphify and hands bounded work to worker/tester/writer subagents (which model, brief template, review, tests to list). Use only for big, multi-file work or when writing a subagent brief; small changes (<= ~3 files) are done inline without it.
---

# Lead workflow: impact map, brief, review

## Who does what (the user pre-approved delegation; no need to ask)
You are the **lead** of your branch: design, planning, tricky bugs, review, commits. Between steps ask the user ONE question (the next
design decision) before building on. Use LOW effort for routine steps (state it when you start a session or subagent).
Subagents in `.claude/agents/`: `worker` (bounded code change), `tester` (tests), `writer` (docs/prose).

- **Delegate** only when the work is large AND self-contained (each subagent starts cold and re-pays the whole baseline context, so a
  small task costs more delegated than inline). Default is to do it yourself. Write the brief yourself. Independent pieces can run in parallel.
- **Do it yourself** when it is small (a few lines), needs a design decision, touches many files at once, is a subtle bug, or the cause is unknown.
- **Model split:** Opus (lead) = design, engines, unknown causes, cross-system changes; Sonnet (`model: "sonnet"`) = bounded writing/screens
  needing some judgment (3+ callers, a new pane copying one); Haiku `worker`/`tester`/`writer` = routine work the impact map fully pins down.
- If a broad sweep seems needed, send it to an `Explore` subagent that returns only a short summary, never raw file dumps.
- **Review cheaply:** `git diff --stat`, the verify tail, and only the key hunks. If a worker's result is wrong, retry once with a sharper
  brief, then fix it yourself. Never loop. Then commit (workers do not commit).

## Impact map first (graphify)
The graph is code-only and free (no LLM): `graphify update .` rebuilds `graphify-out/` (git-ignored, per worktree) in ~1 min; run it when
code changed since the last build. Commands (all print `file:Lline`):
- `graphify affected "<func or Class>" --depth 1` = every caller/importer/test. Depth 2 only if needed.
- `graphify explain "<name>"` = a node and its neighbours; `graphify path "A" "B"` = how two systems connect.
- `graphify query "<question>" --budget 800` for "where does X happen" when you do not know a name yet.

**Config routing** (the graph stops at the registry, since code reads configs as attributes like `reg.farming.free_plots`):
- A key in `configs/<name>.toml` -> its model via `_build(<Model>, "<name>", ...)` in `load_registry()` (`cococap/registry/loader.py`) ->
  field on that model in `registry/models.py` -> readers: `Grep -n "\.<key>\b" cococap tests`. Cross-file checks: `Grep "<name>.toml" loader.py`.
- An item/stat/enchant id -> `Grep -n "<id>" configs cococap tests art` (TOML tables, code, tests, sprites, emoji all in one).
Then read only the few hunks you need, once.

## Tests to list in every brief
The `tests/` lines of `graphify affected "<changed func>" --depth 2` plus tests found by the config-routing Grep, run as
`pytest -q -p no:cacheprovider --tb=line <files>`. Backup: `python -m scripts.quick_tests`. Never put the full suite in a brief:
say "targeted tests + ruff only".

## Brief template (under ~40 lines; no project background, no history, no pasted file contents)
```
Goal: <one sentence, the player-visible behaviour>
Change: <file:line> <function> - what to do (exact names, values from which config key)
Also update (from graphify affected): <file:line> - why ... ; tests: <tests/file::test> to update or add
Reuse: <helper(s) with file:line>; copy the pattern in <file:line>
Do not touch: <files>. Done = the listed test files + ruff pass (pytest -q <files>; ruff check <changed files>).
```
Use `@path` mentions for files. Briefs live in the prompt, not in files; plans for bigger work go in `docs/plans/`.
