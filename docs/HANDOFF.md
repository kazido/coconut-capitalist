# Handoff: read this first in a new chat

Where the project stands and what is next. (`docs/ROADMAP.md` = architecture rules and long-term plan, `docs/DESIGN.md` = how each
system works and why, `docs/HOSTING.md` = going live notes, `scripts/balance.py` = prints what every skill pays.)
Keep this file current: update the "Open work" list at the end of every session.

## Setup

- Repo `kazido/coconut-capitalist`. Work happens on `master` in the main checkout (the old audit branch/worktree was deleted). Never push or merge without being asked.
- Python 3.12 in `.venv`. **Read `CLAUDE.md` first** (rules, architecture, checklists). Tests: `.venv/bin/python -m pytest -q [file]` (full suite ~55 s, ~1580 tests, all green). Lint: `.venv/bin/ruff check .`.
- discord.py 2.7 Components V2 hub (`cococap/ui/nav.py`: `Navigator`, `Screen`, `Page`, `Result`). Game rules live in `cococap/services/*`
  (no Discord objects), data in `configs/*.toml` (validated by `cococap/registry/models.py`). SQLite + Alembic (migrations 0001-0004).
- The live-ish database is `data/cococap.db` (gitignored; 4 players: bry, Ahna, zennor, one more). Backups in `data/backups/`.
  Back it up before touching it. `data/cococap.db` is meant to become THE live database.

## How we work (preferences)

- **Commit after every commit-worthy change without asking** (detailed history is wanted). **Never push** unless asked.
- Design discussion before big features; less screen clutter; mining rework comes LAST; combat after pets; party-focused versions
  of every skill eventually.
- Test everything (mutation-check the important rules: break the code on purpose and see a test fail). Update tests, never delete
  them without a replacement. Use Python string replace for scripted edits (BSD `sed -i` silently fails).
- The user edits configs by hand; commit those edits when asked and make tests read numbers from the registry. Tests pin a few economy values in `tests/conftest.py`.
- **Secrets**: the user once shared a MongoDB login. It was rejected ("bad auth") and is NOT stored anywhere. Never write
  credentials into files, docs or commits. The old-player migration (copy only rank + tokens; give pet owners one basic pet; leave
  bits and everything else fresh; restore bry's and zennor's old rank, both were Weathered = rank 6) is waiting on a working login.

## What is built (all committed)

Mining (descent, wyrmholes, reactor, magnet), farming (plots, hourly rain, water, market, crop time estimate, 10 crops),
foraging (20 zones, stance patterns + grain notes, community tree scaled by recent crowd, party trees, the Releaf Foundation (server-wide meter,
temporary Bloom)), fishing (cast/reel/❓ tells, field notes page, quests, books, community goals, bosses, records, crab pots, 8 waters... see
config), pets (orbs, stars, hunting a target, skill food drops in 3 tiers, pet skills), ranks 0-15 with +1% xp per rank, party idle
kick (24 h), wiki (topics + item lookup with where-to-catch for fish), tools with 8 levels for axe/pickaxe/rod.

## Recently decided numbers (tune in configs)

- Zones: `zone_levels` in `configs/foraging.toml` (zone 20 = level 136). Community tree: hp = typical tree x 5 x recent choppers.
- Tool income target per level: x1, 1.5, 2.6, 4, 6, 9, 13, 18. Axe power 3..54, pickaxe 1..69 (+25% ore per power), rod 3..120
  (faster bites, rarer fish, extra fish). Each upgrade costs ~5x the last.
- Pet food xp 200 / 1,000 / 5,000 by tier; a pet has ONE fixed skill (`skill` in pets.toml, emoji after its name; 🌐 global = Dog, Koala,
  Phoenix): its own skill's food x3, a global pet x2 from any food.

## Latest state (read this before the list below)

- **One branch only: `master`** (the audit branch was deleted; the bot runs from the main checkout). Push only when asked (`git push origin master`). The old pre-AI code is preserved on `history/pre-ai`.
- Done since the list below was written: shipments by skill (basic at level 10, hard at 30; community off), trading (shared window, both Accept), settings (keep upgrade
  materials, confirm upgrades, fishing estimate), combat PAUSED (button disabled, `/fight` says so; code and tests kept), tool lines (3 plain upgrades then the split at the
  4th: axe = Lumberjack/Forager, can = Sprinkler/Alchemist), mastery trees for mining/fishing/foraging/farming with a tuned capstone per branch, the fishing radar, Home
  layout (superseded: see the `ideas` effort below). See DESIGN.md sections of the same names.
- Numbers still to tune by play: axe/can road stats, shipment sizes, radar costs, capstones for fishing/foraging/farming are estimates (mining's are simulated).
- The user's config edits are now COMMITTED (balance numbers in `configs/economy|farming|foraging|mining.toml`). Personal, unshared tuning goes in the git-ignored `configs/local/<name>.toml` overlay (see CLAUDE.md). The full suite is green.
- Workflow decisions: do not run the full suite after every change (only on request or a reported break); use plan mode for big features; project skills in `.claude/skills/` (add-item, balance-check, finish-feature); optional `scripts/pre-commit` runs ruff.
- **The `ideas` file effort (all committed, not pushed; restart the bot to see it)**: daily Farmer's Market window; one-item shake and grain-based Windfall; community tree pool scales with choppers;
  Leave-button pages hide Home/Back; new Home (Skills, Shipments, Shop, Inventory, Pets, Check-in as sections, one row of Profile/Ranks/Leaderboards/Party/More; Trade lives under More);
  expired menus delete themselves; one shared rewards screen (`cococap/ui/rewards.py`) with a page per rare drop and its drop rate (`services/odds.py`); shop sells no tools (free starter
  tools claimed on first /play); orb buying on the orbs page and three orb tiers; per-rarity pet leveling (levels preserved by `Pethouse.curve_version`); pets Magpie/Mole/Fox/Bee/Raven;
  (the inventory colour experiment was reverted); tree species by zone; Releaf Foundation (Bloom); mine types; small wyrmholes (1 in 100 mines);
  crafting (Workbench under Inventory, `configs/recipes.toml`: battery, iron/gilded wedge, scarab bomb); fishing double hook (Double Hook enchant + Angler node) and the "Where does an effect belong?" rule in DESIGN.md.
  Numbers are sim-based guesses marked TODO(balance). Open from it: five pets/effects flagged as misplaced in DESIGN.md, Scholar's Cavern a little weak, small wyrmhole strong at low power.
- **Emoji art overhaul (in progress)**: all art is 16x16, exported 64x64; items sit in the owner's stone cell recoloured by rarity (palette in `art/palette.toml`, same 7 colours as `Rarities`), pets/UI are frameless. `python -m art.build [--sheets]` builds `art/out/`; the owner's own emoji are extracted to `art/sources/` (spirits and autominer are NOT on a 16x16 grid: left as they are). Third-party packs (Raven Fantasy Icons, JOI3) are local only and never committed; the owner has the Raven author's OK for this personal bot. Next: Raven item mapping (`art/mappings/raven.toml`), flame wisps for pets (slim flames with skull/core faces, no outline; stars are paused), item batches, then the upload. Starred materials (3 star tiers) are a later plan.
- **Pet wisps (built, not uploaded)**: all 25 pets are now flame wisps with new display names (ids in the DB stay the animal ids: dog = Cinder, cat = Drizzle, ... see `art/wisps.toml` `pet_<id>` entries and `configs/pets.toml`). Hue = skill theme, saturation = rarity, globals are white/grey/black; `art/flame.py` has 10 faces (core, skull, eyes, fang, cyclops, visor, sleepy, horned, grin, slim) and an optional `accent` for a dual-toned tip. The `emoji` field in pets.toml is still the old animal unicode (fallback only). Next: upload (`scripts/upload_emojis.py`, dry run then `--yes`), restart, then enchant/UI emoji art.
- Custom emoji by name: upload `art/out/` with `scripts/upload_emojis.py` (dry run, then `--yes`), restart; screens pick up `<item_id>`, `pet_<id>`, `species_<id>`, `enchant_<id>`, `mine_<id>`, `water_<id>`, `rank_<id>` emoji automatically (DESIGN.md "Custom emoji at runtime").
- Dead code removed (exploration prototype, empty cogs, unused models/helpers). Wedges now leave a chop bonus, the burger is a pet feast, rare drops show banners (`cococap/ui/flair.py`), every item/enchant has an emoji, Sell all keeps upgrade materials by default.

## Moving machines (2026-11-16: the owner moved from the Mac to a PC for good)

Git carries the code, configs, art sources and docs. It does NOT carry these; copy them by hand if you need them:
- `.env` (BOT_TOKEN; use the token of the SAME Discord application the bot runs as: emoji belong to one application).
- `data/cococap.db` (the player database; back it up first) and `data/backups/`.
- `configs/local/*.toml` (the owner's private balance tuning, git-ignored).
- `art/out/` (built emoji; zip made with `cd art/out && zip -r ../emoji-out.zip . -x "sheets/*"`), `art/local.toml` and `art/vendor/` (the Raven Fantasy Icons pack and an atlas of it,
  local only because of its license; without them `python -m art.build` skips the ~110 Raven-mapped items).
- the owner's untracked `ideas` notes file (its open items are copied into "Open work" below).

Emoji upload state: the new art (restyled owner emoji under item ids, 63 hand-drawn redraws, shine for rarity 6-7) is built but may not be uploaded. On the new machine:
`.venv\Scripts\python scripts\upload_emojis.py --replace-all` (dry run) then `--yes`, restart the bot; then delete the 10 old emoji by hand
(gemstone_balance/implosion/oreo/peace/rage/sanity, ore_copper/gold/iron, seed_weathered) once the new ones look right.

Workflow: Claude (lead) plans and delegates to the subagents in `.claude/agents/`; `scripts/verify.sh` is the done-gate.

## Open work (in rough priority)

1. DONE this session: tool levels checked (balance table), pet skills fixed + emoji, rank prices + random tokens (35%/active hour),
   one-click tool purchase, bank scrapped (daily interest on the purse; migrations 0005 and 0006). Not yet in the live bot: restart needed.
   Possible follow-ups: a pet bonus for tokens, a "you found a token" channel ping, rank xp buff shown on Home.
2. Migrate old players from MongoDB (needs a working login) and restore ranks; then make `data/cococap.db` live, split a dev DB.
3. Hosting (VPS + backups + GitHub Action deploy): notes in `docs/HOSTING.md`, nothing built.
4. Releaf Foundation rebuilt as a server-wide Bloom (DESIGN.md); the old growth mode is dropped. Tune `[releaf]` numbers by play.
5. Late-game "advanced" content for every skill, locked behind high levels (user wants ideas kept in mind, built later).
6. **Combat in progress** (branch `claude/combat-item-drops-566935`, built on top of the audit branch): the battle engine and `/fight`
   are done (see DESIGN.md "Combat"). The final boss (Gravewarden: phases, telegraph, stun-immune, Brace counterplay) is built too. Enemy drops (weighted tables, bits or any item, `configs/drops.toml`) and the Graveyard Key that opens the boss are built too. Next: channel drops
   rolling the same tables (`exts/economy/drops.py` is still the old Mongo code), combat tiers for levels 20-90, balance, party fights. Done since: the xp audit (tools never change xp: foraging pays per chop quality, fishing per catch by water, farming by
   growth time; migration 0007) and the Bestiary (the Coconut Level was added and then removed; DESIGN.md). Foraging was reworked (one chop style per grain, spot wear, rotation wedges, Seasoned enchant; see DESIGN.md) and the Bestiary now holds fish and sea bosses. Party invites show on the Party page; special foraging spots and wedges drop; **Mastery trees and tool forks are built for mining and fishing** (DESIGN.md). Next: balance them (the roads should earn within ~10%), roll out to foraging/farming, level 5/10 unlocks, then combat tiers for levels 20-90 and more point sources
   (collection books, achievements as new skills/features arrive). Then: mining rework (last), party versions
   of each skill.
7. Foraging tree events, channel drops / megadrop, Familiar Orb sources, and a "you were removed from your party" notice.
8. **Open items from the owner's `ideas` file (Batch 2, each needs its own plan first):** DONE (plan `docs/plans/batch2-thumbnails-and-shop-list.md`): shop buy/sell is a list + dropdown + one button; wiki item page has a big thumbnail (`emojis.image_url`, CDN picture; check how it looks live). Still to do from that plan: thumbnails on reward and rare-drop screens;
   live screen refresh for shared events (party joins, trade invites, falling trees; opening a new play menu closes the old one); the fishing rework (a sinking-hook minigame
   instead of the arrow reel: decide whether the arrow game stays, what bosses, rods and enchants then do); markdown/spoiler/radio-modal ideas; thumbnails (big art) on the
   reward, rare-drop, item and shop screens because inline emoji are small; starred materials (3 star tiers, needed for upgrades; stars on the art are paused until they can be
   drawn small without covering the sprite); the flame wisps as pets (the generator and 8 approved examples ARE in the repo now: `art/flame.py`, `art/wisps.toml`, built as animated `flame_*` emoji; still to do: decide which wisp each of the 25 pets gets, name them `pet_<id>`, and add rarity-tied variety) and art for
   species, enchants, UI icons, mine types. Weak art still worth redoing: sardine vs herring (same fish), rods look alike by tier, geode/worldsplitter pickaxes, weeping pearl, silver catkin.
