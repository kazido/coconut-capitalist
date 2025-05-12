import discord
import pydealer
import asyncio


from enum import Enum
from cococap.user import User
from utils.custom_embeds import CustomEmbed


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


class Actions(Enum):
    DEAL = "deal"
    HIT = "hit"
    STAND = "stand"
    FOLD = "fold"


def act(p_total: int, d_total: int, p_hand: list, action: Actions = None) -> GameStates:
    if action == Actions.DEAL:
        if p_total == 21 and len(p_hand) == 2:
            return GameStates.BLACKJACK
        return GameStates.READY
    elif action == Actions.HIT:
        if p_total > 21:
            return GameStates.LOSE
        return GameStates.READY
    elif action == Actions.STAND:
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
        if d_total < 17:
            return GameStates.DEALER_REVEAL
        return GameStates.LOSE


class Player:
    def __init__(self, bet: int = None):
        self.hand = []
        self.bet = bet
        self.winnings: int = 0

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

    def __str__(self) -> str:
        cards = []
        for card in self.hand:
            suit_emoji = f":{card.suit.lower()}:"
            value = card.value
            if value in ["King", "Queen", "Jack", "Ace"]:
                value = value[0]
            cards.append(f"{value}{suit_emoji}")
        return "".join(cards)


class Blackjack(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, bet: int):
        super().__init__(timeout=120)
        self.user: User = interaction.extras.get("user")
        self.interaction = interaction

        self.add_item(HitButton())
        self.add_item(StandButton())
        self.add_item(FoldButton())

        self.deck = pydealer.Deck()
        self.deck.shuffle()

        self.state: GameStates = GameStates.READY

        self.player = Player(bet=bet)
        self.dealer = Player()

    def interaction_check(self, interaction):
        # Will verify that whenever a button is pressed, it can only be done by the command caller.
        if interaction.user != self.interaction.user:
            print("someone else try to clicky button in blackjack!!!")
            return False
        return super().interaction_check(interaction)

    async def on_timeout(self):
        bot = await User(1016054559581413457).load()
        await bot.inc_purse(self.dealer.winnings)
        self.clear_items()

    async def deal_card(self, player: Player):
        """Waits a short delay before dealing a card to player and updating embed."""
        await asyncio.sleep(0.25)
        card = self.deck.deal(1)[0]  # Pull a card from the virtual deck
        player.hand.append(card)  # Add it to passed player's hand
        await self.interaction.edit_original_response(
            embed=await self.update(Actions.DEAL), view=self
        )

    async def update(self, action: Actions):
        """Generate an game state themed embed with player and dealer's hands."""
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

        if self.state == GameStates.BLACKJACK:
            profit = self.player.bet * 2
            await self.user.inc_purse(amount=self.player.bet * 2)
            embed.add_field(name="Profit", value=f"{profit:,} bits", inline=False)
            embed.add_field(name="Bits", value=f"{self.user.get_field('purse'):,} bits")

        return embed


class HitButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Hit", style=discord.ButtonStyle.blurple, emoji="🃏", disabled=True)

    async def callback(self, interaction: discord.Interaction):
        view: Blackjack = self.view

        await view.deal_card(view.player)
        embed = await view.update(Actions.HIT)

        if view.state == GameStates.LOSE:
            profit = -view.player.bet
            embed.add_field(name="Profit", value=f"{profit:,} bits", inline=False)
            embed.add_field(name="Bits", value=f"{view.user.get_field('purse'):,} bits")
            # Pay the bot
            view.dealer.winnings += view.player.bet

        await interaction.response.edit_message(embed=embed, view=view)


class FoldButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Fold", style=discord.ButtonStyle.red, emoji="🏳️", disabled=True)

    async def callback(self, interaction: discord.Interaction):
        view: Blackjack = self.view

        embed = await view.update(Actions.FOLD)

        # Dealer draws if needed
        while view.state == GameStates.DEALER_REVEAL:
            await view.deal_card(view.dealer)
            embed = await view.update(Actions.FOLD)

        # Give the user half of their bet back
        await view.user.inc_purse(amount=round(view.player.bet / 2))

        embed.add_field(name="Profit", value=f"{round(-view.player.bet / 2):,} bits", inline=False)
        embed.add_field(name="Bits", value=f"{view.user.get_field('purse'):,} bits")

        await interaction.response.edit_message(embed=embed, view=None)

        view.dealer.winnings += round(view.player.bet / 2)


class StandButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Stand", style=discord.ButtonStyle.green, emoji="✅", disabled=True)

    async def callback(self, interaction: discord.Interaction):
        view: Blackjack = self.view

        # Updates the game state
        embed = await view.update(Actions.STAND)

        # Dealer draws if needed
        while view.state == GameStates.DEALER_REVEAL:
            await view.deal_card(view.dealer)
            embed = await view.update(Actions.STAND)

        # Now resolve the final state
        if view.state == GameStates.LOSE:
            profit = -view.player.bet
            # Give the bot the lost money
            view.dealer.winnings += view.player.bet

        elif view.state == GameStates.PUSH:
            profit = 0
            await view.user.inc_purse(amount=view.player.bet)  # Pay the user back their bet

        elif view.state == GameStates.WIN:
            profit = view.player.bet * 2
            await view.user.inc_purse(amount=view.player.bet * 2)

        embed.add_field(name="Profit", value=f"{profit:,} bits", inline=False)
        embed.add_field(name="Bits", value=f"{view.user.get_field('purse'):,} bits")
        await asyncio.sleep(0.5)
        await interaction.response.edit_message(embed=embed, view=None)
