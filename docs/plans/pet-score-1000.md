# Pet score out of 1000 + traits

Status: APPROVED in direction (owner's spec below; rarity table still to confirm). Builds on `pet-sidekicks.md` (which stays for the tank/haul/UI parts).

## Owner's spec
- Every pet has a score out of 1000 (a perfect pet = 1000), shown on its card, with the parts visible:
  - **500 skills**: 100 per skill (mining, fishing, foraging, farming, combat = 5 skills).
  - **200 mastery level**, **200 gear level** (the loadout's tool tier + enchants).
  - **100 ability**: 100 if the pet has an ability, 50 for a mid-tier one, 0 for none.
- Pets give NO other bonuses: the flat `bonuses` and the `passive_bonus` go away. What replaces them is the pet's **trait** (and its haul).
- **Traits**: a pet strong in one skill gets an XP trait for that skill; one strong in all skills gets a global XP trait. Skill points scale with rarity
  (Mythical = 100 in one skill + that skill's XP buff; Celestial = 500 across all five + global XP buff). Other pets get a different trait where it makes sense; traits are optional.
- A haul find is shown with the active pet's emoji; if a trait caused it, the trait's name is shown next to it.
- Lending a tool is ON HOLD.

## Score vs level and stars (decided)
- The **score out of 1000 is a fixed trait of the pet species** (skills + mastery + gear + ability): it tells a player how strong a pet is. Level and stars do NOT change it.
- **Level and stars** make that pet stronger when it works, and feed the **sidekick bonus**: every pet you own adds `score/1000 x its level and star strength`
  to a pool that gives the ACTIVE pet a small capped bonus (nothing game breaking; cap and rate in `pet_score.toml`, TODO(balance)).
- Haul = (score/1000) x (own level/star strength) x haul constants x (1 + sidekick bonus). The guard test (maxed pet <= 15% of active play) stays.
- New pets: several **Mythical** and exactly **1 Celestial** pet (rarity range 1-8; Premium unused). Their art is on STATUS: pets get the rarity border art and a dark outline.

## Proposed skill-point table (total points in skills by rarity)
| Rarity | specialist (one skill) | global pet (spread over 5 skills) |
|---|---|---|
| Common 1 | 25 | 5 each = 25 |
| Uncommon 2 | 40 | 8 each = 40 |
| Rare 3 | 55 | 12 each = 60 |
| Super Rare 4 | 70 | 20 each = 100 |
| Legendary 5 | 85 | 30 each = 150 |
| Mythical 6 | 100 | 60 each = 300 |
| Celestial 8 | 100 in one + more | 100 each = 500 |
Existing pets are rarity 1-5; Mythical and Celestial pets do not exist yet (rarity max is 5 in the model).

## Existing flat bonuses -> traits (first pass, to review)
Each of the 25 pets keeps what it did as a named trait (e.g. Drizzle "Quick Bite", Cinder "Paymaster"); XP traits for strong-skill pets; the rest keep a
unique trait only where it makes sense. Traits replace `bonuses` in `pets.toml`; the old stats keep working through the trait.

## Traits (step 2 plan)
A trait is a pet's ONE named effect (`[pet.trait] name, stat, value, text`). It replaces the `bonuses` list; the stats and engine hooks stay exactly as they are
today, so no skill code changes. A trait scales with the pet's level and stars like a bonus does now (`value` at max level, one star; `pets.strength`). `passive_bonus`
and the flat-bonus code path are deleted. Pets MAY have no trait.

Rules: a pet whose points sit in ONE skill and whose effect is xp gets "<Skill> xp" (value by rarity: Uncommon 16%, Rare 20%, Super Rare 28%, Legendary 36%,
Mythical 50%); a global pet that is strong everywhere gets global xp (Rare 10%, Legendary 20%, Celestial 35%). Other pets keep their unique effect under a name.

| Pet | Rarity / skill | Trait (name: effect) |
|---|---|---|
| Cinder | 1 global | none (the starter; its work wage `work_bonus` becomes **Paymaster** 20% only if you want it kept: default KEEP) |
| Dew | 2 farming | **Rainmaker**: +12% crop growth chance each rain |
| Pollen | 2 farming | **Cross-Pollinator**: +10% extra harvest |
| Clover | 2 farming | **Green Thumb**: +16% farming xp |
| Drizzle | 2 fishing | **Quick Bite**: -30% bite wait |
| Ripple | 2 fishing | **Current Reader**: +16% fishing xp |
| Sprig | 2 foraging | **Woodwise**: +16% foraging xp |
| Murk | 2 mining | **Steady Hand**: -6% mine pressure and +10% ore (two stats; trim to one: keep ore) |
| Scorch | 3 combat | **Fire Spirit**: +20% combat xp (combat paused) |
| Bough | 3 foraging | **Good Chop**: +16% good-chop chance |
| Haze | 3 global | **Wanderer**: +10% xp in every skill |
| Gloam | 3 global | **Bargain Hunter**: +6% sell price |
| Lode | 3 mining | **Lamplight**: -7% pressure per dug row |
| Thistle | 4 farming | **Green Thumb II**: +28% farming xp |
| Squall | 4 fishing | **Storm Luck**: +50% rare fish luck |
| Undertow | 4 fishing | **Pot Hauler**: +50% pot speed |
| Brine | 4 fishing | **Pot Luck**: +100% pot luck |
| Eddy | 4 fishing | **Deep Reader**: +28% fishing xp |
| Canopy | 4 foraging | **Forest Sage**: +28% foraging xp |
| Lune | 4 global | **Lucky Roll**: +15% rare reroll |
| Cairn | 4 mining | **Stone Sense**: +28% mining xp |
| Pyre | 5 combat | **Inferno**: +36% combat xp (paused) |
| Tempest | 5 fishing | **Treasure Hunter**: +70% treasure luck |
| Halo | 5 global | **Blessed**: +20% xp in every skill |
| Umbra | 5 global | **Tithe**: +6% shipment and daily payouts |
All trait values are today's numbers; names are first-pass and `TODO(balance)`. The new Mythical pets get skill-xp traits (Mythical 50%) and the one Celestial pet
gets **global xp +35%** (500 skill points, gear/mastery near max).

## Build order
1. (BUILT) Score model: `pet_score.toml` budgets (skills/mastery/gear/ability), loadout gets per-skill points + `ability` tier; `pet_score.total(pet)` out of 1000 + breakdown. Test: every pet <= 1000, Celestial = 500 skills.
2. (BUILT) Traits in registry (`Pet.trait` replaces `bonuses`), convert the 25 pets, services read traits, remove `passive_bonus` and flat bonuses (changelog + notice).
3. Pet card shows the breakdown; haul drops show the trait name when it triggered.

## Open question
Pets only go to rarity 5 today: add Mythical (6) and Celestial (8) as pet rarities now (new pets later), and is the table above right?
