from cococap.ui import levelup
from cococap.user import User


def test_message_names_the_skill_the_level_and_the_next_goal():
    xp = User.level_to_xp(12)
    text = levelup.message("mining", 11, 12, xp)
    assert "Mining" in text and "11 -> 12" in text and "to level 13" in text


def test_every_skill_with_an_icon_is_watched():
    assert set(levelup.SKILLS) == {"mining", "fishing", "foraging", "farming", "combat"}


async def test_a_click_that_levels_you_up_sends_the_notification(db, monkeypatch):
    from cococap.services import foraging
    from tests.test_hub import all_text, chop, click, find_button, freeze_time, hub, with_axe

    freeze_time(monkeypatch)
    user = await with_axe()
    nav, inter = await hub("forage")

    def near_level_up(skill):
        skill.xp = User.level_to_xp(User.xp_to_level(skill.xp) + 1) - 1

    await user.update_skill("foraging", near_level_up)
    await click(nav, inter, "Chop a tree")
    nav.screen.tree = foraging.Tree(1, 1, 1)
    await chop(nav, inter)
    assert "level up!" in all_text(nav) and find_button(nav, "Share") is not None  # on the loot screen itself, no popup
    assert inter.followup.send.await_count == 0


async def test_jumping_several_levels_in_one_click_is_one_notice_old_to_new(db):
    from unittest.mock import AsyncMock, MagicMock

    user = await User.get(1)
    seen = await levelup.snapshot(user)
    await user.update_skill("mining", lambda s: setattr(s, "xp", User.level_to_xp(seen["mining"] + 5)))
    inter = MagicMock(followup=MagicMock(send=AsyncMock()))
    await levelup.check(inter, user, seen)
    assert inter.followup.send.await_count == 1
    new = (await levelup.snapshot(user))["mining"]
    assert new > seen["mining"] + 1  # a real multi-level jump
    assert f"{seen['mining']} -> {new}" in inter.followup.send.await_args.kwargs["embed"].description
    assert inter.followup.send.await_args.kwargs["view"] is not None  # Share + Close


async def test_the_active_pet_levelling_up_rides_in_the_same_notice(db):
    from unittest.mock import AsyncMock, MagicMock

    from cococap.registry import get_registry
    from cococap.services import pets

    reg = get_registry()
    user = await User.get(1)

    def adopt(house):
        from cococap.models.pethouse import OwnedPet

        house.pets["drizzle"] = OwnedPet(stars=1, xp=0)
        house.active = "drizzle"

    await user.update_pethouse(adopt)
    seen = await levelup.snapshot(user)
    assert seen["pet:drizzle"] == 1
    await user.update_pethouse(lambda h: setattr(h.pets["drizzle"], "xp", pets.level_xp(3, reg.pets["drizzle"].rarity, reg)))
    inter = MagicMock(followup=MagicMock(send=AsyncMock()))
    await levelup.check(inter, user, seen)
    assert inter.followup.send.await_count == 1
    assert "Drizzle" in inter.followup.send.await_args.kwargs["embed"].description and "1 -> 3" in inter.followup.send.await_args.kwargs["embed"].description
