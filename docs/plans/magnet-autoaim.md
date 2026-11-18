# Magnet auto-aim (plan, NOT built; waiting for approval)

Today (`services/mining.py`, `screens/mine.py`): the magnet is a fuel meter (`magnet_on`, mining level 5, `magnet_meter`, `drain_per_row`). While it has fuel,
`MineRun.best_columns()` returns the column(s) of the NEXT row worth the most (sell price x qty, holes ignored) and the screen draws a ✨ over them. The player
still presses ⬅️/➡️ (`MineRun.move`, shifts ALL cursors by one, wrapping) to put the cursor(s) there, then digs. With several cursors (reactor columns) the cursors are a fixed pattern that moves as one block.

Simplest version: **auto-place by default while the magnet has fuel.** In `MineRun`, after each dig (and at start) if `magnet_active`, set `self.cursors` to the columns the
pattern needs so it covers the best column (shift the whole block, so the player's spacing stays). Move buttons stay, so the player can override a row; the magnet fuel is already spent per row it marks, so no new cost.
Tests: cursors land on `best_columns()` when the magnet has fuel, stay put without fuel, multi-cursor block still covers the best column. About 15 lines plus tests, no config or DB change.

Alternative: make it an upgrade (a flag/stat such as a `magnet_aim` mastery node or tool stat, default off). Costs a config entry, a mastery/tool line and a wiki line, and leaves the base magnet as "marks only".

APPROVED by the user: auto-place for everyone while the magnet has fuel; build AFTER the screen consolidation, as its own commit.

## Addendum (plan only, NOT built; corrected by the user)
Build all of it after the screen consolidation, as its own commit(s).
1. **Vents visible**: while the magnet has fuel, the cursor row marks vent columns with a small 💨 (vents stay hidden otherwise). `MineRun.vent_columns()` drawn in `render_shaft`. The player steers to vents themselves.
2. **Auto-aim is value-only**: it ALWAYS picks the richest column (no vent/brace logic). Braces stay a button the player presses.
3. **Brace buff (approved)**: `brace_amount` 15 -> 25, nothing else (guard tests read the number from the registry).
4. **Magnet METER harder to fill** (the meter is the magnet's fuel, `[magnet]` in configs/mining.toml): it fills from ore (copper 1, iron 6, gold 38 points), holds `capacity` 1000 and each marked row burns `drain_per_row` 4.
   Before: a full meter = 250 marked rows (8 full 30-row mines), costs ~50,000 bits of ore (50 bits a point), so a marked row costs ~200 bits of ore.
   Proposed: `drain_per_row` 4 -> 6 only (capacity and ore values unchanged, so the meter still fills the same way). After: 166 marked rows (about 5.5 mines), a marked row costs ~300 bits of ore (+50%).
   Why drain and not the fill: auto-aim makes EVERY row a marked row, so the cost per row is the honest lever; it needs no change to the Auto-feed or shop numbers. (Sim = this arithmetic: 1000/4 = 250 rows vs 1000/6 = 166; the Magnet Save tool stat `magnet_save` still takes up to 90% off the drain.) Before landing, re-run `scripts.balance` and `tests/test_economy_guard.py`.
