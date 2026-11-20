---
paths:
  - "configs/**"
  - "cococap/services/**"
  - "cococap/registry/**"
  - "cococap/models/**"
  - "tests/**"
---

# Data model facts

- **Items** (`configs/items.toml`): `[id]` table with `name, description, wiki, emoji, rarity (1-7), skill, category, price, sell_price`
  and optional sub-tables: `.drop {rate, min, max}` (1-in-rate per drop roll), `.tool` (power, `upgrade` and `fork` chains, `path`, `ability`,
  `stats`), `.scroll {enchant}`, `.pet_food {tier, xp_mult}`, `.crop`, `.seed`, `.bait`. Categories: material, tool, key_item, pet_item,
  pet_food, crop, seed, fish, scroll, bait. Every item and enchant needs an `emoji` (a test enforces it). New items: use the `add-item` skill.
- **Tools** are unique instances matched to a template id. Chain: 3 plain upgrades, the 4th upgrade is a FORK into two paths
  (pickaxe Warden/Prospector, rod Angler/Treasure Hunter, axe Lumberjack/Forager, can Sprinkler/Alchemist). `configs/tools.toml` has the
  per-kind power curves; `services/tool_effects.py` turns path/ability into engine effects. Every tool starts at power 3.
- **Enchants** (`configs/enchants.toml`) are effects on a tool instance, applied with scrolls. **Mastery** (`configs/mastery.toml`): 4 trees x 3
  branches x 5 nodes; nodes are plain stat names merged into `equipment.equipped_stats`; level-50 capstones are stat flags read by engines
  (Lifeline, Gold Rush, Hot Streak, Salvage, Windfall, ...). Capstones in a skill are tuned to be equally strong (guard tests).
- **Foraging wedges** (`[[rotate.wedges]]` in `configs/foraging.toml`): reroll the spot AND leave a `boost`/`boost_chops` bonus on the `Spot`.
- **Shipments** (`configs/shipments.toml`, `services/shipments.py`): per-skill basic (unlock lvl 10) and hard (lvl 30) crates; the community
  shipment is scrapped (`community.enabled = false`, code kept). State lives in `services/community.py` (`read`/`update`).
- **Trading** (`services/trade.py`): in-memory invites and windows, both players Accept, version-guarded, all-or-nothing completion.
- **Selling**: one item at a time in the Shop (`screens/shop.py`, Sell mode: 1x / 10x / custom). Skill pages have no bulk sell button.
- **Rare-drop banners**: `cococap/ui/flair.py` (level 1 = rarity 4+ and 1-in-100 or rarer; level 2 = rarity 5+ or 1-in-700+). Call
  `flair.banner(drops)` wherever a screen lists drops.
- Fishing radar, mastery, shipments, trading all have DESIGN.md sections: before changing them, `Grep -n "^#" docs/DESIGN.md` for headers,
  then Read only that section (offset/limit).

**A new rule/system**: service module (no discord) + registry model + config TOML + screen + tests + DESIGN.md section + STATUS.md line.
