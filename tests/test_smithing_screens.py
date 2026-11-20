"""The Smithing and Parts tabs of the Tools page (screens/smithing.py)."""

from cococap.constants import STARTER_TOOLS
from cococap.registry import get_registry
from cococap.services import smithing
from cococap.user import User
from tests.test_hub import all_text, buttons, choose, click, hub, select_named, selects

RULES = get_registry().smithing


def _kind_tool(kind: str) -> str:
    return next(i for i in STARTER_TOOLS if get_registry().item(i).tool.kind == kind)


def _pane_selects(nav):
    # The tab dropdown ("Choose a tab") is not part of the smithing pane.
    return [s for s in selects(nav) if not s.placeholder.startswith("Choose a tab")]


async def _give_part(user: User, slot: str, tier: int = 1, traits: list[str] | None = None):
    return await user.give_instance(f"part_{slot}", rolled={"tier": tier}, traits=traits or [])


async def test_smithing_tab_builds_a_tool_from_three_parts(db):
    user_1 = await User.get(1)
    kind = RULES.traits_for("pickaxe")[0].id
    base = await _give_part(user_1, "base", 1, [kind])
    trim = await _give_part(user_1, "trim", 1)
    accent = await _give_part(user_1, "accent", 1)

    nav, inter = await hub("tools", tab="smithing")
    assert nav.screen.tab == "smithing"
    await choose(nav, inter, select_named(nav, "Pick a tool kind"), "pickaxe")
    await choose(nav, inter, select_named(nav, "Base part"), str(base.id))
    await choose(nav, inter, select_named(nav, "Base trait"), kind)
    await click(nav, inter, "Next")
    await choose(nav, inter, select_named(nav, "Trim part"), str(trim.id))
    await click(nav, inter, "Next")
    await choose(nav, inter, select_named(nav, "Accent part"), str(accent.id))
    await click(nav, inter, "Next")
    assert "Preview" in all_text(nav) and "power" in all_text(nav)
    await click(nav, inter, "Smith")

    tools = [i for i in await user_1.instances() if i.smith_id == user_1.id]
    assert len(tools) == 1
    assert tools[0].parts["base"]["trait"] == kind
    assert not [i for i in await user_1.instances() if i.template_id.startswith("part_")]
    assert nav.screen.step == 0


async def test_no_smithing_step_shows_more_than_two_dropdowns(db):
    user_1 = await User.get(1)
    kind = RULES.traits_for("pickaxe")[0].id
    base = await _give_part(user_1, "base", 1, [kind])
    await _give_part(user_1, "trim", 1)
    await _give_part(user_1, "accent", 1)

    nav, inter = await hub("tools", tab="smithing")
    assert len(_pane_selects(nav)) <= 2
    await choose(nav, inter, select_named(nav, "Pick a tool kind"), "pickaxe")
    assert len(_pane_selects(nav)) <= 2
    await choose(nav, inter, select_named(nav, "Base part"), str(base.id))
    assert len(_pane_selects(nav)) == 2
    await click(nav, inter, "Next")
    assert len(_pane_selects(nav)) <= 2
    await click(nav, inter, "Next")
    assert len(_pane_selects(nav)) <= 2
    await click(nav, inter, "Next")
    assert len(_pane_selects(nav)) <= 2


async def test_smithing_back_returns_to_previous_step_and_keeps_picks(db):
    user_1 = await User.get(1)
    kind = RULES.traits_for("pickaxe")[0].id
    base = await _give_part(user_1, "base", 1, [kind])
    trim = await _give_part(user_1, "trim", 1)
    await _give_part(user_1, "accent", 1)

    nav, inter = await hub("tools", tab="smithing")
    await choose(nav, inter, select_named(nav, "Pick a tool kind"), "pickaxe")
    await choose(nav, inter, select_named(nav, "Base part"), str(base.id))
    await choose(nav, inter, select_named(nav, "Base trait"), kind)
    await click(nav, inter, "Next")
    await choose(nav, inter, select_named(nav, "Trim part"), str(trim.id))
    await click(nav, inter, "Back")

    assert nav.screen.step == 1
    assert "Step 1/3" in all_text(nav)
    assert nav.screen.chosen["base"] == base.id and nav.screen.picks[base.id] == kind
    await click(nav, inter, "Back")
    assert nav.screen.step == 0 and nav.screen.kind == "pickaxe"


async def test_smithing_tab_without_parts_says_where_parts_come_from(db):
    user_1 = await User.get(1)
    nav, _ = await hub("tools", tab="smithing")
    assert "skill actions" in all_text(nav)


async def test_parts_tab_lists_parts_by_type(db):
    user_1 = await User.get(1)
    trait = RULES.trait_pool[0].id
    await _give_part(user_1, "base", 2, [trait])
    nav, _ = await hub("tools", tab="parts")
    text = all_text(nav)
    assert "Base" in text and "T2" in text and smithing.trait_icons([trait], RULES, plain=True) in text
    assert "Only tools smithed by someone else" in text


async def test_parts_tab_salvages_a_tool_smithed_by_someone_else(db):
    user_1 = await User.get(1)
    tool = await user_1.give_instance(
        _kind_tool("pickaxe"), smith_id=user_1.id + 1000,
        parts={s: {"tier": 1, "trait": None} for s in smithing.PART_TYPES}, quality=RULES.grades[0].name,
    )
    nav, inter = await hub("tools", tab="parts")
    await choose(nav, inter, select_named(nav, "Pick a tool to salvage"), str(tool.id))
    await click(nav, inter, "Salvage")

    assert await user_1.instance(tool.id) is None
    got = [i.template_id for i in await user_1.instances() if i.template_id.startswith("part_")]
    assert sorted(got) == ["part_accent", "part_base", "part_trim"]


async def test_tools_list_shows_quality_and_trait_of_smithed_tool(db):
    user_1 = await User.get(1)
    trait = RULES.traits_for("pickaxe")[0].id
    await user_1.give_instance(
        _kind_tool("pickaxe"), smith_id=user_1.id,
        parts={"base": {"tier": 1, "trait": trait}, "trim": {"tier": 1, "trait": None},
               "accent": {"tier": 1, "trait": None}},
        quality=RULES.grades[0].name,
    )
    nav, _ = await hub("tools", tab="tools")
    text = all_text(nav)
    assert RULES.grades[0].name in text and RULES.trait(trait).name in text


async def test_empty_parts_tab_says_only_others_tools_can_be_salvaged(db):
    user_1 = await User.get(1)
    nav, _ = await hub("tools", tab="parts")
    assert "Only tools smithed by someone else" in all_text(nav)
    assert "Salvage" not in [b.label for b in buttons(nav)]
