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
    user, inst = await with_tool("wilted_axe")
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
    assert (await user.instance(inst.id)).template_id == "wilted_axe" and steps == 6
    assert offer is None


# ---- the screens ------------------------------------------------------------------------------------------------
async def test_the_upgrade_screen_lists_tools_and_upgrades_one(db):
    up = cost_of("starter_axe")
    user, inst = await with_tool(purse=up.bits, materials=dict(up.items))
    nav, inter = await hub("inventory")
    await click(nav, inter, "Upgrade tools")
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
    assert "You already have a axe" in all_text(nav)
    assert [b.disabled for b in buttons(nav) if b.label == "Buy"].count(True) == 1  # just the axe's Buy button


# ---- every tool upgrades, with a bit of everything -------------------------------------------------------------------
def tools_by_kind():
    kinds = {}
    for item in REG.items.values():
        if item.tool:
            kinds.setdefault(item.tool.kind, []).append(item)
    return kinds


def test_every_kind_of_tool_has_an_upgrade_chain_and_only_the_best_tool_ends_it():
    kinds = tools_by_kind()
    assert set(kinds) == {"pickaxe", "axe", "rod", "sword"}
    for kind, tools in kinds.items():
        tops = [t for t in tools if t.tool.upgrade is None]
        assert len(tops) == 1, (kind, [t.id for t in tops])
        assert tops[0].tool.power == max(t.tool.power for t in tools)
        # ...and every other tool of that kind leads there
        for tool in tools:
            current = tool
            while current.tool.upgrade:
                current = REG.item(current.tool.upgrade.to)
            assert current.id == tops[0].id, (tool.id, current.id)


TOOL_SKILL = {"pickaxe": "mining", "axe": "foraging", "rod": "fishing"}  # (swords: combat has no materials yet)


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
