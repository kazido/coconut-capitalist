# Pet abilities

Status: DESIGN (decided: passive, one per pet; not built)

## Decision
Every pet keeps its small stat bonus AND gets one named **ability** (passive, no new buttons). The ability is active from level 1 of the
pet and scales with its level, the same way the stat does (`level_floor` 0.1 at level 1 up to 1.0 at level 100, so the numbers grow ~10x).
Abilities must be clearly weaker than tool enchants and mastery capstones: a flavour/utility proc, not a multiplier on everything.

## Rules of thumb
- One ability per pet, one sentence on its card, with the live number shown at the current level (max in brackets), like stats today.
- Procs need an engine hook that already exists or is tiny. Rarer pets get a more interesting ability, not just a bigger number.
- Stars (existing +25% per star) scale the ability number too.
- Guard test: ability strength by rarity stays in a band (like the capstone guard tests).

## Ability ideas (rough; numbers TODO(balance))
Fishing
- Drizzle (r2): **Second Cast** - a bite has a chance to hook a second, common fish.
- Squall (r4): **Big Game** - a chance that a catch's size/rarity roll is taken twice, keeping the better.
- Tempest (r5): **Storm Surge** - after a rare catch, the next few casts bite faster.
- Undertow/Brine (r4): **Full Nets** - a crab pot you empty has a chance to refill half-full at once.
Mining
- Murk (r2): **Steady Hands** - once per run, a pressure spike is absorbed.
- Lode (r3): **Lantern** - the next row after a rich vein is revealed before you pick it.
- Cairn (r4): **Rockfall Recovery** - a collapse keeps a share of that run's ore.
Foraging
- Bough (r3): **Clean Cut** - a chance a chop counts as two swings.
- Sprig (r2): **Seedling** - felled trees sometimes drop a sapling/plant fibre extra.
- Canopy (r4): **Hollow Log** - a chance for a bonus food (acorn mix) from a tree.
Farming
- Dew (r2): **Morning Dew** - a watering also waters one extra plot.
- Pollen (r2): **Cross-pollinate** - a harvest has a chance to give a seed of the same crop back.
- Clover (r2): **Lucky Patch** - a chance a harvest becomes one crop tier richer in sell value.
- Thistle (r4): **Hardy** - a plot keeps growing through a missed rain (no lost cycle).
Global
- Cinder (r1): **Warm Glow** - first action each hour pays a small bit bonus.
- Haze (r3): **Quick Study** - the first xp of a skill each session is boosted.
- Gloam (r3): **Haggler** - selling one item in a stack of 10+ gets a chance at a bonus.
- Lune (r4): **Second Look** - rare drops that fail the flair roll get one reroll (already `rare_reroll`; make it the named ability).
- Umbra (r5): **Quartermaster** - shipments have a chance to pay a bonus crate item.
- Halo (r5): **Echo** - a level-up refunds some of the xp toward the next one.

## New pets (also need art; each is a new species + sprite via the make-emoji skill)
Gaps to fill: no mining pet above r4, no farming r5, no foraging r5, no r1 pet except Cinder, combat has only two.
- r1 starters per skill (cheap, tutorial-friendly): a mining pebble, a foraging seedling, a fishing minnow, a farming sprout.
- r5 per skill (the dream drops): a mining gem-eater, a foraging elder-stag, a farming harvest spirit.
- Each new pet ships with its own ability from the list style above.

## Build order
1. Registry: add `ability` (id + per-level `value`) to the pet model; config in `configs/pets.toml`; loader validates ids.
2. Services: `services/pet_abilities.py` maps ability id -> engine hook (mining/fishing/foraging/farming/shipments); pets service exposes the
   active pet's current value.
3. Pet card + wiki show the ability line with the live number.
4. Add the existing pets' abilities first (pick ~10 easy hooks), then new species + art.
5. Tests: one per ability (proc fires at value 1.0, never at 0), a guard test on strength by rarity; changelog + notice.

## Open questions for the owner
- Which existing pets get an ability first (suggest the farming and fishing ones: hooks already exist).
- How many new species, and in which skills.
