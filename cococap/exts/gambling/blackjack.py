import discord
import pydealer
import asyncio

from cococap.user import User
from discord import app_commands
from discord.ext import commands
from utils.custom_embeds import Cembed
from utils.checks import button_check
from cococap.exts.utils.error import InvalidBet
from utils.decorators import not_in_game_check, load_user, start_game
from enum import Enum


class Actions(Enum):
    HIT = "hit"
    STAND = "stand"
    FOLD = "fold"
    DEAL = "deal"


class GameStates(Enum):
    WIN = ("WIN", discord.Color.green(), ("WIN", "LOSE"), "Nice win!")
    SAFE = ("Blackjack", discord.Color.blue(), ("Your hand", "Dealer's hand"), "Hit or stand?")
    LOSE = ("LOSE", discord.Color.red(), ("LOSE", "WIN"), "Better luck next time...")
    PUSH = ("PUSH", discord.Color.light_gray(), ("PUSH", "PUSH"), "Bruh.")
    BLACKJACK = ("BLACKJACK!", discord.Color.purple(), ("BLACKJACK!", "LOSE"), "Easy money.")
    DEALER_REVEAL = ("Blackjack", discord.Color.blue(), ("STOOD", "Drawing..."), "Revealing...")

    def __new__(cls, title: str, color: discord.Color, hand_titles: tuple, footer: str):
        obj = object.__new__(cls)
        obj._value_ = title.lower()
        obj.title = title
        obj.color = color
        obj.hand_titles = hand_titles
        obj.footer = footer
        return obj

    @classmethod
    def from_state(cls, state: str):
        return cls(state)


class Player:
    def __init__(self, bet: int = None):
        self.hand = []
        self.bet = bet

    def total_hand(self) -> int:
        total = aces = 0
        for card in self.hand:
            card: pydealer.Card = card.value
            total += 11 if card == "Ace" else 10 if card in ["King", "Queen", "Jack"] else int(card)
        aces = sum(1 for card in self.hand if card.value[0] == "Ace")
        while total > 21 and aces:
            total, aces = total - 10, aces - 1
        return total

    def hand_to_string(self) -> str:
        cards = []
        for card in self.hand:
            suit_emoji = f":{card.suit.lower()}:"
            card = card.value
            if card in ["King", "Queen", "Jack", "Ace"]:
                card = card[0]
            cards.append(f"{card}{suit_emoji}")
        return "".join(cards)


class BlackJackGame(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, bet: int):
        super().__init__()
        self.user: User = interaction.extras.get("user")

        # Add the 3 game buttons to the View
        self.add_item(BlackJack.HitButton(interaction))
        self.add_item(BlackJack.StandButton(interaction))
        self.add_item(BlackJack.FoldButton(interaction))

        self.deck = pydealer.Deck()
        self.deck.shuffle()

        self.state: GameStates = GameStates.SAFE

        self.player = Player(bet=bet)
        self.dealer = Player()

    def _deal_card(self, player: Player):
        card = self.deck.deal(1)[0]
        return player.hand.append(card)

    async def deal_card_animated(self, player: Player):
        await asyncio.sleep(0.25)
        self._deal_card(player)
        await self.interaction.edit_original_response(embed=self.update_embed("hit"), view=self)
        
    def payout(self):
        if self.state

    def update_embed(self, action: str):
        """Generate an game state themed embed with player and dealer's hands."""
        self._update_state(action)
        self._update_view()
        embed = Cembed(
            title=f"{self.state.title} | User: {str(self.user)} - Bet: {self.player.bet:,}",
            color=self.state.color,
        )
        embed.add_field(
            name=self.state.hand_titles[0],
            value=f"{self.player.hand_to_string()}\nTotal: {self.player.total_hand()}",
            inline=True,
        )
        embed.add_field(
            name=self.state.hand_titles[1],
            value=f"{self.dealer.hand_to_string()}\nTotal: {self.dealer.total_hand()}",
            inline=True,
        )
        embed.set_footer(text=self.state.footer)
        return embed

    def _update_state(self, action: str) -> GameStates:
        """Evaluate the game state based on the current player and dealer hands."""
        player_total = self.player.total_hand()
        dealer_total = self.dealer.total_hand()

        if player_total > 21:
            state = GameStates.LOSE
        elif action == Actions.STAND:
            if player_total > dealer_total:
                if dealer_total < 17:
                    state = GameStates.DEALER_REVEAL
                else:
                    state = GameStates.WIN
            elif player_total == dealer_total:
                state = GameStates.PUSH
            else:
                state = GameStates.LOSE
        elif action == "hit":
            if player_total == 21 and len(self.player.hand) == 2:
                state = GameStates.BLACKJACK
            else:
                state = GameStates.SAFE if player_total <= 21 else GameStates.LOSE
        elif action == "fold":
            if dealer_total < 17:
                state = GameStates.DEALER_REVEAL
            else:
                state = GameStates.LOSE  # Default fallback
        self.state = state

    def _update_view(self):
        if self.state != GameStates.SAFE:
            for child in self.children:
                self.remove_item(child)


class HitButton(discord.ui.Button):
    def __init__(self, interaction):
        super().__init__(label="Hit", style=discord.ButtonStyle.blurple, emoji="🃏")
        self.interaction = interaction

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: BlackJackGame = self.view
        if not await button_check(self.interaction, [interaction.user.id]):
            return

        embed = view.update_embed("hit")

        if view.state == GameStates.LOSE:
            embed.add_field(name="Profit", value=f"{-view.player.bet:,} bits", inline=False)
            embed.add_field(name="Bits", value=f"{view.user.get_field('purse'):,} bits")

        await interaction.response.edit_message(embed=embed, view=view)

        await view.user.update_game(in_game=False)
        bot = User(1016054559581413457)
        await bot.load()
        # await bot.inc_purse(amount=view.player.bet)


class FoldButton(discord.ui.Button):
    def __init__(self, interaction):
        super().__init__(label="Fold", style=discord.ButtonStyle.red, emoji="🏳️")
        self.interaction = interaction

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: BlackJackGame = self.view
        if not await button_check(self.interaction, [interaction.user.id]):
            return

        embed = view.update_embed("fold")

        # Keep half of your bet
        while view.dealer.total_hand() < 17:
            await view.deal_card_animated(view.dealer)

        # Give the user half of their bet back
        await view.user.inc_purse(amount=round(view.player.bet / 2))

        embed.add_field(name="Profit", value=f"{round(-view.player.bet / 2):,} bits", inline=False)
        embed.add_field(name="Bits", value=f"{view.user.get_field('purse'):,} bits")

        await interaction.response.edit_message(embed=embed, view=self)

        bot = await User(1016054559581413457).load()
        await bot.inc_purse(amount=round(view.player.bet / 2))


class StandButton(discord.ui.Button):
    def __init__(self, interaction):
        super().__init__(label="Stand", style=discord.ButtonStyle.green, emoji="✅")
        self.interaction = interaction

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: BlackJackGame = self.view
        if not await button_check(self.interaction, [interaction.user.id]):
            return

        embed = view.update_embed("stand")

        if view.state == GameStates.LOSE:
            embed.add_field(name="Profit", value=f"{-view.player.bet:,} bits", inline=False)
            # Give the bot the lost money
            bot = await User(1016054559581413457).load()
            await bot.inc_purse(amount=view.player.bet)

        elif view.state == GameStates.PUSH:
            embed.add_field(name="Profit", value=f"0 bits", inline=False)
            await view.user.inc_purse(amount=view.player.bet)

        elif view.state == GameStates.WIN:
            embed.add_field(name="Profit", value=f"{view.player.bet * 2:,} bits", inline=False)
            await view.user.inc_purse(amount=view.player.bet * 2)

        embed.add_field(name="Bits", value=f"{view.user.get_field('purse'):,} bits")

        while view.dealer.total_hand() < 17:
            await view.deal_card_animated(view.dealer)
            if view.d_hand_total > 21:
                await view.user.inc_purse(amount=view.player.bet * 2)
                await view.user.update_game(in_game=False, interaction=interaction)
                dealer_bust_embed = discord.Embed(
                    title=f"Blackjack | User: {interaction.user.name} - Bet: {view.player.bet:,}",
                    colour=discord.Color.green(),
                )

                await interaction.response.edit_message(embed=dealer_bust_embed, view=None)
                return
        await compare_hands()


class BlackJack(commands.Cog, name="Blackjack"):
    """Basic Blackjack. HIT, STAND, FOLD, or DOUBLE DOWN!"""

    @app_commands.command(name="blackjack")
    @app_commands.describe(bet="amount of bits you want to bet | use max for all bits in purse")
    @load_user  # Loads the user
    @start_game  # Starts the user's game and finishes it when command is over
    @not_in_game_check()  # Ensures that the user is not already playing a game
    async def blackjack(self, interaction: discord.Interaction, bet: str):
        """Classic blackjack. Get as close to 21 as possible, but not over."""
        user: User = interaction.extras.get("user")
        purse = user.get_field("purse")

        # Bet validation
        if bet.isalpha():
            if bet != "max":
                raise InvalidBet("Only 'max' is a valid non-integer.")
            bet = purse
        elif int(bet) <= 0:
            raise InvalidBet("I sense something fishy...")
        elif int(bet) > purse:
            raise InvalidBet(f"You only have {purse:,} bits.")

        bet = int(bet)

        # Collect their bet and set their status to in_game
        await user.inc_purse(-bet)

        game = BlackJackGame(interaction=interaction, bet=bet)
        await interaction.response.send_message(embed=game.update_embed(), view=game)

        # Deal out starting hands for dealer and player
        await game.deal_card_animated(game.player)
        await game.deal_card_animated(game.player)
        await game.deal_card_animated(game.dealer)


async def setup(bot):
    await bot.add_cog(BlackJack(bot))
