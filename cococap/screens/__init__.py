"""The hub's screens, in menu order, and the one function every command uses to open them."""

import random

from discord import Interaction

from cococap.services import legacy_tools
from cococap.ui import Navigator, Screen
from cococap.user import User

from .bestiary import BestiaryScreen
from .blackjack import BlackjackPane
from .checkin import CheckInScreen
from .craft import CraftScreen
from .farm import FarmScreen
from .combat import CombatScreen
from .fight import FightScreen
from .fish import FishLogScreen, FishPotsScreen, FishScreen
from .forage import ForageScreen, TreesScreen
from .releaf import ReleafScreen
from .home import HomeScreen, MoreScreen
from .inventory import InventoryScreen
from .mine import MineScreen
from .market import MarketScreen
from .mastery import MasteryScreen
from .games_page import GamesScreen
from .mining import MiningScreen
from .news import NewsScreen
from .party import PartyScreen
from .pets import PetsScreen
from .player import PlayerScreen
from .reactor import ReactorScreen
from .radar import RadarScreen
from .rank import RankScreen
from .settings import SettingsScreen
from .ship import ShipScreen
from .shipments import ShipmentsScreen
from .shop import ShopScreen
from .skills import SkillsScreen
from .tools import ToolsScreen
from .trade import TradeScreen
from .wiki import WikiScreen

SCREENS: dict[str, type[Screen]] = {
    screen.id: screen
    for screen in (
        HomeScreen,
        MoreScreen,
        PartyScreen,
        PetsScreen,
        PlayerScreen,
        BestiaryScreen,
        ToolsScreen,
        ShipmentsScreen,
        ShipScreen,
        TradeScreen,
        MasteryScreen,
        CheckInScreen,
        SkillsScreen,
        FarmScreen,
        CombatScreen,
        FightScreen,
        ForageScreen,
        ReleafScreen,
        FishScreen,
        FishLogScreen,
        FishPotsScreen,
        TreesScreen,
        MarketScreen,
        MiningScreen,
        ReactorScreen,
        RadarScreen,
        MineScreen,
        GamesScreen,
        InventoryScreen,
        CraftScreen,
        WikiScreen,
        ShopScreen,
        RankScreen,
        SettingsScreen,
        NewsScreen,
    )
}


async def open_screen(interaction: Interaction, screen_id: str = "home", **state) -> Navigator:
    """Open the hub as a new message on `screen_id`. Every slash-command shortcut calls this."""
    user = await User.get(interaction.user.id)
    await user.set_name(interaction.user.display_name)
    await legacy_tools.reset_player(user, random.Random())  # one-time tools reset (runs once per player)
    nav = Navigator(interaction.user, user, SCREENS)
    await nav.open(interaction, screen_id, **state)
    from cococap.ui import notices  # local import: like levelup, it needs the finished ui package

    await notices.check(interaction, user)  # unseen notices pop up once, after the menu is sent
    return nav
