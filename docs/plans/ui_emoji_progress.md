# UI emoji work: what is still open (art)

Art rules and the upload steps: `.claude/skills/make-emoji/SKILL.md`.
Routing code and the glyph sweep (`cococap/glyphs.py`, `tests/test_glyphs.py`) are built; new glyphs/icons need art in `art/mappings/raven_magic.toml` or `art/sprites/ui_glyphs.toml`.

- All 56 location icons, 9 species and 7 mine types are drawn and uploaded. Ship tier icons (`ship_<slug>`) are not drawn.
- `art/out/` holds stale files from cut items/previews: always upload with `--only <prefix>`.
- Further items: `docs/plans/2026-11-19-tomorrow.md` (Art section).
