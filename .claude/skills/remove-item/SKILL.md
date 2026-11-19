---
name: remove-item
description: Cut, merge or rename Coconut Capitalist items (the reverse of add-item): config, every reference, star variants, a DB migration that converts or gifts players' stacks, sprites and Discord emoji. Use when asked to remove, cull, merge or rename items or materials.
---

# Remove or rename items

Removing/renaming item ids changes the registry shape: it lands on `master` FIRST and alone (CLAUDE.md landing rule).

1. List the ids. Each has generated star variants `<id>_s2`, `<id>_s3` that players may hold too.
2. Find every reference: `grep -rn "<id>" configs cococap tests scripts docs art/sprites art/mappings`. Replace or delete each (shop, drop
   tables, recipes, upgrade costs, ship parts, shipments, quests, wiki text), then delete the `[id]` table in `configs/items.toml`.
   A rename also renames the emoji (emoji name == id) and any `art/` mapping key.
3. Ask the owner what holders get (default: a small thank-you of a related item, not a 1:1 pile). Back up `data/cococap.db` into
   `data/backups/` first.
4. Migration: copy the shape of `migrations/versions/0010_cut_zone_materials.py` (IDS with star suffixes, GIFT per distinct kind, upsert into
   `user_items`, then DELETE). Number = highest in `migrations/versions/` + 1; `down_revision` = the previous one. A rename is an UPDATE of
   `item_id` (merge with the upsert if the new id may already exist). Tool instances and pets may hold ids too: check `cococap/db/tables.py`.
5. Art: delete the sprite and `art/out/<id>*`; remove Discord emoji with `scripts/upload_emojis.py --delete <name>` (dry run, then `--yes`).
6. Tests: drop the ids from any test list that enumerates a category. Run `python -m scripts.quick_tests` plus `tests/test_registry.py
   tests/test_item_features.py tests/test_db_migrations.py`, and ruff.
7. Fix the DESIGN.md and STATUS.md lines, then commit (say what players get).
