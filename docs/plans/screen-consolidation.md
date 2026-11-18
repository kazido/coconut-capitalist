# Screen consolidation (plan, NOT built; waiting for the user's approval). Comes BEFORE area gating (docs/plans/area-gating.md).

Goal: 49 screens -> ~29, no feature removed. New rule (add to CLAUDE.md when done): **a new feature goes into an existing page as a tab/dropdown, not a new screen.**
No DB changes. Mechanics stay: every merged page keeps the old handlers as methods; the old screen ids are deleted (nothing stores them; verify
`grep -rn '"<id>"'` in `cococap/` and `tests/`, see step list). Slash commands in `exts/` that open a screen by id need updating (`exts/core/stats.py`, `exts/economy/top.py`, ...).

## Mechanism (step 0, lead builds once)
A small helper `ui/tabs.py`: a page holds `tabs = {key: (label, emoji, async render_fn)}` and a `select`/button row to switch; state `self.tab`.
Each old screen's body becomes a `_render_<tab>` method plus its existing click handlers, so the diff is mostly moves. Open with `open_screen(..., tab="book")` so other
screens (and gating) can link straight to a tab.

## Merges (old screen -> new page; what its buttons become)
| New page | Replaces | Becomes |
|---|---|---|
| **Fishing Collection** (`fishlog`) | fishquests, fishbook, fishcommunity, fishrecords, fishnotes | tabs Quests / Book / Community / Records / Notes. `fish` keeps ONE "Collection" button (was 5 links) + Crab pots + Radar. Book's link to Records and Community's link to Records become tab switches. |
| **Foraging Trees** (`trees`) | tree, grove, partygrove | selector Own / Community grove / Party grove. `forage` keeps Releaf. |
| **Tools** (`tools`) | tools, upgrade, enchant | pick a tool (existing dropdown), then actions Upgrade / Enchant on it. `upgrade.py` and `enchant.py` become service-facing helpers/tab renderers. Inventory's link to Tools stays. |
| **Games** (`games`, replaces minigames) | minigames, casino, highlow, blackjack, flashcard, sequence, trivia, unscramble | picker dropdown (grouped Casino / Brain games). Games that need their own multi-step state (blackjack hand, sequence, trivia round) KEEP their class as a sub-view the Games page opens, so only the menu layer (minigames+casino) really merges: 8 -> 6 sub-views behind 1 page, hub links drop from ~10 to 1. Candidates to cut (ask first, none cut here): flashcard and unscramble look like low-value study toys; highlow is the thinnest casino game. |
| **Player** (`player`) | profile, stats, top | tabs Profile / Stats / Leaderboards. `exts/core/stats.py` and `exts/economy/top.py` open it with a tab. `rank` (rank.py) stays a Profile sub-block if small, else its own tab. |
| **Selling** (see below) | sellall, shop (sell half) | |
| Mining | mining + mine | NOT merged: `mining` is the skill hub (level, mines list, links), `mine` is the live dig session (map, rows, vents; 368 lines of game state). Different lifecycle. Keep both; `wyrmhole` stays linked from `mine`. |
| Reactor | reactor + wyrmhole | Merge wyrmhole into reactor as a tab (Reactor / Wyrmholes). Wyrmholes are only reached from reactor gems and the dig. |
| Pets | pets + orbs | orbs becomes a tab of pets. |

## Selling: one clear place
Today: **shop** (buy seeds/supplies + sell), **sellall** (bulk sell, "keep upgrade materials", opened from fish/forage/farm/mining), **inventory** (list + links). Proposal:
- **Shop** page, tabs **Buy** / **Sell**. Sell tab = the sellall UI (single item and sell-all with the keep-materials switch). `start_sell_all` (used by skill screens) opens Shop on the Sell tab.
- Inventory stays "your items" (read, plus links to Tools/Trade/Craft); no selling there.
(Verify first that shop's current sell half has no feature sellall lacks.)

## Hide combat while paused
Remove `fight` and `bestiary` from `MORE_LINKS` (home.py:15) and from any `links`; keep the files, the services and `exts/skills/combat.py`'s command registered (decision: keep slash command? default: unregister the command too, one line, reversible). Their tests keep running by opening the screens directly.

## Rename: ship vs shipments
- `ship` (travel, tiers, fuel) -> label **"Voyage"** or "Travel" (id stays `ship` internally; only label/description/emoji change), keeps the 🛶.
- `shipments` (crates) -> label **"Crates"** (description "Fill crates with materials for bits"). Docs/wiki text updated. Suggest "Travel" and "Crates" (plain, no overlap).

## Resulting menu (49 -> 29)
Keep: home, more, skills, mastery, party, settings, wiki, checkin, craft, inventory, market, farm, forage, mining, mine, fish, fishpots, radar, releaf, reactor(+wyrmholes), pets(+orbs), ship, shipments, trade, shop(+sell), tools, player, games, fishlog, trees.
Hidden (code kept): fight, bestiary. Game sub-views (blackjack, flashcard, ...) are views, not menu screens. Counting registered `SCREENS` ids: ~49 -> ~31, ~22 shown in menus.
(Bestiary could return as a Player tab when combat resumes.)

## Reactor "prestige" (what it does today, `services/mining.py:869`)
Needs all four core gems placed in the reactor (gem slots unlock at mining 10). Spends ONE implosion gem (only dropped by wyrmholes, 1 in 5) to raise
`reactor.level` by 1, max 25 (`max_prestige`). The level buys: +1 dug column every 5 levels, +1 brace every 5 levels, 2% slower pressure gain per level, and bigger auto-mine
(1 lode per level every 6 min, 24 h cap). It does NOT reset anything: it is an upgrade track named "prestige", not a classic prestige. If a real prestige (reset for permanent bonus) comes later,
call that something else or rename this "Reactor level"; the Reactor page's tab slot makes room for it.

## Order of steps (each bounded; worker briefs; commit after each; run `scripts.quick_tests`)
1. (lead) `ui/tabs.py` helper + test + the tab-opening argument on `open_screen`. 
2. (worker) Rename Ship/Shipments labels; hide fight/bestiary from menus. Tiny, no merges.
3. (worker) Fishing Collection merge (fish.py 884 lines: biggest win). Update `fish` links, tests that reference old ids (`test_fishing.py`, `test_hub.py`).
4. (worker) Foraging trees merge. 5. (worker) Tools merge (tools+upgrade+enchant). 6. (worker) Player merge + `exts` command targets.
7. (worker) Shop Buy/Sell + sellall fold, `start_sell_all` retarget. 8. (worker) Reactor+Wyrmholes, Pets+Orbs tabs.
9. (lead + worker) Games page: first only the menu layer (minigames+casino), then decide cuts with the user.
10. (tester) Sweep: `grep` for dead ids in screens, `exts/`, docs, wiki text; full tests + ruff; DESIGN.md/HANDOFF update; add the "new features = tab" rule to CLAUDE.md.

## Tests affected
- `tests/test_hub.py` (125 tests): `test_every_screen_renders_valid_layout_within_discord_limits` auto-covers new pages but each TAB must be rendered by it (loop over `tabs`); `click(...)`
  helpers that open `fishquests/fishbook/tree/grove/upgrade/enchant/stats/top/...` change to open the page with a tab. Navigation test "never dead-ends": links updated.
- `tests/test_fishing.py`, `test_foraging.py`, `test_enchanting.py`, `test_command_smoke.py`, `test_emojis.py` reference old ids (grep hits); fix by id swap, no logic change.
- `screens/__init__.py` registration list and Home/More `FEATURED`/`SECOND_ROW`/`MORE_LINKS` lists.
Risk: Discord's Components V2 limit (40 components per message): a tab page must render only the ACTIVE tab; the layout test enforces it.
