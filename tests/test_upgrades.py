import discord
import pytest

from cococap.registry import get_registry
from cococap.services import shop, upgrades
from cococap.services.equipment import add_enchant, effective_stats, equip
from cococap.user import User
from tests.conftest import set_columns
from tests.test_hub import all_text, buttons, click, find_button, hub

REG = get_registry()


async def with_tool(template="starter_axe", skill="foraging", purse=10**9, materials=None):
    user = await User.get(1)
    await set_columns(user, purse=purse)
    inst = await user.give_instance(template)
    await equip(user, skill, inst.id)
    for item_id, quantity in (materials or {}).items():
        await user.add_item(item_id, quantity)
    return user, inst


def cost_of(template):
    return REG.item(template).tool.upgrade


async def stock_up(user, template):
    for item_id, quantity in cost_of(template).items.items():
        await user.add_item(item_id, quantity)


# ---- the data ---------------------------------------------------------------------------------------------------
def test_every_chain_climbs_and_ends():
    for item in REG.items.values():
        if not (item.tool and item.tool.upgrade):
            continue
        seen, current = {item.id}, item
        while current.tool.upgrade:
            nxt = REG.item(current.tool.upgrade.to)
            assert nxt.tool.kind == item.tool.kind and nxt.tool.power > current.tool.power
            assert nxt.id not in seen
            seen.add(nxt.id)
            current = nxt


def test_every_starter_tool_can_be_upgraded_and_costs_bits_and_materials():
    for starter in ("starter_axe", "starter_rod", "rookiepickaxe"):
        up = cost_of(starter)
        assert up.bits > 0 and up.items, starter


# ---- upgrading --------------------------------------------------------------------------------------------------
async def test_an_upgrade_costs_bits_and_materials_and_the_tool_changes_in_place(db):
    up = cost_of("starter_axe")
    user, inst = await with_tool(purse=up.bits + 5, materials={k: v + 3 for k, v in up.items.items()})
    await add_enchant(user, inst.id, "soloist")
    done = await upgrades.upgrade(user, inst.id)
    assert done.target.id == "thornwhip_axe"
    await user.refresh()
    assert user.purse == 5
    for item_id, quantity in up.items.items():
        assert await user.item_quantity(item_id) == 3
    after = await user.instance(inst.id)
    assert after.template_id == "thornwhip_axe" and after.enchants == {"soloist": 1}
    assert (await user.equipped_instance("foraging")).id == inst.id  # still equipped, same tool
    assert effective_stats(after).power == REG.item("thornwhip_axe").tool.power
    assert len(await user.instances()) == 1


async def test_a_rolled_bonus_survives_the_upgrade(db):
    user = await User.get(1)
    await set_columns(user, purse=10**9)
    inst = await user.give_instance("starter_axe", rolled={"power": 2})
    await stock_up(user, "starter_axe")
    await upgrades.upgrade(user, inst.id)
    assert effective_stats(await user.instance(inst.id)).power == REG.item("thornwhip_axe").tool.power + 2


async def test_missing_bits_or_materials_changes_nothing_and_says_what_is_short(db):
    up = cost_of("starter_axe")
    user, inst = await with_tool(purse=up.bits - 1, materials={k: v for k, v in up.items.items()})
    with pytest.raises(upgrades.UpgradeError, match="more bits"):
        await upgrades.upgrade(user, inst.id)
    user2 = await User.get(2)
    await set_columns(user2, purse=10**9)
    inst2 = await user2.give_instance("starter_axe")
    short = {k: v - 1 for k, v in up.items.items()}
    for item_id, quantity in short.items():
        await user2.add_item(item_id, quantity)
    with pytest.raises(upgrades.UpgradeError, match=r"\d+/\d+"):
        await upgrades.upgrade(user2, inst2.id)
    assert (await user2.instance(inst2.id)).template_id == "starter_axe"
    assert await user2.get_bits() == 10**9
    assert await user2.items() == short


async def test_two_clicks_at_once_upgrade_once_and_charge_once(db):
    import asyncio

    up = cost_of("starter_axe")
    user, inst = await with_tool(purse=up.bits * 2, materials={k: v * 2 for k, v in up.items.items()})
    results = await asyncio.gather(upgrades.upgrade(user, inst.id), upgrades.upgrade(user, inst.id), return_exceptions=True)
    assert sum(not isinstance(r, Exception) for r in results) == 1
    await user.refresh()
    assert (await user.instance(inst.id)).template_id == "thornwhip_axe"
    assert user.purse == up.bits  # charged once...
    for item_id, quantity in up.items.items():
        assert await user.item_quantity(item_id) == quantity  # ...for the materials too


async def test_the_best_tool_of_a_kind_has_nowhere_to_go(db):
    user, inst = await with_tool("elderwood_axe")
    assert await upgrades.offer_for(user, inst) is None
    with pytest.raises(upgrades.UpgradeError, match="any further"):
        await upgrades.upgrade(user, inst.id)


async def test_you_cannot_upgrade_someone_elses_tool(db):
    _, inst = await with_tool()
    other = await User.get(2)
    with pytest.raises(upgrades.UpgradeError, match="don't own"):
        await upgrades.upgrade(other, inst.id)


async def test_a_tool_that_needs_a_higher_level_waits_for_it(db, monkeypatch):
    up = cost_of("starter_axe")
    user, inst = await with_tool(purse=up.bits, materials=dict(up.items))
    target = REG.item("thornwhip_axe")
    harder = target.model_copy(update={"tool": target.tool.model_copy(update={"requirement": 5})})
    monkeypatch.setitem(REG.items, "thornwhip_axe", harder)
    with pytest.raises(upgrades.UpgradeError, match="level 5"):
        await upgrades.upgrade(user, inst.id)


async def test_the_whole_axe_chain_can_be_climbed(db):
    user, inst = await with_tool(purse=10**12)
    steps = 0
    while (offer := await upgrades.offer_for(user, await user.instance(inst.id))):
        await stock_up(user, (await user.instance(inst.id)).template_id)
        await upgrades.upgrade(user, inst.id)
        steps += 1
    assert (await user.instance(inst.id)).template_id == "elderwood_axe" and steps == 7
    assert offer is None


# ---- the screens ------------------------------------------------------------------------------------------------
async def test_the_upgrade_screen_lists_tools_and_upgrades_one(db):
    up = cost_of("starter_axe")
    user, inst = await with_tool(purse=up.bits, materials=dict(up.items))
    nav, inter = await hub("tools")
    await click(nav, inter, "Upgrade")
    assert nav.screen.id == "upgrade" and "Thornwhip Axe" in all_text(nav)
    await click(nav, inter, "Upgrade")
    assert "became a **Thornwhip Axe**" in all_text(nav)
    assert (await user.instance(inst.id)).template_id == "thornwhip_axe"
    assert all(b.disabled for b in buttons(nav) if b.label == "Upgrade")  # can't afford the next one


async def test_an_unaffordable_upgrade_is_disabled_and_a_stale_click_is_refused(db):
    user, inst = await with_tool(purse=1)
    nav, inter = await hub("upgrade")
    button = find_button(nav, "Upgrade")
    assert button.disabled
    with pytest.raises(upgrades.UpgradeError):
        await button.callback(inter)  # a click that was already on its way


async def test_the_upgrade_screen_with_nothing_to_upgrade(db):
    nav, _ = await hub("upgrade")
    assert "Nothing to upgrade" in all_text(nav)


async def test_the_shop_marks_tools_you_already_have(db):
    user = await User.get(1)
    await set_columns(user, purse=10**6)
    await shop.buy(user, "starter_axe")
    nav, inter = await hub("shop")
    nav.screen.category = "foraging"
    await nav.screen.nav.refresh(inter)
    assert "Owned" in all_text(nav)
    assert not [b for b in buttons(nav) if b.label == "Buy" and b.style == discord.ButtonStyle.success and "axe" in (b.custom_id or "")]
    upgrade = next(b for b in buttons(nav) if b.label == "Upgrade tool")  # the axe's button is now a way to its upgrades
    await upgrade.callback(inter)
    assert nav.screen.id == "upgrade"


async def test_the_shop_lists_tools_before_everything_else_in_each_section(db):
    reg = get_registry()
    nav, inter = await hub("shop")
    headings = lambda: [line[4:] for line in all_text(nav).split("\n") if line.startswith("### ")]  # noqa: E731
    is_tool = lambda heading: any(i.tool and i.display == heading for i in reg.shop_items())  # noqa: E731
    for category in (None, "farming", "mining"):
        nav.screen.category, nav.screen.page = category, 0
        await nav.screen.nav.refresh(inter)
        kinds = [is_tool(h) for h in headings()]
        assert kinds and kinds == sorted(kinds, reverse=True), (category, headings())  # every tool comes before every non-tool


# ---- every tool upgrades, with a bit of everything -------------------------------------------------------------------
def tools_by_kind():
    kinds = {}
    for item in REG.items.values():
        if item.tool:
            kinds.setdefault(item.tool.kind, []).append(item)
    return kinds


def test_every_kind_of_tool_has_an_upgrade_chain_and_the_best_tools_end_it():
    kinds = tools_by_kind()
    assert set(kinds) == {"pickaxe", "axe", "rod", "sword", "can"}
    for kind, tools in kinds.items():
        tops = [t for t in tools if t.tool.upgrade is None]
        top_power = max(t.tool.power for t in tools)
        forked = any(t.tool.fork for t in tools)
        assert len(tops) == (2 if forked else 1), (kind, [t.id for t in tops])  # one top per road
        assert all(t.tool.power == top_power for t in tops)  # (both roads end equally strong)
        for tool in tools:  # ...and every tool leads to one of them
            current = tool
            while current.tool.upgrade:
                current = REG.item(current.tool.upgrade.to)
            assert current.id in {t.id for t in tops}, (tool.id, current.id)


def test_a_fork_offers_two_roads_of_the_same_power_and_bits_but_different_abilities_stats_and_materials():
    forks = [t for t in REG.items.values() if t.tool and t.tool.fork]
    assert {t.tool.kind for t in forks} == {"pickaxe", "rod", "axe", "can"}  # every skill with a tool line splits (at the 4th upgrade)
    for tool in forks:
        up, fork = tool.tool.upgrade, tool.tool.fork
        a, b = REG.item(up.to), REG.item(fork.to)
        while True:
            assert a.tool.power == b.tool.power and up.bits == fork.bits  # (the same power and the same bits at every step)
            assert a.tool.path and b.tool.path and a.tool.path != b.tool.path
            assert a.tool.ability and b.tool.ability and a.tool.ability != b.tool.ability  # a different ability on each road
            assert set(a.tool.stats) != set(b.tool.stats)  # different in kind, not just in size
            kind = tool.tool.kind
            mats = lambda cost, kind=kind: {i for i in cost.items if (REG.item(i).category == "fish" if kind == "rod" else REG.item(i).skill == TOOL_SKILL[kind])}  # noqa: E731
            assert mats(up) and mats(fork), (up.to, fork.to)
            if kind in ("pickaxe", "rod"):
                assert not mats(up) & mats(fork), (up.to, fork.to)  # each road asks for its own materials
            else:  # (a skill with few materials shares some, but the two roads never ask for the same set)
                assert mats(up) != mats(fork), (up.to, fork.to)
            if not (a.tool.upgrade and b.tool.upgrade):
                break
            up, fork = a.tool.upgrade, b.tool.upgrade
            a, b = REG.item(up.to), REG.item(fork.to)
        assert a.tool.upgrade is None and b.tool.upgrade is None


TOOL_SKILL = {"pickaxe": "mining", "axe": "foraging", "rod": "fishing", "can": "farming"}  # (swords: combat has no materials yet)


def chain_of(kind):
    tools = tools_by_kind()[kind]
    current = next(t for t in tools if not any(o.tool.upgrade and o.tool.upgrade.to == t.id for o in tools))
    steps = []
    while current.tool.upgrade:
        steps.append(current)
        current = REG.item(current.tool.upgrade.to)
    return steps


def test_early_upgrades_use_only_the_tools_own_skill_and_later_ones_mostly_do():
    for kind, skill in TOOL_SKILL.items():
        steps = chain_of(kind)
        for index, tool in enumerate(steps):
            up = tool.tool.upgrade
            items = {REG.item(m): q for m, q in up.items.items()}
            own = {i: q for i, q in items.items() if i.skill == skill}
            foreign = {i: q for i, q in items.items() if i.skill != skill}
            assert up.bits > 0 and len(own) >= 2, (tool.id, [i.id for i in own])
            if index == 0 or (index == 1 and len(steps) >= 5):  # the first steps (the first two of a long chain)
                assert not foreign, (tool.id, [i.id for i in foreign])
            else:  # later: a majority from its own skill, a smaller share from others
                assert foreign, (tool.id, "later steps should call on other skills too")
                assert len(own) > len(foreign) and sum(own.values()) > sum(foreign.values()), tool.id


def test_every_upgrade_step_takes_bits_and_several_materials():
    for item in REG.items.values():
        if item.tool and item.tool.upgrade:
            assert item.tool.upgrade.bits > 0 and len(item.tool.upgrade.items) >= 2, item.id


def test_every_upgrade_material_can_actually_be_found_somewhere():
    for item in REG.items.values():
        if not (item.tool and item.tool.upgrade):
            continue
        for material in item.tool.upgrade.items:
            it = REG.item(material)
            assert it.drop is not None or it.crop is not None, (item.id, material)


def test_later_steps_cost_more_than_earlier_ones():
    for tools in tools_by_kind().values():
        costs = []
        current = next(t for t in tools if not any(o.tool.upgrade and o.tool.upgrade.to == t.id for o in tools))
        while current.tool.upgrade:
            costs.append(current.tool.upgrade.bits)
            current = REG.item(current.tool.upgrade.to)
        assert costs == sorted(costs) and len(set(costs)) == len(costs)


async def test_every_chain_can_be_climbed_to_the_top_with_the_right_stuff(db):
    for kind, skill in (("pickaxe", "mining"), ("axe", "foraging"), ("rod", "fishing"), ("sword", "combat")):
        starter = next(t for t in tools_by_kind()[kind]
                       if not any(o.tool.upgrade and o.tool.upgrade.to == t.id for o in tools_by_kind()[kind]))
        user = await User.get(abs(hash(kind)) % 10_000 + 100)
        await set_columns(user, purse=10**12)
        await user.add_xp(skill, 10**9)  # high enough for every level requirement
        inst = await user.give_instance(starter.id)
        while (offer := await upgrades.offer_for(user, await user.instance(inst.id))):
            await stock_up(user, (await user.instance(inst.id)).template_id)
            await upgrades.upgrade(user, inst.id)
        top = (await user.instance(inst.id)).template_id
        assert REG.item(top).tool.upgrade is None and offer is None, kind


# ---- forks: two roads from one tool ----------------------------------------------------------------------------------------------
async def forked_pickaxe():
    both = {**cost_of("masterwork_pickaxe").items, **REG.item("masterwork_pickaxe").tool.fork.items}  # (the stock for either road)
    user, inst = await with_tool("masterwork_pickaxe", "mining", materials=both)
    await user.add_xp("mining", User.level_to_xp(1))
    return user, inst


async def test_a_tool_at_a_fork_has_two_offers_and_each_road_is_taken_on_its_own(db):
    user, inst = await forked_pickaxe()
    found = await upgrades.offers(user)
    assert [(o.path, o.target.id) for o in found] == [("up", "ironbound_pickaxe"), ("fork", "prospector_pickaxe")]
    done = await upgrades.upgrade(user, inst.id, path="fork")
    assert done.target.id == "prospector_pickaxe" and (await user.instance(inst.id)).template_id == "prospector_pickaxe"
    assert [o.target.id for o in await upgrades.offers(user)] == ["geode_pickaxe"]  # the road you took is the only one now
    assert (await user.equipped_instance("mining")).id == inst.id


async def test_each_road_gives_its_own_stats_and_ability_to_the_tool_in_use(db):
    from cococap.services import tool_effects
    from cococap.services.equipment import equipped_stats

    user, inst = await forked_pickaxe()
    await upgrades.upgrade(user, inst.id)  # the usual road: Warden
    safe = await equipped_stats(user, "mining")
    warden = tool_effects.power_stats("pickaxe", safe.power, REG, "Warden")
    assert safe.stats["danger_reduction"] == pytest.approx(warden["danger_reduction"]) and "ore_yield" not in safe.stats
    assert safe.stats["auto_bomb"] == 32 and "multi_mine" not in safe.stats and safe.stats["rich_chance"] == 0  # safety and an Auto-Bomb, no rich-lode bonus
    user2 = await User.get(2)
    await set_columns(user2, purse=10**9)
    inst2 = await user2.give_instance("masterwork_pickaxe")
    await equip(user2, "mining", inst2.id)
    for item_id, quantity in REG.item("masterwork_pickaxe").tool.fork.items.items():
        await user2.add_item(item_id, quantity)
    await upgrades.upgrade(user2, inst2.id, path="fork")
    greedy = await equipped_stats(user2, "mining")
    assert greedy.stats["ore_yield"] == pytest.approx(0.11) and greedy.stats["multi_mine"] == 0.25 and "auto_bomb" not in greedy.stats
    assert greedy.stats["danger_reduction"] == 0 and greedy.stats["braces"] == 0 and greedy.stats["rich_chance"] > 0  # NO pressure slow, but more rich lodes
    assert greedy.power == safe.power  # the same power: a different way to dig, not a stronger one


async def test_a_tool_with_no_fork_has_no_fork_offer(db):
    user, inst = await with_tool()
    assert [o.path for o in await upgrades.offers(user)] == ["up"]
    with pytest.raises(upgrades.UpgradeError, match="any further"):
        await upgrades.upgrade(user, inst.id, path="fork")


async def test_a_fork_shows_one_path_at_a_time_and_a_dropdown_swaps_between_them(db):
    from tests.test_hub import choose, select_named

    user, inst = await forked_pickaxe()
    nav, inter = await hub("upgrade")
    menu = select_named(nav, "Pick a path")
    assert [o.label for o in menu.options] == ["Warden path", "Prospector path"] and sum(o.default for o in menu.options) == 1
    text = all_text(nav)
    ups = [b for b in buttons(nav) if b.label == "Upgrade"]
    assert len(ups) == 1  # one path on the page
    first = text
    await choose(nav, inter, menu, menu.options[1].value)
    text = all_text(nav)
    assert text != first and "Prospector" in text
    ups = [b for b in buttons(nav) if b.label == "Upgrade"]
    assert len(ups) == 1 and not ups[0].disabled
    await ups[0].callback(inter)
    assert (await user.instance(inst.id)).template_id == "prospector_pickaxe" and "Prospector's Pickaxe" in all_text(nav)


async def test_each_path_page_has_its_own_ability_materials_and_numbers(db):
    from tests.test_hub import choose, select_named

    await forked_pickaxe()
    nav, inter = await hub("upgrade")
    seen = {}
    for option in select_named(nav, "Pick a path").options:
        menu = select_named(nav, "Pick a path")
        await choose(nav, inter, menu, option.value)
        seen[option.label] = all_text(nav)
    warden, prospector = seen["Warden path"], seen["Prospector path"]
    assert "Auto-Bomb" in warden and "Multi-Mine" not in warden and "Multi-Mine" in prospector and "Auto-Bomb" not in prospector.split("✨ New ability")[1]
    assert "Ore per lode: ×2.50 → **×4.00**" in warden and "Ore per lode: ×2.50 → **×4.44**" in prospector
    assert "Pressure builds: 2% slower → **6% slower**" in warden and "Pressure builds: 2% slower → **0% slower**" in prospector
    assert ("Obsidian" in warden) != ("Obsidian" in prospector) and ("Tin Ore" in warden) != ("Tin Ore" in prospector) and "fork in the road" in warden


def test_describe_stats_reads_negative_numbers_as_the_opposite():
    from cococap.screens.upgrade import describe_stats

    assert describe_stats({"ore_yield": 0.04, "danger_reduction": -0.01}) == "+4% more ore, +1% more creaking"
    assert describe_stats({"bite_speed": -0.02, "slips": 1}) == "+2% slower bites, +1 extra forgiven arrow(s)"


# ---- one tool per page ---------------------------------------------------------------------------------------------------------------
async def own_every_kind(user):
    for template in ("rookiepickaxe", "starter_axe", "starter_rod", "tin_can", "largebranch"):
        await user.give_instance(template)


def tool_page_title(nav) -> str:
    return next(line for line in all_text(nav).split("\n") if line.startswith("### "))


async def test_the_upgrade_page_shows_one_tool_at_a_time_and_pages_between_them(db):
    user = await User.get(1)
    await own_every_kind(user)
    nav, inter = await hub("upgrade")
    labels = [b.label for b in buttons(nav)]
    assert "1/5" in labels and next(b for b in buttons(nav) if b.label == "Prev").disabled
    first = tool_page_title(nav)
    text = all_text(nav)
    assert "Rookie Pickaxe" in first and "Reinforced Pickaxe" in text
    assert not any(name in text for name in ("Starter Axe", "Starter Rod", "Tin Watering Can", "Large Branch"))  # the others are on their own pages
    seen = [first]
    for _ in range(4):
        await click(nav, inter, "Next")
        seen.append(tool_page_title(nav))
    assert len(set(seen)) == 5 and "5/5" in [b.label for b in buttons(nav)] and next(b for b in buttons(nav) if b.label == "Next").disabled
    await click(nav, inter, "Prev")
    assert "4/5" in [b.label for b in buttons(nav)]


async def test_a_page_has_that_tools_costs_and_upgrading_it_keeps_you_on_it(db):
    user = await User.get(1)
    await set_columns(user, purse=10**9)
    await own_every_kind(user)
    axe_cost = cost_of("starter_axe")
    for item, quantity in axe_cost.items.items():
        await user.add_item(item, quantity)
    nav, inter = await hub("upgrade")
    await click(nav, inter, "Next")  # to the axe
    assert "Starter Axe" in tool_page_title(nav) and f"{axe_cost.items['feather']}" in all_text(nav)
    await click(nav, inter, "Upgrade")
    assert "became a **Thornwhip Axe**" in all_text(nav) and "Thornwhip Axe" in tool_page_title(nav)  # still on the axe's page, now the next step


async def test_a_single_tool_has_no_page_buttons_and_only_a_fork_has_a_dropdown(db):
    from tests.test_hub import selects

    user, inst = await forked_pickaxe()
    nav, _ = await hub("upgrade")
    assert not any(b.label in ("Prev", "Next") for b in buttons(nav)) and len(selects(nav)) == 1  # (one tool: nothing to page through)
    await user.give_instance("starter_axe")
    nav, _ = await hub("upgrade")
    assert any(b.label == "Prev" for b in buttons(nav))


async def test_the_upgrade_page_number_cannot_run_off_the_end(db):
    user = await User.get(1)
    await user.give_instance("starter_axe")
    nav, inter = await hub("upgrade")
    nav.screen.page = 9
    await nav.screen.nav.refresh(inter)
    assert nav.screen.page == 0 and "Starter Axe" in tool_page_title(nav)


async def test_confirm_upgrades_needs_a_second_press_and_moving_away_cancels_it(db):
    user, inst = await forked_pickaxe()
    await user.set_setting("confirm_upgrades", True)
    nav, inter = await hub("upgrade")
    up = [b for b in buttons(nav) if b.label == "Upgrade"][0]
    await up.callback(inter)
    assert (await user.instance(inst.id)).template_id != "prospector_pickaxe" and any(b.label == "Sure?" for b in buttons(nav))
    from tests.test_hub import choose, select_named

    menu = select_named(nav, "Pick a path")
    await choose(nav, inter, menu, menu.options[1].value)
    assert not any(b.label == "Sure?" for b in buttons(nav))  # (looking elsewhere cancels it)
    await [b for b in buttons(nav) if b.label == "Upgrade"][0].callback(inter)
    await [b for b in buttons(nav) if b.label == "Sure?"][0].callback(inter)
    assert (await user.instance(inst.id)).template_id != inst.template_id


async def test_upgrades_are_one_press_by_default(db):
    user, inst = await forked_pickaxe()
    nav, inter = await hub("upgrade")
    await [b for b in buttons(nav) if b.label == "Upgrade"][0].callback(inter)
    assert (await user.instance(inst.id)).template_id != inst.template_id


# ---- every tool line: three plain upgrades, and the fourth upgrade is the split ---------------------------------------------------------------
def test_every_line_takes_three_plain_upgrades_and_the_fourth_is_the_split():
    for kind, start in (("pickaxe", "rookiepickaxe"), ("axe", "starter_axe"), ("rod", "starter_rod"), ("can", "tin_can")):
        tool, plain = REG.item(start), 0
        while not tool.tool.fork:
            assert tool.tool.path is None, (kind, tool.id)  # no road before the split
            tool = REG.item(tool.tool.upgrade.to)
            plain += 1
        assert plain == 3, (kind, tool.id)  # three plain upgrades got us here: the next one (either way) is the split
        a, b = REG.item(tool.tool.upgrade.to), REG.item(tool.tool.fork.to)
        assert a.tool.path and b.tool.path and a.tool.path != b.tool.path and a.tool.power == b.tool.power, kind


def test_each_line_gets_longer_with_every_split_road_going_at_least_three_more_steps():
    for start in ("rookiepickaxe", "starter_axe", "starter_rod", "tin_can"):
        for first_road in (lambda t: t.tool.upgrade.to, lambda t: t.tool.fork.to):
            tool = REG.item(start)
            while not tool.tool.fork:
                tool = REG.item(tool.tool.upgrade.to)
            tool, steps = REG.item(first_road(tool)), 0
            while tool.tool.upgrade:
                tool, steps = REG.item(tool.tool.upgrade.to), steps + 1
            assert steps >= 2, (start, tool.id)  # (a road of at least three tools)


def test_the_four_roads_all_differ_in_their_own_numbers_and_the_axe_and_can_roads_lean_opposite_ways():
    from cococap.services import tool_effects as te

    lj, fg = te.power_stats("axe", 40, REG, "Lumberjack"), te.power_stats("axe", 40, REG, "Forager")
    assert lj["good_chop"] > fg["good_chop"] and lj["wear_slow"] < fg["wear_slow"]
    sp, al = te.power_stats("can", 9, REG, "Sprinkler"), te.power_stats("can", 9, REG, "Alchemist")
    assert al["crop_yield"] > sp["crop_yield"] and sp["drop_luck"] > al["drop_luck"]
    for tool_id in ("elderwood_axe", "canopy_axe", "moonwell_can", "athanor_can"):
        assert REG.item(tool_id).tool.ability and REG.item(tool_id).tool.stats  # each road has its own ability
