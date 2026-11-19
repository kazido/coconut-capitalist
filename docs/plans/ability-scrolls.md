# Ability scrolls (draft, waiting on owner)
Status: built on design (Echo Strike, Second Wind, Prospector's Ping, Timber!, Ember Bite, Net Cast, Golden Sprout; Rain Dance dropped). Delete when design lands.

Rule (owner, 2026-11-19): an enchant is ALWAYS a unique ability you can see or trigger, never a plain stat.
Stat bonuses (xp, less pressure, slower wear, shorter waits, rare odds) belong to mastery, pets and accessories.
Every scroll drops from ONE specific source (a mine type, a tree species, a water or boss, a crop or anomaly), not a skill-wide pool.

## Existing enchants, sorted by that rule
- Keep (they are abilities): Double Hook, Double Strike, Steady Line, Seedkeeper, Soloist.
- Stat-like, to retire later (move their effect to mastery/pets/accessories): Iron Frame (less pressure), Seasoned (slower wear),
  Lure (shorter waits), Deepcall (rare odds), Gleaner (+drops).

## New ability ideas (one source each)
| Skill | Scroll | Only from | What you see |
|---|---|---|---|
| Mining | Echo Strike | Wyrm Tunnels | a dig sometimes also breaks the tile beside it |
| Mining | Second Wind | Unstable mines | once per mine, a collapse gives you a 5 s "Brace!" button that saves the run |
| Mining | Prospector's Ping | Scholar's Cavern | once per mine, a button reveals the 3 tiles under you |
| Foraging | Timber! | Redwood | a felled tree sometimes topples into the next: a half-chopped tree appears |
| Foraging | Ember Bite | Emberwood | a chop sometimes sets the trunk smouldering: the next 3 chops hit harder (flame shown) |
| Fishing | Net Cast | one boss | once per trip, a button casts a net that hauls 3 small fish at once |
| Farming | Golden Sprout | crop anomalies | a plot sometimes grows golden (shown on the field); harvest it for triple yield |
| Farming | Rain Dance | one crop | once a day, a button waters every plot |
Existing keepers each move to one source too (e.g. Double Strike from Burl grain, Double Hook from one water).

## Build notes
Each ability is a small hook in its skill's engine (an effect flag on the tool, read where the event happens) plus a button or a
visible line on the skill screen. One scroll per commit; tests force the trigger with a seeded rng.
