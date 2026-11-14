"""The hub's screens, in menu order, and the one function every command uses to open them."""

from discord import Interaction

from cococap.ui import Navigator, Screen
from cococap.user import User

from .blackjack import BlackjackScreen
from .casino import CasinoScreen
from .checkin import CheckInScreen
from .highlow import HighLowScreen
from .farm import FarmScreen
from .flashcard import FlashcardScreen
from .fish import FishBookScreen, FishCommunityScreen, FishPotsScreen, FishQuestsScreen, FishRecordsScreen, FishScreen
from .enchant import EnchantScreen
from .forage import ForageScreen, GroveScreen, TreeScreen
from .sequence import SequenceScreen
from .trivia import TriviaScreen
from .unscramble import UnscrambleScreen
from .home import HomeScreen, MoreScreen
from .inventory import InventoryScreen
from .mine import MineScreen
from .market import MarketScreen
from .minigames import MinigamesScreen
from .mining import MiningScreen
from .party import PartyScreen
from .pets import PetScreen
from .profile import ProfileScreen
from .reactor import ReactorScreen
from .rank import RankScreen
from .settings import SettingsScreen
from .shop import ShopScreen
from .skills import SkillsScreen
from .stats import StatsScreen
from .top import TopScreen
from .upgrade import UpgradeScreen
from .wyrmhole import WyrmholeScreen

SCREENS: dict[str, type[Screen]] = {
    screen.id: screen
    for screen in (
        HomeScreen,
        MoreScreen,
        PartyScreen,
        PetScreen,
        ProfileScreen,
        CheckInScreen,
        SkillsScreen,
        FarmScreen,
        ForageScreen,
        FishScreen,
        FishQuestsScreen,
        FishBookScreen,
        FishCommunityScreen,
        FishRecordsScreen,
        FishPotsScreen,
        TreeScreen,
        GroveScreen,
        MarketScreen,
        MiningScreen,
        ReactorScreen,
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
        UpgradeScreen,
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
