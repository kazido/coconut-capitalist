# Item art: rarity outline instead of rarity frames
Status: approved by owner 2026-11-19; building.

Every framed item emoji is rebuilt without its rarity cell:
- Strip the sprite's own baked-in dark edge (edge pixels that touch transparency and are near-black).
- Put it on a **20x20** grid (2px margin, so nothing clips), exported at **x6 = 120px** (Discord max 128).
- Ring 1 (inner): **sprite-dark**, each pixel a darkened version of the sprite colour it touches (4-neighbour, no corners).
- Ring 2 (outer): the **rarity colour** (4-neighbour). Two-tone rarities (`color2` in art/palette.toml, Celestial) run a
  diagonal gradient from color (top-left) to color2 (bottom-right).
- Animation by rarity (art only; still frames for the rest):
  - 1-3 Common, Uncommon, Rare: static.
  - 4-5 Super Rare, Legendary: **wave**, a slow hue + brightness ripple running around the rarity ring.
  - 6-7 Mythical, Premium: wave + **gleam**, a white diagonal glint sweeping across, then a pause (about one gleam every 3 s).
  - 8 Celestial: wave + gleam + **sparkles**, a few twinkling star pixels around the item.
- Sprites that are already animated (e.g. crop_ambrosia) keep their own frames; the outline + effects are applied to every frame.
- Free sprites (UI icons, locations, species, tools drawn free) are NOT changed.
- Reference scripts used for the owner's previews: scratchpad `outline_variants.py`, `anim_preview.py`, `rarity_examples.py`.
- Roll-out: build, owner reviews a sheet, then upload in passes with `scripts/upload_emojis.py --replace` (animated ones become .webp;
  delete the old .png of the same name first).
