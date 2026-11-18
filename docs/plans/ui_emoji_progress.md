# UI emoji work: what is still open (art)

**Rules from the user:** commit an art sprite only after they say they like it; upload to Discord only when they say so (restart the bot after); never push.
Routing code and the glyph sweep (`cococap/glyphs.py`, `tests/test_glyphs.py`) are built; new glyphs/icons need art in `art/mappings/raven_magic.toml` or `art/sprites/ui_glyphs.toml`.

- 56 location icons (`location_<id>`): waiting on the user's choice (tinted skill icons vs one icon each). Ship tier icons (`ship_<slug>`) are not drawn.
- Unsure if everything built is uploaded: dry-run `scripts/upload_emojis.py`, then `--yes` and restart when the user says.
- Further items: `docs/plans/2026-11-19-tomorrow.md` (Art section).
