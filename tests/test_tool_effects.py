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
    assert tool_effects.compare("pickaxe", 3, 9)[0] == "Ore per lode: ×1.00 → **×2.50**"
    assert tool_effects.summary("axe", 5).startswith("Hit points per chop 5")


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
    assert tool_effects.sword_stats(3) == (0, 0.0)


def test_more_power_never_gives_less_of_anything():
    for kind in ("pickaxe", "axe", "can"):
        low, high = tool_effects.power_stats(kind, 9), tool_effects.power_stats(kind, 71)
        assert all(high[k] >= low[k] for k in low) and any(high[k] > low[k] for k in low), kind


async def test_the_extras_are_in_the_stats_the_games_read(db):
    from cococap.services.equipment import effective_stats

    user = await User.get(1)
    pick = effective_stats(await user.give_instance("ironbound_pickaxe"))
    assert pick.stats["danger_reduction"] == pytest.approx(0.003 * 12 + 0.02) and pick.stats["braces"] == 0 and pick.stats["rich_chance"] > 0
    deep = effective_stats(await user.give_instance("mythril_pickaxe"))
    assert deep.stats["braces"] == 1 and deep.stats["danger_reduction"] > pick.stats["danger_reduction"]
    axe = effective_stats(await user.give_instance("masterwork_axe"))
    assert axe.stats["good_chop"] > 0 and axe.stats["wear_slow"] > 0 and effective_stats(await user.give_instance("starter_axe")).stats["good_chop"] == 0


async def test_a_better_pickaxe_makes_a_safer_and_richer_start_to_a_dig(db):
    from cococap.services import mining

    user = await User.get(1)
    await equip(user, "mining", (await user.give_instance("rookiepickaxe")).id)
    plain = await mining.start_run(user, Random(1))
    inst = await user.give_instance("mythril_pickaxe")
    await equip(user, "mining", inst.id)
    deep = await mining.start_run(user, Random(1))
    assert deep.growth_factor < plain.growth_factor and deep.rich_bonus > plain.rich_bonus and deep.braces > plain.braces


async def test_a_better_can_gives_bigger_harvests_and_sometimes_the_seed_back(db):
    from cococap.services import farming as f

    users = {}
    for uid, can in ((1, "tin_can"), (2, "moonwell_can")):
        user = await User.get(uid)
        await equip(user, "farming", (await user.give_instance(can)).id)
        users[uid] = user
    back = {}
    for uid, user in users.items():
        back[uid] = 0
        for i in range(120):
            await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "unlocked", True))
            await user.add_item("apple_seed", 1)
            await f.plant(user, 1, "apple_seed", now=0, registry=REG)
            await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "can_harvest", True))
            back[uid] += (await f.harvest(user, 1, Random(i), 0, REG)).extras["apple_seed"]
    assert back[1] == 0 and back[2] > 10  # (the starter can never gives a seed back: 18% for the best can)


async def test_a_better_sword_makes_you_tougher_not_only_stronger_and_a_starter_is_as_before(db):
    from cococap.services import combat

    user = await User.get(1)
    await user.add_xp("combat", User.level_to_xp(10) + 1)
    bare = await combat.build_player(user, REG)
    await equip(user, "combat", (await user.give_instance("largebranch")).id)
    starter = await combat.build_player(user, REG)
    assert (starter.max_hp, starter.defense) == (bare.max_hp, bare.defense)  # (a power 3 sword adds no hp or defense)
    await equip(user, "combat", (await user.give_instance("dreamnail")).id)
    dream = await combat.build_player(user, REG)
    assert dream.max_hp > starter.max_hp and dream.defense > starter.defense and dream.attack > starter.attack


async def test_the_upgrade_page_lists_each_of_the_several_changes_for_every_tool(db):
    user = await User.get(1)
    for item in STARTERS.values():
        await user.give_instance(item)
    nav, inter = await hub("upgrade")
    for _ in range(5):
        arrows = [line for line in all_text(nav).split("\n") if "→ **" in line and ":" in line and "Power" not in line]
        assert len(arrows) >= 3, arrows  # at least three "label: now → after" lines on every tool's page
        if next(b for b in buttons(nav) if b.label == "Next").disabled:
            break
        await click(nav, inter, "Next")
