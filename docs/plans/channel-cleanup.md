# Plan: keep the play channels clean (ops branch)

## What I found
- `/play` (`exts/core/play.py`) -> `open_screen` -> `Navigator.start` (`ui/nav.py:173`) sends the menu with `interaction.response.send_message(view=self)` (public) and keeps `self.message`.
- It already deletes itself on view timeout (`Navigator.on_timeout`, 300 s idle). That lives in memory only: a bot restart, crash or a failed delete leaves the message behind forever. That is the pile-up.
- Other bot posts in the same channels: tictactoe (`exts/minigames/tictactoe.py`), shop/economics/party replies, and `exts/economy/drops.py` (random channel drops posted to all six `GamblingChannels`; drops must NOT be swept while still claimable).
- `bot.py` has `setup_hook` and an existing `tasks.loop` (`idle_sweep`): the janitor follows that pattern.
- `GamblingChannels` (`constants.py:53`) holds the six ids.

## Design (confirming the recommendation, with changes)
1. **No record table needed.** The stateless sweep (author == bot, in the configured channels, older than N minutes) already survives restarts, because Discord holds the state. A persisted record adds a migration for no gain, except for protecting live sessions, which the age limit already does (a Navigator is idle-deleted at 5 min; refreshing panels edit the same message, so age is by creation time: set N well above any live game, e.g. 30 min). Drops are protected by a content/flag check (skip messages the drops cog marks, or give drops their own longer age).
2. **Janitor** `cococap/services/janitor.py` (no discord objects in the decision logic: `should_delete(message_age, is_bot, protected)`), plus a thin task in a new `exts/ops/janitor.py` cog: runs once at startup (after ready), then every `interval_minutes`. Uses `channel.history(before=cutoff)` filtered to the bot's own messages; `purge` for < 14 days (bulk), one-by-one with a short sleep for older ones (handles 429 via discord.py).
3. **Owner-only `/cleanup`** (`is_owner`): `dry_run` default True, shows counts per channel (bulk-able vs old); a Confirm button runs the real pass with progress edits. One-time cleanup = this command. Never auto-runs the first big pass.
4. **Ephemeral menus**: `/play` is single-player in effect (the Navigator rejects other users, nav.py:354), so opening it ephemeral would leave nothing in the channel. Downsides: ephemeral messages can't be deleted/edited after 15 min (nav already tolerates that, nav.py:279), and parties/trading windows that are shared must stay public. Tictactoe and any multiplayer game stay public. This is a design/UX change, so it belongs to the `design` branch; I'd only expose a setting.
5. **Threads**: skip. The owner still sees archived threads, so it solves nothing.

## Config
`configs/janitor.toml` (commented): `enabled`, `channel_ids` (default: the six), `max_age_minutes = 30`, `interval_minutes = 5`, `drop_max_age_minutes = 180`, `request_delay_seconds`. Loaded with tomllib directly (no registry change); ids stay in the TOML so constants are untouched.

## Files
New: `configs/janitor.toml`, `cococap/services/janitor.py`, `cococap/exts/ops/janitor.py` (cog + `/cleanup`), `tests/test_janitor.py`. Edit: none in design-owned files (the startup hook is the cog's `cog_load`/`on_ready`).

## Tests
Service-level: age cutoff, bot-only, protected drops, bulk-vs-old split, dry-run counts nothing deleted. Fake channel object with `history`/`delete`. `quick_tests`.

## Permissions
Bot needs Manage Messages + Read Message History in the six channels: cannot verify from here; the `/cleanup` dry run will report a clear error per channel if missing.

## Decided
Janitor deletes ONLY the bot's own messages (user's answer). Plan approval still pending.
