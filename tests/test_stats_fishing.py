"""The Fishing stat page: existing numbers are shown for old players, new counters add exactly one per record, and they are written in services."""

from pathlib import Path

from cococap.registry import get_registry
from cococap.services import fishing as f
from cococap.services import stats_fishing
from cococap.services.stats import stat_pages
from cococap.user import User
from tests.test_hub import all_text, hub

REG = get_registry()
ROOT = Path(__file__).resolve().parent.parent
NEW_COUNTERS = ("longest_fishing_streak", "crab_pot_hauls", "radar_scans")


def value(page, label):
    return next(v for _, rows in page.groups for name, v in rows if name == label)


async def fishing_page(user):
    return await stats_fishing.page(user, await user.stats())


async def old_player():
    """A player from before the stats existed: fishing data only, no counter rows."""
    user = await User.get(1)
    salmon = REG.item("fish_salmon")
    cod = REG.item("fish_cod")

    def old(skill) -> None:
        skill.xp = 0
        skill.stats.fish_caught = 5
        skill.stats.caught = {salmon.id: 3, cod.id: 2}
        skill.stats.bosses_beaten = 1
        skill.stats.bosses = {REG.fishing.boss.bosses[0].name: 1}
        skill.stats.treasures_found = 2
        skill.stats.quests_completed = 1
        skill.records = {salmon.id: 31.0}
        skill.streak = 4

    await user.update_skill("fishing", old)
    return user, salmon, cod


async def test_an_existing_player_sees_their_old_numbers_before_any_new_record(db):
    user, salmon, cod = await old_player()
    page = await fishing_page(user)
    assert value(page, "Fish caught") == 5 and value(page, "Species caught") == 2
    assert value(page, "Biggest fish") == f"31 cm · {salmon.name}"
    assert value(page, f"Rarity {salmon.rarity}") >= 3
    assert value(page, "Bosses beaten") == 1 and value(page, REG.fishing.boss.bosses[0].name) == 1
    assert value(page, "Treasures found") == 2 and value(page, "Quests completed") == 1
    assert value(page, "Longest clean-reel streak") == 4  # seeded from the run they were on
    assert value(page, "Crab pot hauls") == 0 and value(page, "Radar scans") == 0


async def test_one_catch_after_the_backfill_adds_exactly_one(db):
    user, salmon, _ = await old_player()
    before = await fishing_page(user)
    cast = f.Cast(salmon, 10.0, 20.0, [f.LEFT], 0, hooked=True)
    cast.size = 40.0
    cast.press(f.LEFT, 11.0)
    await f.land(user, cast, REG)
    page = await fishing_page(user)
    assert value(page, "Fish caught") == 6 and value(page, "Species caught") == 2
    assert value(page, "Biggest fish") == f"40 cm · {salmon.name}"
    assert value(page, f"Rarity {salmon.rarity}") == value(before, f"Rarity {salmon.rarity}") + 1  # derived, counted once
    assert (await user.skill("fishing")).stats.caught[salmon.id] == 4
    assert value(page, "Longest clean-reel streak") == 5  # the run went 4 -> 5, not 4 + 4
    assert (await user.stats())["longest_fishing_streak"] == 5


def test_every_new_counter_is_written_in_services():
    source = "\n".join((ROOT / "cococap" / "services" / name).read_text(encoding="utf-8")
                       for name in ("fishing.py", "pots.py"))
    for name in NEW_COUNTERS:
        assert f'"{name}"' in source, name


async def test_the_fishing_page_is_one_of_the_stat_pages_and_the_tab_renders(db):
    user, _, _ = await old_player()
    pages = await stat_pages(user)
    assert any(p.key == "fishing" for p in pages)
    nav, _ = await hub("player", tab="stats")
    assert "Economy" in all_text(nav)
