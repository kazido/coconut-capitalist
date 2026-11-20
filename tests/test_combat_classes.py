"""The four combat classes: the weapon in the combat slot picks the kit (configs/combat.toml [classes])."""

import pytest

from cococap.registry import get_registry
from cococap.registry.loader import _validate_combat
from cococap.registry.models import KitSkill
from cococap.services import combat, equipment
from cococap.user import User

REG = get_registry()
WEAPONS = {"sword": "tool_sword_starter", "bow": "tool_bow_starter", "staff": "tool_staff_starter", "shield": "tool_shield_starter"}


async def test_each_weapon_equips_into_combat_and_picks_its_class_kit(db):
    for kind, template in WEAPONS.items():
        user = await User.get(1)
        item = await user.give_instance(template)
        await equipment.equip(user, "combat", item.id)
        cls = REG.combat.classes[next(c for c, v in REG.combat.classes.items() if v.weapon == kind)]
        unit = await combat.build_player(user)
        assert unit.skills == [cls.kit[0].skill]  # level 0 here: only the basic is open
        assert combat.class_for(kind) is cls


async def test_kit_skills_unlock_with_combat_level(db):
    user = await User.get(1)
    item = await user.give_instance(WEAPONS["bow"])
    await equipment.equip(user, "combat", item.id)
    kit = REG.combat.classes["archer"].kit
    unit = await combat.build_player(user)
    assert all(k.skill not in unit.skills for k in kit if k.level > 0)
    await user.add_xp("combat", User.level_to_xp(max(k.level for k in kit)) + 1)  # +1: float rounding
    assert (await combat.build_player(user)).skills == [k.skill for k in kit]


async def test_bare_hands_use_the_default_kit(db):
    user = await User.get(1)
    assert (await combat.build_player(user)).skills == REG.combat.kits["default"]
    assert combat.class_for(None) is None


def test_loader_rejects_a_class_whose_first_skill_has_a_cooldown():
    rules = REG.combat
    melee = rules.classes["melee"]
    bad = melee.model_copy(update={"kit": [KitSkill(skill="cleave", level=0), *melee.kit[1:]]})
    problems = _validate_combat(REG, rules.model_copy(update={"classes": {**rules.classes, "melee": bad}}))
    assert any("melee" in p and "no cooldown" in p for p in problems)
    assert _validate_combat(REG, rules) == []
