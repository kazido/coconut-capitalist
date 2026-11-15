---
name: add-item
description: Add a new item (material, tool, scroll, pet food, seed...) to Coconut Capitalist the data-driven way, with emoji, wiki text, drop odds, a test and a DESIGN.md line. Use when asked to add or change an item.
---

# Add an item

1. Read `CLAUDE.md` (data model facts) and look at one existing item of the same category in `configs/items.toml` to copy its shape.
2. Add the `[id]` table: `name, description, wiki` (what it does in plain words, with numbers), `emoji` (required: pick any placeholder),
   `rarity` (1-7), `skill`, `category`, `price`, `sell_price`. Add sub-tables only if needed: `.drop` (`rate` = 1 in N per drop roll),
   `.tool`, `.scroll`, `.pet_food`, `.crop`, `.seed`. Mark guessed numbers `# TODO(balance)`.
3. Wire it in: shop list, craft/upgrade chain (`[x.tool.upgrade]`/`.fork` items), drop table in `configs/drops.toml`, or a config that
   names it (e.g. a wedge in `configs/foraging.toml`). An item nothing refers to and nothing drops is dead data.
4. If it has an effect, put the effect in a `services/` module reading a registry value, not a hard-coded number.
5. If it is rare (rarity 4+ and 1-in-100 or rarer) the drop banner in `cococap/ui/flair.py` applies automatically.
6. Tests: add one that checks the behaviour using numbers read from the registry; update any list that enumerates the category
   (e.g. `FOODS`/`FEASTS` in `tests/test_pets.py`). Run just the touched test files plus `tests/test_registry.py` and `tests/test_item_features.py`.
7. Add a line to the matching `docs/DESIGN.md` section, then commit.
