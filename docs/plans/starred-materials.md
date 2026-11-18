# Starred materials (plan)

## Context
Upgrades should eventually need higher-quality materials. The user's decisions:
- Stars are quality tiers 1★/2★/3★. Each tier is its OWN inventory slot (1★ and 2★ never stack), so players can bulk-sell lower stars once they are past that stage.
- Stars can NOT be crafted up. They only drop.
- Higher stars depend on the LOCATION, never on depth: each skill moves between locations (forests, waters, ...; see docs/plans/areas-and-ship.md) and only the later locations drop higher stars. 2★ can drop early but rarely; by mid-progression (e.g. foraging forest 10 of 14) 2★ is the main drop. 3★ is never the majority drop anywhere.
- Only LATER upgrades (the fork and top tiers) ask for 2★/3★ materials. Early upgrades stay plain.
- Rename foraging "zones" to "forests" (player-facing text only; keep code identifiers).

## Design
**Storage (no migration).** `ItemRow.item_id` is a plain string; ids must be alnum + `_`. The existing id is the 1★ item (every current inventory stays valid). The registry generates derived items `<id>_s2` and `<id>_s3` for each material listed as `starrable` (name "Copper Ore ★★", same emoji/price base, sell price multiplied). Files: `cococap/registry/models.py` (a `stars` field/`star_of` link on Item), `cococap/registry/loader.py` (generate variants, validate), `configs/items.toml` (`starrable = true` on chosen materials, plus a `[stars]` table of sell_price multipliers in `configs/economy.toml`).

**Which materials.** Start with upgrade-cost staples: mining ores (copper, tin, iron, gold, silver, platinum) and gems (amber, garnet, sapphire, emerald, obsidian); foraging hardwood, fine bark, maple leaf, feathers; fishing coral shard; farming compost, dewdrop, plant fiber, beeswax, living vine. Not starrable: fish, crops, seeds, bait, key items, wedges.

**Drop rule (the core).** One shared helper `star_tier(progress, rng) -> 1|2|3` in a new `cococap/services/stars.py`, driven by a per-skill progress axis and a data table in `configs/stars.toml`:
- progress = the player's chosen LOCATION in the skill, as a fraction of the skill's ordered locations (`stars.progress(step, steps)`): foraging forest 1-14, fishing waters 1-14. Mining and farming have no location ladder yet (their locations are still TODO in areas-and-ship.md). NOT depth.
- Steps 1-3 are built (variants, curve, roll helper). Step 4 is DONE for foraging and fishing; farming TODO (its locations exist now; progress = fields reached).
Table = per progress step, weights for 1★/2★/3★, e.g. step 1: 97/3/0; mid: 35/60/5; max: 15/65/20. A guard test asserts 3★ weight < 50% everywhere and 2★ is majority from the configured mid step. The roll happens where drops are granted (one per drop stack; quantity splits are rolled per item or per stack, decide at build), so each skill service calls the helper for starrable drops only.

**Upgrade costs.** `ToolUpgrade.items` keys may be `<id>_s2`/`<id>_s3`; `upgrades._missing` already reads by id so it works unchanged. Edit late-chain tools in `configs/items.toml` (fork and top tiers) to swap part of the plain cost for 2★/3★. Numbers go through `scripts.balance` / `balance-check` so each skill's time-to-upgrade stays equal.

**UI.** Names show stars (★ text now; art stars stay paused per HANDOFF). Sell-all keeps working per id; the "keep upgrade materials" rule already holds back per item id, so lower stars not needed by any owned tool's next upgrade can be sold in bulk. Wiki/shop list the variants under the base item.

## Steps (each bounded, delegable)
1. TODO Rename zone -> forest in player-facing text (screens/forage.py still has 33 "zone" mentions). Small, separate commit.
2. DONE Registry: starrable flag + generated variants + validation + tests (`tests/test_registry*.py`).
3. DONE `services/stars.py` + `configs/stars.toml` + guard tests (3★ never majority; monotone with progress).
4. Wire into each skill's drop grant (foraging, mining, fishing, farming), one skill at a time, with a test each. DONE foraging, fishing; TODO mining, farming.
5. Edit late-tier upgrade costs + balance run; update `tests/test_economy_guard.py` if needed.
6. UI names/wiki/shop/sell-all check; DESIGN.md section + HANDOFF "Latest state".

## Open decisions (defaults chosen, change if wrong)
- Per-drop vs per-stack star roll: default per drop event (whole stack same tier), simpler to read.
- Sell value multipliers: default 1x / 2.5x / 6x.
- Fishing and farming progress axes need a quick look before step 3.

## Verification
Registry loads with variants; `pytest` on the touched test files; `scripts.balance` before/after; a sim of 1000 drops per progress step prints the star mix (checks "3★ never majority"); add one 2★ item to a test inventory and confirm sell-all, upgrade `_missing`, and wiki render it.
