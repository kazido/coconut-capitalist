# Handoff: read this first in a new chat

Where the project stands and what is next. (`docs/ROADMAP.md` = architecture rules and long-term plan, `docs/DESIGN.md` = how each
system works and why, `docs/HOSTING.md` = going live notes, `scripts/balance.py` = prints what every skill pays.)
Keep this file current: update the "Open work" list at the end of every session.

## Setup

- Repo `kazido/coconut-capitalist`. Work happens in the worktree `/Users/ellalbrys/Coding/coconut-capitalist/.claude/worktrees/discord-bot-audit-modernize-4dd6c5`
  on branch `claude/discord-bot-audit-modernize-4dd6c5` (NOT pushed; never push or merge without being asked).
- Python 3.12 in `.venv`. Tests: `perl -e 'alarm 300; exec @ARGV' .venv/bin/python -m pytest -q` (about 25 s, ~1125 tests). Lint: `uvx ruff@0.8.6 check .`.
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
- The user edits configs by hand and sometimes leaves them uncommitted (`configs/economy.toml`: idle limit 0.1h, starting
  luckbucks 0, weekly 25; `configs/mining.toml`: an extra CAUTION warning). Do NOT revert or commit those; tests pin the economy
  values in `tests/conftest.py` so tuning never breaks them.
- **Secrets**: the user once shared a MongoDB login. It was rejected ("bad auth") and is NOT stored anywhere. Never write
  credentials into files, docs or commits. The old-player migration (copy only rank + tokens; give pet owners one basic pet; leave
  bits and everything else fresh; restore bry's and zennor's old rank, both were Weathered = rank 6) is waiting on a working login.

## What is built (all committed)

Mining (descent, wyrmholes, reactor, magnet), farming (plots, hourly rain, water, market, crop time estimate, 10 crops),
foraging (20 zones, stance patterns + grain notes, community tree scaled by recent crowd, party trees, Re-leaf donations + double
tree), fishing (cast/reel/❓ tells, field notes page, quests, books, community goals, bosses, records, crab pots, 8 waters... see
config), pets (orbs, stars, hunting a target, skill food drops in 3 tiers, pet skills), ranks 0-15 with +1% xp per rank, party idle
kick (24 h), wiki (topics + item lookup with where-to-catch for fish), tools with 8 levels for axe/pickaxe/rod.

## Recently decided numbers (tune in configs)

- Zones: `zone_levels` in `configs/foraging.toml` (zone 20 = level 136). Community tree: hp = typical tree x 5 x recent choppers.
- Tool income target per level: x1, 1.5, 2.6, 4, 6, 9, 13, 18. Axe power 3..54, pickaxe 1..69 (+25% ore per power), rod 3..120
  (faster bites, rarer fish, extra fish). Each upgrade costs ~5x the last.
- Pet food xp 200 / 1,000 / 5,000 by tier; a pet has ONE fixed skill (`skill` in pets.toml, emoji after its name; 🌐 global = Dog, Koala,
  Phoenix): its own skill's food x3, a global pet x2 from any food.

## Open work (in rough priority)

1. DONE this session: tool levels checked (balance table), pet skills fixed + emoji, rank prices + random tokens (35%/active hour),
   one-click tool purchase, bank scrapped (daily interest on the purse; migrations 0005 and 0006). Not yet in the live bot: restart needed.
   Possible follow-ups: a pet bonus for tokens, a "you found a token" channel ping, rank xp buff shown on Home.
2. Migrate old players from MongoDB (needs a working login) and restore ranks; then make `data/cococap.db` live, split a dev DB.
3. Hosting (VPS + backups + GitHub Action deploy): notes in `docs/HOSTING.md`, nothing built.
4. Growth mode for Re-leaf (420 donations): the wiki gives no mechanics, needs the user's design.
5. Late-game "advanced" content for every skill, locked behind high levels (user wants ideas kept in mind, built later).
6. **Combat in progress** (branch `claude/combat-item-drops-566935`, built on top of the audit branch): the battle engine and `/fight`
   are done (see DESIGN.md "Combat"). The final boss (Gravewarden: phases, telegraph, stun-immune, Brace counterplay) is built too. Enemy drops (weighted tables, bits or any item, `configs/drops.toml`) and the Graveyard Key that opens the boss are built too. Next: channel drops
   rolling the same tables (`exts/economy/drops.py` is still the old Mongo code), combat tiers for levels 20-90, balance, party fights. Done since: the xp audit (tools never change xp: foraging pays per chop quality, fishing per catch by water, farming by
   growth time; migration 0007) and the Bestiary (the Coconut Level was added and then removed; DESIGN.md). Foraging was reworked (one chop style per grain, spot wear, rotation wedges, Seasoned enchant; see DESIGN.md) and the Bestiary now holds fish and sea bosses. Party invites show on the Party page; special foraging spots and wedges drop; **Mastery trees and tool forks are built for mining and fishing** (DESIGN.md). Next: balance them (the roads should earn within ~10%), roll out to foraging/farming, level 5/10 unlocks, then combat tiers for levels 20-90 and more point sources
   (collection books, achievements as new skills/features arrive). Then: mining rework (last), party versions
   of each skill.
7. Foraging tree events, channel drops / megadrop, Familiar Orb sources, and a "you were removed from your party" notice.
