---
paths:
  - "configs/**"
  - "scripts/balance.py"
  - "tests/test_economy_guard.py"
---

# Editing configs: balance, changelog, notices

## The user's own balance tuning
- Shared numbers live in `configs/*.toml` and are COMMITTED. The user may tune numbers by hand in the shared files; when they ask,
  commit those edits (do not revert them) and update any test that hard-coded the old number so tests read it from the registry
  (e.g. `RULES.free_plots`). Never hard-code a configured value in a test.
- Personal tuning that should not be shared goes in `configs/local/<name>.toml` (git-ignored), merged over the shared file when the bot
  runs (tables merge key by key, lists are replaced). Tests ignore it (`COCOCAP_NO_LOCAL_CONFIG=1` in `tests/conftest.py`).
- `tests/conftest.py` also pins a few economy numbers (starting luckbucks, weekly luckbucks, party idle hours) so tuning never breaks tests.

## A balance change
Edit the TOML, run `.venv/Scripts/python.exe -m scripts.balance` (what each skill pays per active minute) or the guard tests in
`tests/test_economy_guard.py`. Config comments explain what a number does; mark guesses `TODO(balance)`. The `balance-check` skill has the full loop.

## A change players will notice
Add it to `configs/changelog.toml` (newest at the top; a big change gets its own `major = true` entry, small ones share one grouped entry).
If players may have questions, also add a notice to `configs/notices.toml` (a new unique `id`; it pops up once for every player, then
stays on More -> News -> Messages).

`configs/items.toml` is shared between branches: keep edits small and land them soon.
