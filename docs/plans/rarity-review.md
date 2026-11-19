Status: IN PROGRESS on `design` (not merged). Delete this file when it merges; trim docs/STATUS.md.

# Rarity review

A drop's rarity is defined by how long an ACTIVE player waits between finds of that one item, so the per-roll rate differs per skill
(rolls per active hour: mining 720 cells, foraging 45 trees, fishing 156 casts, farming ~400 byproduct rolls). rate = rolls/hour x minutes / 60.
Tune the two tables below (they live in `tests/test_rarity_bands.py`, the single place; the guard test checks every item against them).

| Tier | Minutes between finds | mining 1/N | foraging 1/N | fishing 1/N | farming 1/N |
|---|---|---|---|---|---|
| R1 | nearly every action (rate 1-3, quantity range) | 1-3 | 1-3 | 1-3 | 1-3 |
| R2 | 10 (bulk R2 materials: rate 1-3 with quantity) | 120 | 8 | 26 | 67 |
| R3 | 60 | 720 | 45 | 156 | 400 |
| R4 | 300 | 3,600 | 225 | 780 | 2,000 |
| R5 | 1,500 (25 h) | 18,000 | 1,125 | 3,900 | 10,000 |
| R6 | 6,000 (100 h) | 72,000 | 4,500 | 15,600 | 40,000 |
| R7 | 24,000 (400 h) | 288,000 | 18,000 | 62,400 | 160,000 |

Allowed band: within x2 of the number. Bulk materials (category material, rarity 1-2) instead keep a rate of 1-3 and a quantity range.

Keeping pay level: per item, price x (expected count per hour) is unchanged, so every skill's income per active minute stays put
(price = old price x old count/hour / new count/hour). Upgrade/recipe INPUT counts of changed items scale by new/old count per hour, so the
time to collect them is unchanged. Mining tables are re-sorted rarest-first (a startup check). Farming zone-table value per roll is unchanged.
Re-rated outliers: food_honeycomb R4->R2, food_golden_sap R5->R3. Items with no real roll (crafted/boss/reactor) just get a rate inside their tier's band.
Scrolls: mining and foraging about one per week of play (~15 h/week).
