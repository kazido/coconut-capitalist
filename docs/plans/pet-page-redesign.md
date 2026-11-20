# Pet page redesign + manual Collect

Status: APPROVED (thumbnail = the pet's own animated emoji). Build on the `design` branch.

## Why
The Pets pane (`cococap/screens/pets.py` `PetScreen.build`) is one wall of text: header, max buffs, xp, perks, score breakdown,
sidekicks, tank, banking note, then four dropdowns. The idle haul banks itself on open (`pets.bank_idle_haul`), so coming back
to your pet feels like nothing.

## New layout: three tabs (`PetsScreen.panes`): Pet, Feed, Orbs

**Pet tab** (look at your pet, collect its work)
1. Section with a big thumbnail on the right (`section_art`):
   `### Rex ⭐⭐` / `Lv 12 · Mining · active` / xp bar `1,200/3,000 xp`.
2. **Stats** (one short block): Score 640/1000 · Sidekicks +20% · works ~1,900 xp/h. Details button keeps the per-skill bars.
3. **Perks**: one line each from `pets.describe()`, the max-level value in small text after it (`-#`), no separate max line.
4. **Work** section, Collect button as its accessory (green when there is a haul, grey + disabled when not):
   `Out working 5.2 h · tank 2.8/10 h` / `About 9,800 mining xp + finds waiting`. Empty tank: `Rex is resting: fuel the tank on Feed`.
5. Pet picker dropdown (unchanged).

**Feed tab** (everything you put into the pet): food dropdown (+ the food hint when you have none), tank bar + fuel
dropdown, Spirit dropdown. Moved as-is from the Pet tab and `_sidekick_block`.

**Orbs tab**: unchanged.

## Collect that feels good
- Remove auto-banking on open (`bank_idle_haul` call in `build`; delete the helper if nothing else uses it).
- Collect opens a `Result` (like the orb hatch): title `Rex is back!`, hours worked, `+9,812 mining xp` (+ level-up line),
  the finds list with `flair.banner(drops)`, buttons `Back to Rex`.
- The Work line is a live preview: worked = min(now - last_collect, fuel) (already computed in `_sidekick_block`), xp from
  `pet_score.haul_xp_per_hour`. Finds stay a surprise.
- Home: a small nudge line when a haul is waiting (`Rex has 5 h of work to collect`) linking to Pets. (Optional, cheap.)

## Correctness fix this needs
`pets.fuel()` and `pets.set_active()` settle the tank (`_settle`), which burns the pending work WITHOUT paying it. Today the
auto-bank hides that. With manual Collect: both call `collect()` first and the screen shows the haul in the note.

## Tests (targeted)
`tests/test_pet_score.py` (collect, fuel keeps the haul, switching keeps the haul), `tests/test_pets.py`,
pet UI tests in `tests/test_hub.py` (Collect button disabled/enabled, Result shown, Feed tab has the dropdowns). Changelog
entry + a notice ("Collect is back").

## Thumbnail
Every pet (all 30, incl. Seraph) already has a drawn, animated `pet_<id>` application emoji (art/wisps.toml). Thumbnail =
`emojis.image_url("pet", pet.id, size=256)` (gif when animated); fall back to plain text if it is not loaded.

## Seraph (Celestial) is unobtainable
`configs/economy.toml` `[pets.orbs.*]` gives rarity 8 weight 0 in every orb, and hunting multiplies a 0 weight, so no
player can ever hatch him. Needs a source (owner's call), then more interesting pets as a separate step.
