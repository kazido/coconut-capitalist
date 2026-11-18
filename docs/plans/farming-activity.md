# Farming: an active way to play (plan, NOT built; waiting for the user)

Today (`services/farming.py`, `screens/farm.py`): you plant, WATER each plot once an hour (a button; always grows a cycle, on top of 50% rain), harvest. Extra materials only come on a
harvest (`drop_rolls`: 1 roll per 2 growth cycles, so apple crops roll 0.5 times). Farming xp is 500 per growth cycle (so about 500 xp/hour per watered plot, paid in lumps at harvest). Nothing to do between waterings = no grind, few materials.
Rule for all options: **xp stays tied to growth cycles** (`xp_per_cycle`); the new activity pays MATERIALS and bits, and at most a tiny trickle of xp (say 1/20 of a mining click), so active play can't outrun waiting.

1. **Tend the plots (streak)**. Button "Tend" per farm: weed/prune one plot, 5 s cooldown; each tend adds to a streak meter (like fishing hot-streak); a full meter = one free extra growth cycle on the tended plot (capped N per hour, so it just speeds
   crops a bit) plus a roll on the farming drop table. Effort: small (new `tend()` in the service + a button + cap in `farming.toml`). Drops: farming materials (compost, fiber, ...). XP: none directly; the extra cycle's xp is the only gain, capped by the hourly cap.
2. **Forage the field edges**. A "Scavenge" button with a 20 s cooldown opens a 3-way pick (like the mine's columns: bush / stump / puddle) with different drop tables; a short run of picks ends the trip. Effort: medium (a mini-screen and 3 tables in `drops.toml`). Drops: the farming materials AND rare seeds (so land you cannot yet buy is sometimes sown). XP: a few hundred, flat.
3. **Watering minigame**. The hourly water button becomes a 5-tap timing/sequence minigame (reuse `screens/sequence.py` pieces): perfect = bonus cycle chance on that plot, miss = normal water. Effort: medium. Drops: none new; it only upgrades water. Smallest change to the existing loop but least grindable (once an hour).

Recommendation: option 1 first (cheap, grindable, bounded), then 2 for materials if wanted. Crop xp (see the xp proposal) is separate and should be lowered before any of this ships.

Question: which one first: Tend streak (1), Scavenge (2) or the watering minigame (3)?

## BUILT (approved shape of option 1: Tend, byproducts every growth cycle)
- `Plot.tended` counts cycles already collected; the **Tend** button on the farm page rolls the farming drop table `byproduct_rolls[field]` times per waiting cycle (a plot keeps at most `byproduct_max_cycles` = 3 waiting: check in about every 3 hours or lose some). No xp (xp_per_cycle stays 500, paid at harvest).
- Rolls per cycle by field: [4, 6, 8, 10, 10, 10, 12, 12, 4, 14, 14, 14, 16, 18]. One full roll of the drop table is worth ~618 bits, so byproducts are 10-45% of a crop's own hourly income (rose, a weak crop, is 43%; ambrosia 14%); guard test keeps every field within 10-50%.
- 9 plots tended every hour add roughly 55,000 bits' worth of materials an hour on top of about 270,000 from the crops themselves; later fields also roll starred materials (`services/stars.py`).
