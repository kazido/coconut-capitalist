# Areas and the Ship (plan, not built)

Goal: make players level every skill in tandem. The world has 7 **areas**; a **ship** (built, upgraded, fuelled with
materials from all skills) moves you to the next one. Each area raises difficulty and rewards in every skill.

## Decisions (user, 2026-11-17)
- **Area caps the zones.** Each area opens a band of skill zones. You still need the skill level for a zone; the area is a hard ceiling.
- **Free travel back** to earlier areas (fuel only needed to go forward). Old areas stay useful for old materials.
- **Ship parts and fuel need materials from every skill** (mining, fishing, foraging, farming) so none can be skipped.

## Areas (name -> foraging zones opened, since foraging has 20 zones today; TODO(balance) bands)
| # | Area | Foraging zones | Idea |
|---|------|----------------|------|
| 1 | Slime Hill (start) | 1-3 | tutorial; plain materials |
| 2 | Twilight Desert | 4-6 | |
| 3 | Rust Belt | 7-9 | scrap/metal flavour |
| 4 | Cadrega City | 10-12 | |
| 5 | Aerial Glades | 13-15 | |
| 6 | Star Kingdom | 16-18 | |
| 7 | The Void | 19-20 | endgame |

## Data model
- `configs/areas.toml`: `[[areas]] id, name, emoji, description, order` plus per-skill caps and the ship tier needed to enter:
  `foraging_max_zone`, `fishing_tier`, `mining_tier`, `farming_tier`, `combat_tier`, `ship_tier`, `fuel` (recipe id + amount).
- `configs/ship.toml`: tiers 1..6 (each = ONE upgrade to reach the next area): `[[tiers]] id, name, parts = {item = qty}, skill_floors = {skill = level}`.
  Fuel is a craftable item (`configs/recipes.toml`), one kind per hop, each recipe mixing items from all four skills.
- Player state: `cococap/models/ship.py` (ship tier, `current_area`, `highest_area`) stored on the `User` document (check whether
  `models/settings.py` or a new doc fits; a DB migration is likely NOT needed if user docs are JSON).
- Registry model `Area`, `ShipTier` in `cococap/registry/models.py`; loader validates item/recipe links.

## Services (no Discord)
- `services/areas.py`: `current_area(user)`, `max_zone(user, skill)`, `can_travel(user, area)`, `travel(user, area)` (forward consumes fuel, back is free).
- `services/ship.py`: `upgrade(user)` consumes parts, checks skill floors; `build` is tier 1.
- Hook points: every skill's zone/tier picker clamps to `areas.max_zone(user, skill)`. Foraging: where zones are chosen (`services/foraging.py`,
  `zone_levels`). Grep "zone_levels" first.

## Per-skill implementation
- **Foraging**: already zoned. Just clamp the zone to the area cap. Easiest, do first.
- **Fishing**: no zones in config yet. Add `[[waters]]` (one per area, optionally 2 sub-bands) with a fish pool + rarity bump; clamp by area.
  Needs new fish items (emoji + wiki per the add-item checklist).
- **Mining**: add area-scaled ore pools / mine depth: each area has an ore tier table (hardness, ore list); `mine_types` stay as modifiers on top.
  The `descent` depth/hardness could be capped per area.
- **Combat**: paused. Define `enemy_tier` per area in `areas.toml` now so it plugs in later; no code.
- **Farming** (decided 2026-11-17): each area unlocks a tier of crops and seeds. The seed shop only sells seeds from areas you have
  reached (highest_area, so seeds stay buyable after travelling back). Add an `area` field to each `.seed`/`.crop` item in `items.toml`
  (default Slime Hill), filter the shop's seed list in `services/shop.py` by it, and make planting check it too (seeds already owned
  from drops/trades should still be plantable only if the area is reached). Needs new crops/seeds for areas 2+ (add-item checklist).
  Existing players who already own or bought high-tier seeds: grandfather them (keep owned seeds usable).

## Screens
- New `screens/ship.py`: shows area, ship tier, parts needed, a Travel dropdown (earlier areas free, next area shows fuel cost). Link from Home/More.
- Skill screens show their current zone cap with a hint "Travel to <next area> to unlock zones X-Y".

## Rewards scaling
- Prefer scaling via the zone's existing `zone_reward_growth`, plus area-exclusive materials needed for ship parts. Check `scripts.balance`
  and `tests/test_economy_guard.py` before/after.

## Build order (each step shippable)
Step 1 DONE: `configs/areas.toml` (areas + ship tiers), 6 fuel items + recipes, `services/areas.py` (state kept in `services.community`
key `ship:<id>`, no migration), `tests/test_areas.py`. Not yet wired into any skill or screen.
1. Areas + ship state + `areas.toml`/`ship.toml` + services + tests (no skill effect yet).
2. Ship screen (travel, upgrade, fuel craft).
3. Clamp foraging zones to area cap.
4. Fishing waters + new fish.
5. Mining area ore tiers.
6. Farming per decision above. Combat later.
7. DESIGN.md section, HANDOFF "Latest state", wiki entries.

## Open questions
- Do skill levels also gate ship tiers (`skill_floors`)? Planned yes; exact numbers TODO(balance).
- Do existing players start in Slime Hill, or in the area their levels already imply (migration)? Suggest: grandfather to the highest area their foraging zone fits.
