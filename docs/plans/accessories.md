# Accessories + Light skills tab (tools-smithing step 8)
Status: built on design (rules, Tools tab, shop basics, drops, Light skills tab). Delete when design lands.

Accessories are where the STAT bonuses live now (enchants are abilities only; part traits are generic only).

- **What:** item instances (like parts and tools), template ids `acc_<skill>_<name>` in `configs/accessories.toml`:
  skill, name, emoji, rarity, base stats (`{stat = amount}`), trait slots by rarity. Each skill has **2 accessory slots**
  (`Skill.accessory_ids: list[int]`, JSON field, no migration). Their stats are merged in `equipment.equipped_stats` next to the tool's,
  so every engine reads them with no engine changes.
- **Per-skill trait pools** (in accessories.toml): the skill traits leave the part pool and move here, plus the retired stat enchants:
  - mining: Vein Sense (rich_chance), Ore Bounty (ore_yield), Steady Hold (danger_reduction)
  - foraging: Sharp Cut (good_chop), Seasoned (wear_slow), Steady Hold (danger_reduction)
  - fishing: Lure (bite_speed), Deepcall (rare_luck)
  - farming: Fertile Blade (crop_yield), Gleaner (drop_luck)
  - all skills: Scholar (xp) as a rarer trait
  Part traits keep only the generic ones (power_core, scholar_edge, appraiser_eye); more generic part traits come later.
- **Getting them:**
  - Basic accessories (no traits, small fixed stat) in the Shop, one or two per skill. Bought with bits.
  - Rarer ones (rolled traits, 1 to 3 by rarity) drop from that skill's actions, rolled where the part roll is (`maybe_drop_part`'s callers),
    with a small chance (TODO(balance)). Tradeable, like parts.
- **UI:** the Tools page gets an **Accessories** tab: your accessories by skill, the 2 slots per skill, equip/unequip dropdowns.
- **Light skills tab:** the Skills page (`screens/skills.py`) becomes a `TabsScreen` with "Skills" (the 4 now) and "Light skills"
  (Smithing: level, xp bar, max part tier, next unlock). Driven by a small list so later light skills just appear.
- Tests: equip 2 max per skill, stats reach `equipped_stats`, part pool now generic only, shop basics buyable, drops roll traits from the
  right pool, Light skills tab renders (hub layout test).
