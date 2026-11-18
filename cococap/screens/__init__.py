"""The hub's screens, in menu order, and the one function every command uses to open them."""

from discord import Interaction

from cococap.ui import Navigator, Screen
from cococap.user import User

from .bestiary import BestiaryScreen
from .blackjack import BlackjackScreen
from .casino import CasinoScreen
from .checkin import CheckInScreen
from .craft import CraftScreen
from .highlow import HighLowScreen
from .farm import FarmScreen
from .fight import FightScreen
from .flashcard import FlashcardScreen
from .fish import FishBookScreen, FishCommunityScreen, FishPotsScreen, FishNotesScreen, FishQuestsScreen, FishRecordsScreen, FishScreen
from .enchant import EnchantScreen
from .forage import ForageScreen, GroveScreen, PartyGroveScreen, TreeScreen
from .releaf import ReleafScreen
from .sequence import SequenceScreen
from .trivia import TriviaScreen
from .unscramble import UnscrambleScreen
from .home import HomeScreen, MoreScreen
from .inventory import InventoryScreen
from .mine import MineScreen
from .market import MarketScreen
from .mastery import MasteryScreen
from .minigames import MinigamesScreen
from .mining import MiningScreen
from .party import PartyScreen
from .pets import OrbScreen, PetScreen
from .profile import ProfileScreen
from .reactor import ReactorScreen
from .radar import RadarScreen
from .rank import RankScreen
from .settings import SettingsScreen
from .sellall import SellAllScreen
from .ship import ShipScreen
from .shipments import ShipmentsScreen
from .shop import ShopScreen
from .skills import SkillsScreen
from .stats import StatsScreen
from .tools import ToolsScreen
from .top import TopScreen
from .trade import TradeScreen
from .upgrade import UpgradeScreen
from .wiki import WikiScreen
from .wyrmhole import WyrmholeScreen

SCREENS: dict[str, type[Screen]] = {
    screen.id: screen
    for screen in (
        HomeScreen,
        MoreScreen,
        PartyScreen,
        PetScreen,
        OrbScreen,
        ProfileScreen,
        BestiaryScreen,
        ToolsScreen,
        SellAllScreen,
        ShipmentsScreen,
        ShipScreen,
        TradeScreen,
        MasteryScreen,
        CheckInScreen,
        SkillsScreen,
        FarmScreen,
        FightScreen,
        ForageScreen,
        ReleafScreen,
        FishScreen,
        FishQuestsScreen,
        FishBookScreen,
        FishCommunityScreen,
        FishRecordsScreen,
        FishNotesScreen,
        FishPotsScreen,
        TreeScreen,
        GroveScreen,
        PartyGroveScreen,
        MarketScreen,
        MiningScreen,
        ReactorScreen,
        RadarScreen,
        MineScreen,
        WyrmholeScreen,
        MinigamesScreen,
        CasinoScreen,
        FlashcardScreen,
        UnscrambleScreen,
        SequenceScreen,
        TriviaScreen,
        HighLowScreen,
        BlackjackScreen,
        InventoryScreen,
        CraftScreen,
        UpgradeScreen,
        WikiScreen,
        EnchantScreen,
        ShopScreen,
        RankScreen,
        TopScreen,
        StatsScreen,
        SettingsScreen,
    )
}


async def open_screen(interaction: Interaction, screen_id: str = "home", **state) -> Navigator:
    """Open the hub as a new message on `screen_id`. Every slash-command shortcut calls this."""
    user = await User.get(interaction.user.id)
    await user.set_name(interaction.user.display_name)
    nav = Navigator(interaction.user, user, SCREENS)
    await nav.open(interaction, screen_id, **state)
    return nav
