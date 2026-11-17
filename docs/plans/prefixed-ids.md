# Plan: prefixed, consistent ids (items + pets), emoji name == id

Goal: every item id is `<category prefix>_<name>`, and the emoji name is exactly the id (no alias layer). Pets get ids that match
what they are now (the flame wisps: Cinder, Drizzle, ...), not `dog`/`cat`.

## Scheme

| category | prefix | example |
|---|---|---|
| tool | `tool_` | `rookiepickaxe` -> `tool_pickaxe_rookie`, `starter_rod` -> `tool_rod_starter` |
| material | `material_` | `coral_shard` -> `material_coral_shard` |
| fish | `fish_` | `oarfish` -> `fish_oarfish` |
| crop / seed | `crop_` / `seed_` | `apple` -> `crop_apple`, `apple_seed` -> `seed_apple` |
| bait | `bait_` | `worm` -> `bait_worm` |
| pet_food | `food_` | `burger` -> `food_burger` |
| key_item | `key_` | `graveyard_key` -> `key_graveyard`, `balance_gemstone` -> `key_gemstone_balance` |
| scroll | `scroll_` | already prefixed, unchanged |
| pet_item | unchanged | already `spirit_of_*` |
| pets | `pet_`?? no: pet ids become the wisp name (`dog` -> `cinder`); emoji kind `pet_<id>` already prefixes them |

Discord caps names at 32 chars: the map builder fails loudly on any longer name. Pickaxes/rods/axes/cans get `tool_<kind>_<tier>`
so a suffix/prefix filter (`--only tool_pickaxe_`) works.

## Steps

1. `scripts/rename_ids.py` (new, dry-run by default): builds the old->new map from the registry (category rules above, plus an
   exceptions table), writes it to `art/rename_map.toml` for the user to eyeball and edit BEFORE anything is applied. Checks: no
   collisions, <= 32 chars, `NAME_RE`.
2. Same script `--apply` rewrites, as quoted TOML/Python strings and table headers (`[old]`, `[old.drop]`, `"old"`), the ids in
   `configs/*.toml`, `art/sprites/*.toml`, `art/mappings/*.toml`, `cococap/**/*.py`, `tests/**/*.py`, `docs/*.md`. Only whole-word
   quoted matches (never bare-substring), longest id first. Ids that are also plain words (`apple`, `worm`, `burger`) are the risk: the
   script reports every changed line count per file and the tests catch strays.
3. Alembic `0009_prefixed_ids.py` (hard-codes the map, like 0008 hard-codes prices): rewrites `user_items.item_id`,
   `tool_instances.template_id`, and every quoted old id in the JSON text columns (`users.settings/pethouse`, skill `data`, drops,
   community state) with an exact-match `"old"` -> `"new"` replace. Pets: pethouse keys + active pet. Back up `data/cococap.db`
   first (CLAUDE.md rule). Downgrade = inverse map.
4. Drop `ALIASES` / `_ITEM_ALIAS` / `LEGACY` handling in `cococap/emojis.py`; `name_for("item", id)` stays `id`. Update
   `art/build.py` output names (sprite names come from the same ids). Rebuild all art.
5. Emoji catalog on Discord: after the code lands, the user deletes the old emoji, then
   `upload_emojis.py --replace-all --yes` (new names simply upload as missing). `--only-suffix` becomes less needed; keep it.
6. Tests: `test_db_migrations.py` plus a new migration test that seeds old ids in every touched column and checks the new ones;
   run the full suite once (large refactor, per CLAUDE.md), ruff, `scripts.balance` unchanged numbers.
7. Docs: DESIGN.md (ids, emoji names), HANDOFF "Latest state", the item checklist in CLAUDE.md ("new item ids use the prefix").

## Risks / decisions to confirm
- Live DB has real players' items: migration must be exact and tested on a COPY of `data/cococap.db` first.
- Any id I miss in JSON blobs would orphan that item: step 3 includes a post-check that no old id remains anywhere in the DB text.
- Commit in one change only after the full suite passes; nothing pushed.
