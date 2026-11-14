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
STARTERS = {"pickaxe": "rookiepickaxe", "axe": "starter_axe", "rod": "starter_rod", "can": "tin_can", "sword": "largebranch"}


def test_every_kind_of_tool_starts_at_power_three():
    assert {kind: REG.item(item).tool.power for kind, item in STARTERS.items()} == {kind: 3 for kind in STARTERS}


def test_a_starter_pickaxe_digs_plain_ore_and_each_step_still_pays_what_it_did():
    d = REG.mining.descent
    ore = lambda tool: tool_effects.effects("pickaxe", REG.item(tool).tool.power)[0].value  # noqa: E731
    assert ore("rookiepickaxe") == "×1.00" and ore("reinforced_pickaxe") == "×1.50" and ore("masterwork_pickaxe") == "×2.50"
    assert d.power_base == 3  # (the jump from level to level is the same as when it started at power 1)


def test_a_starter_sword_hits_as_hard_as_it_did_when_it_started_at_power_one():
    p = REG.combat.player
    assert p.base_attack + p.attack_per_power * REG.item("largebranch").tool.power == 17  # (14 + 3 x 1 before)


def test_the_effect_numbers_are_the_ones_the_game_uses():
    rules = REG.fishing
    for power in (3, 8, 30):
        wait, slips, rare, extra = tool_effects.effects("rod", power)
        assert wait.value == f"~{fishing.typical_wait(power, rules):.0f}s" and slips.value == str(fishing.slips_allowed(power, rules))
        assert rare.value == f"+{fishing.rod_luck(power, rules):.0%} likelier"
        mean = sum(fishing.extra_fish(power, rules, Random(i)) for i in range(4000)) / 4000
        assert float(extra.value) == pytest.approx(mean, abs=0.06)
    assert tool_effects.effects("axe", 12)[0].value == "12" and tool_effects.effects("can", 7)[0].value == "7"
    assert tool_effects.effects("sword", 5)[0].value == f"+{REG.combat.player.attack_per_power * 5}"


def test_every_kind_has_a_plain_sentence_about_what_power_is_for_and_a_better_tool_never_does_less():
    assert set(tool_effects.HOW) == set(STARTERS)
    for kind in STARTERS:
        assert tool_effects.HOW[kind] and tool_effects.effects(kind, 3)
    assert tool_effects.compare("pickaxe", 3, 9) == ["Ore per lode: ×1.00 → **×2.50**"]
    assert tool_effects.summary("axe", 5) == "Hit points per chop 5"


async def test_the_upgrade_page_says_what_the_tool_does_and_what_the_next_one_changes(db):
    user = await User.get(1)
    for kind, item in STARTERS.items():
        await user.give_instance(item)
    nav, inter = await hub("upgrade")
    seen = {}
    for _ in range(5):
        text = all_text(nav)
        seen[next(line for line in text.split("\n") if line.startswith("### "))] = text
        if next(b for b in buttons(nav) if b.label == "Next").disabled:
            break
        await click(nav, inter, "Next")
    joined = "\n".join(seen.values())
    assert len(seen) == 5
    assert "Ore per lode: ×1.00 → **×1.50**" in joined  # the pickaxe
    assert "Hit points per chop: 3 → **5**" in joined  # the axe
    assert "Plots watered an hour: 3 → **4**" in joined  # the can
    assert "Wait for a bite" in joined and "Forgiven wrong arrows" in joined and "Rare fish" in joined and "Extra fish per catch" in joined  # the rod
    assert "Attack from the sword: +9 → **+15**" in joined  # the sword
    for how in tool_effects.HOW.values():
        assert how in joined  # each page opens with what power is for


async def test_an_enchant_or_rolled_bonus_is_counted_in_the_before_and_after(db):
    user = await User.get(1)
    await set_columns(user, purse=10**9)
    await user.give_instance("rookiepickaxe", rolled={"power": 2})
    nav, _ = await hub("upgrade")
    # now 3 + 2 = 5 (x1.50), after 5 + 2 = 7 (x2.00): the bonus carries over to the better pickaxe
    assert "Power **5** → **7**" in all_text(nav) and "Ore per lode: ×1.50 → **×2.00**" in all_text(nav)


async def test_a_new_ability_is_announced_on_the_upgrade_that_gives_it(db):
    user = await User.get(1)
    await user.give_instance("rustedbroadsword")
    nav, _ = await hub("upgrade")
    assert "New ability" in all_text(nav) and REG.item("dreamnail").tool.ability_name in all_text(nav)
    nav2, _ = await hub("upgrade", user_id=2)  # (nobody has anything to upgrade: no page)
    assert "Nothing to upgrade" in all_text(nav2)


async def test_the_tools_page_shows_each_tools_numbers(db):
    user = await User.get(1)
    for kind, item in STARTERS.items():
        await equip(user, {"pickaxe": "mining", "axe": "foraging", "rod": "fishing", "can": "farming", "sword": "combat"}[kind],
                    (await user.give_instance(item)).id)
    nav, _ = await hub("tools")
    text = all_text(nav)
    for fragment in ("Ore per lode ×1.00", "Hit points per chop 3", "Plots watered an hour 3", "Wait for a bite", "Attack from the sword +9"):
        assert fragment in text


async def test_each_requirement_of_an_upgrade_is_on_its_own_line(db):
    from tests.test_upgrades import cost_of

    user = await User.get(1)
    await user.give_instance("starter_axe")
    nav, _ = await hub("upgrade")
    lines = all_text(nav).split("\n")
    cost = cost_of("starter_axe")
    wanted = [f"{REG.item(i).display}  **0/{q}**" for i, q in cost.items.items()]
    assert len(wanted) >= 2
    for requirement in wanted:
        assert sum(requirement in line for line in lines) == 1
    bits_line = next(line for line in lines if "bits (you have" in line)
    assert all(requirement not in bits_line for requirement in wanted) and "·" not in bits_line  # (the bits are not squeezed onto the same line)
    assert len({lines.index(next(line for line in lines if r in line)) for r in wanted}) == len(wanted)
