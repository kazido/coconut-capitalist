# Foraging materials: what the designer needs to come up with

Foraging is the thinnest skill for materials. The cull (commit 1a51fb4) removed the 18 species drops and golden pollen, so a forest has
almost nothing to find. With 14 forests (2 per area, see `areas-and-ship.md`) we need more things for foraging to drop and for other
systems to ask for. Placeholders will be used until these exist.

## What exists now (foraging items)
| id | rarity | notes |
|----|--------|-------|
| feather | 1 | |
| hardwood | 2 | starrable; used in ship parts, wedges, fuel |
| fine_bark | 3 | starrable |
| maple_leaf | 4 | starrable |
| aged_feather | 5 | |
| rotation_wedge, iron_wedge, gilded_wedge | 2 / 4 / 6 | crafted wedges (reroll a forest spot); not drops |
Trees have species (birch ... emberwood) but no signature drops now. Mastery/enchant/pet systems that care about foraging items: grep the item id.

## What we need: 9 new base materials, so every one of the 14 forests has something new
Stars (2/3-star versions of the same item) do NOT count as a new unlock, so we want a different material for (nearly) every forest. We have
5 (feather, hardwood, fine_bark, maple_leaf, aged_feather) and need 9 more. Roughly one new material becomes available per forest, by rarity:

| forests | area | rarity band | new materials needed (existing ones fill some) |
|---------|------|-------------|------------------------------------------------|
| 1-2 | Slime Hill | 1-2 | feather, hardwood exist; maybe 1 new |
| 3-4 | Twilight Desert | 2-3 | 2 new |
| 5-6 | Rust Belt | 3 | fine_bark exists; 1-2 new |
| 7-8 | Cadrega City | 3-4 | maple_leaf exists; 1-2 new |
| 9-10 | Aerial Glades | 4-5 | 1-2 new |
| 11-12 | Star Kingdom | 5-6 | aged_feather exists; 1-2 new |
| 13-14 | The Void | 6-7 | 2 new (the rare endgame woods) |

## For each one, give me
1. id, name, emoji (needs a unique emoji; the wiki/shop show a big art thumbnail of it)
2. rarity (1-7) and a one-line description + wiki text (where it drops, what it is for)
3. base sell price (compare: hardwood 5,500; fine_bark 36,000; maple_leaf 330,000; aged_feather 3,600,000 bits)
4. drop rate (1 in N per drop roll) and which forests it drops in (a range)
5. starrable? (yes by default)
6. A USE. An item nobody uses gets culled again. Candidates: ship parts or fuel (`configs/areas.toml`, `configs/recipes.toml`), a tool
   upgrade or fork (`items.toml` tool.upgrade), a pet food, a recipe at the Workbench, or a shipment crate filler.

## Optional: species signature drops
Species can have their own drops (`[[species]] drops = [{item, rate, min, max}]`, currently empty). Giving some species a signature item
is another way to vary forests (e.g. the palm of Oasis Palms drops one). Decide which species (if any) get one.

## When it is ready
Send the list (a table is fine). Adding items follows the `add-item` checklist (item entry, drop odds, wiki, test, DESIGN.md line).
