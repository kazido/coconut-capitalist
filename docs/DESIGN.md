# Game design decisions

Living record of how the game is meant to play. Update it when a decision changes.

## Principles

- **Each skill has its own verb.** No two skills should feel like "press the button again".
- **Choices with a cost.** Every minigame needs a decision where more reward means more risk or effort.
- **Sessions are short** (30-90 s), turn-based, and never need sub-second reflexes: Discord allows
  roughly 5 message edits per 5 s, so no animation or timing games.
- **Rules live in `services/`, Discord only draws.** Designs below are cheap to change for that reason.
- **Navigation is never a dead end**: everything is reachable from `/play`, and every slash command
  is just a shortcut that opens the hub on that screen.

## Interface

- `/play` opens one message (a Components V2 `LayoutView`) that is edited in place. Every screen is a
  `Screen` class in `cococap/screens/`; the `Navigator` adds Home / Back and a "Go to..." menu.
- Layout kit: panels (`Container`), text, separators, `Section` (text + a button/thumbnail on the right),
  action rows, selects. Modals ask "how many?" / "how much do you bet?".
- Board-style games can use a grid of buttons as the board itself (5 rows x 5 buttons).
- No "go anywhere" menu: navigate with Home / Back and the section buttons (Home -> Skills / Minigames / ...).
- Casino games (High-Low, Blackjack) play **inside** the hub window, so menus never pile up; Home/Back are
  locked while a hand is live, and walking away settles it. Screenshot a big win to share it.
- Embeds are only used where a screen has not been ported to the hub yet (the mine board; brain games).
- Modals (discord.py 2.7) can hold labelled text inputs, selects, radio groups, checkbox groups and
  text blocks. Good fits: planting several plots in one form (farming), choosing an enchant to craft,
  entering a treasure-chest code (fishing), splitting a trade.

## Currencies: one job each

| Currency | Question it answers | Earned by | Spent on |
|---|---|---|---|
| **Bits** | "what can I afford?" | selling, work, daily interest, drops, gambling | tools, seeds, land deeds, enchants, upgrades |
| **Tokens** | "how far have I progressed?" | 1/day (scarce, time-gated) | ranks only |
| **Luckbucks** | "how lucky/flashy am I?" | weekly check-in, gambling wins | **cosmetics and fun extras only**: skins, titles, emotes. Never power. |
| **XP** | "how good am I at this skill?" | playing the skill | (unlocks) |

- **Gambling never unlocks power.** It is the fastest way to earn bits (high risk) and the only way
  to earn luckbucks in quantity; luckbucks buy things that don't matter for progression. Players still
  gamble for the leaderboard and cosmetics.
- Every way of earning needs a matching way of spending (watch bank interest, which creates bits).
- The house account is an economy health meter (shown on the bits leaderboard).

### Decided: two economies (built)

- **Bits** = power. Only skills, work, selling and drops pay bits. Brain games no longer do.
- **Luckbucks** = fun. Brain games, the weekly check-in and gambling pay and stake luckbucks
  (`constants.CASINO_CURRENCY = "luckbucks"`); the planned sink is cosmetics.
- Numbers live in `configs/economy.toml`: new players start with 100 luckbucks, weekly = 100.
- **Minigames are capped per UTC day** (300 luckbucks across all of them) because trivia etc. can be
  played non-stop; streaks add up to +90%. Anything past the cap still counts for streaks and stats.
- **Exchange:** bits -> luckbucks, one way, 5,000 bits each, max 500 luckbucks/day. Early players barely
  notice it; late-game wages hit the daily limit, so bits can't flood the casino.
- Still to build: the cosmetics shop (the luckbuck sink).

## Skills

| Skill | Verb | Core idea |
|---|---|---|
| Mining | **push your luck** | descend row by row; a *danger meter* slowly rises as you go deeper; bank your haul to leave safely or keep digging for rarer ores/gems. |
| Farming | **plan and wait** | 3x3 plots; hourly rain; neighbouring crops can give bonuses; Farmer's Market timing. |
| Foraging | **cooperate** | two players alternate chops with a shared combo; Soloist enchant lets you go alone. |
| Fishing | **tension** | wait for a bite, then a short tug-of-war (Reel / Hold / Ease) against the fish's pattern; memory code for treasure. |
| Combat | **tactics** | turn-based tile dungeon, weapon abilities, idols to collect before the boss. |
| Pets | **collect and tend** | gacha, feeding, passive bonuses. |

### Mining v2 (built)

- Keep what exists: reactor, gems, prestige, auto-miner, magnet, wyrmholes, scarab, loot tables.
- Replace "press mine on each row" with a **descent**: each step you choose how to dig; deeper rows
  roll better loot but raise a **danger meter** (visible, slowly increasing, with clear risk signals
  - e.g. 🟢 calm, 🟡 tremors, 🟠 unstable, 🔴 collapse imminent).
- The run should not end quickly: danger rises slowly, and the player has tools to manage it
  (scarab bombs, reactor level = safety margin, magnet = see the safest/richest line).
- Banking (leaving) always keeps what you carried; a collapse costs part of the unbanked haul.
- Built as: dig row after row (each dig descends one row); the meter rises by `2 + 0.15 x rows dug`
  per dig (slowed by reactor level); the band (Calm / Tremors / Unstable / Critical) sets the collapse
  chance of the *next* dig (0 / 3 / 10 / 25%), shown before you click; Brace (limited) lowers the meter;
  Leave banks everything; a collapse loses half the haul but keeps xp. Pickaxe power adds yield. All
  numbers are `TODO(balance)` in `configs/mining.toml`.

## Open questions

- Command style: separate commands per skill (the wiki) vs the `/explore` map prototype.
- Pet design.
- Balance placeholders (`TODO(balance)` in `configs/`).

## Mining: the shaft (v3)

A run is a shaft of `floor` rows (30). Digging the last row opens the **vault** (150 gold, and a small `vault_gem_chance` of one reactor gem: gems are rare).

- **Cells are hidden.** You see 3 rows ahead, but ore, empty cells, vents and caches all look like plain rock. Only
  rich lodes (`cell_upgraded`) and wyrmholes stand out, so those are what you steer toward or around. A cell you dig
  is revealed. A charged magnet marks the richest cell of the next row.
- **Hardness:** every dig adds `creak` pressure plus the hardness of each cell dug; richer ore is louder.
  Because ore is hidden, pressure is the signal: if the risk jumps after a dig, you found something heavy.
- **Collapse risk** is one smooth number (the chance for the *next dig*; it compounds over a run) (0 below `safe_pressure`, `max_risk` at 100) and is the only thing the
  player sees. Collapse loses half the haul; xp is kept.
- **Special cells:** rich lode (`cell_upgraded`: a mystery that rolls the next tier's table, more of it), vent
  (💨 no loot, cools), cache (📦 +1 brace), wyrmhole (as before).
- **Bomb** (`scarab_bomb`, up to 3 carried per run): clears a whole row (not wyrmholes) for a flat pressure and no
  collapse check. Worth saving for a row with several rich lodes.
- **Brace:** skips a dig to lower pressure.
- The screen is deliberately small: risk line, map, pack, buttons. A `?` button toggles the legend.

**The decision each row is "leave or push?"** Every row deeper pays +5% more (`depth_bonus_per_row`), but pressure
climbs and the collapse chance with it. Simulated with starting gear: leaving around the *Unstable* label (about 7-10%
risk, roughly row 14-15) earns the most; never leaving earns ~40% less, leaving at the first tremor ~40% less.
With mid-game gear the best point moves later and the haul is ~15x bigger; only well-upgraded gear reaches the vault.
All numbers are `TODO(balance)` in `configs/mining.toml` `[descent]`.

### Upgrades (what each one is *for*)

| Upgrade | Does | Status |
|---|---|---|
| Reactor level | pressure builds 2% slower per level (max 50%), +1 brace per 5 levels, +1 column per 5 levels, auto-miner lodes | built |
| Reactor gems | each placed gem makes wyrmholes more likely | built |
| Pickaxe power | +10% yield per point above 1 | built (only the Rookie Pickaxe exists) |
| Pickaxe upgrade template | raises pickaxe power (once the scarab's reward; the scarab now gives other prizes) | **dropped** |
| Mining enchants | see below | **not built** |

Proposed roles: the **reactor is endurance** (how deep a run can go: stability, braces, bombs carried, passive
lodes); the **pickaxe is payoff** (yield, rich-lode chance, vault gem chance). Pickaxe enchants would be e.g.
*Reinforced* (less pressure per dig), *Prospector* (more rich lodes), *Demolitionist* (bombs add less pressure),
*Lucky* (better vault gem chance).

## Custom emojis

The bot's emojis are **application emojis**, looked up by *name* at startup (`cococap/emojis.py`). Data files
may keep `<a:name:id>` strings; the name wins over the id. Missing emojis fall back to plain Unicode.

## Farming

Wiki rules, built as written: up to 9 plots (plot 1 free, the rest cost a **land deed**); seeds take `cycles` rains to
grow; each hour it rains and every growing plot grows with `grow_chance`; a rain in which anything grew has a 1/10
chance of a **rain god's blessing**; each harvest has a 1/25 chance of an **agricultural anomaly** (work and daily
cooldowns refresh); the **Farmer's Market** (farming level 5, open daily for a few hours, UTC (`open_hour`, `open_hours`)) pays +50% for crops and turns blessings into
land deeds at 1/10 each.

**Rain is computed, not scheduled.** A farm catches up on missed rains whenever it is looked at or changed, and each
roll is seeded by (player, plot, hour). So reopening the farm can't re-roll, rain keeps falling while the bot is
offline, and there is no hourly job. (Trade-off: no "the rain fell" channel announcement; it can be added later as a
cosmetic-only task.) Numbers are in `configs/farming.toml` (`TODO(balance)`).

### How long will it take? and more crops

Cycles stay (later things can speed them up or add more). To make them readable, the farm shows **how long a crop will
take**: in the seed menu before you plant ("20 cycles · about 40h (30h to 52h)"), when you plant, and on every growing plot.
It is the expected time from the hourly rain (`grow_chance`), with a range because rain is luck: you are done by the first
number one time in ten and by the second nine times in ten (`farming.estimate`; exact for short crops, a normal curve for long
ones). New crops, priced so a watered plot earns about 20-30k bits an hour once the seed is paid for: **blueberry** (12
cycles), **watermelon** (40) and **starfruit** (80). `python -m scripts.balance` prints the numbers for every crop.

### Getting into farming

Farming used to be slow to start: the first seed cost 10,000 bits (a new player has 1,000) and everything waited on the hourly
rain. Now every farmer gets **3 free apple seeds** the first time they open their farm, an apple seed costs **500** bits (a
lemon seed 8,000), and there is a **Water** button: once an hour each growing plot can be watered, and it grows a cycle with an 80%
chance on top of the rain (the roll is fixed by you, the plot and the hour, so looking again can't redo it). An apple needs one
cycle, so a new farmer can plant, water and harvest straight away; the long crops (20 to 777 cycles) still take days.

## Foraging

**Solo always works; friends are better.** The wiki's "two players at zone 7" rule is replaced so nobody is ever
stuck waiting for another player online:

- **Private trees** (any time, in your own panel): pick a zone you've unlocked (level `1 + 2 x (zone - 1)`), chop it
  down. From zone 7 up a lone chopper swings at half power (never below 1) unless their axe has the **Soloist**
  enchant, which removes that penalty.
- **The community tree**: one grows every hour and stands for 30 minutes. It is the same for everyone (zone and hp come
  from the clock) and is chopped at full power. Everyone who joins from their own panel adds to one shared hp pool.
- **Party bonus:** skill xp in *every* skill (mining, farming, foraging, fishing) goes up with the size of your party:
  **+10%** for 2 members, **+25%** for 3, **+50%** for 4 or more (`economy.toml` `party_xp_bonus_by_size`).

**Why the community tree has no race conditions.** Each chop is one atomic database update (take hp off the tree, add it
to your total), so any number of simultaneous chops all count and the tree can only fall once. The "batching" you see is
only the panel redrawing itself every few seconds, not a delay in chopping. Panels edit themselves for as long as
Discord allows (15 minutes per panel); the next click revives one.

**Rewards** are worked out once, when the tree falls or falls over, and stored per player; each player claims theirs from
their own panel (even if they were offline). Drops and bits go by share of the tree's hp, only for players with at least
5% of it; everyone gets xp for the work they did. The group gets a bonus (+5% per extra qualifying chopper, up to +50%).
A tree nobody finished pays a 25% consolation.

### Party trees

A party of two or more can start a **party tree** from the Foraging page (any member, in the deepest zone *everyone* in the
party has unlocked; one at a time). It stands for 20 minutes and is bigger the more members you have (a typical tree of its
zone x 4 x the party's size). Only members can chop it; every chop is one atomic update (the same guarantee as the community
tree), so members chopping at once lose nothing and it falls once. Rewards are worked out exactly once, when it falls or falls
over, and each member collects theirs from their own panel. They pay a little better than the community tree for the same work:
**+10% per extra member who did at least 10% of it, up to +50%** (the community tree gives +5% each). This is the first of the
**party versions of each skill** (the others are still to come). Settings: `configs/foraging.toml` `[party_tree]`.

### Grains, one chop style each, spot wear and rotation wedges (decided; replaced the 8-step patterns)

Every spot has a **grain** (Plain, Knotty, Clean, Twisted, Split, Burl) and every grain likes **one chop style**: Overhead,
Sidecut or Undercut (`configs/foraging.toml` `[[chopping.grains]]`, each stance liked by two grains). One grain = one style, so it is
a thing you learn once and remember, not a pattern you re-read every spot.
- **Right style = full strength; any other glances off** at `wrong_stance_factor` (half) of the damage and xp.
- **Your Grain notes remember.** A style that worked is kept for good; a wrong one is crossed off (✖️), so two wrong guesses give away the
  third. The panel never tells you the style (it shows the grain, its quality, the spot's wear and what a chop does right now).
- **Spots wear.** Each chop wears the spot by `wear_per_chop` x the grain's `wear` (so a plain spot lasts 25 chops). **Good grains wear
  slowly and bad ones fast** (Burl 0.6, Clean 0.7 ... Knotty 1.6): a clean spot is worth staying on, a knotty one burns out. A worn
  spot chops weaker (down to 60% at the end, `wear_penalty`). When it is used up you are moved to a new random grain by yourself.
- **Rotation wedges** are consumable items (shop): use one to leave the spot at once and land on a different grain. Three tiers
  (`[rotate]`): Rotation Wedge (random), Iron Wedge and Gilded Wedge, which lean toward good grains (a new grain's chance is its weight
  x multiplier ** bias). So you can only rotate as often as you can afford wedges.
- **Special spots** (`[[chopping.specials]]`, `special_chance` 8% of new spots): a grain plus a special, shown by name. Chopped in the grain's RIGHT
  style: 💎 **Heartwood** x4 damage, ✨ **Golden Knot** x2 xp (effort, not damage), 🏷️ **Rich Seam** +15% bits and drops when the tree falls (tree-wide
  cap `mark_cap` 50%, private trees only, so it is never rolled on shared trees). They wear x6 faster, so you get about four chops. Wrong style = just
  a glancing blow. Wedges multiply the special chance (1.5x / 4x / 10x) on top of their grain bias.
- **Wedges are found as well as bought:** they are on the foraging drop table (1 in 60 / 400 / 2,500 per roll) and cost 1k / 8k / 50k in the shop
  (a wedge only moves you to a new spot, so it should not be expensive).
- **Double Strike** enchant (axe, 3 levels, +8% each): a chop hits twice as hard, still one swing for xp. Scroll drops from chopping.
- **Upgrades that slow wear:** the **Seasoned** enchant (axe, 3 levels, -15% wear each; the scroll drops from chopping). Wear can never be
  slowed below a quarter of normal.
- Same on private, community and party trees. Wear is per screen, like the spot always was. Xp follows the quality of the chop, so wear and
  a wrong style cost xp too; `xp_per_swing` and `bits_per_hp` were raised a little to keep foraging where the xp audit put it (about 6,800 xp/h, a little under mining).
- **Old notes:** the 8-step pattern notes are ignored (a new `styles` field); everyone relearns six styles, which takes minutes.

### The Releaf Foundation (server-wide Bloom)

Rebuilt from the old per-player Re-leaf (donate a tree's drops for a personal double tree, removed). `services/releaf.py`, `screens/releaf.py`, `[releaf]`
in `configs/foraging.toml`. It is reached from a button on the Foraging page (from foraging level 10); the reward pages no longer offer donations.

- **One shared meter** for the whole server, kept as one JSON document in the existing `community_state` table (key `releaf`, `services/community.py`: a read-modify-write
  in one serialized transaction, so two givers at once cannot start two Blooms or overfill it; no new table, so no migration). It holds the meter, this round's and lifetime
  points per player, and the recent Bloom windows.
- **Rare only.** Only foraging items (not tools or key items) of rarity `min_rarity` (4) or more can be given, worth `points` by rarity (1/3/8/20). The item is consumed:
  a real loss, and the page shows the bits it would have sold for. Items refused or left over (closed, cap, meter nearly full) go straight back.
- **Bloom.** At `meter_goal` (300 points) a Bloom starts for `bloom_hours` (3): everybody's foraging xp is +10% (the `party.xp_multiplier` hook, foraging only) and every drop
  chance of every foraging tree is +10% (`roll_drops(boost=)`: private trees at the moment they fall; community trees if a Bloom was up at any time in the tree's hour, since
  they settle lazily; party trees take the best boost seen while they were chopped). Then the meter empties, the round's tallies reset and giving reopens.
- **Why nobody has to give (the four rules):** (a) giving is CLOSED while the meter is full / a Bloom runs, so surplus is never wanted or wasted (the last item may top the meter
  off; the surplus is not counted); (b) the Bloom is temporary and shared, so it is a gift to everyone including non-givers, never a personal to-do, and not giving costs
  nothing but the bonus a few hours a day; (c) one player can give at most `max_share` (25% = 75 points) per round, so at least four people are needed; (d) there is no personal
  reward at all, only a thank-you list (top givers this round, your own tally). Because points follow rarity but the sell value follows rarity much faster, the cheap rarity-4
  drops (honeycomb) are the efficient thing to give; the rare feathers are better sold. The wiki says all of this.
- **Numbers (sim in the session scratchpad, `releaf_sim.py`):** about 0.19 points per drop roll if every donatable drop were given, ~300 rolls an hour for an active mid-game
  forager. A server of 12 players (half online each hour) that gives 20% of its donatable drops keeps a Bloom up about 29% of the time (a Bloom every ~10 h); 6 players at the same
  rate 18%, 25 players 44%; giving 5% gives 10-18%. Even if everyone gave 40% it stays around 40-55%. The Bloom is worth about +3% xp averaged over the day. TODO(balance)
- **Removed:** the personal meter, daily limit, `double_ready`, double trees (+hp, jackpot, double_items haul), the Re-leaf buttons on result pages and **growth mode** (never built).
  The old per-player fields (`releaf_meter`, `donations_made_today`, `donation_day`, `double_ready`, `stats.double_trees_chopped`) stay on the Foraging model as unused legacy
  so old saves load; `stats.releaf_donations` now counts your gifts to the Foundation.

### Zones and the community tree (v2)

There are **20 zones**; zone N needs the foraging level `zone_levels[N-1]` in `configs/foraging.toml` (1, 4, 7, 11, 15, 20, 25, 31, ...
136). The gaps grow, so each zone takes longer than the last (the level curve is quadratic: level 20 is about 74k xp, level 100 about
2M). Trees from zone 8 are heavy. Deeper zones pay only +7% per hp each (zone 20: x2.3), so depth does not run away from other skills.

The **community tree** now follows the crowd. When an hour's tree is made (and stored, so everyone sees the same one) the server
looks at who chopped a community tree in the last 24 hours: the zone is picked around what the *median* of them can reach
(`reach - 2` to `reach + 1`), and hp = a typical tree of that zone x 5 x the number of choppers (counted as at least 3, at most 40).
A quiet hour gets a small tree you can finish, a busy one a bigger tree; with nobody chopping it falls back to zone 3.

### Foraging pay vs mining

Measured with fixed-seed simulations (a test guards it): mining at base gear pays about 1,100 bits per click; foraging at
the starter axe in zone 1 pays a bit less (a test keeps it under mining and over 40% of it), because it has no collapse risk. Pay is proportional to hp chopped
(`bits_per_hp`, drop rolls per hp), so stronger axes earn more per click, and each zone above 1 pays +15% per hp.
Drop rolls are fractional (a half-roll is a 50% chance of a roll), so small trees are not over-paid.

## Getting started: every skill needs a tool, and tools cost bits

A new player has **1,000 bits** and their first **Work** pays **2,500** (rank 0), so they can afford exactly one starter
tool straight away: the **Rookie Pickaxe**, **Starter Axe** or **Starter Rod**, each **2,000 bits**. Your first tool for
a skill is **equipped automatically** when you buy it. Mining used to run without a pickaxe; it now needs one like every
other skill. Farming has no tool, but its
first seed is 10,000 bits, so a new player needs a couple of Work claims or another skill first (`TODO(balance)`).
Whichever skill they pick first pays for the next tool.

## Idle party members

Every command and button press stamps `users.last_active` (written at most once a minute per player). Every 10 minutes the bot
sweeps (`services/activity.py`): anyone in a party who has been idle longer than `party_idle_hours` (24, in `configs/economy.toml`)
is taken out in one transaction. If they owned the party it goes to the most recently active remaining member; if nobody active is
left the party is disbanded. No per-command history is stored, only that one number. Migration 0004 sets everyone to "active now",
so nobody is kicked the day it ships. Players are not told when it happens (a possible follow-up: a note on their next party screen).

## No bank

The bank is gone (it had no way to withdraw and no real use). Migration 0006 moved everything in it back to the purse (the `bank`
column stays, always 0, and nothing reads it). `/deposit`, `/withdraw` and the auto-deposit setting are removed. The **daily** now
pays interest on the bits you carry: 3% for a small purse, shrinking toward 0.3% as it grows past tens of millions
(`economy.daily_interest`), plus the token. Leaderboards and `/beg` count the purse only. The Settings page is empty for now.

## Tokens and rank prices

Tokens buy ranks. A player gets **1 a day** from the daily and finds more **at random while playing**: each hour in which you press
anything there is a 35% chance (`token_drop_chance`, economy.toml) of one, rolled once an hour and seeded by (player, hour), with the
hour written first in the same statement, so a second press, a second process or a restart cannot roll again. It shows as a note on
the next screen. That is about 2 tokens a day for a regular player. Rank prices (`configs/ranks.toml`) were rescaled to match:
3, 6, 12, 20, 32, 48, 70 (Expert, about 3 months), then 110, 150, 200, 260, 330, 410 and 500 for rank 15 (2,150 tokens in all, about 3 years at 2 a day). Not built yet: a pet bonus for tokens.

## The wiki

`/wiki`, or **More -> Wiki**: one page per topic (getting started, each skill, fish, waters, crab pots and bait, tools and
upgrades, enchants and scrolls, pets, parties) plus an item lookup by skill. **Every page is written from the game's data**
(`services/wiki.py`), so a changed price, bonus or fish shows up in the wiki by itself; tests check that it names every fish,
pet, upgrade step, bait and enchant and uses the real numbers.

## Pets

Pets are the gacha part of the bot, and **every pet gives a bonus somewhere in the game** while it is your active pet
(one at a time; `/pets` or the Pets shortcut on Home). They come from **Familiar Orbs** (treasure chests, boss loot,
the shop at 1.5M), which hatch a random pet by rarity (`economy.toml` `[pets.orbs.<orb id>]`; three kinds: Lesser at 150k mostly common, Familiar at 1.5M, Greater at 15M mostly rare); a duplicate adds a **star**
(up to 5; a fifth-star duplicate gives xp instead). Feed them **food** (and play with them active) to level them up to 100, and give them
a **Spirit** item for +15% xp in its skill. A bonus is its listed value x stars (+25%
each) x level (a fresh pet does a tenth, a max one all of it). A level costs xp by the pet's rarity (`[pets.xp_scale]`: common quickest, legendary slowest); old saves were rescaled once (`Pethouse.curve_version`, `pets.upgrade_curve`) so no pet changed level.

### Pet food and pet skills

Crops are no longer the only food. **Every skill drops its own food in three tiers** (`category = "pet_food"` in
`items.toml`, worth 200 / 1,000 / 5,000 pet xp, never sold): foraging **Acorn Mix / Honeycomb / Golden Sap** (rolled per tree
like any foraging drop), mining **Stone Biscuit / Crystal Chew / Geode Feast** (rolled per lode when a run ends), fishing
**Fish Flakes / Dried Squid / Sea Feast** (one roll per catch, like coral). Crops are **farming's** food. Combat has none yet.

**Every pet has one fixed skill** (`skill` in `configs/pets.toml`; shown as an emoji after its name: 🎣 ⛏️ 🌳 🌽 ⚔️, or 🌐 for the
global pets Dog, Koala and Phoenix, whose bonus works everywhere). You cannot change it. On the Pets page you look at any pet
(not just the active one), feed it, or make it active. Food of **its skill is worth x3**; a 🌐 global pet gets **x2 from any food**;
food of a different skill is the plain amount. So a specialist levels fastest on its own skill's food, and a global pet is the
flexible, slower choice. **Why a number "jumps":** a bonus is `value x level factor x stars`, where the level factor goes from 0.5
(fresh) to 1.0 (top level; see "Pets: levels to 100" below for today's numbers), so changing `value` from 0.05 to 1 multiplies what you see by 20 only at the same level; the screen now
also shows the max-level number in brackets.
Looking at a pet no longer switches it: **Make active** does. The drop rates aim at roughly 3-5k base pet xp an hour in each
skill (`python -m scripts.balance` prints it); level 100 is 2.94M xp (and play xp adds to it).

| Pet | Does |
|---|---|
| Dog | +bits from Work |
| Cat | shorter wait for a fish to bite |
| Turtle | less mine pressure, more ore |
| Frog | crops grow more often in the rain |
| Monkey | more good chops on trees |
| Koala | +xp in every skill |
| Bee | each harvested plot may give a free extra harvest |
| Eagle | more rare fish |
| Python | faster crab pots |
| Crab | rarer fish in crab pots |
| Dragon | hallucinations and chests more often |
| Otter / Seal | +8% / +14% fishing xp |
| Beaver / Woodpecker | +8% / +14% foraging xp |
| Badger | +14% mining xp |
| Rabbit / Hedgehog | +8% / +14% farming xp |
| Wolf / Lion | +10% / +18% combat xp (combat is coming) |
| Phoenix | +10% xp in every skill |
| Magpie / Raven / Fox | every sale pays more / shipments and the daily pay more / rare drops may roll twice |
| Mole | every dug row adds less pressure |

**Hunting a pet.** Pick a pet to hunt on the Familiar Orbs page and orbs are `8x` likelier to give it, plus `1x` more for every orb
that missed it (up to `40x`), so a long streak of bad luck makes the next orb better. A hit resets the count; a pet you
already have at every star can't be hunted. The chance per orb is shown for every pet and for your hunt.

The pet bonuses stack with the party xp bonus. All numbers are in `configs/pets.toml` (`TODO(balance)`).

## Tool levels (eight each)

Axes, pickaxes and rods have **eight levels**, tuned so a level earns the same in every skill: about x1.5 at level 2, **x2.6 at
level 3**, x4, x6, x9, x13 and **x18 at level 8** compared with the starter (`python -m scripts.balance` prints the table). Axe power
is damage per swing (3 to 54). A pickaxe's power adds +25% ore per point (1 to 69). A rod's power (3 to 120) does three things: bites
come sooner (never below 15% of the wait), rare fish (rarity 4+) are likelier (+2.5% per point above 3) and a catch can bring extra
fish (+0.022 fish per point above 3), while the wrong arrows it forgives are capped at 4. Each upgrade costs about 5x the one before
(axe 20k up to 500M; pickaxe 30k up to 1.2B; rod 100k up to 1.5B), the first two steps use only the tool's own skill, and later ones
add a little from the others. Swords are unchanged until combat exists. Numbers: `configs/items.toml`, `configs/fishing.toml` `[rod]`.

## Tools: buy one, then upgrade it

The shop sells **no tools**: every player gets the four free **starter tools** (`STARTER_TOOLS` in `constants.py`) from `/play` (once ever, tracked by `starter_claimed_<id>` stats) or the **Claim free starter tools** button on the Tools page (for players who predate this), and you can own **one tool per kind**.
Everything better comes from **Inventory -> Upgrade tools**, which turns your tool into the next one up for **bits plus
materials**. Every tool kind has a chain (axes 7 tiers, pickaxes 3, rods 3, swords 4). **The first upgrades use only the
tool's own skill** (an axe wants feathers, hardwood and bark; a pickaxe ore; a rod fish), and **later ones add smaller
amounts from other skills** (a bit of ore, plant fiber, coral...), so most of every cost always comes from the skill
itself. (Swords are the exception for now: combat has no materials yet.) The tool keeps its id, so it stays equipped,
and it keeps its enchants and rolled bonuses. Money, materials and the change happen together or not at all, and a
double click upgrades once. The chains and costs are in `configs/items.toml` under each tool's `[x.tool.upgrade]`
(`TODO(balance)`): axes Starter -> Thornwhip -> Reinforced -> Bastard's Broadaxe -> Masterwork -> Sovereign Hatchet ->
Wilted; pickaxes Rookie -> Reinforced -> Masterwork; rods Starter -> Reinforced -> Masterwork; swords Large Branch ->
Rusted Broadsword -> Dreamnail -> Shining Silver (combat isn't playable yet; their level requirements still apply).

## Enchants from play: scrolls

Enchants (stored on a tool) now have sources. A **scroll** is a one-use item that adds one level of an enchant to a
tool of a fitting kind (never past the enchant's maximum); the scroll and the enchant happen together or not at all.
Use them from **Inventory -> Enchant**. Scrolls are found by playing: **Keen** (+1 power, any pickaxe/axe/rod) and
**Sharp Eye** (+5% good chops, axes) drop from chopping; **Iron Frame** (less mine pressure) drops deep in the mines;
**Lure** (shorter waits), **Steady Line** (forgives more wrong arrows) and Keen come from fishing bosses and treasure
chests. Soloist is unchanged. Chances are `TODO(balance)` in `configs/items.toml`, `mining.toml` and `fishing.toml`.

## Crab pots

An AFK corner of fishing (fishing level 6; 1 pot at 6, 2 at 12, 3 at 20). **Craft** a pot (25,000 bits, hardwood, plant fiber
and coral), put it in a water you have opened, and **load bait**: each catch uses one. While you are away it catches
**rare fish and better only** (never the common ones), one per interval, until it is full or out of bait; you collect
them later (and they are a way to get fish for the collection books). Nothing is scheduled: the number waiting comes
from the clock when you look, and collecting is one transaction, so a second click gets nothing.

It is a side dish, not a money maker. A basic pot earns a few thousand bits an hour (a test keeps it under 4% of fishing
by hand); five pot levels (60 -> 24 minutes a catch, holding 6 -> 24), better bait (**Worm** 300, **Shrimp** 1,500,
**Squid Chunk** 6,000 bits, and the never-sold **Golden Roe** from chests and bosses), and pets (**Python** for speed,
**Crab** for rare fish) stack up, but bait costs bits too, so even three max pots with the best of everything net a
third of what fishing by hand does (a test keeps it under 40%). Everything is in `configs/fishing.toml` `[pots]` and the
bait items (`TODO(balance)`).

## Fishing

`/fish` (or Skills -> Fishing). One panel, no channel spam:

1. **Cast.** The fish is rolled at once from the fishing items' `drop` odds (rarest first; the cod is the 1-in-1
   catch-all), so reopening the panel can't re-roll it. A bite comes after 8-20 seconds; a stronger rod shortens that
   (never below 35%). The panel redraws itself every couple of seconds only while a line is in the water.
2. **A bite.** The panel says "A bite!" and you have **6 seconds** to press **Pull up the line**, or the fish gets away.
   Nothing starts until you do. Then it shows the fish's rarity and a row of arrows; press **Left** / **Right** to match
   them in order (rarity + 2 arrows). A wrong arrow loses the fish,
   unless your rod forgives it (one slip per 8 power). Timing buttons don't work well over Discord, so reeling is
   about order, not speed.
3. **Land it.** The fish goes in your bag, xp is rarity x 30 (plus the party bonus), and **Sell fish** sells the whole
   bag. Nothing is spent to cast, and cancelling a cast costs nothing.

Numbers: `configs/fishing.toml` and the fish/rod entries in `configs/items.toml` (`TODO(balance)`). A test pins the
average catch at ~4-6.5k bits and a catch at ~15-20 s, which is about what foraging earns per second at starter gear.

### A reel with more to it: breaks and mystery arrows

A reel is no longer just ◄ ► repeated. Uncommon fish and up make you **stop and press Reel** (🌀, a third button) between
runs of arrows, about once per four arrows, in a different place every time. **Super rare fish and up hide some arrows
behind a ❓** (one at rarity 4, up to four at 7). The ❓ is secretly an arrow that follows *that fish's own tell*, set in
the data: always ◄, always ►, the same as the arrow before it, or the opposite. Press the ❓ and you find out what it was
even if you guess wrong, and it is written in your **field notes** (on the Records page) as "after ◄ → ►", so you can work
the pattern out over a few catches (a test proves every learnable tell can be worked out from a handful). Some fish are
pure coin flips (`random`): those can't be learned and hide at most two ❓, so they are luck as well as skill. Slips from
your rod still forgive wrong guesses. Bosses have breaks but no ❓.

### Surprises in the reel

- **You see five steps at a time**, then "… +N more" (a tick count for what you have done), so you can't memorise the
  whole pattern.
- **Reel steps are a surprise.** A 🌀 step looks like an ordinary arrow until you get to it, and then the arrow *turns
  into* the Reel symbol: be ready to press **Reel** instead.
- **You can see which fish is on the line** once you pull up the line (name and rarity), so what you have learned about
  that fish (its ❓ tell, in your field notes) can be put to use.

### Bosses with a twist

Each boss has its own twist (or two), shown above the reel: **Mirror** (press the opposite of each arrow), **Reverse**
(work from the end; the next step is on the right), **Shuffle** (the Left/Right/Reel buttons change places every step),
**Fog** (you only see two steps) and **Wild** (three coin-flip ❓ you can only guess). Old Whiskers is a mirror, the Drowned
Duke reverses, Big Mama shuffles, Captain Barnacle is foggy, the Silver Ghost is wild, Grandfather Carp is mirror and
shuffle, and Kraken Jr. is reverse and fog. They are in `configs/fishing.toml` `[[boss.bosses]]`.

### When the connection lags: never lose a fish to something outside your control

Discord sometimes drops or delays a click (the "this interaction failed" message). Fishing forgives that in five ways,
without changing the rules a player sees:

1. **Grace period.** The bite lasts 6 seconds on screen, but the fish is only written off 3 quiet seconds later.
2. **Click time, not arrival time.** Discord stamps every click. If the bot or the connection was slow, the click counts
   from when it was *made* (never later than our own clock, so a wrong clock can't help anyone cheat).
3. **Salvage.** If a fish was already written off but the click that pulls it up was made in time and only reached us
   late, the fish is taken back and the game carries on.
4. **Echo presses.** Pressing the arrow you *just* pressed again within 2 seconds (because the panel was slow to show the
   first press) is ignored, not counted as a wrong arrow.
5. **The hub falls back.** If Discord refuses our answer to a click because it came too late, the panel is updated by
   editing the message directly, and the self-refresh now never queues up behind a click and gives up after 2 seconds on
   a slow edit. This helps every screen, not just fishing.

### Waters

You fish in one of the **waters** your fishing level has opened, picked from a menu on the Fishing page (it defaults to
your deepest): the **Quiet Pond** (level 1), **Winding River** (3), **Coral Reef** (8) and **The Deep Sea** (15). Each has
its own fish and its own odds (`[[waters]]` in `configs/fishing.toml`, `fish = N` meaning 1 in N, rarest first), and
deeper water takes longer to bite (x1.0, 1.0, 1.2, 1.5). An average catch is worth about 3,000 bits in the pond,
5,400 in the river, 7,000 on the reef and 17,000 in the deep, so there is always somewhere to climb to. Daily and weekly
quests and the monthly community goals only ask for fish from the first two waters (the ones open by the level that
unlocks quests), so anyone who has them can finish them; the collection books ask for fish from everywhere, which is
what sends people exploring.

### Bosses

About 1 cast in 80 turns out to be a **boss** instead of a fish. It bites like anything else (nothing gives it away), but
once you pull up the line it is a **15-arrow reel** with your rod's usual forgiveness, and a name ("Old Whiskers"). Land
it and there is no fish to keep: you are paid 80-200k bits, xp and a loot table (coral, a chance at a sturgeon, oarfish
or leviathan pup). Slip and it is gone. Bosses are for one player (no community boss: the community already has the
book and monthly goals). Numbers in `configs/fishing.toml` `[boss]` (`TODO(balance)`). The same long-reel idea is why the
rarest fish already take 7-9 arrows. A chest outranks a boss when both come up.

### Record fish

Every catch has its own size in cm, fixed when you cast (most are smallish, the odd one is a giant: `size.min`/`max` on
each fish). You keep your biggest of each fish; the first of a fish and every new personal best pays a little xp. The
server keeps the biggest ever caught of each fish: beating it pays `2 x` the fish's sell price in bits and names the
old holder ("you beat Ahna"); tying doesn't count. **Records** (from the Book and Community pages) lists your best next
to the server's, with a crown where you hold it, and hides fish you haven't caught.

### One screen after you win or lose

After a win or a loss the hub shows a **result page** of its own (what you caught, how big, what it paid, records and
quests, loot) instead of a line at the top of the page you were playing on. Home/Back are locked there so it is seen
and then you pick **Again** (e.g. "Cast again") or **Continue**. A screen just sets `self.result = Result(...)` and
redraws; the hub (`ui/nav.py`) does the rest, even when the result comes from a timer (a fish that got away). Used by
fishing (catches, bosses, chests, escapes), farming harvests and foraging (a felled tree, the community tree's rewards).
Mining already ends a run on its own summary page.

### Fishing quests (level 3)

Every player gets **5 daily quests** and **1 weekly** (Monday to Sunday), each asking for a **specific fish**: "Catch 6
Sardine". Each quest slot in `configs/fishing.toml` names a rarity and a count range; the fish and count are picked from
the clock and the player, so lists differ between players and nobody rolls or claims anything. (Two slots of the same
rarity get different fish where possible.) Dailies are 2 common, 2 uncommon and 1 rare fish; the weekly is a super-rare
one. Only that exact fish counts. Finishing a quest pays at once: bits = the fish's sell price x count x 1.5 (x 3 for the
weekly), xp = rarity x count x 20, shown in the catch message. Progress is saved with the fishing skill and resets when
the day or week changes. The catch that takes you to level 3 doesn't count toward quests.

### The collection book (fishing level 5; the wiki says 10)

A personal book with a page for every fish up to rarity 4 (common to super rare, 12 of them). **Turn in** a fish and it
fills that page (the book only takes as many as it needs) and pays **+50% of the fish's value** and xp, so turning in
beats selling. Fill every page and **Finish the book**: it pays 50,000 bits x its level, goes up a level and starts over
needing more fish, scaled by rarity: level 2 wants 5 of each common fish, 3 of each uncommon and 1 of each rare and
super rare; level 5 wants 17, 9, 3 and 2 (`need_step_by_rarity`). Up to level 10. Atomic like everything else: a double click can't over-fill a
page or finish the book twice. Numbers in `configs/fishing.toml` `[book]` (`TODO(balance)`; `min_level` is one number
to put back to 10).

### Fish and what comes up with them

19 fish across all 7 rarities (3 mythical-to-premium pairs, the cod as the catch-all). A catch can also bring up a
**Coral Shard** (1 in 6), one of the **pickaxe materials**: every skill drops one so a pickaxe upgrade takes a bit of
everything: ores (mining), **Hardwood** (foraging), **Plant Fiber** (farming harvests) and **Coral Shards** (fishing).

### Hallucinations and treasure

About 1 in 35 catches (a little rarer than the wiki's 1 in 25) makes you hallucinate: the numbers (4 digits) flash on
your panel for 8 seconds, then fade, so you have to remember them. While the hallucination lasts (10 minutes) every
cast has a 1 in 35 chance (as rare as the hallucination itself) to bring up a **treasure chest** instead of a fish. It
bites like any fish, but once you pull up the line it wants the numbers instead of arrows: you get 3 tries in a pop-up
before it sinks. Opening it pays 20-60k bits, xp (at least 150, or a quarter of the xp it takes to finish your current level, so it stays worth
opening as you grow) and a loot table (coral shards, a chance at a sturgeon, oarfish or
leviathan pup, and 1 in 1,000 for the **Spirit of the Sea**). One hallucination at a time; the numbers are used up
when the chest opens or sinks. Everything is in `configs/fishing.toml` `[treasure]` (`TODO(balance)`): with these
numbers about 1 catch in 60 turns into a chest, which is generous.

Catch messages name the fish's rarity.

### Fishing together: the community book and monthly goals

**Fishing -> Community** (level 3) has two shared things, kept as small JSON documents in `community_state` (one
serialized transaction per change, like everything else):

- **The community book** holds 5 rare fish (2 legendary, 2 premium, 1 mythical). Anyone of fishing level 5+ donates
  from their bag with a menu; the donor is paid +100% of the fish's value and xp straight away. When the last page fills
  the book is finished *exactly once* (in the transaction that took the last fish), the server's level goes up and every
  player of level 5+ is owed `300,000 x level` bits and xp. Nobody has to be online: each player collects their share
  the next time they open the page (even for levels they missed). Each level needs more fish (3/3/2/2/1 at level 1).
- **Monthly goals**: three counters for the whole server ("catch 1,500 fish", "catch 150 rare or better", "catch 15 of
  this month's fish"). Every landed fish adds to the goals it fits. A finished goal pays everyone who did at least 5% of
  it, once, collected from the page (this month's and last month's).

Not built yet (wiki): fish that appear in channels like drops.

## Combat (`/fight`; first slice built)

Modelled on Summoners War: **a turn-meter battle with cooldowns and no consumables.** Engine: `services/combat.py` (no Discord,
seedable rng), data: `configs/combat.toml` + `configs/enemies.toml`, screen: `screens/fight.py`. All numbers `TODO(balance)`.

- **Turn meter.** Every unit has a speed; its meter fills by that much per tick and the first to reach 100 acts, then drops to 0.
  The screen shows the next 7 turns, so speed, slows and meter pushes (`meter` effect) are real tactics.
- **Skills, not items.** Each sword gives a *kit* (`[kits]`): skill 1 is always free, the rest have **cooldowns** (a cooldown of 3
  means it is back on your 4th turn). Nothing is consumed. Swords unlock more skills (Rusted Broadsword: Sanguine Priming,
  Dreamnail: Enter the Mind, Shining Silver: Glistening Haven); bare hands only have Slash.
- **Damage** = attack x skill power x 100 / (100 + defense), only crits are random (15%, x1.5). Shields soak damage first.
- **Effects** last N of the *affected unit's own* turns: attack/defense/speed up or down, stun (skips the turn), bleed (ignores
  defense), shield, heal, meter push/pull, empower (next damaging skill x2), reveal (see each enemy's next skill). `chance` is
  rolled per target; an enemy's `immune` list (bosses: stun) blocks an effect outright. Re-applying refreshes, never stacks.
- **Enemies** use the first of their `skills` that is off cooldown, so they are readable. Their next skill is planned ahead
  (`next_skill`); only Enter the Mind shows it for now.
- **Player stats** come from combat level and the equipped sword's power (`[player]`). A fight is a one-off: you start at full hp,
  losing costs nothing, a win pays the enemies' combat xp and counts kills.
- **A fight can last at most `max_rounds` turns** (a stalemate is a loss).

### The final boss (the Gravewarden)
A normal enemy plus three things (`configs/enemies.toml`): **telegraph** (you always see its next skill), **immune = ["stun"]**, and
**phases** (`[[gravewarden.phases]]`): when its hp drops below a mark (60%, then 30%) it says a line, gives itself buffs and may swap
skill lists (cooldowns reset). A big hit can skip a phase. Its **Death Knell** (x3 damage, every 5 turns) is the thing to plan for:
**Brace** (every sword kit has it: x4 defense for 2 turns), slows, and killing it faster. The boss is a touch slower than a fresh
player, so you always see the first knell before it lands. Locked to combat level 20 for now; numbers are placeholders (a Dreamnail
at level ~25-30 is the intended first win). Its xp is 1,500. Keys and loot attach to this encounter later.

### Drops and keys
Drop tables live in `configs/drops.toml` and are shared by everything that drops things: a table is a list of weighted entries, each
**bits (a range) or an item (a range, skewed low)**. An enemy names a table (`drops`) and a `drop_chance` (percent of kills that drop
anything); the real odds of an entry are drop_chance x weight / total. The graveyard table is mostly bits and common materials with
tiny weights for scrolls, Familiar Orbs, Land Deeds and the Spirit of the Sword; the Gravewarden's table always drops and is better.
Rolled in `services/loot.py` (`roll_kill`, `roll_drop_table`), paid by `combat.settle` (only for a win; a loss pays nothing, even if
you killed something first).

**Keys.** The Gravewarden's encounter has `key = "graveyard_key"`: you need level 20 and a key, and the key is **spent when you walk
in**, win or lose (checked in `combat.start_fight`; a missing level never costs a key). Keys are just an entry in the graveyard table
(about 1 kill in 30) and in the boss's own table, so winning can fund the next attempt.

Planned: the **channel drops** (`exts/economy/drops.py`, still the old Mongo code) will roll the same tables, so a channel drop can be
bits or any item; then party fights (several player units already work in the engine).

## XP and the level curve (audit, `python -m scripts.balance`)

The curve is quadratic: total xp for level L is ((L-1)/0.07)^2. Level 10 = 16.5k, 20 = 73.7k, 50 = 490k, 90 = 1.62M, 100 = 2.0M. The next
level costs 3.9k at L10, 8k at L20, 20k at L50, 36.5k at L90. Measured with a click every 5 seconds:

| Skill | xp/hour starter gear | xp/hour top tool | Hours from level 1 to L20 / L50 / L90 (starter) |
|---|---|---|---|
| Mining | 7,100 | 7,100 (pickaxe adds ore, not xp) | 10 / 69 / 227 |
| Foraging | 7,000 | 128,000 (xp = hp chopped x 3, faster axes chop more) | 10 / 70 / 230 |
| Fishing | 7,000 | 79,000 (rarer fish, extra fish) | 10 / 70 / 230 |
| Combat (lone zombie, level 1) | 6,800 | grows with tougher fights | 11 / 72 / 238 |
| Farming (9 plots, best crop) | 490 | 490 | 150 / not realistic |

Findings:
1. **Starter-gear xp is already consistent at about 7k/hour** in the three active skills, and now combat matches.
2. **Farming xp is far too low**: xp is crop rarity x 20 per harvest (20 to 120 xp), no matter how long the crop takes. A coconut is 100
   cycles for 80 xp; ambrosia is 777 cycles for 120 xp. Even the best crop on 9 plots gives 490 xp/hour. Proposal: xp scales with growth
   time (about 450 xp per cycle: apple 450, coconut 45,000, ambrosia 350,000), so 9 plots are worth about 4k/hour, a bit under the active skills.
3. **Tools scale xp unevenly.** Foraging and fishing xp grow about 11x to 18x with the top tool, mining's stays flat. Top-tool foraging
   reaches level 90 in about 13 hours, which skips the curve. Proposal: decide whether xp should follow tool power; if so, mining needs it too.
4. **Combat**: enemy xp must scale with the level the fight is meant for, like foraging zones do. Boss xp is sized as "about one level at
   its level lock" (8,000 at level 20) because keys keep it rare, not as an hourly rate. Fights for levels 20 to 90 still need tiers.

### XP rules (decided): tools never change xp
**xp comes from rank, party and pets (and the level you are at in the content). A better tool makes the base mechanic easier or faster.**
Enchants, pets and so on buff the fun parts. What that means per skill (all `TODO(balance)`):
- **Mining**: `xp_per_column` per column dug. The pickaxe adds ore yield, never xp.
- **Foraging**: `xp_per_swing` x the **quality of each chop** (the grain and good chops, never the axe's power). A stronger axe fells a
  tree in fewer swings, so the same minute of chopping pays the same xp. Private, party and community trees all record each chop's
  `effort` (the community table has a new `tree_chops.effort` column, migration 0007).
- **Fishing**: every landed fish pays its **water's** `xp` (pond 46, river 55, reef 65, deep sea 90): not the fish's rarity, not the number of
  extra fish. Deeper waters pay more because you needed the level. What is left: a better rod bites sooner, so about 2x more catches an hour at the top.
- **Farming**: xp = the seed's growth cycles x `xp_per_cycle` (500): an apple 500, a coconut 50,000. 9 plots are worth about 4k xp/hour.
- **Combat**: enemy xp by the fight's tier; the sword changes how fast you win, not what you are paid.
At starter gear that is about 7k xp/hour in mining, foraging and (about 8.5k) fishing, 6.8k combat, and a passive 4k farming.

## The Bestiary (the Coconut Level was removed)

**The Coconut Level is gone** (decided): there is no global level, no Progress page, no tier colors and no avatar picture on Home. Home is your name,
rank, balances and check-in, then Party, Skills and Minigames. (It had been a calculated sum of one-time milestones; the code, its config
`progress.toml` and its tests were deleted, not hidden.) Mastery points come from skill levels only.

**Wiki vs Bestiary.** The wiki stays a reference you can always read (how things work). The **Bestiary** (the `/fight` lobby and **More**)
tracks what you have *done*, and it holds every creature, not only monsters: combat enemies (`combat.kills`, only for won fights), every fish
species (`fishing.stats.caught`, extras included; a personal-best record counts as "met" for old players) and the fishing bosses
(`fishing.stats.bosses`, by name). Each is "Unknown" until you meet one; a monster shows its stats, and its moves once you have fought a few.
The counts never stop climbing; `configs/bestiary.toml` only holds the goals the page shows next (`next goal 25`). It pays nothing.
`services/bestiary.py` `creatures()` is the one list, so **later** creatures in mining, farming and foraging join by adding a counter to that
skill's stats and a few lines there.

### Pets: levels to 100, a wide range, and they level as you play (decided)
- **Levels 1 to 100** (`max_level`, `xp_scale = 300`: level 20 is 108k pet xp, 50 is 720k, 100 is 2.94M). A bonus `value` is what a pet gives at
  **level 100 with one star**; a new pet gives `level_floor` (10%) of it, and every extra star adds +25% (a five-star level-100 pet gives double). So a pet
  grows about 20x from fresh to the top, not the 3-5% it used to span. Every listed bonus value was doubled (Koala all-skill xp 10%, up to 20% at five stars).
- **They level as you play**, like Skyblock pets, not only from food: your **active** pet gains `play_xp_share` (50%) of the xp you earn in **its own
  skill**; a global pet gains `play_xp_global` (25%) from every skill; a pet that looks after a different skill gains nothing from it. Done in one place
  (`User.add_xp` and `User.update_skill` both call `pets.grant_play_xp`), so every skill works without being touched, and the xp counted is what you were actually paid.
- Feeding still works and is faster (food x3 for its own skill, x2 for a global pet). Existing pets keep their xp; they simply land at a higher level.

## Tool forks and the Mastery tree (pilot built for mining and fishing)

Problem: every ladder is one chain of "more power", so everyone makes the same choices and the late steps are poor value (payback of 200-300
active hours for x1.35). The fix is two layers, **tools** (what you wield) and **Mastery** (how you play), and neither touches xp.
- **Tool forks.** From about tier 3 a tool upgrades into one of two or three different tools instead of one: each has its own ability and some
  stats are better and some worse (axe: Broadaxe, fewer bigger chops with a finishing crit, vs Hatchet, fast chops that build a combo; pickaxe:
  one branch lowers the danger meter, the other digs richer lodes for more pressure; rod: faster bites and more slips vs slower with more
  treasure and bosses). Switching costs bits. Data: `upgrade` becomes a list of branches; `ability` already exists on tools.
- **Mastery tree per skill:** about 3 branches x 5 nodes, so you cannot fill it and must choose. Points come from skill levels (e.g. 1 per
  5 levels) never from upgrade count. Respec costs bits. Every node is a trade-off that
  bends the skill's own mechanic (mining: Safe / Greedy / Gem hunter; fishing: Angler / Treasure hunter / Trophy; foraging: Solo / Party /
  Forester; farming: Gardener / Trader / Botanist; combat: its kit pool is already this). Nodes may give bits or drop bonuses (this is
  where tool bits/drop multipliers live; **tool parts are deferred**).
- **Balance rule:** at equal investment every branch earns within about 10% of the others in bits per minute (checked with the balance script).
  Differences are playstyle, not power.
- **Pilot:** mining and fishing first, then foraging and farming. The first Mastery branch opens at skill level 5 and the first tool fork at 10.
- **Level unlock audit** (today): mining magnet 5 and gems 10, farming market 5, foraging Releaf Foundation 10 and zones 4, 7, fishing quests 3, waters
  3/8/15, pot 6, book 10, combat fights 3/8 and the boss 20. Gaps to fill: foraging and fishing at 5, farming at 10, combat at 5.

**What the pilot built** (all numbers `TODO(balance)`):
- **Mastery** (`configs/mastery.toml`, `services/mastery.py`, `screens/mastery.py`, a "Mastery" button on the mining and fishing pages): one point per
  5 skill levels (20 at level 100), spent on nodes. Each skill has 3 branches of 5 nodes in a line (each needs the one before it and a skill level
  5/10/20/35/50, costing 1/1/2/2/3 points, so a full branch is 9 and you cannot take all 27). Mining: **Safe Digger** (less creaking, braces),
  **Greedy Digger** (more ore and rich lodes, creakier tunnel), **Gem Hunter** (vault gems). Fishing: **Angler** (faster bites, forgiven arrows),
  **Treasure Hunter** (chests, rare fish), **Trophy Hunter** (more bosses and rare fish, slower bites). A node's effects are plain tool-style stats
  that `equipment.equipped_stats` adds to the equipped tool, so the games read them like they read an enchant. Respec clears a tree for 100k bits.
  Stored as `mastery: [node ids]` on each skill. Nothing touches xp.
- **Tool forks** (`Tool.fork`, `Tool.path`, `Tool.stats`): the Masterwork Pickaxe and Masterwork Rod each branch into two roads of the same power
  and cost at every tier, with different stats: pickaxe **Warden** (2% less creaking per tier) vs **Prospector** (11% more ore and 0.5% more creaking per tier; a mining simulation that leaves at 7% collapse risk puts the two roads within about 5% of each other at tiers 4, 6 and 8: 1.09, 1.01, 1.03); rod **Angler** (faster
  bites, extra forgiven arrows) vs **Treasure Hunter** (rare fish and treasure, slower bites). The upgrade page shows both roads with what each does
  and warns it is a fork. The shop allows one tool per kind, so the road you take is the one you climb. The rod roads are NOT simulated yet (treasure and rare-fish luck are hard to price). **Not built yet:** changing roads later for bits.
- **Still to do:** foraging and farming Mastery trees, forks for the axe, a numeric balance pass that the two roads really earn about the same
  (the rule above: within ~10%), and the level 5/10 unlock content.

## The watering can and farming drops (decided)
- **A new tool for farming: the watering can** (`kind = "can"`; Tin, Copper, Iron, Silver, Gold, Crystal, Moonwell; the Tin Watering Can is
  sold for 2,000 bits and equips itself like the other starter tools). Its **power is how many plots it waters an hour**, 3 up to 9 (the whole farm).
- **Watering is now 100%**: a plot you water always grows a cycle, once an hour per plot, on top of the rain. If the can cannot reach every
  growing plot the lowest plot numbers go first and the page says how many stayed dry. Plots you watered earlier in the hour use up the can.
- **Tools never change xp, so the can does not grow crops faster than that.** Past the first four it gives other things instead: `crop_yield`
  (bigger harvests, +5% to +25%) and `drop_luck` (more farming drops, +15% to +50%). Capacity is the main draw: a bigger farm needs a bigger can.
- **Farming drops:** a harvest rolls the farming drop table once per `drop_cycles_per_roll` (4) growth cycles of the crop (a long crop pays for
  the waiting; at most 30 rolls). New materials, each rarer than the last: Rich Compost (1 in 3), Morning Dewdrop (1 in 12), Beeswax (1 in 40),
  Living Vine (1 in 150), Golden Pollen (1 in 600), besides Plant Fiber. They upgrade the can and are also in a few steps of every other
  tool (axe, pickaxe, rod and sword), so farming feeds the rest of the game.
- Existing farmers have no can: they buy a Tin Watering Can first (the Water button says so). `free_plots` is a balance dial (a player set it to 3 by hand).

## Less on the screen (decided)
A pass over the busiest pages to cut text without cutting information. The rules we follow from now on:
- **One line per thing.** A list row is `name · number · one short fact`; ranges, odds and flavour go where you choose or act (a menu description,
  the note after you click), not on every row. Example: a growing plot reads `3 🍋 Lemon 2/4 💧 · ~28h`; the full "about 28h (22h to 35h)"
  appears once, when you plant, and the seed menu says `~8h`.
- **Collapse the unknown.** Many "???" rows become one line (`❓ 21 fish nobody has caught yet: Common 3 · Rare 3 ...`) on Records and Field notes.
- **Costs: one requirement per line** (`needs_text`): `✅ 20,000 bits`, then `❌ Feather 0/40`, then `❌ Hardwood 0/6`, each on its own line (squeezing them onto one line looked bad), used by upgrades, pots and crafting.
- **Mastery** shows each node on one line; **Collection Book** shows two fish per line; a few intro paragraphs became a single line.
- **Farm pages:** nine plots to a page (three rows of three) with Prev / Page n/N / Next once there is more than one page. The farm model has room
  for 27 plots (`MAX_PLOTS`); `services.farming.PLOTS` is how many exist now (9). **Plant page** plants only the plots on the page you are looking
  at; Harvest all and Water cover every page.
- **Shop:** tools come first in every section; once you own a kind of tool its Buy button becomes **Upgrade tool** and opens the upgrade page.

## Tools page, vault and Home (decided)
- **Tools page** (`screens/tools.py`, from Inventory, the Upgrade page and the shop's Upgrade tool button): every tool you own with its skill, power and
  road, a check mark on the equipped one for every skill (the watering can was missing from the inventory's check), an Equip button, and Upgrade /
  Enchant / Inventory buttons. With one tool per kind equipping is mostly automatic, so the page is mainly the doorway to upgrades; it is the place
  to grow if tools ever differ (an open question: the game may not need alternates).
- **The mining vault** pays all three ores in the proportion you would mine them (the rarer, the fewer). It first paid 1,100 copper / 300 iron /
  100 gold, but that covered the whole ore ask of the Masterwork pickaxe in one visit, so it was **cut to a third: 330 / 90 / 30** (one vault is
  about a third of the iron Masterwork needs). In the balance simulation the vault was about 75% of mining's bits, so **ore sell prices doubled**
  (copper 20, iron 200, gold 2,000) to keep mining near where it was: mining is now about 85% of foraging per click at that simple strategy
  (it was ahead). The upgrade bits costs did not change. Gems are unchanged.
- **Skills page:** each skill is its name, level and xp bar and an Open button; no blurbs.

## Inventory, the upgrade page, and how fast each skill upgrades its tool (decided)
- **Inventory** lists stacks only (tools are on the Tools page) and has **Sell** (opens the shop in sell mode) and **Tools** buttons; Enchant lives on the Tools page.
- **Upgrade Tools** shows **one tool per page** with Prev / n of N / Next (a tool at a fork shows both roads on its page).
- **Pace check** (hours of play to gather the materials for the tier-3 step, at that tool's income): mining about 0.5 h (ore pours out: 36 copper a
  minute), fishing about 1-2 h (but across several waters), foraging was **6+ h** (hardwood 1 in 6 and fine bark 1 in 30 per roll, 170 hp a roll),
  farming's can **days** (passive). So the others were brought up, not mining down:
  - **Foraging:** `hp_per_roll` 170 -> 70 (2.4x the rolls), hardwood 1-in-6 -> 1-in-3, fine bark 1-in-30 -> 1-in-12, and `bits_per_hp` 230 -> 60 so the
    pay stays the same (about 11k bits a minute): the income moved from bits to materials. The first two axe steps now take about 1.5-2 h.
  - **Fishing boss:** a sure haul of salmon (6-10) and trout (8-12), pufferfish and tuna sometimes, on top of the coral and rare loot.
  - **Farming:** the drop table rolls once per 2 growth cycles (was 4), up to 60 rolls.

## What a tool's power means, and every tool starts at 3 (decided)
- **Every tool starts at power 3** (pickaxe, axe, rod, can, sword). The pickaxe used to start at 1 and the sword at 1: both were moved up by 2 all the way
  up their chains, and the formulas moved with them so nothing changed in play: ore per lode is `1 + 0.25 x (power - power_base)` with `power_base = 3`
  in `mining.toml` (Rookie x1.0, Reinforced x1.5, Masterwork x2.5 as before), and the sword's `base_attack` went 14 -> 8 (a starter sword still hits for 17).
- **Every upgrade changes several things at once** (`configs/tools.toml`, `services/tool_effects.py`): besides its main effect each tool's power also gives extras,
  per point above 3, so a starter tool gets none. Pickaxe: ore per lode, slower pressure (0.3%/pt), rich lode chance, a spare brace every 25 points. Axe: hit points
  per chop, good-chop chance (0.2%/pt), spots that wear out slower (0.5%/pt). Can: plots watered, bigger harvests (4%/pt), more drops (8%/pt), the seed comes back
  (3%/pt). Sword: attack (+3/pt), max hp (+3/pt) and defense (+0.25/pt). Rod: bite wait, forgiven arrows, rare fish, extra fish. The extras are merged into the
  tool's stats (`equipment.effective_stats`), so every game reads them like it reads an enchant, and the can's old hand-set per-tier stats were dropped for them.
  The fork roads keep their own stats on top.
- **What power does**, said on the upgrade page (`services/tool_effects.py` reads the real rules, so it cannot disagree with the game):
  pickaxe = ore per lode (x); axe = hit points a chop takes off; can = plots watered an hour; sword = attack added in a fight (+3 a point);
  rod = shorter wait for a bite, forgiven wrong arrows, rarer fish and extra fish per catch.
- Each upgrade page opens with that one-line meaning, then for the next tool shows **before -> after for every effect** ("Ore per lode: x1.00 -> x1.50"),
  its extra stats and road, and any new ability. Rolled and enchant power carry over to the next tool, and the page counts them. The Tools page shows each tool's numbers.

## Fishing: a clean reel pays, and the cast tells you how long to wait (decided)
- **Unused slack pays.** The rod forgives wrong arrows ("slack"); once you know the patterns that safety net is never used, so now every slack you did **not**
  need pays `reel.slack_bonus` (8%) of the catch's worth in bits (a boss: of its bits), counting the extra fish a good rod hauls in. Bits only, never xp. The
  reel page says "each one unused pays a bonus"; the catch page says "Clean reel! N slack unused: +X bits". A better rod forgives more, so it can pay more.
- **The cast shows the wait**: "A bite in about 17s  ·  a starter rod: 29s" (the typical wait for your rod, pet and water, beside a starter rod's), so an upgrade is something you feel.

## Where the bits come from, checkpoints in the mine, and the sell list (decided)
- **Where players' bits really came from:** the **Work** button (every 6 hours) at 240k-375k a claim at ranks 6-7, plus the mining vault: a rank-7 player
  who pressed Work twice already holds 750k without selling anything. Next to that, an hour of mining at starter gear is about 570k bits and a single
  ore sells for 20-2,000, so selling felt like pocket change. **Wages were cut to 30% from rank 2 up** (rank 7: 375k -> 112k, 4 claims a day is about
  450k, under an hour of play), so skills and what you gather are the economy. Ranks 0 and 1 still pay 2,500 for a start. Other direct payouts (fishing
  quests at about 6x the fish's worth, boss bits, community books, the double-tree jackpot) were looked at but not changed yet.
- **Checkpoints** (`[[descent.milestones]]`, rows 10 and 20; the vault is row 30): finishing one makes a checkpoint, so what is in your pack is safe from
  a collapse from then on (a collapse takes its share only of what you dug after it). The rows ahead show 🏁 checkpoint and 🏆 vault, and the header says
  how far the next landmark is. A milestone can also give pressure relief, braces or a taste of the vault's ore, but each of those made the vault much easier
  to reach (relief of only 4/6 raised the vault rate from 12% to 18% and the mine's pay by 70%), so they are off by default.
- **Sell list:** a stack reads `x7 · 500 each · 3,500 for all` under the item's name (the count is plain text, not part of the bold heading).

## Reading the rock, flatter sell prices, and the income guards (decided)
- **Read the rock** (`MineRun.feel`, `soft_below` / `hard_from` in `mining.toml`): from above a cell feels 🟫 **soft** (pressure under 5: copper, nothing, vents, caches),
  🟧 **firm** (5-8: iron) or 🟥 **hard** (9+: gold), or it is a highlighted rich lode or a wyrmhole. Harder rock costs more pressure to dig and is where the better
  ore is, so which column to dig is a real choice (a test checks that on average hard cells hold more and cost more). What is *inside* (ore, nothing, a vent, a cache) is
  still hidden. Veins and spending ore on safety were dropped.
- **Sell prices were flattened** so common finds are worth something and the very rare ones are not most of the pay, keeping each skill's income (the exact
  per-roll value) the same. Foraging: feather 100 -> 1,600, hardwood 500 -> 5,500, fine bark 30k -> 36k, maple leaf 500k -> 330k, aged feather 7M -> 3.6M, spirit 500k -> 400k.
  Mining: copper 20 -> 50, iron 200 -> 300, gold 2,000 -> 1,900, gems 100k -> 45k, spirit 500k -> 160k. Fishing and farming were already spread out and are unchanged.
  Before, foraging's pay was 38% one 1-in-1,000 feather and 33% one 1-in-100 leaf, so a normal session was pennies and a lucky one was a fortune.
- **Income guards** (`tests/test_economy_guard.py`, same simulations as `python -m scripts.balance`): an hour of mining, foraging and fishing at starter gear each
  pays 6k-20k bits a minute and no skill out-earns another by more than about double; no foraging drop is more than 35% of its pay and the everyday finds are at
  least 15%; no ore or find is more than 55% of mining's; a rare drop is at most 3,000 times a common one; four Work claims a day at ranks 0-7 pay less than an hour of
  mining. When one fails, a payout was changed without looking at the others.

## Bigger mine loot pools and the scarab (decided)
- **Ten new finds**, so each kind of rock has a real pool (coal, clay, amber and copper in soft rock; tin, silver, garnet, iron in firm; obsidian, platinum,
  sapphire, emerald and gold in hard; the gems and the spirit stay deep). They are in the depth tables, so the pool opens up as you go deeper (the top of the mine
  has 4 things to find, the bottom 20). **They only sell for now**; crafting and other uses come later. Their prices were tuned so mining pays what it did
  (857 bits a click in the simulation, was 860). Harder rock holds the better things (a test checks the medians).
- **Subterranean scarabs** can show up after **any** mine, however it ended (a safe exit, the vault, a collapse or a wyrmhole), 1 in 12 mines (it was 1 in 51
  and only after a safe exit). The scroll takes **45 seconds** to unscramble (was 30). The old "level 6" bonus level never existed; the text now just says it will
  reward you. A solved scroll gives one **prize by weight** (`[[scarab.prizes]]`): 3 scarab bombs (35), 1,500 mining xp (35), a hoard of ore plus 400 xp (20) or a
  sapphire and an emerald plus 800 xp (10). The xp gets the usual party, rank and pet bonuses.

## The forks got real: abilities, different numbers and different materials (decided)
A road is no longer "the same tool with other stats". Each road of a forked tool has its **own ability**, leans its **numbers** a different way, and is built from **its own materials**,
so the choice is also a choice of what you go out and collect.
- **Pickaxe, Warden (safe):** **Auto-Bomb**: every 32 rows at the first tier down to every 14 at the last, a charge blows the whole row for free (flat pressure, no collapse check). It keeps
  the pressure slow (x1.6) and braces, and has no rich-lode bonus. Built from **soft and firm rock**: coal, clay, tin, iron, silver, amber, garnet.
- **Pickaxe, Prospector (greedy):** **Multi-Mine**: each dig has a 25% chance (60% at the last tier) to bite the rock beside you too (its hardness adds pressure). It gets **no pressure slow
  and no braces**, but extra ore per lode (+11% per tier on top of x4.0 and so on) and 2.5x the rich-lode chance. Built from **hard rock**: gold, obsidian, platinum, sapphire, emerald.
  (`configs/tools.toml` `[pickaxe.paths.*]` holds the weights; the abilities and stats are on the tools in `items.toml`.) A mining simulation (leave at 7% risk) puts the two roads within about
  10% of each other at every tier (1.05, 1.01, 0.95, 1.10, 1.03 for Prospector over Warden), tuned with the intervals and chances above.
- **Rod, Angler (steady):** **Auto-Reel**: the first 1-3 plain arrows of every reel are pressed for you (never a Reel break, a ❓ or the last press), plus faster bites and extra forgiven arrows.
  Built from **river, pond and reef fish**: salmon, trout, catfish, pike, muskie, sturgeon, oarfish, golden koi.
- **Rod, Treasure Hunter:** **Bycatch**: 10% to 30% of catches also bring up a second, **different** fish from the water; plus rare-fish and treasure luck, slower bites. Built from
  **deep-sea and rare fish**: swordfish, tuna, marlin, giant squid, abyssal angler, leviathan pup. (The rod roads are not simulated; their numbers are a first guess.)
- **Materials per step** were generated so each road takes about as long to collect as the old shared recipe did (each step's rate of finds at that tool's power), keeping non-mining extras like
  hardwood and coral the same for both roads. The upgrade page shows each road's ability, its own numbers (`Pressure builds: 2% slower -> 6% slower` for the Warden, `-> 0% slower` for the
  Prospector, ore per lode including the road's extra ore) and its materials. The ten new mine finds now have a use.

## Party invites without chat spam, party tree rewards you always see, and party boss fights (decided)
- **Invites are never posted in the chat.** They show on the Party page only (the inviter gets a private note); the old Join/Decline message (`ui/party_invite.py`) is gone.
- **A party tree a teammate fells while your panel is old** no longer says "no party tree": a chop on the old panel just redraws it, which collects and shows your rewards. And **a result
  that never reached you is never lost**: the hub (`ui/nav.py`) remembers the last result page it built until an edit of the message succeeds, and shows it on your next click (a self-refresh
  of a message older than 15 minutes cannot be edited, which is how rewards used to be paid without being shown).
- **Party boss fights** (`services/party_boss.py`, `[boss.party]` in `fishing.toml`): when a member of a party of two or more **hooks a boss**, a fight opens for the party for 180 seconds.
  The others see "💀 Old Whiskers is on your party's line! Join the fight" on their Fishing page (it redraws by itself while a fight is open). Joining gives you your **own set of
  arrows** (the same boss and twists, a different reel, with your rod's own slack). Everyone who lands theirs is paid the boss's rewards, with **+25% for every extra teammate who landed
  theirs, up to double**, plus their own clean-reel bonus. Slipping off the hook (or letting it go, or running out of time) only loses your own share; if nobody lands theirs it is lost.
  One fight at a time per party (a second boss is a solo fight). The fight is settled once in one transaction and each member collects their payout from their Fishing page, like a party tree.

## Sell all, accomplishments, shipments (latest)

- **Sell all** button on every skill page sells that skill's rewards in one click. It asks first unless the player turns off the `confirm_sell_all` setting (on by default). It can keep what your next upgrade still needs.
- **Bits come mainly from selling.** Daily interest and some accomplishments still pay bits, but big accomplishments (quests, books, community goals, bosses) now pay much more *xp*. The double-tree jackpot pays foraging xp (`double_xp`) instead of a million bits.
- **Shipments** (`configs/shipments.toml`, `services/shipments.py`): tasks you fill with materials from several skills, then ship for bits (1.3x their sell value) and xp in the skills involved. Each player has 3 crates: two themed on a skill (a few of its materials plus others) and one mixed. Shipping replaces the crate in the same slot. A weekly *community* shipment is filled by everyone; once full, everyone who gave at least 2% of it claims 1.5x what they gave plus xp. State lives in the community store (`shipments:{uid}`, `shipment_community`), so there are no migrations.
- **Settings audit** and **combat redesign** are still open (see HANDOFF).

## Combat paused, settings, upgrade paths

- **Combat is paused** while it is redesigned: the Skills page shows a disabled "Paused" button, `/fight` says so, and nothing links to the fight screen (code and tests stay). Ideas for the rework: stance/counters, a resource/combo system, interrupts and targeting.
- **Settings** (Settings page, all saved per player): `confirm_sell_all` (on), `keep_upgrade_materials` (off: Sell all always holds back what your next upgrades need), `confirm_upgrades` (off: upgrades take a second "Sure?" press), `fishing_estimate` (on). A test keeps the page's list equal to the `Settings` model.
- **Upgrade paths**: a tool at a fork shows one path at a time, swapped with a "Pick a path" dropdown; tools are still one per page.
- **Shipments cooldown**: deliberately none. Materials are the limit and shipping only pays a modest premium over selling.

- **Shipments page**: one shipment per page, swapped with a "Pick a shipment" dropdown (your crates, then the community one). It has its own section on Home between Skills and Minigames (no longer on the Skills page).

## Easier shipments and gifting

- **Shipments are easier.** Personal crates ask for about 40% of the old materials (`value_base` 60,000, `value_per_level` 6,000) and pay more xp per bit. The weekly **community** goal is sized when the week starts: players active in the last `active_days` (floor `min_players`) times (`value_per_player` + `value_per_level` x their average skill level). It is stored with the week (`players`, `value`) so it never moves mid-week, and the page says who it was sized for. Pool rarity follows the average level.
- **Trading** (`services/trade.py`, `screens/trade.py`, `/trade`, buttons on Inventory and More): you ask a player to trade (the request waits a minute on their Trade page). When they accept, both see one shared window: each adds items and bits to their own side, and the trade happens when both press Accept. Any change takes both Accepts back, and an Accept only counts for the offer version the player was looking at, so nobody can swap things in after you agree. A trade where one side adds nothing is a gift. Finishing takes both sides' things first (giving them back if any are gone), then credits both; the window is closed before anything moves, so a double press trades once. Rules: human players only, bits entries at least 100, ordinary stackable items only (no tools or gear), one trade at a time each, a window closes after 10 idle minutes. Windows live in memory. `/pay` is unchanged.

## Shipments by skill, and the Home layout

- **Shipments**: every skill has a *basic* crate (unlocks at that skill's level 10) and a *hard* one (level 30, about 4x the value and a better rate), sized by that skill's level so a player at the unlock level can finish it. Crates are mostly the skill's own materials with a few from others, shipped for xp in the skills involved. Old three-crate saves are cleared and whatever was inside is handed back. **Community shipments are off** (`[community] enabled = false`); the rules and code stay.
- **Home**: page 1 is balance + check-in + party line, then Skills, Shipments, Minigames, and two rows of buttons (Check-in, Inventory, Shop, Trade / Party, Pets, More). More holds Profile, Rank, Leaderboard, Stats, Bestiary, Wiki, Settings.

## Tool lines: three plain upgrades, then the split

Every tool line now has the same shape: **three plain upgrades, and the 4th upgrade is the split** into two roads that keep climbing. The pickaxe and rod got one new plain tier each (Steel Pickaxe, Sturdy Rod) so the split stays at the 4th upgrade without moving anyone's existing tools. The **axe** splits into **Lumberjack** (the old line; `timber`: chops land twice, via `double_chop`) and **Forager** (new; `shake`: a chop sometimes shakes loose a drop, paid on the spot). The **can** splits into **Sprinkler** (the old line; `sprinkle`: a watered plot sometimes grows a second cycle) and **Alchemist** (new; `transmute`: some harvests come up double). Each road has its own numbers (`configs/tools.toml [axe.paths.*]`, `[can.paths.*]`) and asks for different materials. TODO(balance): the road numbers still need a simulation pass, like the capstones.

## Mastery for every skill, with capstones

Mining, fishing, farming and foraging (not combat: it is paused) each have a tree of three branches, five nodes each. The last node of every branch (level 50, 4 points) is a **capstone** that changes how you play, tuned so the three in a skill are worth about the same (each adds roughly a fifth to that skill's income; guard tests in `test_mining.py`, `test_fishing.py`, `test_foraging.py`, `test_farming.py`). Mining is simulated with the real mine; the others are estimated from the config (see each test's docstring).

- Mining: **Lifeline** (a brace back every 15th row), **Gold Rush** (every 7th cell pays triple), **Geode Cracker** (2% of cells hold a reactor gem).
- Fishing: **Hot Streak** (each clean reel in a row makes your next catch pay 8% more, up to 5), **Salvage** (every 13th fish also brings a chest haul), **Chum Slick** (a boss you beat pays twice).
- Foraging: **Final Cut** (a tree you fell yourself pays 25% more), **Windfall** (every grain you finish clean, every chop in its own style, shakes loose a roll of drops; it counts grains, not chops), **Clean Cut** (right-style chops hit 20% harder).
- Farming: **Evergreen** (half of harvests replant free), **Heirloom** (30% of harvests are 60% bigger), **Haggler** (farm goods sell for 15% more).

Players who had taken an old level-50 node get those points back (unknown nodes are ignored).

## The fishing radar

A gadget (an upgrade level on your fishing skill, like the mining reactor, not a rod) that opens at fishing level 25. On the Radar page you pick the fish to chase (slots grow with its level), switch it on, and every cast in a water where a target lives uses one **Radar Battery** (3,000 bits in the shop). Chased fish are 1.4x to 3.3x likelier (their own odds are divided by the factor). Five levels cost bits and fish from the deeper waters. Balance: at level 1-2 it barely pays for the batteries (it is for chasing a quest, book or community fish); at level 3+ chasing the expensive deep-sea fish adds about a quarter to two-thirds to a cast's worth.


## Wedges, the burger, rare-drop fanfare, emoji

- **Wedges leave a lasting bonus.** A plain Rotation Wedge only moves you. Iron: also +20% damage and xp for 40 chops; Gilded: +50% for 120 chops (`boost`, `boost_chops` in `configs/foraging.toml [[rotate.wedges]]`). The bonus lives on the `Spot`, follows you when a worn spot moves you on, and a new wedge replaces it (no stacking).
- **Burger** is now a pet feast (`pet_food.xp_mult = 5` on a tier-3 food: 25,000 pet xp, x3 to a foraging pet). Not sellable.
- **Scroll wiki pages** show the enchant they apply (its description, what it goes on, max level).
- **Rare-drop fanfare** (`cococap/ui/flair.py`): level 1 (rarity 4+, odds 1-in-100 or rarer) is a highlighted line; level 2 (rarity 5+ or 1-in-700+) is a big banner. Everyday finds, fish and crops never get one. Wired into chopping, digging, banked mining loot, fishing extras/boss loot/chests and farming extras.
- **Emoji:** every item and enchant now has a placeholder emoji (a test fails if one has none), ready to be swapped for custom ones.

## Seasoning trade-off, everything sells, rare scrolls, no chop bits, Back = up one level

- **Wear-slowing gear is a trade.** `wear_slow` (Seasoned, axe stats, mastery) slows plain and good grains and speeds BAD grains (grain wear above 1: knotty, twisted) up by the same amount, so you leave bad spots sooner.
- **Everything but tools can be sold** (seeds, bait, keys, deeds, orbs, scrolls, pet food; a test enforces it). **Sell all** still leaves the things you keep to use (`KEPT_BY_SELL_ALL` in `services/shop.py`: seeds, bait, key items, scrolls, pet food, pet items).
- **Scrolls are rare**: foraging 1-in-3,500 to 1-in-6,000 per drop roll, mining 1-in-6,000 (moved ahead of the gemstones in the depth tables so the list stays rarest-first), fishing chest/boss chances quartered, combat weights cut. They sell for 400,000+.
- **Chopping pays no bits** (`bits_per_hp = 0`): foraging pays xp and drops (sell them). It was only about 5% of foraging pay, so no other number changed. The bit-sharing rules still exist and are tested with the value turned on.
- **Back goes up one level.** The nav stack is the path down from Home; opening a screen that is already on it cuts the path back to that screen instead of stacking a second copy, so Back is never an "undo".

## Chopping panel and the right-style streak

- The spot panel shows `Grain (±%) ▰▰▰ Fresh|Worn|Nearly gone  🪓 N per swing`: the percent is the grain's pull LESS the wear, so it falls with the spot and matches the swing number; wear is only the bar and a word. The word "grain" follows the grain's name again (the grain "Clean grain" is now just "Clean").
- **Right-style streak** (`[chopping] streak_bonus = 0.01`, `streak_max = 10`): every chop in the grain's right style in a row adds +1% damage to the next ones on the same tree, up to +10%. A wrong style resets it; a chop with no style leaves it alone; a new tree starts it over (the key is the tree: private `id(tree)`, shared trees their closing time). Damage only, never xp, and the cap is the same on private, party and community trees, so on shared trees a careful chopper takes a slightly bigger share, never a lot (a test pins the cap at 15% or less).

## Scrolls: three per skill, three for every tool, about one every few hours

- **15 scrolls.** Each skill has three of its own (mining: Iron Frame, Veinfinder, Bounty; fishing: Lure, Steady Line, Deepcall; foraging: Sharp Eye, Seasoned, Double Strike; farming: Fertile, Seedkeeper, Gleaner) and three **global** ones that fit every tool (Keenness: +power, Scholar: +5% xp per level in the tool's skill, Appraiser: +4% bits per level when you sell items of the tool's skill).
- **Where they come from** (`configs/scrolls.toml`, `services/scrolls.py`): one steady rare roll per skill, then one of that skill's six at random: mining 1 in 2,200 cells dug, foraging 1 in 150 private trees felled, farming 1 in 30 growth cycles harvested. About one scroll per 3 hours of play in each skill (`tests/test_enchanting.py` pins every skill between one per 2 and one per 6 hours). Fishing keeps its treasure-chest and boss-loot lists (`fishing.toml`), spread over the six fishing-available scrolls (boss total 0.22 per boss, was 0.28; chests 0.05/0.03 for the main two). Items no longer carry `[drop]` for scrolls. They always show the big "SUPER RARE" banner.
- Scholar plugs into `party.xp_multiplier` (the one place every skill's xp goes through) and Appraiser into `shop.haggle`.

## Streak by grain, and the spot's remaining life

- The foraging streak counts **grains**, not chops: when a spot wears out and every chop on it was in the grain's right style (`Spot.clean`), the streak grows by one; a single wrong-style chop spoils that grain and the streak resets when it wears out. Each streak step adds `streak_bonus = 5%` damage to the next chops on the same tree, capped at `streak_max = 3` (+15%). A private tree has only a grain or two, so it is worth +5-10% there; party and community trees run long enough to reach the cap, which is the same everywhere. Leaving a grain early with a wedge neither counts nor resets.
- The spot panel shows the grain with its pull net of wear (so it matches the swing number), the bar with **how much is left in percent**, and **about how many chops** (`Spot.chops_left`, which knows the grain's wear and your Seasoning).

## Community tree cap, compact streak text, "max" wording

- **The community pool scales with the choppers** (see "Community tree pool" at the end; this replaced the old 50% cap on a lone chopper). Party trees pay the whole pool (`party_rules` sets `pool_base = 1`, `pool_per_chopper = 0`).
- The streak shows only as `🔥 +10%` (and `max` at the cap) on the swing line; no sentences.
- Player-facing text says **max** for "the most/the best" (the wiki says "Max odds in" for a fish's best water; upgrades say "maxed").

## Magnet fuel, Reactor Engineer, rarer gems

- **The magnet is a fuel meter** (`[magnet]` in `configs/mining.toml`): capacity 1,000, copper 1 / iron 6 / gold 38 per ore (about 50 bits a point whatever you feed), and with it on every row you dig uses `drain_per_row = 4` and is marked with ✨ (the richest column). A full meter is about 12 mines. The meter stays between mines; `settle_run` takes off only what the mine used. It can only be fed outside a mine (`mining.in_a_mine`, a small in-memory map of live runs; a run counts for 15 minutes at most). The Reactor page has a picker (each ore with how many you hold and its points), Feed 1 / 10 / 100 / Fill with an exact preview, a Magnet on/off switch, and **Auto-miner feeds it** (copper, iron and gold from claimed lodes fill the meter first, never over capacity). Sim: following the marker roughly doubles a row's ore value at about +2 pressure a row, which is the trade-off (you spend braces on it).
- **Reactor Engineer** replaces Safe Digger: Coolant Loop (`reactor_cool`: +0.4% less pressure per reactor level), Overclock (`auto_speed` +25% lodes), Efficient Magnet (`magnet_save` -30% drain, +1 brace), Deep Reserve (`auto_hours` +24, +25% lodes), and the capstone **Lifeline = a second chance from a collapse**: when a dig would collapse the mine, the reactor holds it once (you lose `lifeline_loss` 25% of what you carry, pressure drops to `lifeline_pressure` 30, the dig goes on) and recharges after `lifeline_runs = 8` mines (`Mining.lifeline_wait`). Un-recharged it was +100% in the sim; with the recharge it lands near +21% (power 3) / +17% (power 12), next to Gold Rush's +13% / +21%.
- **Gems are rarer and worth more**: the four core gems sell for 400,000 (were 45,000) and drop at 1 in 12,000 (were 1 in 1,500), so mining income stays about the same but a gem is an event. **Geode Cracker** is about 1 cell in 1,400 (was 2%, about 14 gems an hour) and holds a gem you have not placed yet while any slot is empty. The guard test runs all three capstones at pickaxe power 3 and 12 (each +8% to +40%, within 15% of each other).

## Community tree pool (balanced by number of choppers)

The community tree used to cap a lone chopper at `max_share` 0.5 of the tree. Now the tree's total reward (drops and bits) is multiplied by a **pool** that depends on how many distinct choppers did their share (`community_pool(n, rules)` in `services/foraging.py`): `pool = pool_base + pool_per_chopper x (1 + d + d^2 + ... up to n-1 terms)` with `d = pool_decay`. Config in `[community]`: `pool_base = 0.5`, `pool_per_chopper = 0.2`, `pool_decay = 0.6` (ceiling 1.0). The group bonus was cut to +2% a chopper, max +20% (was 5% / 50%) because the pool now does most of the scaling. `max_share` stays at 1.0 (no cap). Party trees keep paying the whole tree.

Sim (scratch, zone 5, 1,000,000 hp tree split evenly, value = sell price of drops per chopper, against the same hp of private-tree work):

| choppers | pool | group bonus | pay vs solo play for the same hp |
|---|---|---|---|
| 1 | 0.50 | 0% | 0.50 |
| 2 | 0.70 | 2% | 0.71 |
| 5 | 0.94 | 8% | 0.99 |
| 10 | 0.99 | 18% | 1.15 |

So a lone chopper is paid half (as before), a pair about 70%, five about solo, and a crowd of ten a modest 15% over solo. TODO(balance): the community screen still shows "max: you are paid for X% of the tree" off `max_share`; it should show the pool instead.

## More pets: Magpie, Mole, Fox, Bee, Raven

Five pets with small effects that are **not xp** and **never forgive a mistake** (a pet that softens a collapse or saves a missed press
is useless once you play well). Each is one stat in `configs/pets.toml` (`TODO(balance)`); all are `value x stars x level factor` like
every pet, and `tests/test_pet_effects.py` keeps the five at a modest max-level value in one band (read from the registry).

| Pet (rarity, skill) | Stat | Max level, 1 star | Where it is applied |
|---|---|---|---|
| Magpie (3, global) | `sell_bonus` | +6% bits per sale | `shop.haggle` (adds to Appraiser/Haggler; also the Farmer's Market and `sell`) |
| Mole (3, mining) | `dig_shave` | -7% pressure per dug row | `mining.start_run`: multiplies the run's `growth_factor` (the collapse curve is untouched) |
| Fox (4, global) | `rare_reroll` | 15% chance of a free second roll | a rare drop (rarity 4+) that missed: `fishing.cast_line` (re-roll the catch, keep it if rare), `MineRun.row` (re-roll the cell), `foraging.roll_drops` (per rare item; private trees and Windfall, not community trees) |
| Bee (2, farming) | `extra_harvest` | 10% chance of a whole extra harvest | `farming.harvest`: a second roll of the same crop's amount |
| Raven (5, global) | `payout_bonus` | +6% bits | `pets.payout` in `shipments.ship`, `claim_community` and the daily interest (`economy.claim_daily`); not the weekly (that pays luckbucks) |

**How the numbers were picked** (a short estimate, `scripts` not needed): the aim is about +5-7% of what the touched activity pays at
max level and one star. Magpie and Raven are a straight % of the bits they touch. Mole: pressure is what ends a run, so 7% less growth
is roughly 7-8% more rows before the same risk. Bee: one harvest in ten doubling is +10% crops, and crops are most of a farm's pay, so
about +6%. Fox: the share of a skill's value that comes from rare (4+) drops is about 46% in the forest, 36-51% in the deep mine and 26-56%
in the mid and deep waters (about 4% in the first pond), and a re-roll only helps when the first roll missed, so a 15% second roll is
worth roughly +15% x 0.4 = +6% there and little in the early game. Five stars multiply each by 1.0 + 4 x 0.25 = 2.0.

The Mole and Bee already existed (mining xp, +20% crops); they were repurposed in place (same ids, so saved pets keep working). A pet's
rarity sets its xp curve, so an owned Mole (2 -> 3) now levels slower and a Bee (3 -> 2) quicker than before.

## Tree species

Every tree has a **species**, set by its zone when the tree is rolled (`[[species]]` in `configs/foraging.toml`: id, name, emoji, `zone_min`..`zone_max`,
`weight`, `drops`). Nine species cover zones 1-20 with bands that overlap a little (2-3 species grow in any zone): Birch 1-5, Oak 1-7, Willow 3-9, Pine 6-12,
Chestnut 8-13, Cherry 10-15, Palm 13-18, Redwood 14-20, Emberwood 16-20. A species adds its own **signature drops** on top of the normal drop pool: each drop
roll of the tree also rolls every signature drop at its `rate` (a chance 0..1 per roll, then `min`..`max` of them), so they are far likelier than the pool's
rare items. Each species has one common and one rarer signature item (`configs/items.toml`, skill foraging, no `[drop]` block so they never join the global pool).
- Who picks the species: private trees roll it in `roll_tree` (after the hp, so seeded hp rolls did not change); community trees derive it from the window and zone
  only (`community_species`, seeded `community-tree:{window}:species:{zone}`, nothing stored), so every chopper and the settling see the same one; party trees roll
  it when started and keep it in the party state (`species`).
- Paths: `roll_drops(..., species=)` is used by `fell_private`, `windfall`, `community_shares` (community and party). The Fox's rare re-roll also applies to
  signature drops of rarity 4+. `odds.py` quotes a signature drop as 1 in 1/rate drop rolls; the wiki lists species by zone band.
- **Phase 5 (not built): set craft.** The intent is a special item crafted from ONE of each species' signature drop. Both signature items of every species
  are plain stackable materials, so the set recipe can ask for either the common or the rare one (or both) of every species.
- Numbers are guesses (`TODO(balance)`): common rate ~0.27-0.30 per roll, rare 0.5-2%; sell prices scale with the zone band.

## Mine types

Every mine you enter ("Enter the mines" and "Mine again") rolls a TYPE by weight (`mining.roll_mine_type`, from `start_run`; `start_run(..., mine_type=)` forces one for tests).
It is shown on the mine page before the first dig and kept on the `MineRun` (`run.mine_type`); nothing is stored. `[[mine_types]]` in `configs/mining.toml`:
id, name, emoji, weight, description and effects, all neutral by default. Standard (first in the list, 75 of 100) must exist, change nothing and be at least half of all
mines (validated in `MiningRules`; ore ids are checked in `_validate_mining_items`; bounds: pressure/xp/yield 0.25-3, rich add 0-0.5, boosts 1-5).

| type | weight | effect |
|---|---|---|
| Copper Seam | 6 | `ore_yield` copper x1.2 (cells and the vault) |
| Iron Vein | 6 | iron drop chance x1.1 and `ore_yield` x1.15 |
| Gold Vein | 5 | `ore_yield` gold x1.25 (cells and the vault) |
| Quiet Shaft | 3 | `pressure_mult` 0.93, applied in `growth_factor` AFTER the reactor/tool/pet cap (`max_reduction`) |
| Scholar's Cavern | 2.5 | `xp_mult` 2.0, applied in `settle_run` on top of the rank/party xp multiplier |
| Deep Pocket | 2.5 | `rich_chance_add` +0.12 (added to the cell chance and the Prospector bonus) and `yield_mult` 1.05 |

Why quantity and not just drop chance for the ores: a bigger share of a hard ore means more pressure per row, so a pure chance boost made the run end sooner and the type
a trap (Gold x2 chance: gold income +30% but the whole run -20%). `ore_yield` pays more of the ore with the same pressure (it rounds at random so +20% on a 1-3 ore
still pays; the chance boost `ore_boost` stays in the model and is used mildly on iron). Capstones (Lifeline, Gold Rush, Geode Cracker) are untouched.

Value check (`scratchpad/typesim*.py`, 12,000 mines per row, a player who stops at 7% collapse risk, braces when pressure is above 10, picks the column of the focused ore by
its soft/firm/hard feel, same seeds as Standard): the focus ore's income per run, and the whole run's value in bits (xp counted at 20 bits per xp, the scarab's "lesson" prize):

| type | focus ore income (power 3 / 12) | whole run (power 3 / 12) |
|---|---|---|
| Copper Seam | +21% / +21% | +4.6% / +4.6% |
| Iron Vein | +22% / +24% | +4.1% / +2.9% |
| Gold Vein | +20% / +28% | +4.3% / +5.0% |
| Quiet Shaft | | +10.9% / +10.4% |
| Deep Pocket | | +11.5% / +13.0% |
| Scholar's Cavern | | +0% bits, +100% xp (about +6% with xp at 20 bits) |

So none is a trap (every type is at or above Standard) and none is a jackpot (the best is about +13% of a run, on 2.5-3% of mines).  TODO(balance): the xp price is a guess;
double xp is the headline, raise `xp_mult` if it feels thin.
The wyrmhole code is untouched: a later "small wyrmhole" mine should decide its kind in `start_run` next to the type roll.
