"""The /play hub: every screen renders to a valid Components V2 layout, navigation never dead-ends,
and each screen's buttons call the right service and redraw."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import ui

from cococap.errors import CustomError
from cococap.registry import get_registry
from cococap.screens import SCREENS, open_screen
from cococap.services.economy import OnCooldown
from cococap.ui import Navigator, PromptModal
from cococap.user import User
from tests.conftest import set_columns


def fake_interaction(user_id=1, name="tester"):
    inter = MagicMock()
    inter.user = SimpleNamespace(id=user_id, name=name, display_name=name, display_avatar=SimpleNamespace(url="http://x/a.png"))
    inter.extras = {}
    inter.data = {"options": []}
    inter.response = MagicMock(
        send_message=AsyncMock(), edit_message=AsyncMock(), send_modal=AsyncMock(),
        defer=AsyncMock(), is_done=MagicMock(return_value=False),
    )
    inter.original_response = AsyncMock(return_value=SimpleNamespace(edit=AsyncMock()))
    inter.edit_original_response = AsyncMock()
    inter.followup = MagicMock(send=AsyncMock())
    inter.client = SimpleNamespace(
        get_user=lambda uid: SimpleNamespace(display_name=f"user{uid}", id=uid, bot=False, mention=f"<@{uid}>"),
        fetch_user=AsyncMock(),
    )
    return inter


async def hub(screen="home", user_id=1, **state):
    inter = fake_interaction(user_id)
    nav = await open_screen(inter, screen, **state)
    return nav, inter


def buttons(nav):
    return [c for c in nav.walk_children() if isinstance(c, ui.Button)]


def check_in_open_button(nav):
    """The Open button of the Check-in section on Home."""
    sections = [c for c in nav.walk_children() if isinstance(c, ui.Section) and "Check-in" in " ".join(getattr(t, "content", "") for t in c.children)]
    return sections[0].accessory


def find_button(nav, label=None, emoji=None):
    for b in buttons(nav):
        if (label is None or b.label == label) and (emoji is None or (b.emoji and str(b.emoji) == emoji)):
            return b
    raise AssertionError(f"no button label={label!r} emoji={emoji!r}; have {[(b.label, str(b.emoji)) for b in buttons(nav)]}")


async def continue_through(nav, inter, label="Continue"):
    """Click Continue on the reward screen and on every rare-drop page after it, until the screen it came from is back."""
    while nav.screen.id == "result":
        await click(nav, inter, label)


def selects(nav):
    return [c for c in nav.walk_children() if isinstance(c, ui.Select)]


def select_named(nav, placeholder):
    return next(s for s in selects(nav) if s.placeholder.startswith(placeholder))


def all_text(nav):
    return "\n".join(c.content for c in nav.walk_children() if isinstance(c, ui.TextDisplay))


async def click(nav, inter, label=None, emoji=None):
    button = find_button(nav, label, emoji)
    inter.response.edit_message.reset_mock()
    await button.callback(inter)


async def chop(nav, inter, zone=1):
    """Chop in the style the spot's grain likes (the player knows their grains)."""
    from cococap.services import foraging as forage

    letter = nav.screen.spot.stance(get_registry().foraging)
    await click(nav, inter, forage.STANCES[letter][0])


async def choose(nav, inter, select, value):
    select._values = [value]
    inter.response.edit_message.reset_mock()
    await select.callback(inter)


# ---- every screen is valid --------------------------------------------------------------------
@pytest.mark.parametrize("screen_id", list(SCREENS))
async def test_every_screen_renders_valid_layout_within_discord_limits(db, screen_id):
    nav, inter = await hub(screen_id)
    nav.to_components()  # raises if the structure is invalid
    assert nav.total_children_count <= 40, nav.total_children_count
    assert nav.content_length() <= 4000
    assert inter.response.send_message.await_args.kwargs["view"] is nav





# ---- navigation -------------------------------------------------------------------------------
async def test_home_buttons_open_screens_and_back_returns(db):
    nav, inter = await hub("home")
    assert find_button(nav, "Home").disabled and find_button(nav, "Back").disabled
    sections = [c for c in nav.walk_children() if isinstance(c, ui.Section) and isinstance(c.accessory, ui.Button)]
    assert len(sections) == 6  # skills, shipments, shop, inventory, pets, check-in
    await sections[0].accessory.callback(inter)
    assert nav.screen.id != "home" and not find_button(nav, "Back").disabled
    await click(nav, inter, "Back")
    assert nav.screen.id == "home"





async def test_shortcut_commands_start_with_home_behind_them(db):
    nav, _ = await hub("shop")
    assert nav.stack == ["home", "shop"]
    assert not find_button(nav, "Back").disabled


async def test_strangers_cannot_use_someone_elses_hub(db):
    nav, _ = await hub("home", user_id=1)
    stranger = fake_interaction(2)
    assert await nav.interaction_check(stranger) is False
    assert "isn't your menu" in stranger.response.send_message.await_args.args[0]
    assert await nav.interaction_check(fake_interaction(1)) is True


async def test_timeout_deletes_the_message(db):
    nav, _ = await hub("home")
    nav.message = SimpleNamespace(edit=AsyncMock(), delete=AsyncMock())
    await nav.on_timeout()
    nav.message.delete.assert_awaited()
    nav.message.edit.assert_not_awaited()


async def test_timeout_disables_the_controls_when_delete_fails(db):
    nav, _ = await hub("home")
    nav.message = SimpleNamespace(edit=AsyncMock(), delete=AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403), "no")))
    await nav.on_timeout()
    assert all(b.disabled for b in buttons(nav)) and all(s.disabled for s in selects(nav))
    nav.message.edit.assert_awaited()


async def test_rule_errors_are_shown_but_bugs_are_not_leaked(db):
    nav, _ = await hub("home")
    inter = fake_interaction()
    await nav.on_error(inter, OnCooldown(60), None)
    assert inter.response.send_message.await_args.args[0] == "That isn't ready yet."
    inter = fake_interaction()
    await nav.on_error(inter, RuntimeError("sqlite:///secret/path"), None)
    assert "secret" not in inter.response.send_message.await_args.args[0]
    followup = fake_interaction()
    followup.response.is_done.return_value = True
    await nav.on_error(followup, CustomError("nope"), None)
    followup.followup.send.assert_awaited_with("nope", ephemeral=True)


# ---- check-in -----------------------------------------------------------------------------------
async def test_checkin_claims_pay_once_and_buttons_lock(db):
    nav, inter = await hub("checkin")
    await click(nav, inter, "Claim")  # the first Claim button is Work
    user = await User.get(1)
    assert user.purse == 1000 + 2500
    assert "Work: +2,500" in all_text(nav)
    # work is now on cooldown: the remaining buttons are Daily / Weekly claims plus a disabled timer
    assert any(b.disabled and "h" in (b.label or "") for b in buttons(nav))
    assert len([b for b in buttons(nav) if b.label == "Claim"]) == 2


async def test_checkin_rejects_a_stale_double_claim(db):
    nav, inter = await hub("checkin")
    stale_claim = find_button(nav, "Claim")
    await stale_claim.callback(inter)
    with pytest.raises(OnCooldown):
        await stale_claim.callback(inter)  # a button from before the claim, clicked again
    assert (await User.get(1)).purse == 3500


# ---- rank / settings / profile / stats ---------------------------------------------------------
async def test_rank_up_button_needs_tokens_then_works(db):
    nav, inter = await hub("rank")
    assert not find_button(nav, "Rank up").disabled  # rank 1 costs 0 tokens
    await click(nav, inter, "Rank up")
    assert (await User.get(1)).rank == 1 and "Peasant" in all_text(nav)
    assert find_button(nav, "Rank up").disabled  # rank 2 costs 10 tokens
    await set_columns(await User.get(1), tokens=10)
    await nav.screen.refresh(inter)
    await click(nav, inter, "Rank up")
    assert (await User.get(1)).rank == 2


async def test_rank_screen_at_max_rank(db):
    await set_columns(await User.get(1), rank=max(get_registry().ranks))
    nav, _ = await hub("rank")
    assert "max rank" in all_text(nav) and not any(b.label == "Rank up" for b in buttons(nav))


async def test_settings_page_lists_each_setting_with_a_toggle_that_saves(db):
    nav, inter = await hub("settings")
    assert "Confirm Sell all" in all_text(nav)
    on = next(b for b in buttons(nav) if b.label == "ON")
    await on.callback(inter)
    assert (await User.get(1)).settings.confirm_sell_all is False and next(b for b in buttons(nav) if b.label == "OFF")


async def test_profile_and_home_show_balances_and_levels(db):
    nav, _ = await hub("profile")
    text = all_text(nav)
    assert "1,000" in text and "Mining" in text and "Lv 1" in text
    home, _ = await hub("home")
    assert "Unranked" in all_text(home) and "✅ Check-in ready" in all_text(home)


async def test_stats_pages_switch_with_the_select(db):
    user = await User.get(1)
    await user.inc_stat("hl_wins", 3)
    nav, inter = await hub("stats")
    await choose(nav, inter, select_named(nav, "Pick a page"), "gambling")
    assert "Wins: `3`" in all_text(nav)


async def test_top_select_changes_category_and_shortcut_preselects_it(db):
    from cococap.exts.economy.top import TopCategories

    await set_columns(await User.get(1), luckbucks=77)
    nav, inter = await hub("top")
    assert "tester" in all_text(nav)
    await choose(nav, inter, select_named(nav, "Pick a leaderboard"), "luckbucks")
    assert "77" in all_text(nav) and "Luckbucks" in all_text(nav)
    nav2, _ = await hub("top", category=TopCategories.LUCKBUCKS)
    assert nav2.screen.category is TopCategories.LUCKBUCKS


# ---- shop / inventory ---------------------------------------------------------------------------
async def submit(inter, text):
    """Pretend the player typed `text` into the modal the last click opened."""
    modal = inter.response.send_modal.await_args.args[0]
    assert isinstance(modal, PromptModal)
    modal.field._value = text
    return modal


async def test_shop_buy_opens_a_modal_and_buying_works(db):
    await set_columns(await User.get(1), purse=10_000_000)
    nav, inter = await hub("shop")
    await click(nav, inter, emoji="🌽")  # seeds stack, so they ask how many (tools do not: see the next test)
    buy = [b for b in buttons(nav) if b.label == "Buy" and b.style == discord.ButtonStyle.success][1]  # (the can comes first: tools lead)
    await buy.callback(inter)
    modal = await submit(inter, "2")
    await modal.on_submit(inter)
    user = await User.get(1)
    items, instances = await user.items(), await user.instances()
    assert len(instances) + sum(items.values()) == 2 and user.purse < 10_000_000
    assert "Bought 2" in all_text(nav)


async def test_the_shop_lists_no_tools_and_the_tools_page_claims_the_free_starters(db):
    from cococap.constants import STARTER_TOOLS

    reg = get_registry()
    await set_columns(await User.get(1), purse=10_000_000)
    nav, inter = await hub("shop")
    assert not any(reg.item(t).name in all_text(nav) for t in STARTER_TOOLS)
    nav, inter = await hub("tools")
    await click(nav, inter, "Claim free starter tools")
    user = await User.get(1)
    assert sorted(i.template_id for i in await user.instances()) == sorted(STARTER_TOOLS) and "You got" in all_text(nav)
    assert "Claim free starter tools" not in {b.label for b in buttons(nav)}  # nothing left to claim


async def test_shop_modal_rejects_nonsense_and_cant_overspend(db):
    def item_buy_buttons(nav):  # the per-item buttons (green), not the Buy/Sell mode toggle
        return [b for b in buttons(nav) if b.label == "Buy" and b.style == discord.ButtonStyle.success]

    nav, inter = await hub("shop")
    # a brand-new player can only afford the very cheapest things (a starter seed for 500), not the rest
    cheap = [b for b in item_buy_buttons(nav) if not b.disabled]
    assert item_buy_buttons(nav) and len(cheap) < len(item_buy_buttons(nav))
    await set_columns(await User.get(1), purse=200_000)
    nav, inter = await hub("shop")
    await click(nav, inter, emoji="🌽")
    buy = [b for b in item_buy_buttons(nav) if not b.disabled][0]
    await buy.callback(inter)
    modal = await submit(inter, "lots")
    with pytest.raises(CustomError):
        await modal.on_submit(inter)
    modal.field._value = "9999"
    with pytest.raises(Exception, match="between 1|need"):
        await modal.on_submit(inter)
    assert (await User.get(1)).purse == 200_000


async def test_shop_sell_mode_sells_the_full_stack_by_default(db):
    user = await User.get(1)
    await user.add_item("gold_ore", 4)
    nav, inter = await hub("shop")
    await click(nav, inter, "Sell")
    await next(b for b in buttons(nav) if b.label == "Sell" and b.style == discord.ButtonStyle.success).callback(inter)
    modal = inter.response.send_modal.await_args.args[0]
    assert modal.field.default == "4"
    modal.field._value = "4"
    await modal.on_submit(inter)
    assert (await User.get(1)).purse == 1000 + 4 * get_registry().item("gold_ore").sell_price and await user.items() == {}


async def test_inventory_lists_items_only_and_has_sell_and_tools_buttons(db):
    from cococap.services.equipment import equip

    user = await User.get(1)
    await user.add_item("copper_ore", 7)
    for template, skill in (("starter_axe", "foraging"), ("tin_can", "farming")):
        await equip(user, skill, (await user.give_instance(template)).id)
    nav, inter = await hub("inventory")
    text = all_text(nav)
    assert "7 Copper Ore" in text and "Starter Axe" not in text and "Watering Can" not in text  # tools are on the Tools page
    labels = {b.label for b in buttons(nav)}
    assert {"Sell", "Tools"} <= labels and "Enchant" not in labels and "Upgrade tools" not in labels
    await click(nav, inter, "Tools")
    assert nav.screen.id == "tools"


async def test_the_sell_button_opens_the_shop_in_sell_mode(db):
    user = await User.get(1)
    await user.add_item("copper_ore", 7)
    nav, inter = await hub("inventory")
    await click(nav, inter, "Sell")
    assert nav.screen.id == "shop" and nav.screen.mode == "sell" and "Copper Ore" in all_text(nav)
    assert any(b.label == "Sell" and b.style == discord.ButtonStyle.success for b in buttons(nav))  # (each stack has its own Sell button)


async def test_the_sell_button_is_off_when_you_have_nothing(db):
    nav, _ = await hub("inventory")
    assert "don't have any items" in all_text(nav) and find_button(nav, "Sell").disabled


async def test_the_tools_page_marks_the_equipped_tool_of_every_kind_including_the_can(db):
    from cococap.services.equipment import equip

    user = await User.get(1)
    for template, skill in (("starter_axe", "foraging"), ("tin_can", "farming"), ("rookiepickaxe", "mining")):
        await equip(user, skill, (await user.give_instance(template)).id)
    await user.give_instance("starter_rod")  # owned but not equipped
    nav, _ = await hub("tools")
    lines = all_text(nav).split("\n")
    marked = {name: any(name in line and "✅" in line for line in lines) for name in ("Starter Axe", "Tin Watering Can", "Rookie Pickaxe", "Starter Rod")}
    assert marked == {"Starter Axe": True, "Tin Watering Can": True, "Rookie Pickaxe": True, "Starter Rod": False}


async def test_the_tools_page_shows_every_tool_equips_one_and_leads_to_upgrades(db):
    from cococap.services.equipment import equip

    user = await User.get(1)
    axe = await user.give_instance("starter_axe")
    can = await user.give_instance("tin_can")
    await equip(user, "foraging", axe.id)
    nav, inter = await hub("tools")
    text = all_text(nav)
    assert "Starter Axe" in text and "Tin Watering Can" in text and "Farming" in text and "Foraging" in text
    assert text.count("✅") == 1  # only the axe is equipped
    assert [b.label for b in buttons(nav) if b.label in ("Equip", "Equipped")].count("Equipped") == 1
    await click(nav, inter, "Equip")
    assert (await user.skill("farming")).equipped_instance_id == can.id and "Equipped **Tin Watering Can**" in all_text(nav)
    assert all_text(nav).count("✅") == 2 and [b.label for b in buttons(nav) if b.label in ("Equip", "Equipped")] == ["Equipped", "Equipped"]
    await click(nav, inter, "Upgrade")
    assert nav.screen.id == "upgrade"
    await click(nav, inter, "Back to tools")
    assert nav.screen.id == "tools"


async def test_the_tools_page_has_room_for_an_account_with_many_tools_and_the_empty_case(db):
    nav, _ = await hub("tools")
    assert "no tools yet" in all_text(nav)
    user = await User.get(1)
    for _ in range(30):
        await user.give_instance("starter_rod")
    nav, _ = await hub("tools")
    assert len([b for b in buttons(nav) if b.label in ("Equip", "Equipped")]) == 8 and "22 more tools" in all_text(nav)


async def test_inventory_paging(db):
    user = await User.get(1)
    stackables = [i for i in get_registry().items if not get_registry().item(i).is_instance]
    for item in stackables:
        await user.add_item(item, 1)
    pages = -(-len(stackables) // 12)
    assert pages >= 2
    nav, inter = await hub("inventory")
    assert find_button(nav, f"1/{pages}").disabled
    await click(nav, inter, emoji="▶️")
    assert find_button(nav, f"2/{pages}")
    await click(nav, inter, emoji="◀️")
    assert find_button(nav, f"1/{pages}")


async def test_empty_inventory_message(db):
    nav, _ = await hub("inventory")
    assert "don't have any items" in all_text(nav)


# ---- casino / mining ------------------------------------------------------------------------------






async def test_mining_screen_reactor_buttons(db):
    user = await User.get(1)
    await user.add_xp("mining", User.level_to_xp(10) + 1)
    await user.add_item("sanity_gemstone", 1)
    nav, inter = await hub("reactor")
    await click(nav, inter, "Insert gems")
    assert (await user.skill("mining")).reactor.core_1.gem_id == "sanity_gemstone"
    assert "Inserted: Sanity" in all_text(nav)
    await choose(nav, inter, select_named(nav, "Feed the magnet"), "copper_ore")  # picking an ore says exactly what feeding it does
    assert "A full meter needs" in all_text(nav) and find_button(nav, "Feed 1").disabled  # (no copper to feed)
    await user.add_item("copper_ore", 30)
    nav, inter = await hub("reactor")
    await choose(nav, inter, select_named(nav, "Feed the magnet"), "copper_ore")
    await click(nav, inter, "Feed 10")
    assert "Fed the magnet **10 Copper Ore**" in all_text(nav) and (await user.skill("mining")).magnet_meter == 10 and await user.item_quantity("copper_ore") == 20
    await click(nav, inter, "Magnet: on")
    assert (await user.skill("mining")).magnet_on is False and find_button(nav, "Magnet: off")
    assert find_button(nav, "Claim lodes").disabled





# ---- navigation without a menu; skills / minigames; shop sections --------------------------------
async def test_no_go_anywhere_menu_remains(db):
    nav, _ = await hub("home")
    assert selects(nav) == []


def reachable_from_home():
    seen, todo = {"home"}, ["home"]
    while todo:
        for target in SCREENS[todo.pop()].links:
            if target not in seen:
                seen.add(target)
                todo.append(target)
    return seen


def test_every_screen_is_reachable_by_following_links_from_home():
    assert reachable_from_home() == set(SCREENS) - {"fight"}  # (combat is paused: nothing links to it until it is reworked)


async def test_home_links_really_open_the_declared_screens(db):
    for parent in ("home", "more", "skills", "minigames"):
        nav, inter = await hub(parent)
        openers = [c.accessory for c in nav.walk_children() if isinstance(c, ui.Section) and isinstance(c.accessory, ui.Button)
                   and not c.accessory.disabled and c.accessory.label == "Open"]
        quick = [b for b in buttons(nav) if b.emoji and b.label in ("Check-in", "Inventory", "Shop", "Trade", "Party", "Pets", "More", "Profile", "Ranks", "Leaderboards")]
        opened = set()
        for opener in openers + quick:
            nav.stack, nav.screen = ["home"], None
            nav2, inter2 = await hub(parent)
            target = next(c for c in nav2.walk_children() if getattr(c, "label", None) == opener.label and getattr(c, "style", None) == opener.style)
            await target.callback(inter2)
            opened.add(nav2.screen.id)
        assert opened <= set(SCREENS[parent].links) and opened, (parent, opened)


async def test_skills_page_lists_all_five_and_combat_is_paused(db):
    nav, _ = await hub("skills")
    text = all_text(nav)
    assert all(name in text for name in ("Mining", "Farming", "Foraging", "Fishing", "Combat"))
    assert [b.label for b in buttons(nav) if b.label in ("Soon", "Paused")] == ["Paused"]  # (combat is paused for its rework)


async def test_shop_has_a_section_per_skill_and_filters(db):
    reg = get_registry()
    await set_columns(await User.get(1), purse=50_000_000)
    nav, inter = await hub("shop")
    assert find_button(nav, "All")
    for emoji, skill in (("🌽", "farming"), ("🌳", "foraging"), ("⛏️", "mining")):
        await click(nav, inter, emoji=emoji)
        shown = all_text(nav)
        expected = sorted((i for i in reg.shop_items() if i.skill == skill), key=lambda i: (i.price, i.name))
        assert expected and all(i.name in shown for i in expected[:4]), skill
        others = [i for i in reg.shop_items() if i.skill != skill]
        assert not any(f"### {i.name}" in shown for i in others), skill
    await click(nav, inter, "All")
    assert "Tin Watering Can" not in all_text(nav)


# ---- the in-window casino --------------------------------------------------------------------------
async def start_from_casino(game_button_index, bet="100", user_id=1):
    nav, inter = await hub("casino", user_id=user_id)
    plays = [b for b in buttons(nav) if b.label == "Play"]
    await plays[game_button_index].callback(inter)
    modal = await submit(inter, bet)
    modal_inter = fake_interaction(user_id)
    await modal.on_submit(modal_inter)
    return nav, modal_inter


async def test_highlow_plays_inside_the_hub_window(db):
    nav, inter = await start_from_casino(0)
    assert nav.screen.id == "highlow" and nav.screen.locked
    assert (await User.get(1)).luckbucks == 0
    assert find_button(nav, "Home").disabled and find_button(nav, "Back").disabled  # can't walk out mid-game
    nav.screen.game.roll = 9
    await find_button(nav, "High").callback(inter)
    assert "Correct" in all_text(nav) and "2×" in all_text(nav)
    await click(nav, inter, "Cash out 200")
    assert (await User.get(1)).luckbucks == 0 + 200
    assert not nav.screen.locked and not find_button(nav, "Home").disabled
    assert "Cashed out" in all_text(nav)
    await click(nav, inter, "Play again")
    assert nav.screen.game.bet == 100 and (await User.get(1)).luckbucks == 200 - 100


async def test_highlow_loss_screen_and_return_to_casino(db):
    nav, inter = await start_from_casino(0)
    nav.screen.game.roll = 2
    await find_button(nav, "High").callback(inter)
    assert "You lost" in all_text(nav)
    await click(nav, inter, "Casino")
    assert nav.screen.id == "casino"


async def test_blackjack_plays_inside_the_hub_window(db):
    for seed_user in range(20, 60):
        nav, inter = await start_from_casino(1, user_id=seed_user)
        if not nav.screen.game.finished:
            break
    else:
        pytest.skip("always dealt a natural")
    game = nav.screen.game
    assert nav.screen.locked and "Dealer" in all_text(nav) and any(b.label == "Fold" for b in buttons(nav))
    await find_button(nav, "Stand").callback(inter)
    assert game.finished and not nav.screen.locked and game.outcome in ("win", "lose", "push")
    assert any(w in all_text(nav) for w in ("win", "house wins", "Push"))


async def test_leaving_by_timeout_mid_game_settles_the_bet(db):
    nav, inter = await start_from_casino(0)
    assert (await User.get(1)).luckbucks == 0  # the whole 100-luckbuck stake is on the table
    nav.message = SimpleNamespace(edit=AsyncMock())
    await nav.on_timeout()
    assert (await User.get(1)).luckbucks == 100  # high-low abandon returns the pot


async def test_casino_rejects_a_bad_bet_without_opening_a_game(db):
    nav, inter = await hub("casino")
    await [b for b in buttons(nav) if b.label == "Play"][0].callback(inter)
    modal = await submit(inter, "999999")
    with pytest.raises(Exception, match="Not enough"):
        await modal.on_submit(fake_interaction())
    assert nav.screen.id == "casino" and (await User.get(1)).luckbucks == 100



# ---- the mines (in-window) ----------------------------------------------------------------------------
from collections import Counter  # noqa: E402
from random import Random  # noqa: E402

from cococap.services import mining as mine_service  # noqa: E402


class Rig(Random):
    def __init__(self, value):
        super().__init__(1)
        self.value = value

    def random(self):
        return self.value


async def enter_mines(user_id=1):
    nav, inter = await hub("mining", user_id=user_id)
    await find_button(nav, "Enter the mines").callback(inter)
    assert nav.screen.id == "mine"
    return nav, inter


async def test_entering_the_mines_shows_the_meter_and_locks_navigation(db):
    nav, inter = await enter_mines()
    text = all_text(nav)
    assert "Row 1 of 30" in text and "**0%** collapse risk" in text
    assert find_button(nav, "Brace (1)") and find_button(nav, "Leave & bank")
    assert nav.screen.locked
    assert not {"Home", "Back"} & {b.label for b in buttons(nav)}  # a live run hides Home/Back: Leave & bank is the way out


async def test_digging_advances_depth_and_raises_danger(db):
    nav, inter = await enter_mines()
    run = nav.screen.run
    run.rng = Rig(0.99)
    await find_button(nav, "Dig").callback(inter)
    assert run.depth == 1 and run.danger > 0 and "Row 2 of 30" in all_text(nav)
    await find_button(nav, emoji="➡️").callback(inter)
    assert run.cursors == [3]


async def test_brace_button_lowers_danger_and_then_disables(db):
    nav, inter = await enter_mines()
    run = nav.screen.run
    run.danger = 40
    await click(nav, inter, "Brace (1)")
    assert run.danger == 25 and run.braces == 0
    assert find_button(nav, "Brace (0)").disabled


async def test_leave_banks_the_haul_and_unlocks_navigation(db):
    user = await User.get(1)
    nav, inter = await enter_mines()
    run = nav.screen.run
    run.rng = Rig(0.99)
    for _ in range(3):
        await find_button(nav, "Dig").callback(inter)
    carried = dict(run.haul)
    await click(nav, inter, "Leave & bank")
    assert nav.screen.id == "result" and "climbed out safely" in all_text(nav) and nav.screen.locked  # the haul is shown first, then you carry on
    await continue_through(nav, inter)
    assert "climbed out safely" in all_text(nav) and not nav.screen.locked
    assert await user.items() == carried
    assert (await user.skill("mining")).xp == 30 and not find_button(nav, "Home").disabled
    await click(nav, inter, "Mine again")
    assert nav.screen.run.depth == 0 and not nav.screen.run.finished


async def test_a_collapse_halves_the_haul_and_still_gives_xp(db):
    user = await User.get(1)
    nav, inter = await enter_mines()
    run = nav.screen.run
    run.rng = Rig(0.99)
    await find_button(nav, "Dig").callback(inter)
    run.haul = Counter(copper_ore=10)
    run.danger = 90
    run.rng = Rig(0.0)
    await find_button(nav, "Dig").callback(inter)
    assert "collapsed" in all_text(nav) and await user.item_quantity("copper_ore") == 5
    await continue_through(nav, inter)
    assert (await user.skill("mining")).xp == 10 and not nav.screen.locked


async def test_a_wyrmhole_leads_to_a_one_pick_screen_and_banks_it(db):
    user = await User.get(1)
    nav, inter = await enter_mines()
    run = nav.screen.run
    run.wyrmholes_ahead()
    run._holes[0] = {2}
    await find_button(nav, "Dig").callback(inter)
    assert run.outcome == "wyrmhole" and "wyrmhole" in all_text(nav)
    await continue_through(nav, inter)
    await find_button(nav, "Enter the wyrmhole").callback(inter)
    assert nav.screen.id == "wyrmhole" and nav.screen.locked
    await find_button(nav, "Dig").callback(inter)
    assert nav.screen.id == "result" and sum((await user.items()).values()) > 0  # the pick is a reward screen like any other
    await continue_through(nav, inter, "Back to the mines")
    assert nav.screen.id == "mining"


async def test_scarab_answered_in_time_pays_out_and_late_or_wrong_does_not(db):
    import time

    from cococap.services.mining import ScarabChallenge

    for answer, delay, rewarded in (("lantern", 0, True), ("lantern", 999, False), ("nope", 0, False)):
        user = await User.get(1)
        before = (sum((await user.items()).values()), (await user.skill("mining")).xp)
        nav, inter = await enter_mines()
        nav.screen.run.leave()
        await nav.screen._end(None)
        nav.screen.challenge = ScarabChallenge("lantern", "ternlan", 30)
        nav.screen.challenge_deadline = time.time() + 30 - delay
        await nav.screen.refresh(inter)
        await continue_through(nav, inter)
        await find_button(nav, "Answer").callback(inter)
        modal = await submit(inter, answer)
        await modal.on_submit(fake_interaction())
        after = (sum((await user.items()).values()), (await user.skill("mining")).xp)
        assert (after != before) is rewarded, (answer, delay)  # (a prize is items, xp, or both)


async def test_leaving_the_hub_idle_mid_run_banks_the_haul(db):
    user = await User.get(1)
    nav, inter = await enter_mines()
    nav.screen.run.rng = Rig(0.99)
    await find_button(nav, "Dig").callback(inter)
    carried = dict(nav.screen.run.haul)
    nav.message = SimpleNamespace(edit=AsyncMock())
    await nav.on_timeout()
    assert nav.screen.run.finished and await user.items() == carried


# ---- the brain games (in-window) -------------------------------------------------------------------------
from cococap.registry import get_registry as _reg  # noqa: E402

START_LUCK = _reg().economy.starting_luckbucks


async def test_minigames_page_links_to_every_brain_game(db):
    nav, inter = await hub("minigames")
    for label in ("Flashcard", "Unscramble", "Sequence", "Trivia"):
        assert label in all_text(nav)
    plays = [b for b in buttons(nav) if b.label == "Play"]
    assert len(plays) == 4
    seen = set()
    for i in range(4):
        nav, inter = await hub("minigames")
        await [b for b in buttons(nav) if b.label == "Play"][i].callback(inter)
        seen.add(nav.screen.id)
    assert seen == {"flashcard", "unscramble", "sequence", "trivia"}


async def test_flashcard_round_trip_pays_luckbucks(db):
    nav, inter = await hub("flashcard")
    await click(nav, inter, "Start")
    game = nav.screen.game
    assert "= ?" in all_text(nav) and len([b for b in buttons(nav) if b.label.lstrip("-").isdigit()]) == 4
    await find_button(nav, str(game.answer)).callback(inter)
    assert "Correct" in all_text(nav) and "luckbucks" in all_text(nav)
    user = await User.get(1)
    assert user.luckbucks > START_LUCK and user.purse == 1000
    await click(nav, inter, "Next card")
    wrong = next(o for o in nav.screen.game.options if o != nav.screen.game.answer)
    await find_button(nav, str(wrong)).callback(inter)
    assert "Not quite" in all_text(nav)


async def test_unscramble_uses_a_modal_answer(db):
    nav, inter = await hub("unscramble")
    await click(nav, inter, "Start")
    word = nav.screen.game.word
    await find_button(nav, "Answer").callback(inter)
    modal = await submit(inter, word.upper())
    await modal.on_submit(fake_interaction())
    assert "Correct" in all_text(nav) and (await User.get(1)).luckbucks > START_LUCK


async def test_sequence_full_game_in_the_window(db):
    nav, inter = await hub("sequence")
    nav.screen.pause = 0
    await click(nav, inter, "Easy")
    screen = nav.screen
    assert screen.phase == "recall" and screen.locked and "Repeat the pattern" in all_text(nav)
    assert find_button(nav, "Home").disabled
    inter.edit_original_response.assert_awaited()  # the animation frames
    await find_button(nav, emoji=screen.game.pattern[0]).callback(inter)  # round 1 done, round 2 shown
    assert screen.game.score == 1 and screen.phase == "recall"
    wrong = next(o for o in screen.game.options if o != screen.game.pattern[0])
    await find_button(nav, emoji=wrong).callback(inter)
    assert screen.phase == "over" and "Game over" in all_text(nav) and not screen.locked
    assert (await User.get(1)).luckbucks == START_LUCK + 1  # 1 element x easy
    await click(nav, inter, "Play again")
    assert screen.phase == "choose"


async def test_sequence_walking_away_still_pays_what_you_remembered(db):
    nav, inter = await hub("sequence")
    nav.screen.pause = 0
    await click(nav, inter, "Medium")
    await find_button(nav, emoji=nav.screen.game.pattern[0]).callback(inter)
    nav.message = SimpleNamespace(edit=AsyncMock())
    await nav.on_timeout()
    assert (await User.get(1)).luckbucks == START_LUCK + 2  # score 1 x medium (2)


async def test_trivia_round_trip_and_outage_message(db, monkeypatch):
    from cococap.services import trivia as trivia_service

    raw = {"category": "science", "difficulty": "easy", "correctAnswer": "Mars", "incorrectAnswers": ["Venus", "Earth", "Pluto"],
           "question": {"text": "Red planet?"}}

    async def ok():
        return raw

    monkeypatch.setattr(trivia_service, "fetch_from_api", ok)
    nav, inter = await hub("trivia")
    await click(nav, inter, "Start")
    assert "Red planet?" in all_text(nav)
    letter = trivia_service.LETTERS[nav.screen.game.answers.index("Mars")]
    await find_button(nav, letter).callback(inter)
    assert "Correct" in all_text(nav) and "✅" in all_text(nav)
    assert (await User.get(1)).luckbucks == START_LUCK + 3

    async def down():
        raise trivia_service.TriviaUnavailable("down")

    monkeypatch.setattr(trivia_service, "fetch_from_api", down)
    nav, inter = await hub("trivia")
    with pytest.raises(trivia_service.TriviaUnavailable):
        await find_button(nav, "Start").callback(inter)


async def test_buttons_stay_attached_during_a_redraw_so_a_fast_second_click_is_not_dropped(db):
    """discord.py drops clicks on detached buttons ("View interaction referencing unknown view")."""
    nav, inter = await enter_mines()
    nav.screen.run.rng = Rig(0.99)
    old_dig = find_button(nav, "Dig")
    await old_dig.callback(inter)
    assert old_dig.view is nav  # it was replaced on screen, but must not be orphaned
    await old_dig.callback(inter)  # the second, stale click still works
    assert nav.screen.run.depth == 2


async def test_a_stale_dig_after_the_mine_ended_just_redraws(db):
    nav, inter = await enter_mines()
    run = nav.screen.run
    run.danger, run.rng = 80, Rig(0.0)  # Critical, and the dice say collapse
    stale = find_button(nav, "Dig")
    await stale.callback(inter)
    assert run.outcome == "collapse"
    await stale.callback(inter)  # arrives after the collapse: no error, no second settlement
    assert "collapsed" in all_text(nav)
    assert (await (await User.get(1)).skill("mining")).stats.lodes_mined == run.lodes


async def test_the_reactor_has_its_own_page_reachable_from_mining(db):
    user = await User.get(1)
    await user.add_xp("mining", User.level_to_xp(10) + 1)
    nav, inter = await hub("mining")
    await click(nav, inter, "Reactor")
    assert nav.screen.id == "reactor"
    text = all_text(nav)
    assert "Reactor Level 1" in text and "Auto-miner" in text and "empty: Sanity" in text
    assert "Digs **1** column" in text and "Wyrmholes: 1 in" in text
    assert {b.label for b in buttons(nav)} >= {"Claim lodes", "Insert gems", "Prestige"}
    assert find_button(nav, "Back")  # Back returns to Mining
    await click(nav, inter, "Back")
    assert nav.screen.id == "mining" and "Insert gems" not in {b.label for b in buttons(nav)}


async def test_the_weathered_seed_has_its_emoji(db):
    nav, _ = await hub("shop")
    seed = get_registry().item("dusty_dandelion_seed")
    assert seed.emoji and "seed_weathered" in seed.emoji


# ---- the streamlined mine screen ---------------------------------------------------------------------------
async def test_the_mine_screen_is_short_and_the_legend_only_shows_on_request(db):
    nav, inter = await enter_mines()
    text = all_text(nav)
    assert len(text.splitlines()) <= 9  # header, risk, map, pack: not a wall of text
    for clutter in ("columns", "Braces:", "Digging here", "volatile", "wyrmhole"):
        assert clutter not in text
    assert "vent" not in text
    await click(nav, inter, "Tips")
    assert "vent" in all_text(nav) and "bomb" in all_text(nav)
    assert find_button(nav, "Hide tips").style == discord.ButtonStyle.primary  # the button shows it is switched on
    await click(nav, inter, "Hide tips")
    assert "vent" not in all_text(nav) and find_button(nav, "Tips").style == discord.ButtonStyle.secondary
    await click(nav, inter, "Tips")
    await find_button(nav, "Dig").callback(inter)
    assert "vent" in all_text(nav)  # still showing after other actions, until you hide it


async def test_the_bomb_button_only_appears_with_bombs_and_clears_a_row(db):
    nav, inter = await enter_mines()
    assert not [b for b in buttons(nav) if b.label and b.label.startswith("Bomb")]
    user = await User.get(1)
    await user.add_item("scarab_bomb", 2)
    await click(nav, inter, "Leave & bank")
    await continue_through(nav, inter)
    await click(nav, inter, "Mine again")
    nav.screen.run.rng = Rig(0.99)
    await click(nav, inter, "Bomb (2)")
    run = nav.screen.run
    assert run.depth == 1 and run.bombs == 1 and run.lodes == 5 and "BOOM" in all_text(nav)
    assert await user.item_quantity("scarab_bomb") == 1
    assert find_button(nav, "Bomb (1)") and not find_button(nav, "Bomb (1)").disabled


async def test_reaching_the_floor_shows_the_vault_and_banks_it(db):
    nav, inter = await enter_mines()
    run = nav.screen.run
    run.rng = Rig(0.99)
    run.depth = run.floor - 1
    await find_button(nav, "Dig").callback(inter)
    assert run.outcome == "floor" and "reached the vault" in all_text(nav)
    user = await User.get(1)
    for ore, quantity in get_registry().mining.descent.vault_ore.items():
        assert await user.item_quantity(ore) >= quantity


# ---- the two-page home and the party ------------------------------------------------------------------------
async def test_the_first_page_is_short_and_the_rest_waits_on_more(db):
    nav, inter = await hub("home")
    text = all_text(nav)
    assert "Skills" in text
    for moved in ("Minigames", "Stats", "Settings", "Trade"):
        assert moved not in text, moved
    assert "Party" not in text.split("Skills")[0]  # (no party line unless the player is in a party)
    assert all(name in text for name in ("Check-in", "Inventory", "Shop", "Pets"))  # the main things are sections, one Open button each
    assert {b.label for b in buttons(nav)} >= {"Party", "More", "Profile", "Ranks", "Leaderboards"}  # one row of smaller things at the bottom
    assert len(text.splitlines()) <= 18  # (six main sections: a title and a line each)
    await click(nav, inter, "More")
    assert nav.screen.id == "more"
    text = all_text(nav)
    assert all(name in text for name in ("Trade", "Minigames", "Stats", "Settings"))
    await click(nav, inter, "Back")
    assert nav.screen.id == "home"


async def test_each_more_page_entry_opens_its_screen(db):
    for index, expected in enumerate(("trade", "minigames", "stats", "bestiary", "wiki", "settings")):
        nav, inter = await hub("more")
        sections = [c for c in nav.walk_children() if isinstance(c, ui.Section)]
        await sections[index].accessory.callback(inter)
        assert nav.screen.id == expected


async def test_check_in_lights_up_when_something_is_ready(db):
    nav, _ = await hub("home")
    assert check_in_open_button(nav).style == discord.ButtonStyle.success  # a fresh player can work/daily


async def test_home_shows_your_party_with_names_and_a_crown(db):
    from cococap.services.party import Party

    nav, _ = await hub("home")
    assert "Party:" not in all_text(nav)
    party = await Party.create(1)
    for uid in (2, 3, 4, 5, 6):
        await party.add_member(uid)
    nav, _ = await hub("home")
    text = all_text(nav)
    assert "tester 👑" in text and "user2" in text and "user4" in text
    assert "user5" not in text and "+2 more" in text  # a long roster is shortened
    assert "<@" not in text  # names, never mentions (no pings)


async def test_party_screen_creates_lists_and_disbands(db):
    from cococap.services.party import Party

    nav, inter = await hub("party")
    assert "Party:" not in all_text(nav)
    await click(nav, inter, "Create party")
    assert (await Party.for_user(1)).is_owner(1) and "Party #" in all_text(nav) and "(you)" in all_text(nav)
    assert [c for c in nav.walk_children() if isinstance(c, ui.UserSelect)]  # the leader can invite
    await click(nav, inter, "Disband party")
    assert await Party.for_user(1) is None and "not in a party" in all_text(nav)


async def test_party_members_can_leave_but_a_leader_with_a_team_must_disband(db):
    from cococap.errors import CustomError
    from cococap.services.party import Party

    party = await Party.create(2)
    await party.add_member(1)
    nav, inter = await hub("party", user_id=1)
    assert not [c for c in nav.walk_children() if isinstance(c, ui.UserSelect)]  # only the leader invites
    await click(nav, inter, "Leave party")
    assert await Party.for_user(1) is None and (await Party.for_user(2)).members == [2]
    await party.add_member(3)
    with pytest.raises(CustomError, match="leader"):  # the leader can't walk out on a team
        await (await Party.for_user(2)).leave(2)


async def test_inviting_uses_the_party_rules_and_posts_nothing_in_the_chat(db):
    from cococap.errors import CustomError
    from cococap.services import party_invites
    from cococap.services.party import Party

    await Party.create(1)
    nav, inter = await hub("party")
    invite = next(c for c in nav.walk_children() if isinstance(c, ui.UserSelect))
    friend = SimpleNamespace(id=9, bot=False)
    invite._values = [friend]
    inter.response.send_message.reset_mock()
    await invite.callback(inter)
    assert party_invites.pending_for(9) is not None and party_invites.pending_for(9).inviter_id == 1
    inter.response.send_message.assert_not_called()  # no Join/Decline message in the channel: it is on their Party page
    assert "Invited" in all_text(nav)
    for bad, message in ((SimpleNamespace(id=1, bot=False), "already here"), (SimpleNamespace(id=7, bot=True), "Bots")):
        invite._values = [bad]
        with pytest.raises(CustomError, match=message):
            await invite.callback(inter)
    assert party_invites.pending_for(7) is None and party_invites.pending_for(1) is None


# ---- farming -------------------------------------------------------------------------------------------------------
FRIDAY = 1_794_571_200  # 2026-11-13 12:00 UTC


async def ripen(user, plot=1, seed="apple_seed"):
    def set_plot(m):
        p = getattr(m.farm, f"plot_{plot}")
        p.crop_id, p.can_harvest = seed, True

    await user.update_skill("farming", set_plot)


async def test_farm_opens_from_skills_and_shows_the_grid(db):
    nav, inter = await hub("skills")
    farm = [b for b in buttons(nav) if b.label == "Open"]
    await farm[1].callback(inter)
    assert nav.screen.id == "farm"
    text = all_text(nav)
    assert "Rain" in text and "Blessings" in text and "Nothing is growing" in text
    labels = [b.label for b in buttons(nav)]
    assert "1 Plant" in labels and labels.count("Buy plot") == 9 - get_registry().farming.free_plots  # the free plots are yours, the rest are locked


async def test_planting_from_the_farm_uses_the_selected_seed(db):
    user = await User.get(1)
    await user.add_item("apple_seed", 2)
    nav, inter = await hub("farm")
    assert [s for s in selects(nav) if s.placeholder == "Seed to plant"]
    have = await user.item_quantity("apple_seed")  # (the 2 plus the free starter seeds)
    await click(nav, inter, "1 Plant")
    assert await user.item_quantity("apple_seed") == have - 1
    assert "Planted Apple Seed in plot 1" in all_text(nav)
    assert any(b.label.startswith("1 ·") and b.disabled for b in buttons(nav))  # now shows its progress


async def test_planting_without_a_seed_says_so(db):
    await (await User.get(1)).update_skill("farming", lambda m: setattr(m, "starter_given", True))  # (a farmer who used theirs up)
    nav, inter = await hub("farm")
    await click(nav, inter, "1 Plant")
    assert "no seeds" in all_text(nav)


async def test_harvesting_a_ripe_plot_from_the_farm(db):
    user = await User.get(1)
    await ripen(user)
    nav, inter = await hub("farm")
    assert "ready" in all_text(nav)
    await click(nav, inter, "1 Harvest")
    assert nav.screen.id == "result" and "You got" in all_text(nav) and await user.item_quantity("apple") >= 10
    assert find_button(nav, "Back to the farm") and (await user.skill("farming")).xp > 0
    await click(nav, inter, "Back to the farm")
    assert nav.screen.id == "farm"
    assert "1 Plant" in [b.label for b in buttons(nav)]  # the plot is empty again


async def test_harvest_all_and_plant_all(db):
    user = await User.get(1)
    await user.update_skill("farming", lambda m: setattr(m, "starter_given", True))  # (no free seeds mixed in)
    await user.add_item("land_deed", 1)
    await ripen(user, 1)
    nav, inter = await hub("farm")
    await click(nav, inter, "Buy plot")
    free = get_registry().farming.free_plots
    assert f"bought plot {free + 1}" in all_text(nav)
    await user.add_item("lemon_seed", 5)
    nav, inter = await hub("farm")
    await click(nav, inter, "Harvest all")
    assert "You got" in all_text(nav)
    await click(nav, inter, "Back to the farm")
    await click(nav, inter, "Plant all")
    assert await user.item_quantity("lemon_seed") == 5 - (free + 1)  # every empty plot took one seed
    assert find_button(nav, "Plant all").disabled  # nothing left to plant into


async def test_buying_a_plot_needs_a_land_deed(db):
    nav, _ = await hub("farm")
    assert all(b.disabled for b in buttons(nav) if b.label == "Buy plot")
    user = await User.get(1)
    await user.add_item("land_deed", 1)
    nav, inter = await hub("farm")
    await click(nav, inter, "Buy plot")
    assert await user.item_quantity("land_deed") == 0 and labels_count(nav, "Buy plot") == 8 - get_registry().farming.free_plots


def labels_count(nav, label):
    return [b.label for b in buttons(nav)].count(label)


async def test_market_is_locked_until_level_five_then_follows_the_calendar(db, monkeypatch):
    nav, inter = await hub("farm")
    await click(nav, inter, "Market")
    assert nav.screen.id == "market" and "level 5" in all_text(nav)
    user = await User.get(1)
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    await user.add_item("apple", 10)
    clock = SimpleNamespace(time=lambda: FRIDAY)
    monkeypatch.setattr("cococap.screens.market.time", clock)
    monkeypatch.setattr("cococap.services.farming.time", clock)
    nav, inter = await hub("market")
    text = all_text(nav)
    assert "Open" in text and "+50%" in text and find_button(nav, "Deposit blessings")
    before = (await User.get(1)).purse
    await click(nav, inter, next(b.label for b in buttons(nav) if b.label.startswith("Sell all")))
    assert (await User.get(1)).purse > before and await user.item_quantity("apple") == 0
    assert "Sold 10 crop(s)" in all_text(nav)


async def test_market_is_closed_outside_its_hours(db, monkeypatch):
    user = await User.get(1)
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    await user.add_item("apple", 3)
    clock = SimpleNamespace(time=lambda: FRIDAY - 12 * 3600)  # midnight UTC, closed
    monkeypatch.setattr("cococap.screens.market.time", clock)
    monkeypatch.setattr("cococap.services.farming.time", clock)
    nav, _ = await hub("market")
    assert "Closed" in all_text(nav)
    assert all(b.disabled for b in buttons(nav) if b.label.startswith("Sell all") or b.label == "Deposit blessings")


async def test_depositing_blessings_from_the_market(db, monkeypatch):
    user = await User.get(1)
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    await user.update_skill("farming", lambda m: setattr(m, "rain_god_blessings", 3))
    clock = SimpleNamespace(time=lambda: FRIDAY)
    monkeypatch.setattr("cococap.screens.market.time", clock)
    monkeypatch.setattr("cococap.services.farming.time", clock)
    nav, inter = await hub("market")
    await click(nav, inter, "Deposit blessings")
    assert "Deposited 3 blessing(s)" in all_text(nav)
    assert (await user.skill("farming")).rain_god_blessings == 0


# ---- the payload Discord would really receive ------------------------------------------------------------------
# Component types: 1 action row, 2 button, 3/5/6/7/8 menus, 9 section, 10 text, 11 thumbnail, 12 gallery, 13 file,
# 14 separator, 17 container. The fake interactions used elsewhere never send anything, so they can't see a menu
# placed where Discord refuses it (that crashed /play -> Party and Farm once).
TOP_LEVEL = {1, 9, 10, 12, 13, 14, 17}
IN_CONTAINER = {1, 9, 10, 12, 13, 14}
IN_ROW = {2, 3, 5, 6, 7, 8}
SECTION_ACCESSORY = {2, 11}


def check_payload(components) -> None:
    for top in components:
        assert top["type"] in TOP_LEVEL, top["type"]
        for child in top.get("components", []) if top["type"] == 17 else []:
            assert child["type"] in IN_CONTAINER, f"type {child['type']} directly inside a container"
            if child["type"] == 1:
                assert child["components"] and all(c["type"] in IN_ROW for c in child["components"])
                menus = [c for c in child["components"] if c["type"] != 2]
                assert len(child["components"]) <= 5 and (not menus or len(child["components"]) == 1)  # a menu fills its row
            if child["type"] == 9:
                assert child["accessory"]["type"] in SECTION_ACCESSORY


async def stock_the_player(user):
    from cococap.services.party import Party

    for item, quantity in (("apple_seed", 3), ("hot_pepper_seed", 2), ("land_deed", 2), ("scarab_bomb", 2), ("apple", 4),
                           ("sanity_gemstone", 1), ("copper_ore", 50), ("iron_ore", 9)):
        await user.add_item(item, quantity)
    await user.give_instance("rookiepickaxe")
    from cococap.services.equipment import equip

    await equip(user, "foraging", (await user.give_instance("starter_axe")).id)
    await user.add_xp("mining", User.level_to_xp(10) + 1)
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    await ripen(user, 1)
    party = await Party.create(user.id)
    await party.add_member(2)


@pytest.mark.parametrize("screen_id", list(SCREENS))
async def test_every_screen_payload_obeys_discords_nesting_rules_for_a_stocked_player(db, screen_id, monkeypatch):
    await stock_the_player(await User.get(1))
    clock = SimpleNamespace(time=lambda: FRIDAY)
    monkeypatch.setattr("cococap.screens.market.time", clock)
    monkeypatch.setattr("cococap.services.farming.time", clock)
    nav, _ = await hub(screen_id)
    check_payload(nav.to_components())


async def test_the_payload_check_really_rejects_a_menu_outside_an_action_row(db):
    nav, _ = await hub("party")
    bad = nav.to_components()
    bad[0]["components"].append({"type": 5})  # what the Party screen used to do
    with pytest.raises(AssertionError, match="directly inside a container"):
        check_payload(bad)


async def test_live_screens_are_valid_too(db):
    await stock_the_player(await User.get(1))
    nav, inter = await enter_mines()
    check_payload(nav.to_components())
    await click(nav, inter, "Tips")
    check_payload(nav.to_components())
    farm, _ = await hub("farm")
    check_payload(farm.to_components())


# ---- foraging ---------------------------------------------------------------------------------------------------
from cococap.services import foraging as foraging_service  # noqa: E402

OPEN_HOUR = 490_000 * 3600 + 60  # a minute into an hour: the community tree is standing


async def with_axe(user_id=1, flags=(), template="starter_axe"):
    from cococap.services.equipment import add_enchant, equip

    user = await User.get(user_id)
    axe = await user.give_instance(template)
    await equip(user, "foraging", axe.id)
    if "soloist" in flags:
        await add_enchant(user, axe.id, "soloist")
    return user


def freeze_time(monkeypatch, now=OPEN_HOUR, good_chops=False):
    """Fix the clock, and make chopping predictable: no good chops unless asked for."""
    monkeypatch.setattr("cococap.screens.forage.new_rng", lambda: Rig(0.0 if good_chops else 0.99))
    plain = foraging_service.Spot  # every spot is a plain one, so damage is predictable
    monkeypatch.setattr(plain, "pick", classmethod(lambda cls, rules, rng, bias=0.0, exclude=None, special_mult=1.0, private=True: cls("Plain", 1.0)))
    clock = SimpleNamespace(time=lambda: now)
    for target in ("cococap.screens.forage.time", "cococap.services.foraging.time"):
        monkeypatch.setattr(target, clock)


async def test_foraging_opens_from_skills(db):
    nav, inter = await hub("skills")
    await [b for b in buttons(nav) if b.label == "Open"][2].callback(inter)
    assert nav.screen.id == "forage"


async def test_without_an_axe_foraging_says_how_to_get_one(db, monkeypatch):
    freeze_time(monkeypatch)
    nav, _ = await hub("forage")
    assert "need an axe" in all_text(nav)
    assert find_button(nav, "Chop a tree").disabled and find_button(nav, "Join the community tree").disabled


async def test_chopping_a_private_tree_to_the_ground_pays_out(db, monkeypatch):
    freeze_time(monkeypatch)
    user = await with_axe()
    nav, inter = await hub("forage")
    await click(nav, inter, "Chop a tree")
    assert nav.screen.id == "tree" and "hp" in all_text(nav)
    nav.screen.tree = foraging_service.Tree(1, 1, 1)  # a one-chop tree, so the test is short
    await chop(nav, inter)
    assert nav.screen.id == "result" and nav.screen.origin.reward is not None and "TIMBER" in all_text(nav)
    assert (await user.skill("foraging")).stats.trees_chopped == 1 and (await user.skill("foraging")).xp > 0  # (it pays xp and drops, not bits)
    await click(nav, inter, "Another tree")
    assert nav.screen.id == "tree" and nav.screen.reward is None and nav.screen.tree.hp == nav.screen.tree.max_hp
    await click(nav, inter, "Leave")
    assert nav.screen.id == "forage"


async def test_a_second_chop_click_on_a_fallen_tree_does_not_pay_twice(db, monkeypatch):
    freeze_time(monkeypatch)
    await with_axe()
    nav, inter = await hub("tree", tree=foraging_service.Tree(1, 1, 1))
    stale = find_button(nav, "Overhead")
    await stale.callback(inter)
    purse = (await User.get(1)).purse
    await stale.callback(inter)
    assert (await User.get(1)).purse == purse


async def test_heavy_trees_are_slower_for_a_lone_chopper_and_soloist_fixes_it(db, monkeypatch):
    freeze_time(monkeypatch)
    heavy = get_registry().foraging.heavy_zone
    await with_axe(1, template="reinforced_axe")
    nav, _ = await hub("tree", tree=foraging_service.Tree(heavy, 100, 100))
    assert "Heavy tree" in all_text(nav)
    await with_axe(2, flags=("soloist",), template="reinforced_axe")
    nav, _ = await hub("tree", tree=foraging_service.Tree(heavy, 100, 100), user_id=2)
    assert "Heavy tree" not in all_text(nav)


async def test_you_can_pick_a_zone_you_have_unlocked(db, monkeypatch):
    freeze_time(monkeypatch)
    user = await with_axe()
    nav, _ = await hub("forage")
    assert not [s for s in selects(nav) if s.placeholder == "Zone"]  # only zone 1 so far
    await user.add_xp("foraging", User.level_to_xp(8) + 1)  # level 8 -> zones 1-3
    nav, inter = await hub("forage")
    menu = select_named(nav, "Zone")
    assert [o.value for o in menu.options] == ["1", "2", "3"] and nav.screen.zone == 3
    await choose(nav, inter, menu, "2")
    assert nav.screen.zone == 2


async def test_two_players_chop_the_community_tree_together(db, monkeypatch):
    freeze_time(monkeypatch)
    alice, bob = await with_axe(1), await with_axe(2)
    a_nav, a_inter = await hub("forage")
    b_nav, b_inter = await hub("forage", user_id=2)
    assert "Community tree" in all_text(a_nav)
    await click(a_nav, a_inter, "Join the community tree")
    await click(b_nav, b_inter, "Join the community tree")
    assert a_nav.screen.id == "grove" and b_nav.screen.id == "grove"
    await chop(a_nav, a_inter)
    await chop(a_nav, a_inter)
    await chop(b_nav, b_inter)
    tree = await foraging_service.community_tree(alice, OPEN_HOUR)
    power = get_registry().item("starter_axe").tool.power
    assert tree.hp == tree.max_hp - 3 * power and tree.choppers == 2
    assert f"**{2 * power:,}** hp" in all_text(a_nav) and f"**{power:,}** hp" in all_text(b_nav)  # each sees their own share
    assert "**2** chopper" in all_text(b_nav)  # and the panel reads the latest total when it redraws


async def test_the_community_panel_refreshes_itself_so_you_see_others_work(db, monkeypatch):
    import asyncio

    freeze_time(monkeypatch)
    watcher, worker = await with_axe(1), await with_axe(2)
    nav, _ = await hub("grove")
    nav.screen.refresh_every = 0.02
    nav._restart_ticker()
    before = all_text(nav)
    await foraging_service.chop_community(worker, 10, OPEN_HOUR)  # somebody else chops; the watcher does nothing
    await asyncio.sleep(0.2)
    assert nav.message.edit.await_count >= 2  # it redrew on its own...
    assert all_text(nav) != before and "**1** chopper" in all_text(nav)  # ...and shows the other player's chops
    await nav.stop_ticker()


async def test_the_self_refresh_stops_when_you_leave_the_screen(db, monkeypatch):
    import asyncio

    freeze_time(monkeypatch)
    await with_axe()
    nav, inter = await hub("grove")
    nav.screen.refresh_every = 0.02
    nav._restart_ticker()
    await click(nav, inter, "Leave")
    assert nav.screen.id == "forage"
    await asyncio.sleep(0.1)
    count = nav.message.edit.await_count
    await asyncio.sleep(0.1)
    assert nav.message.edit.await_count == count and nav._ticker is None


async def test_felling_the_community_tree_pays_everyone_from_their_own_panel(db, monkeypatch):
    freeze_time(monkeypatch)
    alice, bob = await with_axe(1), await with_axe(2)
    tree = await foraging_service.community_tree(alice, OPEN_HOUR)
    await foraging_service.chop_community(alice, tree.max_hp // 2, OPEN_HOUR)
    nav, inter = await hub("grove", user_id=2)
    await foraging_service.chop_community(bob, tree.max_hp - tree.max_hp // 2, OPEN_HOUR)  # bob's chop fells it
    await nav.screen.refresh(inter)
    assert nav.screen.id == "result" and "TIMBER" in all_text(nav) and (await bob.skill("foraging")).xp > 0  # bob's share arrived (xp and drops: chopping pays no bits)
    await continue_through(nav, inter)
    assert "felled" in all_text(nav)
    nav_a, _ = await hub("forage", user_id=1)  # alice returns later and finds hers too
    assert nav_a.screen.id == "result" and "TIMBER" in all_text(nav_a) and (await (await User.get(1)).skill("foraging")).xp > 0


async def test_the_tree_falling_over_unfinished_ends_the_panel_gracefully(db, monkeypatch):
    freeze_time(monkeypatch)
    user = await with_axe()
    nav, inter = await hub("grove")
    await chop(nav, inter)
    freeze_time(monkeypatch, OPEN_HOUR + 40 * 60)  # 40 minutes in: it fell over
    await nav.screen.refresh(inter)
    assert nav.screen.id == "result" and "fell over" in all_text(nav)  # the consolation arrives on its own page
    await click(nav, inter, "Continue")
    text = all_text(nav)
    assert "fell over" in text and "next one grows" in text
    assert [b for b in buttons(nav) if b.label == "Back to foraging"]
    assert "consolation" in text.lower() or "TIMBER" not in text


async def test_home_only_says_whether_check_in_is_ready_and_the_timers_live_on_the_check_in_page(db):
    home, _ = await hub("home")
    text = all_text(home)
    assert "✅ Check-in ready" in text
    for timer_clutter in ("Work", "Daily", "Weekly", "⏳"):
        assert timer_clutter not in text
    nav, inter = await hub("checkin")
    await click(nav, inter, "Claim")  # work
    await click(nav, inter, "Claim")  # daily
    await click(nav, inter, "Claim")  # weekly
    home, _ = await hub("home")
    assert "⏳ Check-in not ready yet" in all_text(home) and "Work" not in all_text(home)
    assert check_in_open_button(home).style == discord.ButtonStyle.primary  # no longer lit
    assert [b for b in buttons(nav) if b.label and b.label.endswith(("h", "m")) and b.disabled]  # timers: on the page


async def test_a_spot_wears_out_and_moves_on_by_itself_and_a_wrong_style_only_glances_off(db, monkeypatch):
    freeze_time(monkeypatch)
    user = await with_axe(template="reinforced_axe")
    power = get_registry().item("reinforced_axe").tool.power
    nav, inter = await hub("tree", tree=foraging_service.Tree(1, 1_000_000, 1_000_000))
    rules = get_registry().foraging
    right = nav.screen.spot.stance(rules)
    wrong = next(letter for letter in "osu" if letter != right)
    await click(nav, inter, foraging_service.STANCES[wrong][0])
    assert nav.screen.tree.hp == 1_000_000 - round(power * rules.chopping.wrong_stance_factor) and "glanced off" in all_text(nav)
    assert 0 < nav.screen.spot.wear and "crossed off" in all_text(nav)
    wear = nav.screen.spot.wear
    for _ in range(int(1 / wear) + 1):  # keep chopping until the spot is used up
        await chop(nav, inter)
    assert nav.screen.spot.wear < 1  # it wore out on the way and was renewed (a spot is never left at 100%)
    skill = await user.skill("foraging")
    assert skill.styles["plain"] == right.upper()  # the right style was learned on the way


async def test_a_good_chop_does_extra_damage_and_says_so(db, monkeypatch):
    freeze_time(monkeypatch, good_chops=True)
    await with_axe(template="reinforced_axe")
    power = get_registry().item("reinforced_axe").tool.power
    nav, inter = await hub("tree", tree=foraging_service.Tree(1, 10_000, 10_000))
    await chop(nav, inter)
    bonus = round(power * (1 + RULES_CHOP.good_chop_bonus))
    assert "Good chop" in all_text(nav) and nav.screen.tree.hp == 10_000 - bonus
    freeze_time(monkeypatch, good_chops=False)
    nav2, inter2 = await hub("tree", tree=foraging_service.Tree(1, 10_000, 10_000))
    await chop(nav2, inter2)
    assert "Good chop" not in all_text(nav2) and nav2.screen.tree.hp == 10_000 - power


async def test_the_community_tree_has_the_same_spot_and_wear(db, monkeypatch):
    freeze_time(monkeypatch)
    user = await with_axe(template="reinforced_axe")
    power = get_registry().item("reinforced_axe").tool.power
    nav, inter = await hub("grove")
    assert "left (about" in all_text(nav) and "per swing" in all_text(nav)
    await chop(nav, inter, zone=3)
    nav.screen.spot.wear = 0.9
    await chop(nav, inter, zone=3)
    worn = (await foraging_service.community_tree(user, OPEN_HOUR)).yours
    assert worn < 2 * power  # the second chop, on a worn spot, did less than a fresh one would have


RULES_CHOP = get_registry().foraging.chopping


async def test_every_leaderboard_says_what_it_counts(db):
    from cococap.exts.economy.top import TopCategories, leaderboard_view

    user = await User.get(1)
    await set_columns(user, purse=1_250, luckbucks=40)
    await user.inc_stat("drops_claimed", 3)
    for skill in ("farming", "foraging", "fishing", "mining", "combat"):
        await user.add_xp(skill, 300)
    expected = {"bits": "1,250 bits", "luckbucks": "40 luckbucks", "drops": "3 drops claimed"}
    for category in TopCategories:
        board, _, _ = await leaderboard_view(category, 1)
        if category.key.startswith("skill:"):
            assert "Lv 2 (300 xp)" in board, (category, board)
        else:
            assert expected[category.value] in board, (category, board)


async def test_the_house_earns_luckbucks_not_bits_on_the_boards(db):
    from cococap.constants import BOT_ID
    from cococap.exts.economy.top import TopCategories, leaderboard_view

    house = await User.get(BOT_ID)
    await set_columns(house, purse=999, luckbucks=1_234)
    _, bits_line, bits_footer = await leaderboard_view(TopCategories.BITS, 1)
    assert "bits in the economy" in bits_line and bits_footer is None  # no "the house has made N bits"
    _, _, luck_footer = await leaderboard_view(TopCategories.LUCKBUCKS, 1)
    assert luck_footer == "The house has made: 1,234 luckbucks"
    nav, inter = await hub("top")
    assert "house" not in all_text(nav).lower()
    await choose(nav, inter, select_named(nav, "Pick a leaderboard"), "luckbucks")
    assert "The house has made: 1,234 luckbucks" in all_text(nav)


# ---- lag: a failed answer must not strand the player ---------------------------------------------------------------
def _http_error(cls, status, code, message):
    return cls(SimpleNamespace(status=status, reason=message), {"code": code, "message": message})


async def test_a_click_acknowledged_too_late_still_updates_the_panel(db):
    nav, inter = await hub("home")
    expired = _http_error(discord.NotFound, 404, 10062, "Unknown interaction")
    inter.response.edit_message = AsyncMock(side_effect=expired)
    nav.message.edit.reset_mock()
    await nav.show(inter, "shop")  # Discord refuses our answer ("this interaction failed")...
    assert nav.screen.id == "shop"
    nav.message.edit.assert_awaited_once_with(view=nav)  # ...so the message is edited directly instead


async def test_an_already_answered_click_also_falls_back(db):
    nav, inter = await hub("home")
    inter.response.edit_message = AsyncMock(side_effect=discord.InteractionResponded(inter))
    nav.message.edit.reset_mock()
    await nav.refresh(inter)
    nav.message.edit.assert_awaited_once_with(view=nav)


async def test_a_real_error_is_not_swallowed_by_the_fallback(db):
    nav, inter = await hub("home")
    bad = _http_error(discord.HTTPException, 400, 50035, "Invalid Form Body")
    inter.response.edit_message = AsyncMock(side_effect=bad)
    nav.message.edit.reset_mock()
    with pytest.raises(discord.HTTPException):
        await nav.refresh(inter)
    nav.message.edit.assert_not_awaited()  # a broken layout would just fail again: tell the developer, not the player


async def test_if_the_fallback_fails_too_the_original_error_surfaces(db):
    nav, inter = await hub("home")
    inter.response.edit_message = AsyncMock(side_effect=_http_error(discord.NotFound, 404, 10062, "Unknown interaction"))
    nav.message.edit = AsyncMock(side_effect=_http_error(discord.NotFound, 404, 10008, "Unknown Message"))
    with pytest.raises(discord.NotFound):
        await nav.refresh(inter)


async def test_a_redraw_never_queues_up_behind_a_click_so_the_next_click_is_not_delayed(db, monkeypatch):
    import asyncio

    from cococap.ui import nav as nav_module

    nav, inter = await hub("home")
    screen = nav.screen

    async def slow_edit(**kwargs):
        await asyncio.sleep(30)

    nav.message.edit = slow_edit
    monkeypatch.setattr(nav_module, "TICK_EDIT_TIMEOUT", 0.2)
    await nav._lock.acquire()  # a click is being handled
    ticker = asyncio.create_task(nav._tick(screen, 0.01))
    await asyncio.sleep(0.1)  # the redraw is due now, but must not line up for the lock
    nav._lock.release()
    # the player's NEXT click gets the lock at once: nothing was queued ahead of it
    await asyncio.wait_for(nav._lock.acquire(), 0.005)
    nav._lock.release()
    ticker.cancel()
    await asyncio.gather(ticker, return_exceptions=True)


async def test_a_redraw_stuck_on_a_rate_limit_gives_the_lock_back_after_a_short_wait(db, monkeypatch):
    import asyncio

    from cococap.ui import nav as nav_module

    nav, inter = await hub("home")

    async def stuck_edit(**kwargs):
        await asyncio.sleep(30)

    nav.message.edit = stuck_edit
    monkeypatch.setattr(nav_module, "TICK_EDIT_TIMEOUT", 0.05)
    ticker = asyncio.create_task(nav._tick(nav.screen, 0.01))
    await asyncio.sleep(0.03)  # the redraw is now stuck inside its edit, holding the lock...
    await asyncio.wait_for(nav._lock.acquire(), 1.0)  # ...but a click only has to wait out the short timeout
    nav._lock.release()
    ticker.cancel()
    await asyncio.gather(ticker, return_exceptions=True)


# ---- the result page: one screen after a win or a loss ------------------------------------------------------------
async def test_a_result_page_shows_what_happened_and_locks_the_menu_until_you_choose(db):
    from cococap.ui import Result

    nav, inter = await hub("home")
    calls = []

    async def again(interaction):
        calls.append("again")
        await nav.screen.refresh(interaction, "round two")

    nav.screen.result = Result("You won!", ["**+5** bits", "a shiny thing"], emoji="🏆", again=again, again_label="Go again")
    await nav.refresh(inter)
    assert nav.screen.id == "result" and "You won!" in all_text(nav) and "a shiny thing" in all_text(nav)
    assert find_button(nav, "Home").disabled and find_button(nav, "Back").disabled  # you must look, then choose
    await click(nav, inter, "Go again")
    assert calls == ["again"] and nav.screen.id == "home" and "round two" in all_text(nav)  # back on the page it came from
    nav.screen.result = Result("Lost!", ["too bad"])
    await nav.refresh(inter)
    assert not [b for b in buttons(nav) if b.label == "Again"]  # nothing to repeat: just Continue
    await click(nav, inter, "Continue")
    assert nav.screen.id == "home"


async def test_the_result_page_is_not_a_screen_you_can_navigate_to_or_a_dead_end(db):
    from cococap.ui import Result

    assert "result" not in SCREENS
    nav, inter = await hub("home")
    nav.screen.result = Result("Done", ["ok"], back=None)
    await nav.refresh(inter)
    await click(nav, inter, "Continue")
    assert nav.screen.id == "home"
    nav.to_components()


async def test_a_result_that_turns_up_on_its_own_still_gets_its_redraw_timer(db):
    import asyncio

    from cococap.ui import Result

    nav, inter = await hub("home")
    state = {"n": 0}

    def live():
        state["n"] += 1
        return ([f"tick {state['n']}"], state["n"] < 3)

    nav.screen.result = Result("Numbers", ["hold on"], live=live)
    await nav.refresh(inter)
    assert nav.screen.refresh_every and "tick 1" in all_text(nav)
    await asyncio.sleep(0.05)
    await nav.stop_ticker()


async def test_a_result_that_appears_while_nobody_clicked_swaps_the_page_by_itself(db, monkeypatch):
    import asyncio

    from cococap.ui import Result, nav as nav_module

    nav_, inter = await hub("home")
    screen = nav_.screen
    monkeypatch.setattr(nav_module, "TICK_EDIT_TIMEOUT", 1.0)
    screen.result = Result("Happened on its own", ["a timer ran out"])
    ticker = asyncio.create_task(nav_._tick(screen, 0.01))
    await asyncio.sleep(0.1)
    assert nav_.screen.id == "result" and "a timer ran out" in all_text(nav_)
    ticker.cancel()
    await asyncio.gather(ticker, return_exceptions=True)
    await nav_.stop_ticker()


async def test_leaving_a_result_page_idle_still_abandons_the_screen_it_came_from(db):
    from cococap.ui import Result

    nav, inter = await hub("home")
    abandoned = []

    async def on_abandon():
        abandoned.append(True)

    nav.screen.on_abandon = on_abandon
    nav.screen.result = Result("x", ["y"])
    await nav.refresh(inter)
    await nav.screen.on_abandon()
    assert abandoned == [True]


# ---- what the home page and the skills page no longer show -----------------------------------------------------------------
async def test_home_has_no_level_no_progress_button_and_no_picture(db):
    nav, _ = await hub("home")
    text = all_text(nav)
    assert "Coconut Level" not in text and "Progress" not in {b.label for b in buttons(nav)}
    assert not [c for c in nav.walk_children() if isinstance(c, ui.Thumbnail)]
    assert "tester" in text and "Check-in" in text  # your name, rank, balances and check-in are still there


async def test_the_skills_page_shows_each_skill_with_its_level_and_no_blurb(db):
    nav, _ = await hub("skills")
    text = all_text(nav)
    for skill in ("Mining", "Farming", "Foraging", "Fishing", "Combat"):
        assert skill in text
    for blurb in ("Push your luck", "wait for the rain", "Fell trees", "reel in the big one", "Turn-based"):
        assert blurb not in text
    assert len([b for b in buttons(nav) if b.label == "Open"]) == 4


async def test_a_scarab_can_turn_up_after_any_mine_and_never_says_level_six(db, monkeypatch):
    from cococap.services import mining as mining_service

    monkeypatch.setattr(mining_service, "scarab_appears", lambda rules, rng: True)
    for how in ("left", "collapse", "wyrmhole", "floor"):
        nav, inter = await enter_mines()
        run = nav.screen.run
        run.outcome = how
        await nav.screen._end(None)
        await nav.screen.refresh(inter)
        await continue_through(nav, inter)
        assert nav.screen.challenge is not None, how
        text = all_text(nav)
        assert "scarab" in text and "level 6" not in text.lower() and "reward you" in text, how


async def test_the_scarab_gives_you_more_time_than_it_used_to(db):
    import random as _random

    from cococap.services.mining import make_scarab

    rules = get_registry().mining
    assert make_scarab(["lantern"], rules, _random.Random(1)).seconds == rules.scarab.seconds > 30


async def test_back_goes_up_one_level_instead_of_undoing_the_last_click(db):
    nav, inter = await hub("home")
    await nav.show(inter, "skills")
    await nav.show(inter, "fish")
    await nav.show(inter, "radar")
    await nav.show(inter, "fish")  # (the radar's own way back to the fishing page)
    assert nav.stack == ["home", "skills", "fish"]  # the radar is not left behind as a place to "go back" to
    await nav.back(inter)
    assert nav.screen.id == "skills"
    await nav.back(inter)
    assert nav.screen.id == "home"


def test_only_tools_cannot_be_sold():
    reg = get_registry()
    assert [i.id for i in reg.items.values() if not i.is_instance and not i.sellable] == []
    assert all(not i.sellable for i in reg.items.values() if i.is_instance)


def _nav_labels(nav):
    return {b.label for b in buttons(nav)}


async def test_a_private_tree_hides_home_and_back_but_a_plain_page_shows_them(db):
    nav, inter = await hub("forage")
    assert {"Home", "Back"} <= _nav_labels(nav)  # no leave button here, so the controller is shown
    await with_axe()
    await click(nav, inter, "Chop a tree")
    assert nav.screen.id == "tree" and nav.screen.locked and "Leave" in _nav_labels(nav) and not {"Home", "Back"} & _nav_labels(nav)
    await click(nav, inter, "Leave")
    assert nav.screen.id == "forage" and {"Home", "Back"} <= _nav_labels(nav)


@pytest.mark.parametrize("screen_id", ["grove", "partygrove"])
async def test_shared_tree_pages_hide_home_and_back(db, screen_id):
    nav, inter = await hub(screen_id)
    assert nav.screen.locked and not {"Home", "Back"} & _nav_labels(nav)
    await nav.screen.on_abandon()  # nothing half-done to settle: must not raise


async def test_a_line_in_the_water_hides_home_and_back_and_a_timeout_cancels_it(db, monkeypatch):
    from cococap.services import fishing, party_boss

    nav, inter = await hub("fish")
    assert {"Home", "Back"} <= _nav_labels(nav)  # no line out: the controller is shown
    screen = nav.screen
    reported = []
    monkeypatch.setattr(party_boss, "report", AsyncMock(side_effect=lambda *a: reported.append(a)))
    screen.cast = SimpleNamespace(party_fight=3, status=lambda t: "waiting")
    assert screen.locked and screen.hides_nav
    await screen.on_abandon()
    assert screen.cast is None and reported and reported[0][1] == "failed" and not screen.locked
    await screen.on_abandon()  # a second time does nothing
    assert len(reported) == 1


async def test_home_shows_pending_party_and_trade_invites(db):
    import time

    from cococap.services import party_invites, trade

    nav, _ = await hub("home", user_id=61)
    assert "Party invite" not in all_text(nav) and "Trade invite" not in all_text(nav)
    party_invites._pending[61] = party_invites.Invite(1, 62, 61, time.time() + 60)
    trade._invites[61] = trade.Invite(63, 61, time.time() + 60)
    try:
        nav, inter = await hub("home", user_id=61)
        assert "Party invite" in all_text(nav) and "Trade invite" in all_text(nav)
        accept = find_button(nav, "Accept")
        await accept.callback(inter)
        assert nav.screen.id == "party"
        nav, inter = await hub("home", user_id=61)
        await find_button(nav, "Open").callback(inter)
        assert nav.screen.id == "trade"
    finally:
        party_invites.clear()
        trade._invites.clear()


async def test_rare_drops_get_their_own_pages_after_the_reward_screen_with_the_drop_rate(db):
    from cococap.services import odds
    from cococap.ui.rewards import rewards_result

    nav, inter = await hub("forage")
    again = AsyncMock()
    screen = nav.screen
    screen.result = rewards_result("TIMBER!", items={"copper_ore": 2, "iron_wedge": 1, "scroll_keen": 1}, xp=40, odds=odds.foraging(),
                                   again=again, again_label="Another tree", back_label="Back to foraging")
    await screen.refresh(inter)
    assert nav.screen.id == "result" and "Copper Ore" in all_text(nav) and "Scroll" not in all_text(nav) and "Wedge" not in all_text(nav)
    assert [b.label for b in buttons(nav) if b.label not in ("Home", "Back")] == ["Continue"]  # no Again until the last page
    await click(nav, inter, "Continue")
    spec = get_registry().scrolls.foraging
    assert "SUPER RARE" in all_text(nav) and f"1 in {spec.odds * len(spec.pool):,} trees felled" in all_text(nav)
    assert nav.screen.locked and [b.label for b in buttons(nav) if b.label not in ("Home", "Back")] == ["Continue"]
    await click(nav, inter, "Continue")
    assert "Rare drop" in all_text(nav) and "1 in" in all_text(nav)  # (the wedge's own drop rate)
    assert {b.label for b in buttons(nav)} >= {"Another tree", "Back to foraging"}
    await click(nav, inter, "Back to foraging")
    assert nav.screen.id == "forage"
