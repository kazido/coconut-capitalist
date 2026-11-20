Status: PLANNED. Step 0 (victory screen) is done. Build one phase per session, in order. Supersedes the idea in `weapon-parts.md` (fold it in here when phase 2 starts).

# Combat rework 2

Rule for every phase: emoji for each new thing (art routed to Opus via `make-emoji`), tests, DESIGN.md "Combat" section, STATUS line.

## 0. Victory screen (DONE)
Uses `ui/rewards.rewards_result` (drops + xp only). Continue goes to Combat.

## 1. UI pass (small, no new rules)
- ui_ emoji for the important combat buttons (fight, flee, target, skills, class, bestiary, area).
- Emoji for every weapon kind (sword, bow, staff, shield, unarmed) in the basic-tool emoji style.
- Class tab: dropdown of classes with emoji. Only classes you own a weapon for; picking one auto-equips the best weapon (tool power) of that class.
- Bestiary paginated, one enemy per page, with its emoji.

## 2. Turn pacing
Fight screen plays a turn in steps with `asyncio.sleep` redraws: your move, pause, enemy telegraph + move, pause, what it did to you.
The log shows only the latest round, split into "You" and "Enemy" blocks. Needs a step list from `Battle.play` (Battle stays Discord-free).

## 3. Skills: 4 per weapon kind (unarmed, sword, bow, staff, shield)
Each kind gets 4 buttons with different jobs: single hit, multi-hit, AOE, utility (buff, heal, guard, stun, mark). Data in the skills config,
cooldowns/resource as today. A balance sim row per kind (`scripts/balance.py`). Design the 20 skills with the owner kind by kind.

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
