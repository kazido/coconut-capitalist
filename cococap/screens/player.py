"""The Player page: your profile, your stats and the leaderboards, as tabs of one page."""

from cococap import emojis
from cococap.screens.profile import ProfilePane
from cococap.screens.stats import StatsPane
from cococap.screens.top import TopPane
from cococap.ui.tabs import TabsScreen


class PlayerScreen(TabsScreen):
    id = "player"
    label = "Player"
    emoji = emojis.Lazy("ui_people", "👤")
    description = "Your profile, your stats and the leaderboards"
    panes = {"profile": ProfilePane, "stats": StatsPane, "top": TopPane}
