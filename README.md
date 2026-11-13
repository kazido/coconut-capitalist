# Coconut Capitalist (`cococap`)

An economy / gambling / skills Discord bot. Python 3.11+, discord.py, SQLite (SQLAlchemy + Alembic).

## Setup

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"
cp .env.example .env        # then fill in BOT_TOKEN and URI (see below)
```

| Variable | Required | Purpose |
|---|---|---|
| `BOT_TOKEN` | yes | Discord bot token (use a separate dev application; `config.ini` → `dev mode: yes`) |
| `DATABASE_PATH` | no | SQLite file (default `data/cococap.db`; created and migrated automatically) |
| `GUILD_ID` | no | Guild the bot waits for before loading extensions (default: the original server) |
| `OWNER_ID` | no | Discord user ID allowed to use debug commands / receive reports |

The bot must also have the **Server Members** and **Message Content** privileged intents enabled in the
Discord developer portal.

## Run

```bash
python -m cococap            # add --drops to enable random channel drops
```

## Develop

```bash
pytest          # real SQLite in a temp dir; no external services needed
ruff check .
```

## Architecture

Dependencies only point down:

```
cococap/exts/<area>/<cog>.py   Discord only: commands, views, embeds. Calls a service, draws the result.
cococap/services/              Game rules (mining.py, shop.py, equipment.py, loot.py). No Discord objects.
cococap/user.py + cococap/db/  The only code that reads/writes player data (atomic SQL, tables, queries).
cococap/registry/ + configs/   Typed, validated game data (items, enchants, ranks, mining rules, ...).
```

Rules of thumb:

- **Items** come in two kinds. *Stackables* (ore, seeds) are `user_items` counters. *Instances* (tools)
  are rows in `item_instances` that store only what is unique to that object (rolled stats, enchants);
  base stats come from the registry template, and `services.equipment.effective_stats()` combines them.
- **A button is a thin translator**: it calls one service method (e.g. `mining.dig_row`) and redraws.
  Game state that spans clicks is a plain object (e.g. `MineSession`) the view holds.
- **Randomness is injected** (`random.Random`), so tests can fix outcomes.
- **Balance numbers live in `configs/*.toml`**, validated at startup (`TODO(balance)` marks guesses).
- Use `cococap.ui.OwnedView` / `ConfirmView` for any new view.

`cococap/exts/skills/mining.py` + `cococap/services/mining.py` + `tests/test_mining*.py` are the
reference slice; port the remaining skills (farming, foraging, fishing, combat) the same way.
Extensions still waiting for a port are listed in `constants.DISABLED_EXTENSIONS` and skipped at startup.

See [docs/AUDIT.md](docs/AUDIT.md) for the full architecture review, known issues and roadmap.

## Database

One SQLite file. Change the schema by editing `cococap/db/tables.py`, then:

```bash
DATABASE_PATH=/tmp/scratch.db alembic revision --autogenerate -m "what changed"
```

Review the generated file in `migrations/versions/`. The bot applies pending migrations at startup,
and a test fails if `tables.py` and the migrations disagree. Back the file up (`sqlite3 data/cococap.db
".backup backup.db"`); run only one bot process per database file.

Importing the old MongoDB data (read-only on Mongo, dry-run by default):

```bash
uv pip install -e ".[mongo-import]"
python -m scripts.import_mongo --uri "mongodb+srv://..." --db discordbot           # report only
python -m scripts.import_mongo --uri "mongodb+srv://..." --db discordbot --write   # create data/cococap.db
```
