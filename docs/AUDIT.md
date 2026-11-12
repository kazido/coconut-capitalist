# Codebase audit, architecture review & roadmap

Scope: whole repository at `d5d63cf` (791 commits, 2022-06 → 2025-09). Everything below was checked
by reading the code, running static analysis (ruff), importing/loading every module, and — for bugs —
writing a failing test or reproduction first. Nothing could be tested against live Discord or a real
MongoDB server (tests use `mongomock-motor`); items that need that are flagged **needs live check**.

---

## A. Current state

**One-sentence summary:** a reasonable, small (≈8.7k LOC) discord.py bot whose last commit sits in the
middle of an unfinished SQLite/peewee → MongoDB/Pydantic migration, so at `HEAD` **the bot could not
start** — and underneath that, several money bugs let players print currency.

At `HEAD`: 29 of ~45 modules failed to import (Pydantic model without annotations, absolute imports of
sibling modules, an `IndentationError`, references to a deleted item database), the game-data loader
pointed at a directory renamed one commit earlier (`game_data` → `configs`), `bot.py`/`__main__.py`
would hang or exit silently on common misconfigurations, and there were no tests, no CI, no lockfile
and no Python version declared (the code needs ≥3.10; this machine's default is 3.9).

### Strengths
- Sensible package layout: `exts/<area>/<cog>.py`, models separated from cogs, `user.py` as the one
  data-access wrapper.
- Good base: discord.py + `pydis_core` extension auto-discovery, Beanie/Pydantic documents, buttons
  restricted to the invoking user, secrets already in `.env` (git-ignored).
- Game content in INI files is easy to edit.

### Weaknesses / most problematic areas
1. **Half-finished migration** (see D). Highest-impact problem; caused every boot failure.
2. **Money integrity**: balance changes were read-modify-write or check-then-write; several gambling
   paths created or destroyed currency (see D).
3. **Global state & hard-coded IDs**: `cococap.instance` / `cococap.args` module globals (captured as
   `None` by `from cococap import instance`), guild/owner/channel/bot IDs scattered through code,
   a hard-coded Mongo `_id` for the megadrop singleton.
4. **`constants.py` is a grab-bag** (secrets, config parsing, reply strings, emoji enums, channel IDs).
5. **Duplicate / dead code**: empty `exts/core/explore/explore.py` and `exts/explore/explore.py`,
   `abilities/sword.py`, `weapon_converter.py`, parallel `utils/shop.py` vs `exts/economy/shop.py`,
   vendored 560-line `utils/pagination.py`.
6. **Weak validation of game data**: `fetch()` returns bags of strings (`int(rank.wage)` everywhere),
   INI files had silently-broken sections.

### Technical debt (rough size)
~11 modules are unported legacy (pets, shop, wiki, inventory, fishing, foraging, mining skill,
trivia, exploration mining) ≈ 2,300 LOC; they are skipped at startup via `DISABLED_EXTENSIONS`.

---

## B. Language recommendation: **stay on Python**

| | Python (discord.py) | TypeScript (discord.js) | Rust (serenity/poise) |
|---|---|---|---|
| Discord library | mature, async, full app-command + view support | mature, largest community | solid, smaller; more boilerplate |
| Workload fit | I/O-bound, low volume: all three are far from any limit | same | overkill |
| Types | optional (pyright/ruff, Pydantic at the DB boundary) | strong | strongest |
| Tooling/tests | pytest, mongomock, ruff — now in place | jest/vitest, similar | cargo, slower iteration |
| Migration cost | none | rewrite ≈ 8.7k LOC + data model + game logic | largest |

Reasons: the bot is a few hundred commands/interactions per day at most; nothing about it is
CPU-bound; the pain points found (broken migration, races, global state, no tests) are
design/process problems that follow you into any language. A rewrite would cost weeks and would not
have prevented a single bug in section D. The one thing TypeScript/Rust would give — compile-time
type checking — is available incrementally in Python via `pyright` (roadmap item). Revisit only if
the bot grows into multi-process sharding with sustained load, which is not in sight.

Python is now declared `>=3.11` in `pyproject.toml` (the code already used 3.10+ syntax).

---

## C. Architectural recommendations

**Keep:** cog-per-feature layout, Beanie documents, nested Pydantic models for skills, INI game data,
button views.

**Done in this pass**
- `cococap/errors.py` holds user-facing exceptions; `utils` no longer imports a cog to get them.
- `User` (`cococap/user.py`) is the single mutation point and now uses atomic Mongo operators only.
- One shared `AsyncIOMotorClient` (`bot.mongo`) instead of a second one created at import in `drops.py`.
- Startup: secrets validated up front with a readable message; DB failure raises `StartupError`;
  guild/owner IDs overridable via env; unported extensions skipped explicitly and visibly.

**Do next (in this order)**
1. **Wager base class** shared by blackjack / high-low / future games: take bet atomically →
   play → settle *exactly once* (win/lose/push/timeout/error). Today each game re-implements this and
   the cog-level `interaction_check` hack that parses `interaction.data["options"]` to charge the bet
   *before* the command runs (so any exception afterwards ate the bet). I patched the symptoms
   (idempotent settle, refund on error, payout on timeout) but the right fix is one tested class.
2. **Schema versioning**: add `schema_version` to `UserDocument`; run `cococap/migrations.py` at
   startup (or via the script) instead of ad-hoc scripts.
3. **Typed game data**: replace `fetch()` string bags with Pydantic models validated once at startup
   (`Rank`, `Item`, `Pet`, ...), so typos fail at boot rather than mid-command. Consider TOML/YAML
   over INI (INI can't express lists/numbers; the indented-section bug is a symptom).
4. **Per-guild configuration** (`GuildDocument` already exists, unused): channels, admin role, drop
   channels, megadrop id — finishes the "GENERALIZE THE BOT" item in `todo`.
5. **Kill module globals**: pass dependencies through `bot` attributes (`bot.mongo`) or cog
   constructors; remove `cococap.instance`/`cococap.args`.
6. **Split `constants.py`** into `settings.py` (env/config) and `content.py` (replies, emoji, enums).
7. Port or retire the unported modules (below), then delete `DISABLED_EXTENSIONS`.

**Don't add:** a DI container, repository layer or event bus — at this size they'd be pure overhead.

---

## D. Issues identified

### Confirmed bugs (all fixed unless noted; each has a test)
| # | Bug | Impact |
|---|---|---|
| 1 | `models/skills/farming.py`: `plot_1 = Plot()` without annotation → Pydantic error at import | Bot could not start (this alone broke 20 modules) |
| 2 | `models/models.py`: `from cooldowns import …` (non-package imports) | Import failure |
| 3 | `exts/economy/top.py` IndentationError; `exploration/mining.py` syntax error | Import failure |
| 4 | `fetch()` read `game_data/` (renamed to `configs/`) relative to the **cwd** | `/profile`, `/check-in`, `/rank` all broken; now anchored to the module path + cached |
| 5 | `configs/items.ini`, `enemies.ini`: indented `[x.seed]` headers are parsed as *continuation of the previous value* | Seeds/zombie.armored didn't exist; `apple.max_harvest == "20\n[apple.seed]\n…"`. Dedented |
| 6 | **Rank-up gave tokens instead of charging**: `add_tokens(-price)` did `inc(abs(amount))`; no server-side affordability or "next rank" check | Infinite tokens; stale button could replay. Now an atomic conditional `rank_up()` |
| 7 | **Blackjack natural paid on every deal** (payout lived in `update()`, called once per card) | A natural paid 3× instead of 1× (test mutation-checked: 1500 vs 1100) |
| 8 | **Bets vanished** on timeout / error: bet charged in `interaction_check`; high-low had no `on_timeout`; blackjack timeout paid the house `0` | Players lost bets silently. High-low timeout → cash out at current multiplier; blackjack timeout → forfeit to house; errors → refund |
| 9 | Blackjack/high-low buttons re-entrant (double-click → double settle); fixed with `busy`/`settled`/`finished` guards | Double payout |
| 10 | `validate_bits`: `"500%"` accepted (bet > balance); int input crashed (`amount[-1]`); `"%"`/`""` crashed; `"1%"` of 10 → 0 | Overbetting, crashes. Rewritten as pure `parse_bits` |
| 11 | `remove_bits` / `process_payment` / `deposit` / `withdraw`: check-then-write → concurrent commands could overdraw or duplicate bits | Now single conditional `$inc` |
| 12 | `/check-in` cooldown only enforced by disabling the button: two open menus (or a stale one) each paid out | Now `claim_cooldown()` atomic |
| 13 | `User.add_item/remove_item` read-modify-write on a copy of the whole inventory (docstring claimed atomic) | Lost updates; now `$inc` on `items.<id>.quantity` |
| 14 | `User.get_stat` read nonexistent `doc.stats`; `claimed_*` stats weren't in the `Stats` model | High-low streaks / check-in stats crashed |
| 15 | `User.get()` could create duplicate users for one Discord ID (no unique index) | Now unique index + `DuplicateKeyError` handling (**see "needs live check" #1**) |
| 16 | Error handler: wrote to `logs/` that doesn't exist (→ the handler itself crashed), `e.args[0]` IndexError, **showed raw exception text (could include connection strings) to users**, blocking file I/O | Rewritten; only intentional errors are shown |
| 17 | `drops.py`: `from cococap import args` captured `None` (cog failed to load), `discord.Object.get_channel` doesn't exist, `megadrop.amount` on a dict, `user.save()`/`_document.drops_claimed` no longer exist, two people could claim one drop | Rewritten claim path; first click wins |
| 18 | `utils/converters.Extension`: `from cococap import instance` captured `None` → `.ext reload` always crashed | Uses `ctx.bot` |
| 19 | Party: `kick` rejected the *owner* and allowed members; `promote` rejected real members; `NotPartyOwner()` without message → `TypeError`; `change_owner` never persisted; invite Join button referenced undefined variables | Fixed; invite flow reimplemented as a small view |
| 20 | `/rank` at max rank raised `KeyError` | `fetch_optional` |
| 21 | `scripts/update_collection.py` `$unset` every field not in `models.py` (e.g. all users' `pets`) with no dry-run, and is incompatible with nested models | Replaced by `migrate_legacy_users.py` (dry-run default, never unsets) |
| 22 | Leaderboard: `("purse")` is a str not a tuple; nested sort paths; whole collection loaded twice for BITS | Fixed (single load; whole-collection scan remains, see perf) |
| 23 | `Mineshaft.LEVEL2 = [...].extend(...)` is `None` | Fixed (WIP file) |
| 24 | `snail_racing.py` `setup()` calls `add_cog()` with no cog (TypeError on load) | Disabled (empty stub) |

### Potential issues needing a decision / live verification
1. **Unique index on `users.discord_id`** will make `init_beanie` fail at startup if production already
   has duplicate users. Check first: `db.users.aggregate([{$group:{_id:"$discord_id",n:{$sum:1}}},{$match:{n:{$gt:1}}}])`.
2. **Live data uses the old flat-dict schema** (`farming.plot1`, `mining.core_slot1`, …). Loading it with
   the new nested models silently shows defaults (progress "reset"). Run
   `python -m scripts.migrate_legacy_users` (dry-run) then `--apply` after a `mongodump`. The
   fishing quest-book mapping (`found[rarity] > 0` → `*_donated`) is an **assumption**; verify.
3. Context-menu commands in `PartySystemCog` (invite/kick/promote) rely on `interaction.extras["party"]`,
   which the cog's `interaction_check` populates; context menus may not go through the cog check.
   **needs live check.**
4. Drop roll `roll in range(1, 2)` is 1% not 1–2%; megadrop pot semantics (`amount` accrues only on
   expired normal drops). Looks unintended but I didn't change game balance.
5. `tasks.loop(minutes=randint(30, 60))` evaluates the random interval once at import.
6. Blackjack shows "Profit: +2×bet" on a win; actual net profit is 1×bet (display only).
7. Several `*_hl_*` streak stats do 3–4 sequential DB round-trips per click; fine at this scale.
8. `intents`: now `default() + members + message_content` instead of `Intents.all()` (which requested
   presence and every other privileged intent then switched some off).

### Security
- **Credentials in git history (rotate them).** `data.json` (2022-06-15 `f5a08b7`, deleted
  2022-10-09 `5e39875`/`a4fd348`) and `.idea/` files contain a MongoDB Atlas connection string *with a
  password*. Deleting the file didn't remove it from history. Rotate that database user's password (or
  delete the user) even if the cluster is gone; if the repo is or becomes public, scrub with
  `git filter-repo`. A scan of the most recent 400 commits for Discord-token-shaped strings found none (older history not exhaustively scanned).
- SQLite databases (`database/*.db`, `economySQLdatabase.sqlite`) are committed in history (old player
  data / the old **item database** you'll need for the port, see roadmap).
- Error messages no longer leak internals; admin-only debug commands now read `OWNER_ID` from config;
  `/clear` is bounded; `sync` no longer targets a hard-coded foreign guild. `.env` is ignored;
  `.env.example` added.
- Permission model is "owner-only debug cog + user-scoped views". There is no per-guild admin role yet.

### Deprecated / outdated
- `requirements.txt`: 54 pins incl. the unrelated PyPI package `discord`, unpinned `pymongo`,
  `soupsieve==2.3.2.post1`, matplotlib/numpy/contourpy (unused in enabled code). Replaced by 10 direct
  dependencies in `pyproject.toml` (a compatibility `requirements.txt` remains).
- `motor` is deprecated upstream in favour of PyMongo's native async API (`AsyncMongoClient`), and
  Beanie ≥2 moves to it. Plan this together with a Beanie upgrade (roadmap, medium).
- `the_trivia_api_library` (PyPI: `the-trivia-api-library`) was never declared in `requirements.txt`; trivia is disabled until it's added to the `legacy` extra and re-enabled.

### Performance
- `/top` loads every user document (twice for BITS) to find the caller's rank → use `.limit(10)` plus
  `count_documents` for rank. Fine at hundreds of users, not thousands.
- `BaseCog.interaction_check` loads the user on every interaction (one indexed query) — acceptable.
- Previously `fetch()` re-parsed an INI file on every call; now cached.

---

## E. Changes implemented

All changes are on branch `claude/discord-bot-audit-modernize-4dd6c5`, in the commits listed at the end.

**Tooling / DX** — `pyproject.toml` (deps, ruff, pytest config), `.env.example`, GitHub Actions CI
(ruff + pytest), README rewrite, `requirements.txt` trimmed to direct deps.

**Boot & data** — models fixed (annotations, relative imports, `default_factory`, `claimed_*` stats,
unique index), `fetch()` rewritten, INI sections un-indented, `constants.py` hardened
(`require_secrets()`, project-root paths, `GUILD_ID`/`OWNER_ID`), `__main__.py`/`bot.py` rewritten
(shared Mongo client, `StartupError`, explicit disabled-extension list, helper-module tolerance).

**Money integrity** — `user.py` atomic operations, `utils.parse_bits`, rank-up, payments, check-in,
blackjack/high-low settlement, drops claim.

**Reliability** — error handler, converters, party system, leaderboard, megadrop seeding on empty DB.

**Migration** — `cococap/migrations.py` + `scripts/migrate_legacy_users.py`.

**Tests (75, ~0.5 s, no external services)**: `parse_bits` table, atomicity under `asyncio.gather`
(10 concurrent spends of 600 on a 1000 purse → exactly one succeeds), cooldown double-claim, pay
conservation, rank-up replay/skip, blackjack single payout (mutation-checked against the old logic),
timeout settlement, legacy→new data migration, every enabled extension imports **and loads into a real
`Bot`**, `fetch` from an arbitrary cwd, error-handler leak test.

**Not changed / remaining concerns**
- Unported modules (D, roadmap) remain disabled, not deleted.
- No live Discord/Mongo run was possible; slash-command sync, intents, and Atlas connectivity are
  unverified. Run the bot against a dev token + dev database before deploying.
- Game balance untouched (even where odd, see D "potential").

---

## F. Roadmap

| Priority | Item | Benefit | Complexity |
|---|---|---|---|
| **Immediate** | Rotate the leaked Mongo credential; scrub history if repo is/will be public | closes a real exposure | low |
| Immediate | `mongodump`, check for duplicate `discord_id`s, run migration dry-run, then deploy to a **dev** bot first | avoids data loss / startup failure | low |
| Immediate | Fill `.env` (`BOT_TOKEN`, `URI`) and smoke-test `/profile`, `/check-in`, `/highlow`, `/blackjack`, `/rank`, `/party` live | verifies what mocks can't | low |
| Short | Wager base class for gambling games (+ tests for push/fold/bust paths) | removes the class of bugs in #7–9 | medium |
| Short | Port the SQLite item DB to Mongo/TOML (recover `itemdatabase.db` from history: `git log --all -- '*.db'`) and re-enable inventory, shop, wiki, pets | restores ~⅓ of features | high |
| Short | `pyright` in CI (start with `cococap/user.py`, `models/`, `utils/`) | typed core | low–medium |
| Short | Pydantic-validated game data loader | boot-time errors for bad content | medium |
| Medium | Per-guild config (`GuildDocument`), drop channels/megadrop per guild | "generalize the bot" | medium |
| Medium | Remove module globals; split `constants.py`; delete dead modules | clarity | medium |
| Medium | Move to PyMongo async + Beanie 2 | removes deprecated Motor | medium |
| Medium | `/top` pagination via queries; indexes on leaderboard fields | scale | low |
| Long | Port skills (mining/fishing/foraging/farming/combat) onto a common `Skill` service; implement exploration | the game's core loop | high |
| Long | Docker/compose for bot + Mongo, deployment docs, structured logging/metrics | operability | medium |
| Long | Re-evaluate language only if sharding/high load appears | — | — |
