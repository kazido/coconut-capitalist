# Ideas inbox

The owner writes ideas here in free text. The lead turns each into a plan under `docs/plans/` (with approval), then deletes the line here.

Integrate special mines into the mastery trees. "+10% chance for mines to special"
Review the rarity of wedges. I think the gilded wedge is way too high of a rarity.
Add more bomb types. Scarab is the only right now and will be the best. We can come up with some cool ones.
Find a reason to craft more than one of each fuel. Don't want to have to pay fuel for each trip, but we have all these different fuel types for what? One trip? We can do something cool with them I'm sure.

Add more ways to interact with the Reactor. Like depositing ores for temporary boosts. +wyrmhole chances, +special mine chance, +xp, etc.

WOULD LIKE TO AVOID LINEAR SKILLS. I want skills to tie into each other somehow. Maybe Reactor could also give bonuses to fishing and foraging if stronger gems are put into it. Maybe Releaf foundation can give bonuses to other skills when it's filled. Maybe fishing could have something similar too. Not all need to have a direct tie in, but cool ideas like that will go far.

## Testing notes (2026-11-19)

Bugs:
- "Claim your tools" shows when tools are owned. Cause: the message fires whenever no tool is EQUIPPED for that skill (services/equipment.py equipped_stats -> None), e.g. a smithed or unequipped tool. Fix: auto-equip, or say "equip a tool" when one is owned.
- Mining / lode claims: show the drop emojis in the top "you got" line.

Tools / smithing:
- Parts should show in the inventory.
- Second look at part traits.
- Restricted parts: just an emoji next to the name.
- Accessories: one toggle button for equip/unequip.
- One page per tool (the detail page) that also opens its accessories; drop the separate accessories page.
- Enchants: today a smithed tool holds ONE enchant and a new scroll replaces (destroys) the old one. Owner does not want to hoard scrolls for the best tool. Later: a way to remove parts or enchants.
- Art: smithing icon; icons for all accessories.

Pets:
- Score breakdown: a pet detail page with a bar per skill.
- Offline work: the active pet DOES haul while away (needs fuel), but it only banks when Collect is pressed on the Pets page; inactive pets only add a % bonus. Owner expected sidekicks to work offline: decide auto-collect and/or sidekicks hauling.
- Food buff: works, but it is 1.5x PET xp for a while, not skill xp. Make that clear (or change it).
- Fuel: still no reason to make more than one fuel per location (see the fuel line above).

Skills:
- Rename "Light skills" to "Lesser skills"; page needs a better look.

Reactor:
- 4 gem slots on one line, ui_square for empty slots, no gem names.
- Remove wyrmhole odds, columns, braces and pressure from the page. Notify on reactor level-up what was unlocked, and list unlocks under the gems.
