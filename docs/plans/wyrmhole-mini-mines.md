# Wyrmholes as mini mines (plan, NOT built; waiting for approval)

Status: design agreed in chat, details below marked TODO need the user's OK.

Goal: a wyrmhole is an EVENT inside a mine, not a Reactor tab. You see it in your mine, dig it, and drop into a small bonus mine on the SAME
mine screen. Remove the Reactor "Wyrmholes" tab (`WyrmholePane` in `screens/reactor.py`, `tab="wyrmholes"` calls in `screens/mine.py`).

## Rules (from the user)
- Two kinds: **small** (decent rewards, good XP) and **big** (last row can hold the implosion gem or a core gem).
- Pure rewards: NO hazard (no pressure, bombs, collapse), and NO empty lode: every cell pays something.
- Gems (implosion + the 4 core gems) appear ONLY on the **last row of the big wyrmhole**.
- Big last-row gem: chance for the implosion gem or one core gem you do NOT own yet; the more core gems you own (placed or in pack), the higher the
  chance it is the implosion gem.
- You can always leave (nothing to lose); finishing banks everything and grants XP.

## Design
- Entering: today the dig result sets `run.outcome = "wyrmhole"` and ends the mine. New: digging a wyrmhole cell (or the small wyrmhole button)
  switches the same `MineScreen` to a `WyrmholeRun` view (no screen change, no tab). Keep the haul so far banked first (as now).
- `WyrmholeRun` (services/mining.py, pure): replaces `WyrmholeSession`. A small grid (reuse the mine's cell rendering from `screens/mine.py`):
  columns x rows, you dig any cell in the current row (several per row allowed? TODO: one dig per row like now, or free digging of the whole grid).
  Every cell is a pool roll (no empty); small = rows from `[[mini_wyrmhole.rows]]`; big = more/better rows and a final gem row.
- XP: finishing grants mining XP (config `xp = ` per wyrmhole kind, TODO(balance): about the XP of a normal mine of the same value, x bonus).
- Gem roll (big, last row): `implosion_chance = base + per_core_owned * n` (TODO numbers in configs/mining.toml `[wyrmhole]`), else a random core gem
  from those not owned (if you own all 4, it is always the implosion gem).

## Steps
1. Config + registry models: `[wyrmhole]` gets rows/columns/xp/implosion chance numbers; `[mini_wyrmhole]` loses `gem_chance` (small has no gems); loader validation.
2. `services/mining.py`: `WyrmholeRun` (no empty cells, gems only last big row), XP, `finish_wyrmhole`; tests (no empty cell, gems only last big row,
   implosion chance rises with owned gems, never offers an owned core gem, XP granted, banked once).
3. `screens/mine.py`: render the wyrmhole mine inline, buttons Dig / move / Leave; delete `WyrmholePane`, the Reactor tab, `_wyrmhole*` handlers' `go(... "reactor")`.
4. Update docs/DESIGN.md "Small wyrmholes", STATUS.md, `scripts/balance` numbers; delete this plan.
