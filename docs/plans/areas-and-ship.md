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

---
# REWORK: locations instead of foraging's 20 zones (2026-11-17, supersedes the "Areas" table and per-skill caps above)

**Idea:** every skill has the same shape as fishing's waters: a list of named *locations* you pick from a dropdown, each opening at a
skill level. 14 locations per skill (2 per area): forests, mines, waters, fields. Area N holds locations 2N-1 and 2N.
Open rule: `location.area index <= your current area index` AND `skill level >= location.min_level`. So you are capped by the area
you are in until you travel on. Config: each location gets `area = "<area id>"` + `min_level`; `foraging_max_zone` and
`fishing_max_water` come OUT of areas.toml.

**Level schedule (all skills the same; fishing keeps its 1/3/8/15):**
| loc | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| min level | 1 | 3 | 8 | 15 | 19 | 23 | 27 | 31 | 35 | 39 | 42 | 45 | 48 | 50 |
| area | Slime Hill | | Twilight Desert | | Rust Belt | | Cadrega City | | Aerial Glades | | Star Kingdom | | The Void | |

Final location at level 50 (of 100): the last 50 levels are mastery and level-50 capstones. Ship `skill_floors` change to match the
first location of each area: 8, 19, 27, 35, 42, 48 (was 8/20/35/55/80/105).

**Foraging:** the 20 zones become 14 forests. Forest k uses old zone round(1 + (k-1) x 19/13) = 1,2,4,5,7,8,10,11,13,14,16,17,19,20 for
hp/reward scaling; species zone_min/max remapped to forest numbers; `zone_levels` replaced by the shared schedule; the picker becomes
a dropdown like fishing's water select. RISK: forest 14 (old zone 20, which used to need level 136) is now reached at level 50, so
`zone_reward_growth` (+7%/zone) and the community/party tree numbers (`default_zone`, `zone_below/above`) must be re-tuned with
`scripts.balance`. Biggest balance job of the rework.
**Mining:** a location picks the ore table (`depth_tables`) and hardness scale for a descent; deeper locations favour rarer ores.
**Fishing:** waters grow from 4 to 14 (10 new, each with a fish list, wait_multiplier, xp).
**Farming:** a location is a field tier that unlocks its crops/seeds (and the shop sells only seeds of reached areas).

**Spreading materials (stars: 1/2/3-star versions drop more in harder locations):**
- Mining: ~14 ores + gems: enough.
- Fishing: 22 fish across 14 waters: enough (a few repeat across neighbours with higher star/rarity weights).
- Farming: only 10 crops for 14 fields and crops are not starrable yet: add ~4 crops or make crops starrable.
- Foraging: THINNEST. After the cull only hardwood, feather, fine_bark, maple_leaf, aged_feather (+ wedges). Need ~4-5 new foraging
  materials (e.g. one per 3 forests) or each forest keeps its species' signature drop (species `drops` already exist, currently empty).
- The star table (`economy.toml [stars]`, `starrable`) is being built by someone else right now: coordinate before touching it.

**Build order (replaces steps 3-6):** 3. shared `Location` model + schedule + `areas.open_locations(skill)` helper + tests.
4. Foraging forests (rebalance). 5. Fishing 14 waters. 6. Mining locations. 7. Farming fields + seed shop gating. 8. Ship screen.

---
# Decisions, round 3 (2026-11-17)
- **Gems everywhere:** every mine location's ore table must be able to drop the reactor gems (`mining.toml [reactor] core_gems`), so the
  reactor can always be fed. Add a loader check/test: each location's table contains all core gems.
- **Principle: every new location needs a NEW unlock, not just a higher star** (stars are 2/3-star versions of the same item, so they do not
  count as something new). Crops may still become starrable later, but 14 fields need 14 different crops (see "Crops" below).
- **Foraging materials:** the user is designing them. See `docs/plans/foraging-materials-needed.md`. Build forests with the existing
  materials as placeholders until then.
- **Ship skill_floors** already updated in `configs/areas.toml` to 8/19/27/35/42/48.

## Location names (themed: area x skill; first column = loc number)
| # | Area | Forest | Mine | Water | Field |
|---|------|--------|------|-------|-------|
| 1 | Slime Hill | Slimewood Thicket | Slimy Burrow | Slime Pond (`pond`) | Slimeside Garden |
| 2 | Slime Hill | Jellybough Grove | Gumdrop Quarry | Slimeflow River (`river`) | Meadow Farmstead |
| 3 | Twilight Desert | Duskthorn Scrub | Duskstone Quarry | Mirage Oasis (`reef`) | Dusk Terraces |
| 4 | Twilight Desert | Oasis Palms | Glassfall Caverns | Sandglass Cenote (`deep_sea`) | Oasis Orchard |
| 5 | Rust Belt | Rustleaf Woods | Scrapheap Tunnels | Oilslick Canal | Scrapyard Allotments |
| 6 | Rust Belt | Cogbark Copse | Foundry Depths | Rustwater Reservoir | Hydroponic Bays |
| 7 | Cadrega City | Canal Park Arboretum | Subway Catacombs | Cadrega Canals | Market Gardens |
| 8 | Cadrega City | Rooftop Gardens | Clockwork Vaults | Grand Harbor | Rooftop Farms |
| 9 | Aerial Glades | Cloudroot Canopy | Cloudstone Crags | Cloud Pools | Cloud Terraces |
| 10 | Aerial Glades | Windbloom Meadow | Stormvein Rift | Skyfall Lake | Windmill Fields |
| 11 | Star Kingdom | Starlit Orchard | Meteor Pits | Moonwell | Stardew Fields |
| 12 | Star Kingdom | Moonbark Forest | Stardust Lode | Starlit Stream | Comet Orchards |
| 13 | The Void | Hollow Wood | Hollow Seams | Black Tide | Pale Gardens |
| 14 | The Void | The Withered Rift | Core of Nothing | The Bottomless | Dreamless Furrows |
Fishing's existing water ids (`pond`, `river`, `reef`, `deep_sea`) are saved in player state (`models/skills/fishing.py` `water`): keep the
ids for locations 1-4 and just rename the display names, or add a fallback to the first open water for unknown ids. Names are placeholders to rename freely.

## Crops: 14 fields need 14 crops (we have 10, add 4)
One new crop unlocks per field, in sell-price order (seed + crop item pair each, `[crop]`/`[seed]` tables in items.toml; the add-item checklist).
| field | crop | sell price (bits) |
|---|---|---|
| 1 Slimeside Garden | apple (have) | 1,000 |
| 2 Meadow Farmstead | lemon (have) | 35,000 |
| 3 Dusk Terraces | blueberry (have) | 40,000 |
| 4 Oasis Orchard | dusty dandelion (have) | 50,000 |
| 5 Scrapyard Allotments | **Rustroot** (new, ~100,000) | |
| 6 Hydroponic Bays | hot pepper (have) | 300,000 |
| 7 Market Gardens | watermelon (have) | 400,000 |
| 8 Rooftop Farms | **Marketfig** (new, ~700,000) | |
| 9 Cloud Terraces | wilted rose (have) | 1,000,000 |
| 10 Windmill Fields | **Cloudberry** (new, ~1,200,000) | |
| 11 Stardew Fields | starfruit (have) | 1,500,000 |
| 12 Comet Orchards | coconut (have) | 2,000,000 |
| 13 Pale Gardens | **Voidbloom** (new, ~10,000,000) | |
| 14 Dreamless Furrows | ambrosia (have) | 50,000,000 |
New crops need: id, name, emoji, wiki, seed price, growth time/yield like their neighbours in `farming.toml`, a use, and the same new-crop checks as the others. Each crop shows in the shop only once its field's area is reached.

## Same check for the other skills (a new unlock per location)
- Fishing: 22 fish over 14 waters: fine (each water adds at least 1-2 fish not found earlier).
- Mining: 13 ores (copper, coal, clay, tin, iron, silver, gold, amber, obsidian, platinum, garnet, sapphire, emerald) for 14 mines, plus the gems that are
  always present. Borderline but workable (neighbouring mines can differ in odds and hardness); one extra high ore would make it clean. Open.
- Foraging: 5 materials for 14 forests: needs 9 new (brief updated).
