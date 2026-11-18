"""The Games page: the casino and the brain games, as tabs of one page. The dropdown is the menu."""

from cococap import emojis
from cococap.screens.blackjack import BlackjackPane
from cococap.screens.flashcard import FlashcardPane
from cococap.screens.highlow import HighLowPane
from cococap.screens.sequence import SequencePane
from cococap.screens.trivia import TriviaPane
from cococap.screens.unscramble import UnscramblePane
from cococap.ui.tabs import TabsScreen


class GamesScreen(TabsScreen):
    id = "games"
    label = "Games"
    emoji = emojis.icon("dice", "🎲")
    description = "The casino and other games for fun"
    tab_placeholder = "Choose a game"
    panes = {
        "highlow": HighLowPane,
        "blackjack": BlackjackPane,
        "flashcard": FlashcardPane,
        "unscramble": UnscramblePane,
        "sequence": SequencePane,
        "trivia": TriviaPane,
    }
