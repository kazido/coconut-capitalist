# UI emoji work: where we are (art branch)

**Rules from the user:** commit an art sprite only after they say they like it (routing code may be committed); upload to Discord only when they say so
(the bot loads emoji at startup, so restart after); never push; merging `art` to master needs the full tests + ruff + their yes.

**Done and routed (code committed on `art`):** currencies (`emojis.currency/bits/tokens/luckbucks`, text pattern "<n> <icon> bits"), skills (`emojis.skill`),
areas/ship tiers/locations kinds (`area_`, `ship_`, `location_` in `emojis.KINDS`), stars (`emojis.stars`), action icons (`emojis.icon`, item-art reuse via
`ITEM_ICONS`), level-up notification (`ui/levelup.py`, hooked in `Navigator._respond`), chest + hook, fishing/radar and foraging screens.
Audit list: `docs/plans/ui_emoji_audit.md`. Art mappings: `art/mappings/raven_magic.toml` (ui_/area_ bare icons use `framed = false`), `art/sprites/ui.toml`.

**Uploaded to Discord:** everything up to ui_star/ui_chest/ui_hook etc. NOT yet uploaded: `ui_tree`. Not uploaded on purpose: `flame_*`, `preview_*`.

**Still to do:**
1. Mining screens (mine.py, mining.py, reactor.py, wyrmhole.py), then farming (farm.py, market.py), then the rest of the audit (pets, shop, inventory, tools, craft...).
2. 56 location icons (`location_<id>`): waiting on the user's choice (tinted skill icons vs one icon each). Ship tier icons (`ship_<slug>`) not drawn.
3. Uncommitted art awaiting the user's OK: new crops/seeds, redone clover, area icons, chest, hook, star, the action icons.
4. MERGE: master only has the early art merge (currency/skill icons). Skills menu + fishing/foraging icons need `art` merged into master (full tests first).

## Glyph sweep (art branch): NO plain unicode emoji anywhere
`cococap/glyphs.py` maps every glyph the code writes (about 300 distinct, screens/cogs/configs) to an icon, and `glyphs.install()` (called in
`bot.py` after `emojis.refresh`) swaps them for the custom emoji on the way to Discord (HTTP layer: message text, embeds, button/select emoji;
a label's leading glyph moves into the component's emoji field, other glyphs are dropped where custom emoji cannot render). A glyph whose icon is
not uploaded stays plain. `tests/test_glyphs.py` fails on an unmapped glyph or an icon name without art. New art: Raven cells in
`art/mappings/raven_magic.toml` ("Glyph replacements"), hand drawn in `art/sprites/ui_glyphs.toml` (check, cross, crown, lock, timer, suits, dice,
board squares/dots...), 17 `enchant_*` icons. To see it: build, upload `ui_` + `enchant_`, restart the bot.
