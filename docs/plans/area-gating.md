# Area gating (plan, NOT built; waiting for the user's approval)

Goal: features need the right AREA (you have travelled there) AND a level. Later areas are hard to reach (gear). Source: `docs/plans/notes-2026-11-18.md` section 1.
What exists: `configs/areas.toml` (7 areas, ship, fuel, 14 locations/skill), `services/areas.py` (`state(user)` -> tier/current/highest, stored in
`services/community` key `ship:<user_id>`; locations already need area + level). Features today only check a skill level (see table).

## 1. Design
- **Config**: new `[[gate]]` table in `configs/areas.toml`: `feature = "reactor"`, `area = "rust_belt"`, `skill = "mining"`, `level = 10` (level optional).
  Registry model `Gate` + loader check (area id exists, feature ids unique). Existing per-feature `min_level` keys in other tomls stay as the
  LEVEL part until step 3, then a test checks the gate level and the feature's own level agree (one source of truth later: move levels into the table).
- **Rule** (`services/areas.py`, no discord): `async def gate(user, feature) -> Gate status` (open bool, `missing` text) and `async def require(user, feature)`
  raising `AreaError("<Feature> unlocks in <Area> at <skill> level N")`. Open = `highest area index >= gate area` AND level met, OR grandfathered.
  NOTE: it uses `highest` (reached), not `current`: once you have been there, the feature stays (free travel back; the area is a ceiling only for locations).
- **Services call `require`** at the action (reactor place/prestige, market buy/sell, book donate, releaf give...), never only in the screen.
- **Screens**: a shared helper `ui/locked.py: locked_note(status)` -> "🔒 The Reactor unlocks in **Rust Belt** at mining level 10 (you: Slime Hill, level 12)".
  Locked screens show that line instead of the body; Home/hub buttons stay visible but disabled with the same hint (less clutter than hiding, and players learn what is ahead).
- **Gear requirement (later areas)**: `[[gate]]`-style `min_tool_power = {pickaxe = N}` per AREA in `[area.*]`, checked in `travel()` next to fuel and the
  ship tier. Numbers TODO(balance); plan only, not in the first build.
- **Fuel costs / starred materials (notes item 2)**: planned, NOT built: area `fuel` entries would accept `<id>_s2/_s3` keys (docs/plans/starred-materials.md);
  only a recipe/config change, no new code expected.

## 2. Current players: nobody loses anything
Everyone is area 1 (Slime Hill, `highest = 0`) today, so a naive gate would lock features players already use.
- **Grandfathering, no DB migration**: stored in the SAME `ship:<id>` community doc as a new optional key `"grandfathered": ["reactor", ...]` (`_clean` defaults it to `[]`; old docs stay valid).
- Applied **lazily** on the player's first gate check after the deploy, by `grandfather(user)`: for each gate, add the feature if the player meets its LEVEL and has used it.
  State read (read-only): skill XP/levels (`user.skill`), `mining.reactor.level > 1` or gems placed or prestige > 0, farming market history / `farming` skill state,
  fishing book/pots/radar docs (`fishing.book`, pots owned, radar level), releaf contribution (`services/foraging` releaf state), plus `user.stats` if it counts uses.
  "Level met" alone is the fallback where no usage trace exists.
- **Who counts as existing**: gated by a cutoff date `grandfather_before` (config) vs. the user's creation time; if `User` has no created timestamp, instead a
  one-time flag (`"gv": 1`) written on first check for any player with skill XP > 0 at deploy time; new accounts start with `gv = 1` and an empty list.
  (To verify in code before building.)
- Back up `data/cococap.db` before first run on live data (no schema change, so no Alembic migration).

## 3. Tests
- Registry: every gate's area/skill/feature exists; ids unique; gate level == the feature's own configured level (no drift).
- `gate()`: locked in Slime Hill, open after `highest` reaches the area, stays open after travelling back, level still required.
- Grandfather: a pre-existing player with reactor level 3 keeps the reactor in area 1; a fresh player does not; idempotent; old `ship:` doc without the key loads.
- Each gated service raises `AreaError` when locked (parametrised over the table); `test_hub.py::test_every_screen_renders...` covers layout; one test per locked screen shows "unlocks".
- Mutation-check the `require` call in one service.

## 4. Candidate features and PROPOSED areas (current unlock -> proposed). Yours to change.
| Feature | Screen / service | Now | Proposed area (+ level) |
|---|---|---|---|
| Magnet (auto-feed) | mine | mining 5 | Slime Hill (no gate; keep) |
| Shipments (basic / hard crates) | shipments | 10 / 30 | Slime Hill / Rust Belt |
| Fishing quests + community | fish | fishing 3 | Slime Hill (keep) |
| Crab pots | fish / `pots` | fishing 6 | Twilight Desert |
| Fishing Book (+ community book) | fish | fishing 10 | Twilight Desert |
| Farmer's Market | market | farming 5 | Twilight Desert |
| Reactor (gem slots, prestige, automine) | reactor | mining 10 | Rust Belt |
| Wyrmhole | wyrmhole | via reactor gems | Rust Belt (follows the reactor) |
| Releaf Foundation | releaf | foraging 10 | Cadrega City |
| Fishing Radar | radar | fishing 25 | Cadrega City |
| Enchanting (scrolls) | enchant | none | Twilight Desert (needs a check of current rules) |
| Mastery trees | mastery | per node | Slime Hill (keep; it is the level-up reward loop) |
| Pets / pet house | pets | none | Slime Hill (keep) |
| Casino / minigames / trade / parties | casino etc. | none | never gated (social) |
| Crafting recipes (workbench) | craft | per recipe `min_level` | unchanged; later recipes can name an area in recipes.toml |
Not found as gates: combat (paused). Aerial Glades, Star Kingdom, The Void get no feature yet (reserved for new content: e.g. tier-2 reactor, big fuels).
