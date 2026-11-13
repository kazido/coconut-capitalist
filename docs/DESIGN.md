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
| Pickaxe upgrade template | raises pickaxe power (the scarab's level-6 reward) | **not built** |
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
cooldowns refresh); the **Farmer's Market** (farming level 5, Fri/Sat UTC) pays +50% for crops and turns blessings into
land deeds at 1/10 each.

**Rain is computed, not scheduled.** A farm catches up on missed rains whenever it is looked at or changed, and each
roll is seeded by (player, plot, hour). So reopening the farm can't re-roll, rain keeps falling while the bot is
offline, and there is no hourly job. (Trade-off: no "the rain fell" channel announcement; it can be added later as a
cosmetic-only task.) Numbers are in `configs/farming.toml` (`TODO(balance)`).

## Foraging

**Solo always works; friends are better.** The wiki's "two players at zone 7" rule is replaced so nobody is ever
stuck waiting for another player online:

- **Private trees** (any time, in your own panel): pick a zone you've unlocked (level `1 + 2 x (zone - 1)`), chop it
  down. From zone 7 up a lone chopper swings at half power (never below 1) unless their axe has the **Soloist**
  enchant, which removes that penalty.
- **The community tree**: one grows every hour and stands for 30 minutes. It is the same for everyone (zone and hp come
  from the clock) and is chopped at full power. Everyone who joins from their own panel adds to one shared hp pool.
- **Party bonus:** +25% skill xp in *every* skill (mining, farming, foraging...) while in a party of 2 or more
  (`economy.toml` `party_xp_bonus`).

**Why the community tree has no race conditions.** Each chop is one atomic database update (take hp off the tree, add it
to your total), so any number of simultaneous chops all count and the tree can only fall once. The "batching" you see is
only the panel redrawing itself every few seconds, not a delay in chopping. Panels edit themselves for as long as
Discord allows (15 minutes per panel); the next click revives one.

**Rewards** are worked out once, when the tree falls or falls over, and stored per player; each player claims theirs from
their own panel (even if they were offline). Drops and bits go by share of the tree's hp, only for players with at least
5% of it; everyone gets xp for the work they did. The group gets a bonus (+5% per extra qualifying chopper, up to +50%).
A tree nobody finished pays a 25% consolation.

### Chopping: the spot, rotating and good chops

Each chop does your axe's power x how fresh the spot is. Chopping the same spot again does 12% less than the chop
before, down to 35% of full damage; **Rotate** (a click that does no damage) moves you to a fresh spot. A chop also has
a 15% chance to be a **good chop** (+50%). With the starter axe (power 3), never rotating averages about 1.2 damage per
click, rotating every 3-5 chops about 2.1, so rotating is worth doing but never forced. The Rotate button lights up once
the spot is worn. The same applies to the community tree.

### Foraging pay vs mining

Measured with fixed-seed simulations (a test guards it): mining at base gear pays about 1,100 bits per click; foraging at
the starter axe in zone 1 pays about 880 (roughly 80%), because it has no collapse risk. Pay is proportional to hp chopped
(`bits_per_hp`, drop rolls per hp), so stronger axes earn more per click, and each zone above 1 pays +15% per hp.
Drop rolls are fractional (a half-roll is a 50% chance of a roll), so small trees are not over-paid.
