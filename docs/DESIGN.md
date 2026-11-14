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

### Chopping: the spot, rotating and good chops

Where you stand matters. Each chop does your axe's power x the **kind of spot** (Knotty x0.7, Plain x1.0, Clean grain
x1.3) x how **worn** it is. Wear is random: every chop has a 20% chance to wear the spot down a step (-15% each, down to
40%), so you don't have to rotate on a schedule. **Rotate** (a click that does no damage) moves you to a *random* new
spot, so it is a real decision: leaving a worn spot is right, leaving a good one wastes a click, and a new spot could be
worse. The panel shows the spot's kind, its wear and what your next chop will do, and Rotate never lights up to tell
you. A chop also has a 15% chance to be a **good chop** (+50%). A simulation shows rotating once the spot is below 80% of
your axe's power earns about 3x what never rotating does, and clearly beats rotating too often or too rarely. The same
applies to the community tree.

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

## Pets

Pets are the gacha part of the bot, and **every pet gives a bonus somewhere in the game** while it is your active pet
(one at a time; `/pets` or the Pets shortcut on Home). They come from **Familiar Orbs** (treasure chests, boss loot,
the shop at 1.5M), which hatch a random pet by rarity (`economy.toml` `[pets.orb_weights]`); a duplicate adds a **star**
(up to 5; a fifth-star duplicate gives xp instead). Feed them **crops** for pet xp (dearer crops feed more) to level
them up to 20, and give them a **Spirit** item for +15% xp in its skill. A bonus is its listed value x stars (+25%
each) x level (a fresh pet does half, a max one all of it).

| Pet | Does |
|---|---|
| Dog | +bits from Work |
| Cat | shorter wait for a fish to bite |
| Turtle | less mine pressure, more ore |
| Frog | crops grow more often in the rain |
| Monkey | more good chops on trees |
| Koala | +xp in every skill |
| Bee | bigger harvests |
| Eagle | more rare fish |
| Python | faster crab pots |
| Crab | rarer fish in crab pots |
| Dragon | hallucinations and chests more often |

The pet bonuses stack with the party xp bonus. All numbers are in `configs/pets.toml` (`TODO(balance)`).

## Tools: buy one, then upgrade it

The shop sells only the **starter tool** of each kind, and you can own **one tool per kind**: buying a second is refused.
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
