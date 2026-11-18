# Magnet auto-aim (plan, NOT built; waiting for approval)

Today (`services/mining.py`, `screens/mine.py`): the magnet is a fuel meter (`magnet_on`, mining level 5, `magnet_meter`, `drain_per_row`). While it has fuel,
`MineRun.best_columns()` returns the column(s) of the NEXT row worth the most (sell price x qty, holes ignored) and the screen draws a ✨ over them. The player
still presses ⬅️/➡️ (`MineRun.move`, shifts ALL cursors by one, wrapping) to put the cursor(s) there, then digs. With several cursors (reactor columns) the cursors are a fixed pattern that moves as one block.

Simplest version: **auto-place by default while the magnet has fuel.** In `MineRun`, after each dig (and at start) if `magnet_active`, set `self.cursors` to the columns the
pattern needs so it covers the best column (shift the whole block, so the player's spacing stays). Move buttons stay, so the player can override a row; the magnet fuel is already spent per row it marks, so no new cost.
Tests: cursors land on `best_columns()` when the magnet has fuel, stay put without fuel, multi-cursor block still covers the best column. About 15 lines plus tests, no config or DB change.

Alternative: make it an upgrade (a flag/stat such as a `magnet_aim` mastery node or tool stat, default off). Costs a config entry, a mastery/tool line and a wiki line, and leaves the base magnet as "marks only".

APPROVED by the user: auto-place for everyone while the magnet has fuel; build AFTER the screen consolidation, as its own commit.

## Addendum (plan only, NOT built)
Facts: `vent_chance` 0.15 per cell (no loot, `vent_relief` 12 pressure off, free, no skipped dig); `brace_amount` 15 (costs a brace AND skips the dig: no loot that row);
braces = `braces_base` 1 + 1 per 5 reactor levels + tool stat, +1 per cache cell (`cache_chance` 0.06). A dig adds `creak` 2 + the ore's hardness (copper ~6, gold 9+) pressure, so
a brace undoes about 2 plain digs' pressure. Risk is 0 under 20 pressure, then 0.40 x ((p-20)/80)^2 per dig.
1. **Vents visible**: `row_mark`/`feel` only show soft/firm/hard from above (vents hide among SOFT cells, deliberately). Proposal: vents stay hidden by default but the magnet row reveals
   them: when the magnet has fuel, the row header marks vent columns (a small 💨 over the column), so the player CAN steer to a vent. Cheap: `MineRun.vent_columns()`, drawn in `render_shaft`. Lookahead rows unchanged.
2. **Magnet vs vents/braces**: keep the magnet value-only (simple, predictable), but auto-aim becomes pressure-aware: when pressure >= a threshold (proposal 60, `autoaim_vent_pressure`) and the row has a visible vent, aim at the vent
   (free relief, no brace). It never auto-uses braces (a brace is a button, the player decides). Below the threshold: richest column. A cache is never chased (its value is 0 to the magnet).
3. **Braces weak**: 15 pressure = ~2 digs, and the dig is lost. Proposal: `brace_amount` 15 -> 22 and a brace no longer skips the dig's NEXT creak (i.e. it still skips the dig but also removes 2 hidden pressure, same as one free creak). Simplest single change: 15 -> 25 and keep the rest. Test: `tests/` descent guards read the number from the registry.
4. **Reactor harder to fill** (what fills it: 4 core gems, found only in the deepest tables/vaults (`vault_gem_chance` 0.03) and wyrmholes; each level needs one implosion gem, `drop rate` 5 = 1 in 5 per wyrmhole implosion roll, wyrmhole odds 1 in 25000 per cell shrinking by 5000 per gem placed, never below 1000;
   max 25 levels). `scripts.balance` does NOT model the reactor (mining = 14,758 bits/active min, 7,123 xp/h today; it will not move with this change), so the numbers are by hand: raising `[wyrmhole].odds` 25000 -> 30000 (and `min_odds` 1000 -> 1200) is a ~17% cut in wyrmholes, i.e. implosion gems; `vault_gem_chance` 0.03 -> 0.025 slows the core gems a bit. Modest: change only the wyrmhole odds. Auto-aim does not change digging speed, only accuracy of the pick, so the real reason to nerf is value/min going up; check with a sim before landing.

One question: go with these four proposals as written (vents revealed by the magnet, vent-aware auto-aim at 60 pressure, brace 15 -> 25, wyrmhole odds 25000 -> 30000)?
