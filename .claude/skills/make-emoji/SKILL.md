---
name: make-emoji
description: Make a new emoji/icon for Coconut Capitalist (UI/action icons `ui_<name>`, items, locations, species...) in the art pipeline, to the owner's quality bar, and upload it. Use when asked to create, replace or redraw an icon. Holds ALL the art style rules.
---

# Make an emoji (art work happens on `master`; keep tokens low)

The LEAD draws art itself (the owner found Sonnet/Haiku art poor). Don't delegate drawing; delegate only the code routing.

## Where things live
- Grid 16x16, exported 64x64 by `python -m art.build [--only NAME]` -> `art/out/NAME.png`. Palette helpers: `art/palette.toml`; outline plum `#2e1c2c`.
- Hand/scripted sprites: `art/sprites/*.toml` (`palette = {letters}`, 16 `rows`, `kind = "free"`, `outline = true` = the build adds the plum outline).
  Raven pack cells: `art/mappings/raven*.toml` (pack is local only: unzip `art/downloaded/Free - Raven Fantasy Icons.zip` into git-ignored
  `art/vendor/` and point git-ignored `art/local.toml` `raven_dir` at it; NEVER commit pack images). A sprite with the same name beats a
  mapping: when you replace a mapped icon, DELETE its mapping line (no dead references).
- Names: UI `ui_<name>`, items = item id, locations `location_<id>`, species `species_<id>`, mine types `mine_<id>` (<=32 chars, unique
  across all files). Lookups: `cococap/emojis.py` (`icon/ui/get/Lazy/for_id`); models' `.emoji` already resolve by these names with a
  Unicode fallback. Custom emoji do NOT render in button/select labels: use `emoji=`.

## Source scripts for the approved sets (`art/gen/`)
Every icon drawn in Nov 2026 comes from a script here; edit the script, re-run it, never hand-edit its TOML:
`ui_icons.py` -> `art/sprites/ui_pages.toml` (run: `python art/gen/ui_icons.py art/sprites/ui_pages.toml`), `trees.py` -> `species.toml`,
`zones_<skill>.py <out.toml> art/gen` -> `locations_<skill>.toml`, `batch2.py art/gen` -> `ui_actions2.toml` (dig, combat, reactor:
the ANIMATED ones; copy its `emit(..., frames)` + `shift()`/`spark()` pattern to animate any other icon: 3-5 frames, 70-240 ms each).
Animated sprites build to `.webp`; delete the old `art/out/<name>.png` before uploading or the uploader marks the name INVALID.

## How to draw (what produced the approved sets)
1. Write a scratch script in the session scratchpad using `art/draw.py` (`Canvas`, `ell`, `circ`, `union`; `shade` = 4-tone ramp lit
   top-left). Shapes from math/explicit pixel lists, never freehand-typed rows. Write its `toml()` into `art/sprites/<file>.toml`.
2. Build + sheet: `python -m art.review <names...> --context 0` -> `art/out/sheets/review.png`. Read it ONCE yourself.
3. **Self-critique first:** redo every icon you think is weak (unclear silhouette, blobby, reads as something else) BEFORE sending.
   Zoom one icon with PIL (nearest x8) when unsure. Only then SendUserFile the sheet. List what each icon is in one line each.
4. Iterate on feedback (edit the script, rebuild). Commit a batch only when the owner approves it (see art-review).

## Style rules (owner insists)
- Light from the top-left, shadow bottom-right, 3-4 tone ramps per material; same outline weight and proportions across a set.
- Readable at 16px in dark mode: one clear silhouette, strong contrast between subject and background (e.g. a white cloud on a
  darker slate peak, blue water on green grass). Avoid same-hue-on-same-hue.
- Leave a 1px empty margin (the outline needs it). Don't let a shape touch the canvas edge or it gets clipped.
- No letters/text in icons (they blur into blobs once outlined). No tiny details that vanish (wisp eyes, 1px thin poles).
- Crescent moons: outer circle r~2.4-2.6 with an inner cut offset up-right by ~(1.1, -0.8), r ~0.5 smaller. Smaller cuts read as "L".
- Recolouring: use a 4-colour `ramp = [dark..light]` on a mapping, NOT a hue shift (hue shifts look unnatural, e.g. teal "sapphire").
- Gears: place teeth explicitly (cos-based teeth quantise into blobs) and give the hub a dark hole.
- Balance: in crossed/paired designs keep both heads at the same height (a double-bit axe balanced the pickaxe).
- Tools: 1px diagonal handle bottom-left to top-right, head at the top, head <= 1/3 of the handle; better tiers differ by SHAPE, not size.
- Colour tells the theme (Elderwood = bark + amber glow). Keep the owner's palette when they like it. Pasted reference images are the style
  target: match silhouette first, then recolour.
- Item art (framed): ~10px sprite centred in the rarity cell, 5-6 hue-shifted shades, one white specular pixel.

## Upload (in passes, after each approved batch; the owner said so)
`.env` is in the master checkout; load it without printing: `set -a; . ./.env; set +a`. Then
`python scripts/upload_emojis.py --only <prefix>` (dry run) -> add `--yes`. Changed existing art: `--replace <name>` (repeatable).
`art/out/` also holds stale/unrelated files (cut items, previews), so ALWAYS filter with `--only` (one prefix per run); delete stale
`art/out` files of names you renamed. Tell the owner to restart the bot. Never push.

## Checks
`python -m pytest -q tests/test_art.py tests/test_glyphs.py tests/test_emojis.py`; ruff clean.
