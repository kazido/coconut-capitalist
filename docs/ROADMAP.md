# Roadmap: what we're building and how

This is the working plan for getting the bot fully working and ready to expand. Read it first when
picking the project up on a new machine. (`docs/AUDIT.md` is the long history of *why*; this is the
*what next*.)

## Goal

An economy / skills / gambling Discord bot that is **easy to extend, easy to test, and hard to
break**: adding a skill or item should mean adding data + a small rules module + a thin cog, with
tests, and never touching unrelated code. The game itself is described in the wiki
(`Discord Bot Wiki.pdf`): mining, farming, foraging, fishing, combat, pets, and a shared economy.

## Where things stand

| Area | State |
|---|---|
| Economy (profile, check-in, bank, pay, beg, rank, top, stats, settings) | working |
| Casino (`/highlow`, `/blackjack`) | working, bets settle exactly once |
| Parties (`/party ...` + right-click invite/kick/promote) | working, context menus unverified live |
| Items: registry, stackables, unique tool instances, enchants | done |
| Shop + inventory (`/shop /buy /sell /inventory /equip /wiki`) | done |
| **Mining** (`/mine`: mine, wyrmholes, scarab, reactor, magnet) | done, the template for other skills |
| **Farming** (`/farm`: plots, hourly rain, harvest, Farmer's Market, land deeds) | done |
| **Foraging** (`/chop`: private trees, hourly community tree, zones, Soloist) | done (Re-leaf donations / double tree / growth mode still to do) |
| Fishing, combat, pets, explore | **not ported yet** (listed in `constants.DISABLED_EXTENSIONS`) |
| Database | SQLite + Alembic (old MongoDB import script: `scripts/import_mongo.py`) |
| Tests | ~300, run in ~3 s with no services; CI on GitHub Actions |

## How the code is organised (the rules to keep)

Dependencies only point down:

```
cococap/exts/<area>/<cog>.py   Discord only: commands, views, embeds. Calls a service, draws the result.
cococap/services/              Game rules (mining, shop, equipment, loot). No Discord objects.
cococap/user.py + cococap/db/  The only code that reads/writes player data (atomic SQL).
cococap/registry/ + configs/   Typed, validated game data (items, enchants, ranks, mining rules...).
```

- A button is a thin translator: it calls **one** service method and redraws. State that spans clicks
  lives in a plain object (e.g. `MineSession`) that the view holds.
- Items are **stackables** (`user_items` counters: ore, seeds) or **instances** (`item_instances`: tools,
  permanent, carry enchants). Templates come from the registry; instances store only what is unique.
- Randomness is injected (`random.Random`) so tests can fix outcomes. Balance numbers live in
  `configs/*.toml`; `TODO(balance)` marks guesses that need your decision.
- New views use `cococap.ui.OwnedView` / `ConfirmView`.
- Every feature ships with tests, including at least one that runs the command through
  `tests/test_command_smoke.py`-style wiring (this caught a real crash the unit tests missed).

## Next up (in order)

0. **Cosmetics shop** (the luckbuck sink), then farming. Mining v2, the in-window casino and the brain games are done.

Each slice = **data -> service + tests -> thin cog -> enable the extension**, copying
`services/mining.py` + `exts/skills/mining.py`.

1. ~~Farming~~ done. Follow-ups: fertilizer/imbued plots, feeding crops to pets (needs pets), a channel announcement for
   the rain, balance of `configs/farming.toml`.
2. ~~Foraging~~ built (see docs/DESIGN.md). Still to do: **Re-leaf donations** (level 10, 3 a day, meter 50 -> double tree),
   **growth mode** (420 donations), balance of `configs/foraging.toml`, a channel announcement for the community tree.
3. **Fishing** (`/fish`): fish appear in channels like drops; daily/weekly/monthly quests; personal and
   community collection books; hallucination -> treasure chest minigame.
4. **Combat** (`/fight`, dungeons): dungeon keys, 8-direction tile grid, idols, boss; mirror gates
   (once a day, one winner). Swords/enemies data already exists.
5. **Pets**: needs a design pass first (gacha via familiar orbs, stars, bonuses, xp from crops).
6. **Enchant sources**: crafting, shop and drops all end in `services.equipment.add_enchant`; add the
   sources as each skill lands. No enchanting table needed yet.
7. Re-enable trivia, the `explore` prototype, and the community drops channel config.

## Open decisions (yours)

- Command style: separate commands per skill (the wiki) vs. the `/explore` map prototype.
- Pet design (stars, bonuses, how xp works).
- Balance placeholders marked `TODO(balance)` in `configs/` (magnet capacity/values, scarab odds, seed
  cycles, axe powers, crop/sword rarities); the scarab's "pickaxe upgrade template" reward needs an
  item definition; whether pickaxe power should affect drops.
- Per-guild configuration (channels, admin role) instead of the hard-coded IDs (`todo` file).

## Before going to production

- Rotate the MongoDB password that is in git history (`data.json`, first commit era), and scrub history
  if the repo is or becomes public.
- Run `scripts/import_mongo.py` as a dry run against the real Atlas data and read the report; then
  `--write`. Back up with `sqlite3 data/cococap.db ".backup backup.db"`.
- Host on something with a **persistent disk** (small VPS, Pi, or a volume-backed app host); run **one**
  bot process per database file; set up nightly backups (or Litestream).
- Use a separate dev bot token + dev database from prod.

## Setting up on a new machine

```bash
git clone https://github.com/kazido/coconut-capitalist.git
cd coconut-capitalist
git checkout claude/discord-bot-audit-modernize-4dd6c5   # until it is merged into master

# Python 3.11+ ; uv is easiest (https://docs.astral.sh/uv/)
uv venv --python 3.12
uv pip install -e ".[dev]"
cp .env.example .env          # set BOT_TOKEN (Bot tab -> Reset Token: ~70 chars with two dots), GUILD_ID, OWNER_ID

# macOS/Linux                         # Windows (PowerShell)
.venv/bin/python -m pytest -q         # .venv\Scripts\python -m pytest -q
.venv/bin/python -m cococap           # .venv\Scripts\python -m cococap
```

The SQLite database (`data/`) is git-ignored, so each machine starts with an empty one. To carry your
test data over, copy `data/cococap.db` between machines (stop the bot first), or just start fresh.
