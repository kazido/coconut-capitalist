from pathlib import Path
from random import Random

from cococap.registry import get_registry
from cococap.services import foraging as f
from cococap.services import stats_foraging
from cococap.services.equipment import equip
from cococap.user import User
from tests.test_hub import all_text, choose, hub, select_named

REG = get_registry()
RULES = REG.foraging
NOW = 1_800_000_000 // 3600 * 3600 + 60  # a minute into an hour: the community tree is standing


async def player(user_id=1):
    user = await User.get(user_id)
    inst = await user.give_instance("tool_axe_starter")
    await equip(user, "foraging", inst.id)
    return user


async def rows_for(user):
    page = await stats_foraging.page(user, await user.stats())
    return page, {label: value for _, lines in page.groups for label, value in lines}


async def test_an_existing_forager_sees_their_old_numbers_without_any_counter_rows(db):
    user = await User.get(1)

    def old(m):
        m.stats.trees_chopped, m.stats.releaf_donations = 5, 2

    await user.update_skill("foraging", old)
    _, values = await rows_for(user)
    assert values["Trees felled"] == 5 and values["Releaf donations"] == 2
    assert values["Chops"] == 0 and values["Rarest drop found"] == "none yet"


async def test_one_felled_tree_adds_exactly_one_to_the_tree_and_its_species(db):
    user = await player(1)
    _, before = await rows_for(user)
    species = RULES.species_in(1)[0]
    tree = f.Tree(1, 10, 10, species=species.id)
    tree.hp = 0  # felled
    reward = await f.fell_private(user, tree, Random(1))
    _, after = await rows_for(user)
    assert after["Trees felled"] == before["Trees felled"] + 1
    assert after[species.name] == before[species.name] + 1
    rates = [REG.item(i).drop.rate for i in reward.drops if REG.item(i).drop]
    assert after["Rarest drop found"] == (f"1 in {max(rates):,}" if rates else "none yet")


async def test_one_chop_adds_exactly_one_and_the_streak_keeps_its_best(db):
    user = await player(1)
    _, values = await rows_for(user)
    await f.record_chop(user, 3)
    _, values = await rows_for(user)
    assert values["Chops"] == 1 and values["Best chop streak"] == 3
    await f.record_chop(user, 1)
    _, values = await rows_for(user)
    assert values["Chops"] == 2 and values["Best chop streak"] == 3


async def test_one_wedge_spent_adds_exactly_one(db):
    user = await player(1)
    wedge = RULES.rotate.wedges[0]
    await user.add_item(wedge.item, 1)
    await f.spend_wedge(user, f.Spot.pick(RULES, Random(1)), wedge.item, Random(2))
    _, values = await rows_for(user)
    assert values["Wedges used"] == 1


async def test_one_community_chop_adds_exactly_one_hit(db):
    user = await player(1)
    _, before = await rows_for(user)
    await f.chop_community(user, 5, NOW)
    _, after = await rows_for(user)
    assert after["Community tree hits"] == before["Community tree hits"] + 1


def test_every_new_counter_is_written_in_the_services():
    services = "".join(p.read_text(encoding="utf-8") for p in (Path(__file__).resolve().parents[1] / "cococap" / "services").glob("*.py"))
    for name in ("rarest_drop", "best_chop_streak", "wedges_used", "community_hits", "party_hits", "felled:", '"chops"'):
        assert name in services, name


async def test_the_foraging_page_renders_in_the_stats_tab(db):
    user = await User.get(1)
    await user.inc_stat("wedges_used", 2)
    nav, inter = await hub("player", tab="stats")
    await choose(nav, inter, select_named(nav, "Pick a page"), "foraging")
    assert "Wedges used: `2`" in all_text(nav)
