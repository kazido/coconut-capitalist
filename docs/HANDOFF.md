# Handoff: read this first in a new chat

Where the project stands and what is next. (`docs/ROADMAP.md` = architecture rules and long-term plan, `docs/DESIGN.md` = how each
system works and why, `docs/HOSTING.md` = going live notes, `scripts/balance.py` = prints what every skill pays.)
Keep this file current: update the "Open work" list at the end of every session.

## Setup

- Repo `kazido/coconut-capitalist`. Work happens in the worktree `/Users/ellalbrys/Coding/coconut-capitalist/.claude/worktrees/discord-bot-audit-modernize-4dd6c5`
  on branch `claude/discord-bot-audit-modernize-4dd6c5` (NOT pushed; never push or merge without being asked).
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

- **One branch only**: all work is on `claude/discord-bot-audit-modernize-4dd6c5` (this worktree; the bot runs from here). Never touch master or make other worktrees. The branch is ahead of GitHub; push only when asked.
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
  rarity words + ANSI colours in the inventory only (experiment: roll out only if the user likes it); tree species by zone; Releaf Foundation (Bloom); mine types; small wyrmholes (1 in 100 mines);
  crafting (Workbench under Inventory, `configs/recipes.toml`: battery, iron/gilded wedge, scarab bomb); fishing double hook (Double Hook enchant + Angler node) and the "Where does an effect belong?" rule in DESIGN.md.
  Numbers are sim-based guesses marked TODO(balance). Open from it: five pets/effects flagged as misplaced in DESIGN.md, Scholar's Cavern a little weak, small wyrmhole strong at low power.
- Dead code removed (exploration prototype, empty cogs, unused models/helpers). Wedges now leave a chop bonus, the burger is a pet feast, rare drops show banners (`cococap/ui/flair.py`), every item/enchant has an emoji, Sell all keeps upgrade materials by default.

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
