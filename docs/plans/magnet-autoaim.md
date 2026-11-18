# Magnet auto-aim (plan, NOT built; waiting for approval)

Today (`services/mining.py`, `screens/mine.py`): the magnet is a fuel meter (`magnet_on`, mining level 5, `magnet_meter`, `drain_per_row`). While it has fuel,
`MineRun.best_columns()` returns the column(s) of the NEXT row worth the most (sell price x qty, holes ignored) and the screen draws a ✨ over them. The player
still presses ⬅️/➡️ (`MineRun.move`, shifts ALL cursors by one, wrapping) to put the cursor(s) there, then digs. With several cursors (reactor columns) the cursors are a fixed pattern that moves as one block.

Simplest version: **auto-place by default while the magnet has fuel.** In `MineRun`, after each dig (and at start) if `magnet_active`, set `self.cursors` to the columns the
pattern needs so it covers the best column (shift the whole block, so the player's spacing stays). Move buttons stay, so the player can override a row; the magnet fuel is already spent per row it marks, so no new cost.
Tests: cursors land on `best_columns()` when the magnet has fuel, stay put without fuel, multi-cursor block still covers the best column. About 15 lines plus tests, no config or DB change.

Alternative: make it an upgrade (a flag/stat such as a `magnet_aim` mastery node or tool stat, default off). Costs a config entry, a mastery/tool line and a wiki line, and leaves the base magnet as "marks only".

One question: auto-aim for everyone with the magnet on (recommended), or only as an upgrade (mastery node)?
