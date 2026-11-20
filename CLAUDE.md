# Coconut Capitalist: guide for Claude

A Discord game bot (discord.py 2.7, Components V2). Skills (mining, fishing, foraging, farming; combat is PAUSED), pets, shipments,
trading, parties, casino and minigames, one shared economy.

This file loads every turn, so it stays short. More detail loads only when needed:
- `.claude/rules/*.md`: path-scoped rules that load when you touch matching files (data model, configs/balance, screens, DB, not-dead-code).
- `.claude/skills/`: workflows (`delegate`, `add-item`, `ui-tweak`, `balance-check`, `remove-item`, `tidy-docs`, ...).
- `docs/STATUS.md` (current state, short; read when resuming work), `docs/IDEAS.md` (the user's inbox), `docs/DESIGN.md`
  (HUGE: never read it whole or at session start; Grep for the system's heading, read only that section).
- Plans for new work go in `docs/plans/` (one file each, with a `Status:` line). **Staleness rule:** when work merges, in the same commit
  delete its plan, remove its line from STATUS.md and fix any doc it made wrong. History lives in git, not in docs.

## How the lead works (usage is tight)

- Default model is Sonnet; Opus only for hard design. Do small changes (<= ~3 files) inline: no plan mode, no subagents, no `delegate` skill.
  Each subagent re-pays the whole baseline context, so delegate (`worker`/`tester`/`writer`, pre-approved) only for large self-contained work,
  and load the `delegate` skill then.
- For a new feature, ask the user ONE design question before building. Plan mode only for big features.
- graphify is the way to find code in big changes; for small ones Grep is enough. Read only the hunks you need, once.

## Hard rules (the user set these; do not break them)

- **Branches (3 total, no others without asking).** `master` = stable and public; its checkout (`C:\Users\Bryson\Documents\Coding\coconut-capitalist`)
  is the integration point and the ONLY place the bot runs and `data/` lives. `design` (features, systems, balance, configs, services; worktree
  `..\coconut-capitalist-design`) and `ops` (Discord server upkeep: cleanup, janitor jobs, startup hooks; worktree `..\coconut-capitalist-ops`).
  ART (emoji, sprites, art pipeline) has no branch: done directly on `master`; the owner approves a sprite before it is committed.
  One Claude session per folder. `history/pre-ai` is never changed.
- **Ownership:** art on `master` owns `art/` and emoji files; `ops` owns janitor/cleanup code and its startup hook; `design` owns everything
  else. `configs/items.toml` is shared: keep edits small and land them soon.
- **Landing work:** in your worktree `git merge master` often. To land: merge master in, run the targeted tests + ruff (FULL suite only if
  the user asks or the registry/loader shape changed), show the user the summary, and on their yes run `git merge --no-ff <branch>` in the
  master checkout. A change that removes/renames item ids or changes the registry shape lands on `master` FIRST and alone, then the other
  branch syncs. Art may PROPOSE removing items; design decides.
- **Commit after every commit-worthy change without asking.** Detailed messages, ending with the harness attribution line.
- **Never push unless the user says so.** Push only `master`: `git push origin master`.
- **Design before big features** (plan mode: explore, write the plan, get approval, then build). Small fixes: just do them.
- **Tests, cheaply:** run only the tests the graph links to the change (see the `delegate` skill), as
  `pytest -q -p no:cacheprovider --tb=line <files>`; backup `python -m scripts.quick_tests`. FULL suite only when the user asks:
  `python -m scripts.full_tests` with `run_in_background: true`, then read `.full_tests_last.txt` ONCE. Never poll, never paste long output.
  If something fails on `master` too, say so and do not chase it.
- Never write secrets (tokens, DB logins) into files, docs or commits.
- Back up `data/cococap.db` (copy into `data/backups/`) before anything that touches it.
- Scripted edits: Python string replaces or the Edit tool, not `sed -i`.

## Environment

- Python 3.12 in `.venv` (master checkout only): always `.venv/Scripts/python.exe` (system python has no `tomllib`). From a worktree run
  `C:/Users/Bryson/Documents/Coding/coconut-capitalist/.venv/Scripts/python.exe -m pytest` with the worktree as cwd.
- Lint: `.venv/Scripts/ruff check .` (must stay clean). Full suite ~55 s, ~1580 tests, all should pass; known noise: none.
- Scratch files, sims and one-off scripts go in the session scratchpad, never in the repo.
- Start the bot: `README.md` and `docs/HOSTING.md`. `config.ini`/`.env` hold settings (never commit real tokens).

## Architecture (data first, rules without Discord, thin UI)

```
configs/*.toml      balance + content as data (items, tools, fishing, mining, foraging, farming, mastery, pets, shipments, ...)
cococap/registry/   models.py = pydantic (frozen) models for every config; loader.py builds the Registry (`get_registry()`); validates links
cococap/services/   the RULES. No discord objects. One module per system (mining, fishing, foraging, farming, shipments, trade, ...). All take a `User`.
cococap/models/     player state as pydantic documents stored in the DB (skills/*.py per skill, pethouse.py, settings.py, instance.py)
cococap/db/         SQLAlchemy tables, queries, migration helpers. Alembic migrations in `migrations/versions/`
cococap/user.py     `User`: the one object every service takes (bits, items, tool instances, skills, settings, stats...)
cococap/screens/    the hub UI: one `Screen` subclass per page; `screens/__init__.py` lists them all
cococap/ui/         Navigator/Screen/Page/Result (nav.py), components, modals, tabs.py, flair.py (rare-drop banners)
cococap/exts/       thin slash-command cogs (most just open a screen)
utils/              old shared helpers still in use
scripts/            balance.py (sims), import_mongo.py (one-time old-player migration)
tests/              real SQLite fixture `db` (tests/conftest.py), no DB mocking; UI helpers in tests/test_hub.py
```

Flow of a click: Discord interaction -> `Screen` handler -> `services.*` function (rules, DB) -> `screen.refresh(interaction, note)` redraws.
Rules never import discord; screens never contain game rules. Player-facing errors are `GameRuleError`s (`cococap/errors.py`).

## Style

- Plain, readable code and comments that say WHY. Tests read numbers from the registry, never hard-code a configured value.
  Mutation-check important rules (copy the file, break the rule, see a test fail, restore the copy; NEVER `git checkout` over uncommitted work).
- Keep screens uncluttered: fewer buttons, detailed dropdowns with emojis for variants, one concept per page. Tiers as TX, no rarity names in item labels
  ('Base Part (T1)'); an emoji on every dropdown option that has one.
- Final replies: short, plain language, say what changed and what is not verified. Never say you cannot test in Discord or that the bot needs a restart: the user knows.
