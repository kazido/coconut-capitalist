# Status: what is true now

Short on purpose. Rules: when work merges, remove its line here and delete its plan; never keep a changelog (use `git log`). How systems work: `docs/DESIGN.md`.
Setup and moving machines: `docs/DEVELOPING.md`. Working rules: `CLAUDE.md`. Last pruned 2026-11-18.

## Built and live in the code
Skills: mining (14 mines, descent, wyrmholes, reactor, magnet with auto-aim), fishing (14 waters, radar, quests, books, bosses), foraging (14 forests, community
and party trees, Releaf Foundation), farming (14 zones picked on the Farm page, per-zone byproduct materials, market twice a day). Pets (25 flame wisps), mastery trees, shipments by skill,
trading, parties, casino and minigames, crafting, ranks, wiki, per-skill stats pages, areas and the ship (Travel), the channel janitor (ops).
Screens are consolidated into tab pages (33 registered). Item ids are prefixed (`<category>_<name>`), emoji named by id. Combat is live again (classes by weapon, 14 zones, tiered party dungeons; DESIGN.md "Combat").

## Plans still open (`docs/plans/`)
- `tools-smithing.md`: APPROVED. Tools become 3 dropped parts (base + trim + accent), Smithing light skill, salvage, accessories, notices/changelog first.
- `area-gating.md`: features need area + level. Written, NOT approved or built.
- `foraging-materials-needed.md`: foraging has too few materials; needs designer input.
- `starred-materials.md`: drops wired in all 4 skills; open: zone->forest text rename, late upgrade costs, UI check.
- `pet-score-1000.md`: pet score out of 1000 + traits + Mythical/Celestial pets. Direction approved, not built.
- `pet-sidekicks.md`: APPROVED, built on master: loadouts, score, tank, Collect/Fuel UI, food buff, foods, guard test. Open: Mythical + Celestial pets and their traits, lend-tool screen (on hold) + equipped check, haul drop tables, balance pass, pet-food art.
- Combat follow-ups: icons for the 6 zone emoji (🪦🏛️🏭🌥️⛈️☄️) and the dungeon map glyphs (art, fixes `test_glyphs`); party-size boss scaling and dungeon run xp; refresh the combat rows in `scripts/balance.py`.
- `notes-2026-11-18.md`: bigger ideas (fuels, recipe rebalance, tutorial/lore, screen streamlining).

## Known open items
- Balance is guesses (`TODO(balance)`): mining locations, axe/can road stats, shipment sizes, radar costs, fishing/foraging/farming capstones, Forest 14 unlock,
  waters 5-14 reuse placeholder fish.
- Old-player migration from Mongo waits on a working login (`scripts/import_mongo.py`). Hosting (VPS, backups, deploy) is unbuilt: `docs/HOSTING.md`.
- ART TODO (waiting on the new art pipeline): pet foods still use unicode emoji (`food_harvest_mash`, `food_garden_stew`, `food_golden_ear`, `food_pet_biscuit`, and the older `food_*` ones); each needs real art named by its id.
- ART TODO (pets): new Mythical pets and 1 Celestial pet (see `plans/pet-score-1000.md`), and all pets drawn with the rarity border and a dark outline.
- ART TODO: the 8 accessories (`acc_*`) all use a 💍 placeholder emoji; each needs framed item art named by its id.
- Emoji upload state may lag the art: check with `scripts/upload_emojis.py` (dry run) before assuming; restart the bot after uploading.
- Not built yet: fishing minigame rework, party versions of each skill, channel drops (`exts/economy/drops.py` is old Mongo code).
