import discord
import pydealer
import asyncio

from enum import Enum
from discord.ext import commands
from discord import Interaction, app_commands
from cococap.constants import BOT_ID
from cococap.user import User
from utils.utils import validate_bits
from utils.custom_embeds import CustomEmbed


# Enum representing all possible game states for blackjack
class GameStates(Enum):
    """
    Different game states for blackjack.

    Attributes:
        WIN: Player has beat the dealer.
        READY: Player is ready to make a move.
        LOSE: Player has either busted or has a lesser hand.
        PUSH: Player has same hand total as dealer.
        BLACKJACK: Player has a natural 21.
        DEALER_REVEAL: Game is over and dealer has to reveal his cards.
    """

    WIN = ("WIN", discord.Color.green(), ("WIN", "LOSE"), "Nice win!")
    READY = ("Blackjack", discord.Color.blue(), ("Your hand", "Dealer's hand"), "Hit or stand?")
    LOSE = ("LOSE", discord.Color.red(), ("LOSE", "WIN"), "Better luck next time...")
    PUSH = ("PUSH", discord.Color.light_gray(), ("PUSH", "PUSH"), "Bruh.")
    BLACKJACK = ("BLACKJACK!", discord.Color.purple(), ("BLACKJACK!", "LOSE"), "Easy money.")
    DEALER_REVEAL = ("Blackjack", discord.Color.blue(), ("STOOD", "Drawing..."), "Revealing...")

    def __new__(cls, title, color, hand_titles, footer):
        obj = object.__new__(cls)
        obj._value_ = title.lower()
        obj.title = title
        obj.color = color
        obj.hand_titles = hand_titles
        obj.footer = footer
        return obj


# Enum for all possible player actions
class Actions(Enum):
    DEAL = "deal"
    HIT = "hit"
    STAND = "stand"
    FOLD = "fold"


def act(p_total: int, d_total: int, p_hand: list, action: Actions = None) -> GameStates:
    # Determine the next game state based on player/dealer totals and action
    if action == Actions.DEAL:
        # Check for natural blackjack
        if p_total == 21 and len(p_hand) == 2:
            return GameStates.BLACKJACK
        return GameStates.READY
    elif action == Actions.HIT:
        # Player busts if over 21
        if p_total > 21:
            return GameStates.LOSE
        return GameStates.READY
    elif action == Actions.STAND:
        # Dealer must draw to 17
        if d_total < 17:
            return GameStates.DEALER_REVEAL
        if p_total > 21:
            return GameStates.LOSE
        if d_total > 21:
            return GameStates.WIN
        if p_total == d_total:
            return GameStates.PUSH
        if p_total > d_total:
            return GameStates.WIN
        return GameStates.LOSE
    elif action == Actions.FOLD:
        # Folding before dealer stands
        if d_total < 17:
            return GameStates.DEALER_REVEAL
        return GameStates.LOSE


# Represents a blackjack player (or dealer)
class Player:
    def __init__(self, bet: int = None):
        self.hand = []  # List of pydealer.Card objects
        self.bet = bet
        self.winnings: int = 0

    def total_hand(self) -> int:
        # Calculate the total value of the hand, handling aces as 1 or 11
        total = 0
        aces = 0
        for card in self.hand:
            card_value = card.value
            if card_value == "Ace":
                total += 11
                aces += 1
            elif card_value in ["King", "Queen", "Jack"]:
                total += 10
            else:
                total += int(card_value)
        # Adjust for aces if bust
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def __str__(self) -> str:
        # Return a string representation of the hand for display
        cards = []
        for card in self.hand:
            suit_emoji = f":{card.suit.lower()}:"
            value = card.value
            if value in ["King", "Queen", "Jack", "Ace"]:
                value = value[0]
            cards.append(f"{value}{suit_emoji}")
        return "".join(cards)


# Main blackjack game view, handles UI and game state
class BlackjackGame(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=120)
        self.user: User = interaction.extras.get("user")
        self.interaction = interaction
        self.deck = pydealer.Deck()
        self.deck.shuffle()
        self.state: GameStates = GameStates.READY
        self.player = Player(bet=interaction.extras.get("bet"))
        self.dealer = Player()
        self.settled = False  # True once the bet has been paid out / forfeited (exactly once)
        self.busy = False  # True while a button press is being processed
        # Add UI buttons
        self.add_item(HitButton())
        self.add_item(StandButton())
        self.add_item(FoldButton())

    async def interaction_check(self, interaction):
        # Only allow the original user to interact with the game
        return interaction.user == self.interaction.user

    async def begin_action(self, interaction: discord.Interaction) -> bool:
        """Claim the right to process a button press. False if the game is over or mid-action."""
        if self.settled or self.busy:
            await interaction.response.defer()
            return False
        self.busy = True
        return True

    async def settle_to_house(self):
        """The player lost their bet: it goes to the house account. Runs at most once."""
        if self.settled:
            return
        self.settled = True
        house = await User.get(BOT_ID)
        await house.add_bits(self.player.bet)

    async def on_timeout(self):
        # An abandoned hand forfeits the bet to the house (it was already taken from the player).
        await self.settle_to_house()
        self.clear_items()

    async def deal_card(self, player: Player):
        # Deal a card to the given player and update the embed
        await asyncio.sleep(0.25)
        card = self.deck.deal(1)[0]
        player.hand.append(card)
        await self.interaction.edit_original_response(
            embed=await self.update(Actions.DEAL), view=self
        )

    async def update(self, action: Actions):
        # Update the game state and return the appropriate embed
        p_total = self.player.total_hand()
        d_total = self.dealer.total_hand()
        self.state = act(p_total, d_total, self.player.hand, action=action)
        if self.state != GameStates.READY:
            self.clear_items()
        embed = CustomEmbed(
            title=f"{self.state.title} | Bet: {self.player.bet:,}",
            color=self.state.color,
            interaction=self.interaction,
            activity="blackjack",
        )
        embed.add_field(
            name=self.state.hand_titles[0],
            value=f"{str(self.player)}\nTotal: {p_total}",
            inline=True,
        )
        embed.add_field(
            name=self.state.hand_titles[1],
            value=f"{str(self.dealer)}\nTotal: {d_total}",
            inline=True,
        )
        embed.set_footer(text=self.state.footer)
        # Handle blackjack payout
        if self.state == GameStates.BLACKJACK:
            profit = self.player.bet * 2
            if not self.settled:  # update() runs on every deal; only pay the natural once
                self.settled = True
                await self.user.add_bits(amount=profit)
                await self.user.inc_stat("blackjacks")
            embed.add_field(name="Profit", value=f"{profit:,} bits", inline=False)
            embed.add_field(name="Bits", value=f"{await self.user.get_bits():,} bits")
        return embed


# Button for hitting (drawing a card)
class HitButton(discord.ui.Button):
    def __init__(self):
        label = "Hit"
        style = discord.ButtonStyle.blurple
        emoji = "🃏"
        super().__init__(label=label, style=style, emoji=emoji)

    async def callback(self, interaction: discord.Interaction):
        view: BlackjackGame = self.view
        if not await view.begin_action(interaction):
            return
        try:
            await view.deal_card(view.player)
            embed = await view.update(Actions.HIT)
            await view.user.inc_stat("blackjack_hits")
            # If player busts, end the game
            if view.state == GameStates.LOSE:
                profit = -view.player.bet
                embed.add_field(name="Profit", value=f"{profit:,} bits", inline=False)
                embed.add_field(name="Bits", value=f"{await view.user.get_bits():,} bits")
                view.dealer.winnings += view.player.bet
                await view.settle_to_house()
                view.clear_items()
            await interaction.response.edit_message(
                embed=embed, view=None if view.state == GameStates.LOSE else view
            )
        finally:
            view.busy = False


# Button for folding (giving up half the bet)
class FoldButton(discord.ui.Button):
    def __init__(self):
        label = "Fold"
        style = discord.ButtonStyle.red
        emoji = "🏳️"
        super().__init__(label=label, style=style, emoji=emoji)

    async def callback(self, interaction: discord.Interaction):
        view: BlackjackGame = self.view
        if not await view.begin_action(interaction):
            return
        embed = await view.update(Actions.FOLD)
        await view.user.inc_stat("blackjack_folds")
        # Dealer draws if needed
        while view.state == GameStates.DEALER_REVEAL:
            await view.deal_card(view.dealer)
            embed = await view.update(Actions.FOLD)
        # Refund half the bet; the other half goes to the house.
        view.settled = True
        refund = round(view.player.bet / 2)
        await view.user.add_bits(amount=refund)
        house = await User.get(BOT_ID)
        await house.add_bits(view.player.bet - refund)
        embed.add_field(name="Profit", value=f"{-(view.player.bet - refund):,} bits", inline=False)
        embed.add_field(name="Bits", value=f"{await view.user.get_bits():,} bits")
        view.dealer.winnings += view.player.bet - refund
        view.clear_items()
        await interaction.response.edit_message(embed=embed, view=None)


# Button for standing (ending turn, dealer plays out hand)
class StandButton(discord.ui.Button):
    def __init__(self):
        label = "Stand"
        style = discord.ButtonStyle.green
        emoji = "✅"
        super().__init__(label=label, style=style, emoji=emoji)

    async def callback(self, interaction: discord.Interaction):
        view: BlackjackGame = self.view
        if not await view.begin_action(interaction):
            return
        embed = await view.update(Actions.STAND)
        await view.user.inc_stat("blackjack_stands")
        # Dealer draws if needed
        while view.state == GameStates.DEALER_REVEAL:
            await view.deal_card(view.dealer)
            embed = await view.update(Actions.STAND)
        # Handle end-of-game payouts
        if view.state == GameStates.LOSE:
            profit = -view.player.bet
            view.dealer.winnings += view.player.bet
            await view.settle_to_house()
        elif view.state == GameStates.PUSH:
            profit = 0
            view.settled = True
            await view.user.add_bits(amount=view.player.bet)
        else:  # WIN
            profit = view.player.bet * 2
            view.settled = True
            await view.user.add_bits(amount=profit)
        embed.add_field(name="Profit", value=f"{profit:,} bits", inline=False)
        embed.add_field(name="Bits", value=f"{await view.user.get_bits():,} bits")
        view.clear_items()
        await asyncio.sleep(0.5)
        await interaction.response.edit_message(embed=embed, view=None)


class Blackjack(commands.Cog, name="Blackjack"):
    """Blackjack! Remeber, the house always wins..."""

    def __init__(self):
        super().__init__()

    async def interaction_check(self, interaction: Interaction):
        # Load user data before each command
        user = await User.get(interaction.user.id)
        interaction.extras.update(user=user)

        # Validate the user's bet so they can't bet more than they have
        args = {opt["name"]: opt["value"] for opt in interaction.data.get("options", [])}
        bet = await validate_bits(user=user, amount=args["bet"])

        # Collect their bet immediately
        await user.remove_bits(bet)
        interaction.extras.update(bet=bet)

        await user.inc_stat("blackjack_games")

        return super().interaction_check(interaction)

    @app_commands.command(name="blackjack")
    @app_commands.describe(bet="the amount of bits you want to bet")
    async def _blackjack(self, interaction: Interaction, bet: str):
        """Classic blackjack. Get as close to 21 as possible, but not over."""
        view = BlackjackGame(interaction=interaction)
        try:
            await interaction.response.send_message(
                embed=await view.update(Actions.DEAL), view=view
            )

            # Deal out starting hands for dealer and player
            await view.deal_card(view.player)
            await view.deal_card(view.player)
            await view.deal_card(view.dealer)

            for item in view.children:
                item.disabled = False

            await interaction.edit_original_response(view=view)
        except Exception:
            # The bet was taken in interaction_check; don't eat it if the game never started.
            if not view.settled:
                view.settled = True
                await view.user.add_bits(view.player.bet)
            raise


async def setup(bot):
    await bot.add_cog(Blackjack())
