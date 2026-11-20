"""What a tool's power does, in numbers: every tool starts at power 3, and the pages say what an upgrade changes."""

from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import fishing, tool_effects
from cococap.services.equipment import equip
from cococap.user import User
from tests.conftest import set_columns
from tests.test_hub import all_text, buttons, click, hub

REG = get_registry()
STARTERS = {"pickaxe": "tool_pickaxe_rookie", "axe": "tool_axe_starter", "rod": "tool_rod_starter", "can": "tool_can_tin"}


def test_every_kind_of_tool_starts_at_power_three():
    assert {kind: REG.item(item).tool.power for kind, item in STARTERS.items()} == {kind: 3 for kind in STARTERS}


def test_the_effect_numbers_are_the_ones_the_game_uses():
    rules = REG.fishing
    for power in (3, 8, 30):
        wait, slips, rare, extra = tool_effects.effects("rod", power)
        assert wait.value == f"~{fishing.typical_wait(power, rules):.0f}s" and slips.value == str(fishing.slips_allowed(power, rules))
        assert rare.value == f"+{fishing.rod_luck(power, rules):.0%} likelier"
        mean = sum(fishing.extra_fish(power, rules, Random(i)) for i in range(4000)) / 4000
        assert float(extra.value) == pytest.approx(mean, abs=0.06)
    assert tool_effects.effects("axe", 12)[0].value == "12" and tool_effects.effects("can", 7)[0].value == "7"
    assert tool_effects.effects("sword", 5)[0].value == f"+{REG.tools.sword.attack * 5:.0f}"


def test_every_kind_has_a_plain_sentence_about_what_power_is_for_and_a_better_tool_never_does_less():
    assert set(tool_effects.HOW) - set(tool_effects.WEAPON_KINDS) == set(STARTERS)  # weapons have their own templates
    for kind in STARTERS:
        assert tool_effects.HOW[kind] and tool_effects.effects(kind, 3)
    assert tool_effects.compare("pickaxe", 3, 9)[0] == "Ore per lode: ×1.00 → **×2.50**"
    assert tool_effects.summary("axe", 5).startswith("Hit points per chop 5")


async def test_the_tools_page_shows_each_tool_with_its_power(db):
    user = await User.get(1)
    for kind, item in STARTERS.items():
        await equip(user, {"pickaxe": "mining", "axe": "foraging", "rod": "fishing", "can": "farming"}[kind],
                    (await user.give_instance(item)).id)
    nav, _ = await hub("tools")
    lines = all_text(nav).split("\n")
    for skill in ("Mining", "Foraging", "Fishing", "Farming"):
        assert sum(skill in line and "power **" in line for line in lines) == 1, skill  # one compact line per skill


# ---- every upgrade changes several things at once -------------------------------------------------------------------------------------
def test_every_kind_of_tool_changes_at_least_three_things_when_it_gets_better():
    for kind in STARTERS:
        now, after = tool_effects.effects(kind, 3), tool_effects.effects(kind, 40)
        changed = [a.label for a, b in zip(now, after, strict=True) if a.value != b.value]
        assert len(changed) >= 3, (kind, changed)
        assert [e.label for e in now] == [e.label for e in after]


def test_a_starter_tool_gets_none_of_the_extras_so_nothing_changed_at_the_start():
    for kind in ("pickaxe", "axe", "can"):
        assert all(v == 0 for v in tool_effects.power_stats(kind, 3).values()), kind
    for kind in tool_effects.WEAPON_KINDS:  # a weapon's attack counts every point; the rest only the points above 3
        stats = tool_effects.power_stats(kind, 3)
        assert stats["attack"] == getattr(REG.tools, kind).attack * 3
        assert stats["hp"] == stats["defense"] == stats["speed"] == 0


def test_more_power_never_gives_less_of_anything():
    for kind in ("pickaxe", "axe", "can"):
        low, high = tool_effects.power_stats(kind, 9), tool_effects.power_stats(kind, 71)
        assert all(high[k] >= low[k] for k in low) and any(high[k] > low[k] for k in low), kind
