"""The one-time legacy tools reset (services/legacy_tools.py) and the free smithed starters."""

import random

import pytest

from cococap.constants import STARTER_TOOLS
from cococap.registry import get_registry
from cococap.services import legacy_tools, shop
from cococap.services.equipment import TOOL_FOR_SKILL
from cococap.services.smithing import PART_TYPES
from cococap.user import User

REG = get_registry()
RULES = REG.smithing
ROWS = {g.step: g for g in RULES.legacy_grants}
STARTER = {REG.item(s).tool.kind: s for s in STARTER_TOOLS}


@pytest.fixture(autouse=True)
async def _real_db(db):
    """Every test here reads and writes the real SQLite fixture."""
    yield


def _fork_and_past_it(starter: str) -> tuple[str, str]:
    """The first fork tool on this starter's chain and the tool one upgrade past it, found by walking the data."""
    tid = starter
    while (tool := REG.item(tid).tool).fork is None:
        tid = tool.upgrade.to
    fork_tool = tool.fork.to
    return fork_tool, REG.item(fork_tool).tool.upgrade.to


def _scroll_for(enchant: str) -> str:
    return next(i.id for i in REG.items.values() if i.scroll and i.scroll.enchant == enchant)


async def _instances_without_parts(user: User) -> list:
    return [i for i in await user.instances() if REG.item(i.template_id).tool and not i.parts]


async def test_reset_turns_old_upgrades_into_parts_scrolls_and_starters():
    user = await User.get(1)
    pickaxe_old = await user.give_instance(_fork_and_past_it(STARTER["pickaxe"])[1], enchants={"keen": 2})
    axe_plain = await user.give_instance(REG.item(STARTER["axe"]).tool.upgrade.to)

    result = await legacy_tools.reset_player(user, random.Random(1))

    assert result is not None
    assert set(result.kinds) == {"pickaxe", "axe"}
    assert await user.get_stat(legacy_tools.RESET_STAT) == 1
    assert await _instances_without_parts(user) == []
    # Ids can be reused by the new parts, so check by template rather than by id.
    old_templates = {pickaxe_old.template_id, axe_plain.template_id}
    assert not old_templates & {i.template_id for i in await user.instances()}

    # Parts: pickaxe gets the fork_up row, axe gets the plain row; three parts each.
    parts = [i for i in await user.instances() if i.template_id.startswith("part_")]
    tiers = sorted(p.rolled["tier"] for p in parts)
    assert tiers == sorted([ROWS["fork_up"].tier] * 3 + [ROWS["plain"].tier] * 3)
    assert result.parts_given == 6
    for part in parts:
        pool = RULES.traits_for("pickaxe" if part.rolled["tier"] == ROWS["fork_up"].tier else "axe")
        assert len(part.traits) == min(ROWS["fork_up"].traits, len(pool))

    # Enchant comes back as its scroll, one per level.
    assert await user.item_quantity(_scroll_for("keen")) == 2
    assert result.scrolls_given == 2

    # Four starters, each made of tier-1 parts and equipped for its skill.
    for kind, starter in STARTER.items():
        skill = next(s for s, k in TOOL_FOR_SKILL.items() if k == kind)
        equipped = await user.equipped_instance(skill)
        assert equipped is not None and equipped.template_id == starter
        assert all(equipped.parts[slot]["tier"] == 1 for slot in PART_TYPES)
        assert equipped.quality == RULES.grades[0].name


async def test_reset_runs_once_and_changes_nothing_on_second_call():
    user = await User.get(1)
    await user.give_instance(REG.item(STARTER["axe"]).tool.upgrade.to)
    assert await legacy_tools.reset_player(user, random.Random(2)) is not None
    before = sorted(i.id for i in await user.instances())

    assert await legacy_tools.reset_player(user, random.Random(3)) is None
    assert sorted(i.id for i in await user.instances()) == before


async def test_fresh_player_gets_only_starters():
    user = await User.get(2)
    result = await legacy_tools.reset_player(user, random.Random(4))

    assert result.parts_given == 0 and result.scrolls_given == 0 and result.kinds == ()
    tools = [i for i in await user.instances() if REG.item(i.template_id).tool]
    assert sorted(t.template_id for t in tools) == sorted(STARTER.values())
    assert all(t.parts for t in tools)
    assert not [i for i in await user.instances() if i.template_id.startswith("part_")]


async def test_claimed_starters_are_smithed_tier_one_tools():
    user = await User.get(3)
    given = await shop.claim_starter_tools(user)

    assert sorted(given) == sorted(STARTER_TOOLS)
    for item_id in given:
        tool = next(i for i in await user.instances() if i.template_id == item_id)
        assert tool.parts and all(tool.parts[slot]["tier"] == 1 for slot in PART_TYPES)
        assert tool.quality == RULES.grades[0].name
