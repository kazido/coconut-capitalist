# Pet abilities

Status: DESIGN (direction decided; ability list is a shortlist to approve; not built)

## Decisions
- **Rarity 1-2 pets stay strictly small stat bonuses** (no ability).
- **Rarity 3+ pets** keep stat bonuses (the same kinds, but better) AND get one named passive **ability**. It is active from the pet's
  first level and scales with level (same `level_floor` curve as stats) and stars. No new buttons or screens.
- **No overlap with tools or mastery.** Already covered, so do NOT reuse: Double Hook (free second fish), Double Strike (chop hits twice),
  Seedkeeper (seed back), Fertile (bigger harvests), Bounty (more ore), Veinfinder (rich cells), Iron Frame (less pressure), Sharp Eye
  (good chop), Lure, Steady Line, Soloist, Appraiser (sell bonus), Scholar (xp), Gleaner (farming drops), Lifeline (collapse save).
  Rule: an ability must do something no enchant or capstone does (check `configs/enchants.toml` and `mastery.toml` before adding one).

## Shortlist (rarity 3+; numbers TODO(balance); each needs an engine-hook check before building)
Farming
- Thistle (r4) **Second Wind**: watering has a small chance to grow the plot two cycles instead of one.
Fishing
- Squall (r4) **Lucky Streak**: a pity counter: every catch without a rare adds a little to the next rare odds, reset on a rare.
- Undertow / Brine (r4) **Tidal Haul**: emptying a crab pot has a chance to also give a bonus catch.
- Tempest (r5) **Treasure Tide**: after a chest or hallucination, the next few casts have boosted treasure odds (a cluster, not a multiplier).
Mining
- Cairn (r4) **Prospector's Luck**: the same pity counter, on rare ore.
- Lode (r3) **Pressure Valve**: every Nth row dug vents some pressure (periodic, not a flat % cut).
Foraging
- Bough (r3) **Second Growth**: a felled tree has a chance to regrow at once in the same spot.
- Canopy (r4) **Heartwood**: a felled tree sometimes drops from the next-better wood table.
Global
- Umbra (r5) **Quartermaster**: a finished shipment can add one bonus crate item.
- Halo (r5) **Echo**: a level-up refunds a slice of the xp toward the next level.
- Lune (r4) **Second Look**: already the `rare_reroll` stat; keep it as the stat and give it a different ability, or leave it stat-only.
- Haze, Gloam (r3): need a non-overlapping idea (a flat sell/xp bonus is already a stat): leave stat-only until one is found.

## Another way to make pets desirable (if abilities are too fiddly)
Pick one or two of these instead of, or as well as, abilities:
- **Errands**: an active pet "fetches" a small item of its skill every few hours (collected from the pet page). Tools cannot do this, it
  rewards owning many pets (one fetch per pet slot), and needs only a timer plus the drop tables.
- **Cross-skill finds**: a pet sometimes drops a material from a skill other than its own, so owning a mining pet helps farmers a bit.
- **Collection**: a pet dex with a reward per rarity completed, titles on the profile, a star showcase.

## New pets (also need art, via the make-emoji skill)
Gaps: no pet above r4 in mining, none at r5 for farming or foraging, combat has only two. New r3+ species ship with their own ability
(from the list style above); new r1-2 ones are plain stats.

## Build order
1. Registry: optional `ability` (id) on a pet model; loader rejects an ability on rarity 1-2; config in `configs/pets.toml`.
2. `services/pet_abilities.py`: ability id -> engine hook; pets service exposes the active pet's current value.
3. Pet card + wiki show the ability line with the live number.
4. Build the cheapest hooks first (Second Wind, Tidal Haul, Echo, Quartermaster), then pity and the rest, then new species + art.
5. Tests: one per ability (fires at full value, never at 0), guard test: ability strength by rarity; changelog + notice.
