import discord
import pydealer
import asyncio
import functools

from enum import Enum
from cococap.user import User
from utils.custom_embeds import Cembed


class GameStates(Enum):
    WIN = ("WIN", discord.Color.green(), ("WIN", "LOSE"), "Nice win!")
    READY = ("Blackjack", discord.Color.blue(), ("Your hand", "Dealer's hand"), "Hit or stand?")
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


def _deal(**kwargs) -> GameStates:
    if kwargs["player_total"] == 21 and len(kwargs["player_hand"]) == 2:
        return GameStates.BLACKJACK
    return GameStates.READY


def _hit(**kwargs) -> GameStates:
    if kwargs["player_total"] > 21:
        return GameStates.LOSE
    return GameStates.READY


def _stand(**kwargs) -> GameStates:
    # If dealer needs to draw, signal DEALER_REVEAL
    if kwargs["dealer_total"] < 17:
        return GameStates.DEALER_REVEAL
    if kwargs["player_total"] > 21:
        return GameStates.LOSE
    if kwargs["dealer_total"] > 21:
        return GameStates.WIN
    if kwargs["player_total"] == kwargs["dealer_total"]:
        return GameStates.PUSH
    if kwargs["player_total"] > kwargs["dealer_total"]:
        return GameStates.WIN
    return GameStates.LOSE


def _fold(**kwargs) -> GameStates:
    # If dealer needs to draw, signal DEALER_REVEAL
    if kwargs["dealer_total"] < 17:
        return GameStates.DEALER_REVEAL
    return GameStates.LOSE


class Actions(Enum):
    HIT = functools.partial(_hit)
    STAND = functools.partial(_stand)
    FOLD = functools.partial(_fold)
    DEAL = functools.partial(_deal)


class Player:
    def __init__(self, bet: int = None):
        self.hand = []
        self.bet = bet

    def total_hand(self) -> int:
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

        while total > 21 and aces:
            total -= 10
            aces -= 1

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


class Blackjack(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, bet: int):
        self.user: User = interaction.extras.get("user")
        self.interaction = interaction

        self.add_item(HitButton(interaction))
        self.add_item(StandButton(interaction))
        self.add_item(FoldButton(interaction))

        self.deck = pydealer.Deck()
        self.deck.shuffle()

        self.state: GameStates = GameStates.READY

        self.player = Player(bet=bet)
        self.dealer = Player()
        super().__init__()

    def interaction_check(self, interaction):
        # Will verify that whenever a button is pressed, it can only be done by the command caller.
        if interaction.user != self.interaction.user:
            print("someone else try to clicky button!!!")
            return False
        return super().interaction_check(interaction)

    async def on_timeout(self):
        await self.end_game()

    async def end_game(self):
        if self.user:
            await self.user.in_game(in_game=False)
        try:
            await self.interaction.edit_original_response(view=None)
        except Exception:
            pass

    def _deal_card(self, player: Player):
        """Pulls a card from the deck and adds it to player hand.
        Shouldn't be called as a method other than in deal_card_animated"""
        card = self.deck.deal(1)[0]
        return player.hand.append(card)

    async def deal_card_animated(self, player: Player):
        """Waits a short delay before dealing a card to player and updating embed."""
        await asyncio.sleep(0.25)
        self._deal_card(player)
        await self.interaction.edit_original_response(embed=self.update(Actions.DEAL), view=self)

    def update(self, action: "Actions"):
        """Generate an game state themed embed with player and dealer's hands."""
        self.state = self._update_state(action)

        if self.state != GameStates.READY:
            self.clear_items()

        embed = Cembed(
            title=f"{self.state.title} | User: {str(self.user)} - Bet: {self.player.bet:,}",
            color=self.state.color,
            interaction=self.interaction,
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

    def _update_state(self, action: "Actions") -> GameStates:
        player_total = self.player.total_hand()
        dealer_total = self.dealer.total_hand()

        return action.value(
            player_total=player_total, dealer_total=dealer_total, player_hand=self.player.hand
        )


class HitButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Hit", style=discord.ButtonStyle.blurple, emoji="🃏", disabled=True)

    async def callback(self, interaction: discord.Interaction):
        view: Blackjack = self.view

        await view.deal_card_animated(view.player)
        embed = view.update(Actions.HIT)

        if view.state == GameStates.LOSE:
            embed.add_field(name="Profit", value=f"{-view.player.bet:,} bits", inline=False)
            embed.add_field(name="Bits", value=f"{view.user.get_field('purse'):,} bits")
            # Pay the bot
            bot = await User(1016054559581413457).load()
            await bot.inc_purse(amount=view.player.bet)

        await interaction.response.edit_message(embed=embed, view=view)


class FoldButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Fold", style=discord.ButtonStyle.red, emoji="🏳️", disabled=True)

    async def callback(self, interaction: discord.Interaction):
        view: Blackjack = self.view

        embed = view.update(Actions.FOLD)

        # Dealer draws if needed
        while view.state == GameStates.DEALER_REVEAL:
            await view.deal_card_animated(view.dealer)
            embed = view.update(Actions.FOLD)

        # Give the user half of their bet back
        await view.user.inc_purse(amount=round(view.player.bet / 2))

        embed.add_field(name="Profit", value=f"{round(-view.player.bet / 2):,} bits", inline=False)
        embed.add_field(name="Bits", value=f"{view.user.get_field('purse'):,} bits")

        await interaction.response.edit_message(embed=embed, view=self)

        bot = await User(1016054559581413457).load()
        await bot.inc_purse(amount=round(view.player.bet / 2))


class StandButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Stand", style=discord.ButtonStyle.green, emoji="✅", disabled=True)

    async def callback(self, interaction: discord.Interaction):
        view: Blackjack = self.view

        # Updates the game state
        embed = view.update(Actions.STAND)

        # Dealer draws if needed
        while view.state == GameStates.DEALER_REVEAL:
            await view.deal_card_animated(view.dealer)
            embed = view.update(Actions.STAND)

        # Now resolve the final state
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
        await asyncio.sleep(0.5)
        view.stop()
        await interaction.response.edit_message(embed=embed, view=None)
