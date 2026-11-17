# Coconut Capitalist: guide for Claude

A Discord game bot (discord.py 2.7, Components V2). Skills (mining, fishing, foraging, farming; combat is PAUSED), pets, shipments,
trading, parties, casino and minigames, one shared economy. Everything below is the short version; the long ones are in `docs/`.

> **Usage tip:** this file is loaded every turn, so it is deliberately lean. Do NOT read `docs/` files up front. Look things up on demand:
> `docs/HANDOFF.md` (current state; read only its "Latest state" part when resuming work), `docs/DESIGN.md` (HUGE, ~120 KB: Grep for the system's
> heading, then read only that section), `docs/ROADMAP.md`, `docs/AUDIT.md` (history, rarely needed). Plans for new work go in `docs/plans/`.

## Team (automatic delegation; the user pre-approved this, no need to ask)

You are the **lead**: design, planning, tricky bugs, review, commits. Subagents in `.claude/agents/` (cheap Haiku) do the bulk work:
`worker` (bounded code change), `tester` (tests), `writer` (docs/prose).

- **Delegate** when the change is well-specified and bounded (<= ~3 files, a clear behaviour, known tests), or tests/docs are needed for finished code.
  Write the brief yourself: exact files, functions to reuse, behaviour, tests to pass. Independent pieces can run in parallel.
- **Do it yourself** when it is small (a few lines), needs a design decision, touches many files at once, is a subtle bug, or the cause is unknown.
- **Review cheaply:** `git diff --stat`, the verify tail, and only the key hunks. If a worker's result is wrong, retry once with a sharper brief,
  then fix it yourself. Never loop. Then commit (workers do not commit).
- Briefs live in the prompt, not in files. Plans for bigger work go in `docs/plans/`.

## Hard rules (the user set these; do not break them)

- **One branch only: `master`.** The old `claude/discord-bot-audit-modernize-4dd6c5` branch and its worktree are gone; `master` in the
  main checkout is the working branch (Windows PC: `C:\Users\Bryson\Documents\Coding\coconut-capitalist`). Do not create other
  worktrees/branches. GitHub's `master` is the public default branch. The pre-AI code lives on `history/pre-ai` (never change it).
- **Commit after every commit-worthy change without asking.** Detailed messages. End them with the attribution line the harness gives you.
- **Never push unless the user says so.** Push only `master`: `git push origin master`.
- **Design before big features** (use plan mode: explore, write the plan, get approval, then build). Small fixes: just do them.
- **Do not run the full test suite after every change** (the user chose speed; they will report breakage). Run it only when asked, when
  something they report is broken, or after a large refactor. DO run the one or two test files that cover what you touched (cheap, ~1 s each).
- Never write secrets (tokens, DB logins) into files, docs or commits.
- Back up `data/cococap.db` (copy into `data/backups/`) before anything that touches it. It is the live-ish database.
- Use Python string replaces for scripted edits. Mac BSD `sed -i` fails silently without `''`; prefer the Edit tool or python.

## Environment

- Python 3.12 in `.venv`: always the venv python (Mac `.venv/bin/python`, Windows `.venv/Scripts/python.exe`; the system python has no `tomllib`). Lint: `.venv/bin/ruff check .` (must stay clean).
- Tests: `.venv/bin/python -m pytest -q [file::test]`. Full suite ~55 s, ~1580 tests, all should pass. Slow/odd: wrap in `perl -e 'alarm 300; exec @ARGV' ...`.
- Scratch files, sims and one-off scripts go in the session scratchpad, never in the repo.
- Balance report: `.venv/bin/python -m scripts.balance` (what each skill pays per active minute). Balance guard tests: `tests/test_economy_guard.py`.
- Start the bot: see `README.md` and `docs/HOSTING.md`. `config.ini`/`.env` hold settings (never commit real tokens).

## The user's own balance tuning

- Shared numbers live in `configs/*.toml` and are COMMITTED. The user may tune numbers by hand in the shared files; when they ask,
  commit those edits (do not revert them) and update any test that hard-coded the old number so tests read the number from the registry
  instead (e.g. `RULES.free_plots`), never hard-code a configured value in a test.
- Personal tuning that should not be shared goes in `configs/local/<name>.toml` (git-ignored). It is merged over the shared file when the bot
  runs (tables merge key by key, lists are replaced). Tests ignore it (`COCOCAP_NO_LOCAL_CONFIG=1` in `tests/conftest.py`).
- `tests/conftest.py` also pins a few economy numbers (starting luckbucks, weekly luckbucks, party idle hours) so tuning never breaks tests.

## Architecture (data first, rules without Discord, thin UI)

```
configs/*.toml      balance + content as data (items, tools, fishing, mining, foraging, farming, mastery, pets, shipments, ...)
cococap/registry/   models.py = pydantic (frozen) models for every config; loader.py builds the Registry (`get_registry()`); validates links
cococap/services/   the RULES. No discord objects. One module per system (mining.py, fishing.py, foraging.py, farming.py, shipments.py,
                    trade.py, mastery.py, tool_effects.py, upgrades.py, shop.py, pets.py, equipment.py, wiki.py, ...). All take a `User`.
cococap/models/     player state as pydantic documents stored in the DB (skills/*.py per skill, pethouse.py, settings.py, instance.py)
cococap/db/         SQLAlchemy tables, queries, migrations helpers. Alembic migrations in `migrations/versions/` (0001..0007)
cococap/user.py     `User`: the one object every service takes (bits, items, tool instances, skills, settings, stats...)
cococap/screens/    the hub UI: one `Screen` subclass per page; `screens/__init__.py` lists them all (register new ones there)
cococap/ui/         Navigator/Screen/Page/Result (nav.py), components (button/select/text/row/bar/bits), modals, flair.py (rare-drop banners)
cococap/exts/       thin slash-command cogs (most just open a screen). `exts/core/party_system.py` = /party + right-click invite/kick (LIVE)
utils/              old shared helpers still in use (items.item_attributes/embeds, custom_embeds, menus, pagination, checks, base_cog)
scripts/            balance.py (sims), import_mongo.py (one-time old-player migration)
tests/              ~50 files; see "Testing" below
```

Flow of a click: Discord interaction -> `Screen` handler -> `services.*` function (rules, DB) -> `screen.refresh(interaction, note)` redraws.
Rules never import discord; screens never contain game rules. Errors the player should see are `GameRuleError`s (see `cococap/errors.py`);
anything else is a bug and is not leaked to the player.

### Data model facts worth knowing

- **Items** (`configs/items.toml`): `[id]` table with `name, description, wiki, emoji, rarity (1-7), skill, category, price, sell_price`
  and optional sub-tables: `.drop {rate, min, max}` (1-in-rate per drop roll), `.tool` (power, `upgrade` and `fork` chains, `path`, `ability`,
  `stats`), `.scroll {enchant}`, `.pet_food {tier, xp_mult}`, `.crop`, `.seed`, `.bait`. Categories: material, tool, key_item, pet_item,
  pet_food, crop, seed, fish, scroll, bait. Every item and enchant needs an `emoji` (a test enforces it).
- **Tools** are unique instances matched to a template id. Chain: 3 plain upgrades, the 4th upgrade is a FORK into two paths
  (pickaxe Warden/Prospector, rod Angler/Treasure Hunter, axe Lumberjack/Forager, can Sprinkler/Alchemist). `configs/tools.toml` has the
  per-kind power curves; `services/tool_effects.py` turns path/ability into engine effects. Every tool starts at power 3.
- **Enchants** (`configs/enchants.toml`) are effects on a tool instance, applied with scrolls. **Mastery** (`configs/mastery.toml`): 4 trees x 3
  branches x 5 nodes; nodes are plain stat names merged into `equipment.equipped_stats`; level-50 capstones are stat flags read by engines
  (Lifeline, Gold Rush, Hot Streak, Salvage, Windfall, ...). Capstones in a skill are tuned to be equally strong (guard tests).
- **Foraging wedges** (`[[rotate.wedges]]` in `configs/foraging.toml`): reroll the spot AND leave a `boost`/`boost_chops` bonus on the `Spot`.
- **Shipments** (`configs/shipments.toml`, `services/shipments.py`): per-skill basic (unlock lvl 10) and hard (lvl 30) crates; the community
  shipment is scrapped (`community.enabled = false`, code kept). State lives in `services/community.py` (`read`/`update`).
- **Trading** (`services/trade.py`): in-memory invites and windows, both players Accept, version-guarded, all-or-nothing completion.
- **Sell all** (`screens/sellall.py`): "keep upgrade materials" (default ON) holds back, per item, the MOST any single next-upgrade needs across EVERY
  tool you own (both roads at a fork). Not a sum.
- **Rare-drop banners**: `cococap/ui/flair.py` (level 1 = rarity 4+ and 1-in-100 or rarer; level 2 = rarity 5+ or 1-in-700+). Call
  `flair.banner(drops)` wherever a screen lists drops.
- Fishing radar, mastery, shipments, trading all have DESIGN.md sections: read them before changing those systems.

## How to add things (checklists)

**A new item**: add `[id]` to `configs/items.toml` (with emoji, wiki text, drop odds if it drops), put it in the right shop/drop/craft table if any,
add the id to any test list that enumerates a category (e.g. `FOODS` in `tests/test_pets.py`), add a test for its behaviour, and a line in DESIGN.md.
**A new screen**: subclass `Screen` in `cococap/screens/`, set `id/label/emoji/description/links`, import it in `screens/__init__.py`, link it from
Home/More/another screen. `tests/test_hub.py::test_every_screen_renders_valid_layout_within_discord_limits` covers layout limits automatically.
**A new rule/system**: service module (no discord) + registry model + config TOML + screen + tests + DESIGN.md section + HANDOFF "Latest state".
**A DB change**: new Alembic migration in `migrations/versions/` (and update `cococap/db/tables.py`); `tests/test_db_migrations.py` checks the schema matches.
**A balance change**: edit the TOML, run `scripts.balance` or the relevant guard test, never hard-code the number in a test.

## Testing

- Real SQLite fixture `db` (see `tests/conftest.py`); no mocking of the DB. UI tests drive screens with fake interactions: helpers in
  `tests/test_hub.py` (`hub("screen_id", **state)`, `click(nav, inter, "Label")`, `find_button`, `select_named`, `choose`, `all_text(nav)`, `buttons`).
- Write tests that read numbers from the registry. Mutation-check important rules (copy the file, break the rule, see a test fail, restore the copy; NEVER `git checkout` over
  uncommitted work).
- UI wording assertions are brittle; assert on structure or a stable word, not a whole sentence.
- Known noise: none. If something fails on a clean tree it is a real regression.

## Style

- Plain, readable code and comments that say WHY. Config comments explain what a number does; mark guesses `TODO(balance)`.
- Keep screens uncluttered (the user dislikes clutter): fewer buttons, dropdowns for variants, one concept per page.
- Pronouns: use they/them for the user unless told otherwise. Don't put personal details in external requests.
- Final replies: short, plain language, say what changed and what is not verified.

## Things that are deliberately still here (not dead code)

- `exts/core/party_system.py`: the live /party command group and right-click invite/kick; `screens/party.py` is the hub page for the same service.
- `exts/gambling/king_of_the_hill.py`: a guild-specific feature with hard-coded ids (TODO: generalize).
- `exts/utils/extensions.py` + `utils/pagination.py`: owner tooling for loading/unloading extensions.
- `services/combat.py`, `screens/fight.py`, combat tests: combat is paused, not removed.
- `scripts/import_mongo.py`: the one-time old-player migration, waiting on a working Mongo login.
- `exts/economy/drops.py`: old channel-drop code (Mongo era), to be rebuilt on the drop tables.
