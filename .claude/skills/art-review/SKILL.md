---
name: art-review
description: Art review loop for Coconut Capitalist emoji/sprites. When the user asks to see, review, redo or redraw some items' art, build ONE labelled sheet of them (plus finished look-alikes for comparison), then iterate on their feedback with a new sheet. Use for any "show me the X art / redo the Y" request.
---

# Art review loop (keep tokens low)

Art work is done directly on `master` (no art branch). Python: the master venv (see CLAUDE.md Environment).

## 1. Show the current state (first pass)
1. One command, no exploring first: `python -m art.review <names or patterns> [--context N]`
   (e.g. `'tool_axe_*' tool_hatchet_*`; default 6 comparison sprites; `--context 0` for none).
   It rebuilds only the named sprites and writes `art/out/sheets/review.png`, targets on top, then "for comparison"
   (same category, hand-drawn first, closest in kind and rarity) so the user judges them in context.
2. `SendUserFile` the PNG (display `render`). Read it yourself with Read only ONCE, to catch glaring bugs (clipped pixels,
   stray cells). Do not Read it again after every tweak.
3. Say in one or two lines what the sprites currently are. No analysis, no options menu. Then wait for feedback.

## 2. Iterate on feedback
1. Find where each sprite lives: `Grep "^\[name\]" art/sprites art/wisps.toml art/mappings`. Hand-drawn = `art/sprites/*.toml`
   (palette letters + 16 `rows`, 16x16, plum outline `o` is drawn by hand). Raven mappings (`art/mappings/*.toml`) are
   third-party cells: to change one, draw a hand sprite with the SAME name in `art/sprites/` (it wins) and DELETE the
   superseded mapping line (the user wants no dead references).
2. Edit only the rows/palette that the feedback is about (Edit tool, small hunks). Never regenerate whole files.
3. Re-run step 1 with the same names. Send the sheet. Only add `--context 0` if the comparison row is no longer needed.
4. When the user zooms in on one sprite ("that one is off"), crop it big with PIL from `art/out/<name>.png`
   (nearest-neighbour x24) instead of resending the whole sheet.
5. Do NOT commit until the user says they are happy with that sprite ("done", "fine", "commit it"). Until then keep iterating
   and leave the changes uncommitted. When committing, stage only the accepted sprites (if a file also holds unaccepted work, commit
   the accepted blocks only). Message format: what changed and why. This overrides the generic commit-after-every-change rule in CLAUDE.md.

## Style rules and upload
All style rules (light, contrast, margins, no letters, ramps not hue shifts, gears, balance, tools) and the upload-in-passes steps live in
the `make-emoji` skill: read its "Style rules" and "Upload" sections before the first pass. Self-critique and redo weak icons before
sending any sheet.
