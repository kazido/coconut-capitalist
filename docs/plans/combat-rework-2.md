Status: PLANNED. Steps 0 (victory screen), 1 (UI pass) and 2 (turn pacing) are done. Build one phase per session, in order. Supersedes the idea in `weapon-parts.md` (fold it in here when phase 2 starts).

# Combat rework 2

Rule for every phase: emoji for each new thing (art routed to Opus via `make-emoji`), tests, DESIGN.md "Combat" section, STATUS line.

## 0. Victory screen (DONE)
Uses `ui/rewards.rewards_result` (drops + xp only). Continue goes to Combat.

## 1. UI pass (small, no new rules)
- ui_ emoji for the important combat buttons (fight, flee, target, skills, class, bestiary, area).
- Emoji for every weapon kind (sword, bow, staff, shield, unarmed) in the basic-tool emoji style.
- Class tab: dropdown of classes with emoji. Only classes you own a weapon for; picking one auto-equips the best weapon (tool power) of that class.
- Bestiary paginated, one enemy per page, with its emoji.

## 2. Turn pacing (DONE)
Fight screen plays a turn in steps with `asyncio.sleep` redraws: your move, pause, enemy telegraph + move, pause, what it did to you.
The log shows only the latest round, split into "You" and "Enemy" blocks. Needs a step list from `Battle.play` (Battle stays Discord-free).

## 3. Skills: a loadout of 4 from ~20 per class (REDESIGNED by the owner, in progress)
- Classes (unarmed, melee/sword, archer/bow, wizard/staff, tank/shield) each own a pool of ~20 skills. The player equips a LOADOUT of 4
  (the fight buttons). Roles to cover across a loadout: single hit, multi-hit, AOE, utility (buff, heal, guard, stun, mark).
- Start with 4 basic skills per class (choice from level 0); the rest unlock as the CLASS levels.
- NEW: class level + class xp, separate from combat level (per class, stored in the player's combat skill doc). A fight pays class xp to the
  class you fought with. Shown on the Class tab (level, xp bar, skill pool with lock levels, loadout picker).
- Resources (rage/focus/mana/guard) and cooldowns stay as today. Today's kits are 5 skills with level unlocks: they become the seed of the pools.
- A balance sim row per class (`scripts/balance.py`). Design the pools kind by kind with the owner (one question at a time).
- Build order: (a) class xp/level model + award in `combat.settle` + Class tab display; (b) loadout storage + picker + fight uses the loadout;
  (c) author pools kind by kind (4 basics first, then unlockables).
- 3b DONE: `Combat.loadout` (class id -> up to 4 skill ids), `combat.loadout/set_loadout`, `build_player` uses it, multi-select picker on the Class tab. Left: 3c.
- 3a DONE: `Combat.class_xp` (class id, "unarmed" for bare hands), paid in `combat.settle`; kit unlocks and the Class tab use the class level.
- DONE already: Explore page has the XP bar line like other skills; `ui/levelup.SCREEN_SKILL` maps fight/combat so the victory screen shows the
  combat + pet progress line and the pet xp tag.

## 4. Weapon parts (see `weapon-parts.md` questions)
Weapons are smithed from weapon parts only; tool parts stay for tools. Parts carry combat traits (+damage, +speed, +hp, +crit).
Needs the open questions answered first (slots, migration, drop source).

## 5. Combat drops + crafting
New combat drop materials per enemy family, feeding weapon-part recipes, and health potion recipes (crafted, used in a fight or before it).

## 6. Dungeon keys
Retexture the Gravewarden key in every rarity = the key per dungeon tier. Wire the emoji everywhere keys show.

## 7. Areas and explore
- Combat areas like the other skills (area switcher on the Combat page; `add-location` skill; art to Opus). Zones group into areas.
- Minibosses appear while exploring (random chance), and the separate miniboss fight section goes away.
- More enemy types, each with an emoji; bestiary pages follow.
