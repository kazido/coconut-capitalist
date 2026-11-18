# Status: what is true now

Short on purpose. Rules: when work merges, remove its line here and delete its plan; never keep a changelog (use `git log`). How systems work: `docs/DESIGN.md`.
Setup and moving machines: `docs/DEVELOPING.md`. Working rules: `CLAUDE.md`. Last pruned 2026-11-18.

## Built and live in the code
Skills: mining (14 mines, descent, wyrmholes, reactor, magnet with auto-aim), fishing (14 waters, radar, quests, books, bosses), foraging (14 forests, community
and party trees, Releaf Foundation), farming (14 fields, Tend byproducts, market twice a day). Pets (25 flame wisps), mastery trees, shipments by skill (Crates),
trading, parties, casino and minigames, crafting, ranks, wiki, per-skill stats pages, areas and the ship (Travel), the channel janitor (ops).
Screens are consolidated into tab pages (33 registered). Item ids are prefixed (`<category>_<name>`), emoji named by id. Combat is PAUSED (code kept).

## Plans still open (`docs/plans/`)
- `area-gating.md`: features need area + level. Written, NOT approved or built.
- `foraging-materials-needed.md`: foraging has too few materials; needs designer input.
- `starred-materials.md`: drops wired in all 4 skills; open: zone->forest text rename, late upgrade costs, UI check.
- `2026-11-19-tomorrow.md`: the owner's art/design list (rank emoji, button icons, Releaf tiers, bar colours).
- `notes-2026-11-18.md`: bigger ideas (fuels, recipe rebalance, tutorial/lore, screen streamlining).
- `ui_emoji_progress.md`: open emoji art items (location and ship icons).

## Known open items
- Balance is guesses (`TODO(balance)`): mining locations, axe/can road stats, shipment sizes, radar costs, fishing/foraging/farming capstones, Forest 14 unlock,
  waters 5-14 reuse placeholder fish.
- Old-player migration from Mongo waits on a working login (`scripts/import_mongo.py`). Hosting (VPS, backups, deploy) is unbuilt: `docs/HOSTING.md`.
- Emoji upload state may lag the art: check with `scripts/upload_emojis.py` (dry run) before assuming; restart the bot after uploading.
- Not built yet: fishing minigame rework, party versions of each skill, channel drops (`exts/economy/drops.py` is old Mongo code), combat drops and tiers.
