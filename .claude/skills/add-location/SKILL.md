---
name: add-location
description: Add or change a Coconut Capitalist location or variant: a mine, water, forest or field (configs/locations.toml + the skill's own table), or a rolled variant like a mine type (Wyrm Tunnels). Covers unlock level, area, drops, effects, icon and tests. Use when asked for a new mine/water/forest/field/mine type or to change one.
---

# Add a location or a variant

Every skill has 14 locations, 2 per area: location n is in area ceil(n/2) and opens at `locations.min_levels[n-1]` (`configs/areas.toml`).
A 15th changes that shared schedule: ask the owner first. Usually the request is to change or reskin one, or to add a variant.

## A location (mine / water / forest / field)
1. `configs/locations.toml`: `[<skill>.<id>]` with `name` and `emoji` (art via `make-emoji`, emoji named after the location id).
2. The skill's own table (`configs/mining.toml` depth tables and yield, `fishing.toml` fish, `foraging.toml` trees, `farming.toml` crop and
   byproducts). Copy a neighbour, scale to its place in the curve, mark guesses `TODO(balance)`.
3. Starred drops follow the location (`services/stars.py`). New items it drops go through `add-item`.

## A variant (mine types and similar rolled modifiers)
1. Add to the rolled list (e.g. `[[mine_types]]` in `configs/mining.toml`: `id, name, emoji, weight, description` + effects).
   Weights are relative and total 100, so a weight reads as a percent: take the weight from `standard`.
2. Reuse an existing effect key if one fits. A new effect = a field on the registry model (`cococap/registry/models.py`) read by the engine
   in `cococap/services/<skill>.py`, never a number in code.
3. The description states the effect with its number, in plain words.

## Both
- Tests read numbers from the registry: it appears, its effect changes the outcome (seeded RNG), weights still total 100.
  `python -m scripts.quick_tests`, then `balance-check` to see the pay change; ruff.
- One DESIGN.md line in the skill's section, then commit.
