# Pet sidekicks (pets as a mini you)

Status: APPROVED (design decided, not built; build on the `design` branch). Supersedes `pet-abilities.md`.

## Context
Pets today are flat stat bonuses. We are reworking them into a simulated "mini you": each pet has a score from a simulated loadout in ONE skill, giving a small passive bonus while you play plus an idle haul fueled by crops. Nothing is visible, nothing real is simulated. Replaces `pet-abilities.md`.

## Decisions (from interview)
- **Payout:** both. Passive bonus while you play (replaces flat `bonuses`) + idle haul (skill xp + common drops, no rares).
- **Pet tool slot:** one real tool, LENT (stays yours, unusable by you while on the pet). Feeds the score.
- **Score** = f(skill proficiency, simulated loadout: tool tier, enchants, mastery score; rarity; level; stars). Rare pets = better loadout and more xp gain.
- **Sidekicks:** every inactive pet adds a % bonus to the active pet's output from the COMBINED levels and stars of all inactive pets (rewards collecting and maxing weak pets). Diminishing/capped.
- **One fuel tank, active pet only.** Crops are the fuel (farming gets a big reason to exist): more fuel = more idle hours. Online play never needs fuel (pet works while you're online). Empty tank: haul stops, passive bonus stays.
- **Skill food = leveling only, and becomes a timed buff:** feeding gives some flat pet xp AND a temporary xp-rate bonus on the pet (feed before you skill and it levels faster). Pets also level alongside you while you play (already via `grant_play_xp`).
- **Pet xp drops:** keep existing drops; add at least 2 skill-specific pet-food drops per skill plus 1 global; buff current xp sources.
- **Global pets (Dog, Koala, Phoenix):** mini-you in every skill at lower proficiency.
- **Haul size:** a fully fueled max pet pays ~15% of an active player per hour, enforced by a guard test.

## Defaults I will use unless you object (all TODO(balance))
- Tank cap ~8 h of work; 1 crop sell-price-weighted unit = fixed minutes of fuel.
- Food buff: +50% pet xp for ~30 min, refreshes (no stacking beyond 1.5x).
- Sidekick bonus: +1% per 10 combined inactive levels/stars-weighted, cap +50%.

## Build order (design branch; workers do bounded steps, I review)
1. Registry (`cococap/registry/models.py`, `loader.py`): pet `loadout`; new `configs/pet_score.toml` for formula constants, fuel rates, haul cap. Convert all 25 pets in `configs/pets.toml`.
2. `cococap/services/pet_score.py` (pure): score from loadout/level/stars/lent tool; sidekick bonus; passive stats; haul per hour. Reuse `pets.strength`, `pets.effects`.
3. State in `cococap/models/pethouse.py`: fuel seconds, last-collect timestamp, food-buff expiry, lent tool id; Alembic migration if a table changes (`cococap/db/tables.py`).
4. `cococap/services/pets.py`: `fuel()` (crops -> tank), `collect()` (haul by skill tables), feeding gives xp + buff, `grant_play_xp` applies buff. Lend/return tool in `services/equipment.py`.
5. Items/drops (`configs/items.toml`, skill drop tables): new pet-food items per skill (via add-item skill; emoji needed) and buffed rates; check with `scripts.balance`.
6. Screens (`cococap/screens/` pets page, tab not new screen): score card, loadout, sidekick %, tank gauge, Collect, Fuel, lent tool; wiki line.
7. Tests (read numbers from registry): score monotonic in level/stars/rarity; haul capped and zero when empty; passive stays at empty; sidekick cap; buff expiry; migration keeps level/stars; guard: haul <= ~15% of active pay. Changelog + notice; DESIGN.md Pets section; STATUS.md; delete superseded plans.

## Verification
`python -m scripts.quick_tests` after each step, ruff clean, `python -m scripts.balance` for haul vs active pay. Back up `data/cococap.db` before the migration. Full suite only on request.

## Still open (decide during build)
Exact loadouts for each of the 25 pets; whether the lent tool can be one you have equipped (assume no); haul drop tables per skill.
