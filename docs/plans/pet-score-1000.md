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

## Build order
1. Score model: `pet_score.toml` budgets (skills/mastery/gear/ability), loadout gets per-skill points + `ability` tier; `pet_score.total(pet)` out of 1000 + breakdown. Test: every pet <= 1000, Celestial = 500 skills.
2. Traits in registry (`Pet.trait` replaces `bonuses`), convert the 25 pets, services read traits, remove `passive_bonus` and flat bonuses (changelog + notice).
3. Pet card shows the breakdown; haul drops show the trait name when it triggered.

## Open question
Pets only go to rarity 5 today: add Mythical (6) and Celestial (8) as pet rarities now (new pets later), and is the table above right?
