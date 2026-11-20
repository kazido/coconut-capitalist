Status: APPROVED 2026-11-20. Steps 0-4 done on design; step 5 (dungeon service) next.


## Context
Combat has been paused since the old sword-kit slice. The owner wants a fun combat skill with these parts:
- **Classes come from the weapon:** sword = Melee, bow = Archer, staff = Wizard, shield = Tank.
- **Field battles:** endless single fights, found by exploring 14 combat zones.
- **Tiered dungeons:** dungeon keys (tiers 1-8) drop and open tile-based dungeons. Players move, step on tiles (rewards, buffs, enemies), fight, and end at a boss. A party can enter together, and every move redraws the screen for every member.

Reuse the built turn-meter engine: `services/combat.py`, with `Battle`, `Unit`, effects, cooldowns, boss phases, telegraph and immunities. Each class adds one resource.

## Workflow rules (step 0, do first after approval)
- Add a short "How the lead works" block to `CLAUDE.md` and trim it elsewhere so the file stays the same size:
  - Find code with graphify first.
  - Think deep, not wide. Broad sweeps go to an Explore subagent that returns only a summary.
  - Use plan mode for almost everything.
  - Model split: Opus = design and engine, Sonnet = bounded writing or screens, Haiku = tests, docs and routine work.
  - Briefs carry `file:line` plus `@path` file mentions (clickable, so the worker opens exactly that file), and never pasted file contents.
- Update the memory file `graphify-briefs.md` to match.
- Copy this plan to `docs/plans/combat-rework.md` with the line `Status: APPROVED`, and add a line for it in STATUS.md.

## Design (data first)
**Classes** (`configs/combat.toml` gets `[classes.<id>]`: weapon kind, resource, stat profile, skills unlocked by combat level):
| Class | Weapon | Resource | Feel |
|---|---|---|---|
| Melee | sword | **Rage**: +gain when you hit or get hit; finishers spend it | burst on one target |
| Archer | bow | **Focus**: builds each turn you don't take damage or when you Aim; +crit per point; Power Shot spends it | crits, speed, meter pull |
| Wizard | staff | **Mana**: refills each turn; spells cost it. **Elements**: frost = chill (slow), fire = burn (damage over time), storm = chain hit. Combos: Shatter on a chilled target, Ignite on a burning one | area damage, debuffs |
| Tank | shield | **Guard**: gained when hit or bracing; spend on Counter, Reflect, Shield Ally, **Taunt** (enemies must target you) | sustain; carries the party at the boss |

- **Engine changes (`services/combat.py`):**
  - `Unit` gains `resource` and `resource_max`. A skill gains `cost`, `gain` and an `element`. New effects: `taunt`, `chill`, `burn`, `reflect`, `counter`.
  - `Battle` takes a list of player units, so a party boss works. Enemy targeting obeys taunt, then picks the lowest hp.
  - The rng stays seedable, and existing effects stay unchanged.
- **Weapons:**
  - Add the kinds `sword`, `bow`, `staff` and `shield` to smithing (one template per kind, as for pickaxe/rod/axe/can) and to the traits' `kinds` lists.
  - Kits come from class plus combat level, not from the item. `services/tool_effects.power_stats` gives each kind its attack/hp/defense/speed profile, and `sword_stats` gets replaced.
  - Before step 1, grep the old sword item ids (`tool_dreamnail`, `tool_rustedbroadsword`, `tool_shiningsilver`, `tool_largebranch`, `spirit_of_the_sword`) in configs, cococap, tests and art. Remove or convert them with the `remove-item` skill. That lands on master first and alone.
- **Zones:**
  - Add 14 `[combat.<id>]` locations in `configs/locations.toml`. The same rules apply: area = ceil(n/2) and the level gates in `areas.toml`. Graveyard is zone 1.
  - Each zone has an enemy pool, a drop table in `configs/drops.toml`, and a key drop chance, with the key tier tied to the area.
  - **Explore** rolls an encounter of 1-3 enemies, then runs a fight. A field loss costs nothing, and the player always starts at full hp.
- **Dungeons** (`configs/dungeons.toml`, tiers 1-8):
  - Each tier sets grid size, tile weights (reward, buff, enemy, empty), enemy pool, boss and loot scale.
  - Keys are `key_dungeon_t1`..`t8`, with rarity = tier. The key is spent on entry.
- **`services/dungeon.py`** (no discord; runs in memory like trade windows):
  - A `Run` holds the seeded grid, revealed tiles, each member's position, hp, buffs and loot, and a `busy` flag.
  - Members move separately. A busy member shows as frozen on the others' maps.
  - An enemy tile starts a solo battle. Hp and buffs carry over within the run, and the player returns to the map afterwards.
  - The boss can start only when nobody is busy. All members join one shared boss battle.
  - A loss ends that player's run, but they keep the loot found so far. *Assumption:* losing the boss fight ends the run for everyone.
- **Sync:**
  - Add `"dungeon"` and `"fight"` to the screen ids that `ui/nav.poke` may redraw (`cococap/ui/nav.py:41`).
  - The dungeon service pokes every member after each move, tile and battle end, and after each boss turn. `refresh_every` is the fallback (pattern: `screens/trade.py:41`).
  - In the boss battle, a member idle for 30 s automatically uses their basic skill.
- **UI:**
  - The `combat` entry in `screens/skills.py:14` (SKILL_SCREENS) points at a new Combat `TabsScreen` with tabs Explore (zone picker + Explore), Dungeons (keys, enter, party), Class (weapon, kit, resource) and Bestiary.
  - Reuse `screens/fight.py` for battles. Add a resource bar next to hp.
  - The dungeon pane is an emoji grid viewport (about 7x7) plus 4 arrows and one context button (Fight / Loot / Boss / Leave).
- **Docs:** add a changelog entry (`major = true`), a notice and a new DESIGN.md combat section. Update the "Combat paused" line.

## Steps (one commit each; lead reviews diffs and runs targeted tests + ruff only)
1. **Remove the old sword items** (Sonnet worker, `remove-item` skill). Lands on master alone.
2. **Weapon kinds + class data:** smithing kinds, templates, `[classes]`, skill definitions, registry models and loader validation (Sonnet). Tests: `test_combat.py`, smithing tests.
3. **Engine:** resources, elements and combos, taunt/counter/reflect, multi-player `Battle` (**Opus lead**). Haiku `tester` adds unit tests per class (seeded rng) and a party taunt test.
4. **Zones + Explore + unpaused Combat page** (Sonnet). Tests: `test_combat_screen.py`, the `test_hub.py` layout test, and a zone config test.
5. **Dungeon service:** generation, movement, tiles, busy flag, loot, boss gate, run end (**Opus lead**). Haiku `tester` covers it.
6. **Dungeon screen + poke sync + shared boss battle UI** (Sonnet; lead reviews the sync and locking).
7. **Keys and drops** across zones and tiers, then a balance pass with the `balance-check` skill (combat xp per minute comparable to the other skills). Docs, changelog and notice go to a Haiku `writer`.

Each brief follows the CLAUDE.md template, with `graphify affected` output and the exact test list.

## Not in this plan
- A combat mastery tree.
- PvP.
- Accessories for combat.
- Saving dungeon runs across bot restarts. Shortcut: runs live in memory, and a restart loses the run and the key. Revisit when hosting is built.

## Verification
- Targeted pytest per step (from `graphify affected --depth 2`) + `ruff check`.
- Seeded engine tests prove each class's resource loop and the wizard combos.
- A dungeon service test simulates 2 players: separate moves, one busy, the boss blocked until both are free, a shared boss win, and the loss path.
- The hub layout test passes the Discord limits for the new panes.
- The owner plays: Explore in zone 1, find a tier 1 key, then run a tier 1 dungeon solo and with a party.
