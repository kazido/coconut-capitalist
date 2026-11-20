Status: IDEA, not started. Owner is "thinking of" it; confirm the open questions before building.

# Separate tool parts and weapon parts

## Idea
Today parts are generic: a tool = 1 Base + 1 Trim + 1 Accent and any part fits any kind (see `tools-smithing.md`).
Split them: **tool parts** (pickaxe, axe, rod, can) and **weapon parts** (sword, bow, staff, shield). Weapons are smithed
from weapon parts only, tools from tool parts only.

## Open questions (ask the owner, one at a time)
- Do weapon parts drop from combat only, and tool parts from the four gathering skills? (Combat is paused, so weapon drops wait.)
- Same 3 slots (Base/Trim/Accent) for weapons, or weapon-specific slots (blade/hilt/guard)?
- Do existing parts become tool parts, with weapon parts starting from zero?
- Same power-per-tier and trait rules? Weapon-only traits (damage, crit) now allowed since the pool is separate.

## Touch points (search first)
- `configs/items.toml` part items + `configs/smithing.toml` (traits, part kinds), `registry/models.py`
- `services/smithing.py` (which parts a kind accepts), `services/equipment.py`, `services/tool_effects.py` `WEAPON_KINDS`
- `screens/smithing.py` and the Parts tab (filter by tool vs weapon), part drop tables, starter-part migration
- Tests pinned to generic parts; run `balance-check` after.

## Done when
A weapon can only be smithed from weapon parts, tool parts can't go into weapons, drops and the Parts tab show both,
and the plan docs / STATUS are updated.
