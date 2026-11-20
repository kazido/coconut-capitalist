"""The four combat classes: the weapon in the combat slot picks the kit (configs/combat.toml [classes])."""

import pytest

from cococap.errors import GameRuleError
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
        assert unit.skills == [k.skill for k in cls.kit if k.level <= 1][: combat.LOADOUT_SIZE]  # class level 1 on a fresh account
        assert combat.class_for(kind) is cls


async def test_kit_skills_unlock_with_combat_level(db):
    user = await User.get(1)
    item = await user.give_instance(WEAPONS["bow"])
    await equipment.equip(user, "combat", item.id)
    kit = REG.combat.classes["archer"].kit
    unit = await combat.build_player(user)
    assert all(k.skill not in unit.skills for k in kit if k.level > 0)
    xp = User.level_to_xp(max(k.level for k in kit)) + 1  # +1: float rounding
    await user.update_skill("combat", lambda s: s.class_xp.__setitem__("archer", xp))
    assert (await combat.build_player(user)).skills == [k.skill for k in kit][: combat.LOADOUT_SIZE]


async def test_loadout_picks_which_unlocked_skills_are_on_the_buttons(db):
    user = await User.get(1)
    await equipment.equip(user, "combat", (await user.give_instance(WEAPONS["bow"])).id)
    kit = REG.combat.classes["archer"].kit
    await user.update_skill("combat", lambda s: s.class_xp.__setitem__("archer", User.level_to_xp(max(k.level for k in kit)) + 1))
    last = kit[-1].skill
    await combat.set_loadout(user, [kit[0].skill, last])
    assert (await combat.build_player(user)).skills == [kit[0].skill, last]
    with pytest.raises(GameRuleError):
        await combat.set_loadout(user, [])
    with pytest.raises(GameRuleError):
        await combat.set_loadout(user, ["not_a_skill"])


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
