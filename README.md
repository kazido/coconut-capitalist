# Coconut Capitalist (`cococap`)

An economy / gambling / skills Discord bot. Python 3.11+, discord.py, MongoDB (Beanie/Motor).

## Setup

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"
cp .env.example .env        # then fill in BOT_TOKEN and URI (see below)
```

| Variable | Required | Purpose |
|---|---|---|
| `BOT_TOKEN` | yes | Discord bot token (use a separate dev application; `config.ini` → `dev mode: yes`) |
| `URI` | yes | MongoDB connection string; the bot uses the `discordbot` database |
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
pytest          # in-memory Mongo (mongomock), no external services needed
ruff check .
```

Layout: `cococap/exts/<area>/<cog>.py` are discord.py extensions (each has `setup()`),
`cococap/models/` the Beanie/Pydantic documents, `cococap/user.py` the only place that mutates a
player's data (atomic Mongo operators), `configs/*.ini` read-only game data (`fetch("ranks.3")`),
`utils/` shared helpers. Extensions that still depend on the removed SQLite item database are listed
in `constants.DISABLED_EXTENSIONS` and skipped at startup.

See [docs/AUDIT.md](docs/AUDIT.md) for the full architecture review, known issues and roadmap.
