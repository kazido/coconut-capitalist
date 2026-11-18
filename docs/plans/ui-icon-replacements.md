# UI icons that borrow item art (replace with their own `ui_*` emoji)

Status: audit done; icons not drawn yet (art branch). Delete this file when all rows are done and merged.

Rule: an item's emoji appears only where the ITEM itself is meant. Actions/labels get their own `ui_<name>`.
Mechanism today: `ITEM_ICONS` (name -> item id) and `SKILL_ICONS` in `cococap/emojis.py`.

| Icon (new name) | Now borrows | Where it is used as an action/label |
|---|---|---|
| `ui_chop` (axe swing) | tool_axe_starter (`icon("axe")`) | forage.py: Chop button, swing result, "Axe power"; tool_effects.py axe blurb |
| `ui_dig` (pick strike) | tool_pickaxe_rookie (`icon("pickaxe")`) | mine.py Dig, mining.py Enter the mines, reactor.py Dig/Back, stats_mining.py page icon |
| `ui_grain` (wood grain lines) | material_hardwood (`icon("wood")`) | forage.py spot headline/"spot wore out"/"A tree of your own" |
| `ui_wedge` | material_iron_wedge | forage.py wedge buttons (hold the ITEM name too; icon = action) |
| `ui_wedge_gold` | material_gilded_wedge | forage.py wedge bonus/drive notes |
| `ui_leaf` | material_maple_leaf | forage.py "tree fell", "Shook loose" notes |
| `ui_skill_mining/fishing/foraging/farming` | starter tool per skill (`SKILL_ICONS`, `emojis.skill`) | skills, profile, mastery, shipments, shop, wiki, levelup, pets, bestiary, radar, reactor, fish |
| `ui_battery` | material_radar_battery | no screen use found (glyphs.py only): drop from ITEM_ICONS |
| worm (`icon("worm")`) | bait_worm | fish.py "Loaded N bait": that IS the item/bait; keep |
| can/rod (`icon("rod"/"can")`) | tools | no direct action use found; covered by skill icons |
