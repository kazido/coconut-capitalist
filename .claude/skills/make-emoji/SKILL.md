---
name: make-emoji
description: Make a new emoji/icon for Coconut Capitalist (UI/action icons `ui_<name>`, items) in the art pipeline, to the quality bar. Use when asked to create or replace an icon.
---

# Make an emoji (art branch only; keep tokens low: Grep, read line ranges)

- Grid: 16x16, exported 64x64 (`python -m art.build --only NAME`; `art/out/NAME.png`). Palette colours: `art/palette.toml`; outline plum `#2e1c2c`.
- Names: UI/action icons `ui_<name>`; item emoji = item id (<=32 chars). An item's emoji is used ONLY where the item itself is meant.
- Two routes: (1) Raven pack (local only, `art/vendor/`, NEVER commit): `art/mappings/raven*.toml` line `ui_x = {cell=[col,row], framed=false}` (+ `hue/sat/val/ramp` recolour);
  (2) hand/procedural: block in `art/sprites/ui*.toml` (`palette = {letters}`, 16 `rows`); a sprite with the same name beats a mapping, delete the superseded mapping line.
- Route in code: `cococap/emojis.py` (`icon("name", glyph)` -> `ui_name`; remove from `ITEM_ICONS`). Custom emoji do NOT render in button labels/selects; use `emoji=`.
- Checks: `python -m scripts.quick_tests`, ruff clean. `tests/test_glyphs.py` / `test_emojis.py` enforce names and fallbacks.
- Review: build one labelled sheet (art-review skill), show the owner, commit sprites ONLY after they approve. Upload to Discord only when told. Never push.

## Quality bar (owner insists)
Consistent light direction (top-left light, bottom-right shadow) with 3-4 tone ramps; same outline weight and proportions across a set;
straight lines and circles drawn from exact pixel patterns (generate rows with a script, never freehand wobble); readable at 16px and in dark mode.
