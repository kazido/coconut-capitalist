import discord
import pydealer
import asyncio

from cococap.user import User
from discord import app_commands
from discord.ext import commands
from utils.messages import Cembed, button_check
from utils.utils import validate_bet
from utils.decorators import not_in_game_check
from enum import Enum


class GameStates(Enum):
    WIN = ("WIN", discord.Color.green(), "Nice win!")
    SAFE = ("Blackjack", discord.Color.blue(), "Will you hit or stand?")
    LOSE = ("LOSE", discord.Color.red(), "Better luck next time...")
    PUSH = ("PUSH", discord.Color.light_gray(), "Bruh.")
    BLACKJACK = ("BLACKJACK", discord.Color.purple(), "Easy money.")

    def __new__(cls, title: str, color: discord.Color, footer: str):
        obj = object.__new__(cls)
        obj._value_ = title.lower()
        obj.title = title
        obj.color = color
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
    def __init__(self, interaction: discord.Interaction, user: User, bet: int):
        super().__init__()
        self.user: User = user

        # Add the 3 game buttons to the View
        self.add_item(BlackJack.HitButton(interaction))
        self.add_item(BlackJack.StandButton(interaction))
        self.add_item(BlackJack.FoldButton(interaction))

        self.deck = pydealer.Deck()
        self.deck.shuffle()

        self.player = Player(bet=bet)
        self.dealer = Player()

    def deal_card(self, player: Player):
        card = self.deck.deal(1)[0]
        player.hand.append(card)

    def embed(self):
        """Generate an game state themed embed with player and dealer's hands."""
        state: GameStates = GameStates.from_state(self.hit_check())
        embed = Cembed(
            title=f"{state.title} | User: {str(self.user)} - Bet: {self.player.bet}",
            color=state.color,
        )
        embed.add_field(
            name="Your hand",
            value=f"{self.player.hand_to_string()}\nTotal: {self.player.total_hand()}",
            inline=True,
        )
        embed.add_field(
            name="Dealer's hand",
            value=f"{self.dealer.hand_to_string()}\nTotal: {self.dealer.total_hand()}",
            inline=True,
        )
        return embed.set_footer(text=state.footer)

    def _check_game_state(self, action: str) -> GameStates:
        """Evaluate the game state based on the current player and dealer hands."""
        player_total = self.player.total_hand()
        dealer_total = self.dealer.total_hand()

        if player_total > 21:
            return GameStates.LOSE
        if action == "stand":
            if dealer_total > 21 or player_total > dealer_total:
                return GameStates.WIN
            elif player_total == dealer_total:
                return GameStates.PUSH
            else:
                return GameStates.LOSE
        if action == "hit":
            if player_total == 21 and len(self.player.hand) == 2:
                return GameStates.BLACKJACK
            return GameStates.SAFE if player_total <= 21 else GameStates.LOSE
        return GameStates.LOSE  # Default fallback

    # Update existing methods to use check_game_state
    def hit_check(self):
        """Return the game state for a hit action."""
        return self._check_game_state("hit")

    def stand_check(self):
        """Return the game state for a stand action."""
        return self._check_game_state("stand")

    def fold_check(self):
        return GameStates.LOSE


class BlackJack(commands.Cog, name="Blackjack"):
    """Basic Blackjack. HIT, STAND, FOLD, or DOUBLE DOWN!"""

    def __init__(self, bot):
        self.bot = bot

    @not_in_game_check()
    @app_commands.command(name="blackjack")
    @app_commands.describe(bet="amount of bits you want to bet | use max for all bits in purse")
    async def blackjack(self, interaction: discord.Interaction, bet: str):
        """Classic blackjack. Get as close to 21 as possible, but not over."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        try:
            bet = int(bet)
        except ValueError:
            if bet != "max":
                return await interaction.response.send_message("Invalid bet.", ephemeral=True)
            if user.get_field("settings")["disable_max_bet"]:
                embed = Cembed(
                    title="Max Bet Disabled",
                    desc="You have disabled betting your purse to protect yourself financially. I won't tell you how to reenable it.",
                    color=discord.Color.red(),
                    interaction=interaction,
                    activity="blackjack",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            bet = user.get_field("purse")

        message = await validate_bet(balance=user.get_field("purse"), bet=bet)
        if message:
            embed = Cembed(
                title="Invalid Bet",
                desc=message,
                color=discord.Color.red(),
                interaction=interaction,
                activity="blackjack",
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Collect their bet and set their status to in_game
        await user.inc_purse(-bet)
        await user.update_game(in_game=True)

        game = BlackJackGame(interaction=interaction, user=user, bet=bet)
        await interaction.response.send_message(embed=game.embed(), view=game)

        # Deal out starting hands for dealer and player
        for _ in range(2):
            await asyncio.sleep(0.25)
            game.deal_card(game.player)
            await interaction.edit_original_response(embed=game.embed(), view=game)

        await asyncio.sleep(0.25)
        game.deal_card(game.dealer)
        await interaction.edit_original_response(embed=game.embed(), view=game)

    class HitButton(discord.ui.Button):
        def __init__(self, interaction):
            super().__init__(label="Hit", style=discord.ButtonStyle.blurple)
            self.interaction = interaction

        async def callback(self, intr: discord.Interaction):
            assert self.view is not None
            if not await button_check(self.interaction, [intr.user.id]):
                return
            view: BlackJackGame = self.view

            game_state = view.hit_check()

            if game_state == GameStates.SAFE:
                pass

            # lose_embed.add_field(name="Profit", value=f"{-view.bet:,} bits", inline=False)
            # lose_embed.add_field(name="Bits", value=f"{view.user.get_field('purse'):,} bits")

            # await intr.response.edit_message(embed=lose_embed, view=None)

            await view.user.update_game(in_game=False)
            bot = User(1016054559581413457)
            await bot.load()
            await bot.inc_purse(amount=view.bet)

    class FoldButton(discord.ui.Button):
        def __init__(self, interaction):
            super().__init__(label="Fold", style=discord.ButtonStyle.blurple)
            self.interaction = interaction

        async def callback(self, fold_intr: discord.Interaction):
            assert self.view is not None
            if not await button_check(self.interaction, [fold_intr.user.id]):
                return
            view: BlackJackGame = self.view

            # Give the user half of their bet back
            await view.user.inc_purse(amount=round(view.bet / 2))

            # Keep half of your bet
            while view.d_hand_total < 17:
                view.draw_card(player=False)
            fold_embed = discord.Embed(
                title=f"Blackjack | User: {fold_intr.user.name} - Bet: {view.bet:,}",
                colour=0xFF0000,
            )
            fold_embed.add_field(
                name="FOLD",
                value=f"{''.join(view.p_hand)}\n" f"Total: {view.p_hand_total}",
                inline=True,
            )
            fold_embed.add_field(
                name="WIN",
                value=f"{''.join(view.d_hand)}\n" f"Total: {view.d_hand_total}",
                inline=True,
            )
            fold_embed.add_field(
                name="Profit", value=f"{round(-view.bet / 2):,} bits", inline=False
            )
            fold_embed.add_field(name="Bits", value=f"{view.user.get_field('purse'):,} bits")
            await fold_intr.response.edit_message(embed=fold_embed, view=None)
            await asyncio.sleep(1)

            await view.user.update_game(in_game=False, interaction=fold_intr)
            bot = User(1016054559581413457)
            await bot.load()
            await bot.inc_purse(amount=round(view.bet / 2))

    class StandButton(discord.ui.Button):
        def __init__(self, interaction):
            super().__init__(label="Stand", style=discord.ButtonStyle.blurple)
            self.interaction = interaction

        async def callback(self, stand_intr: discord.Interaction):
            assert self.view is not None
            if not await button_check(self.interaction, [stand_intr.user.id]):
                return
            view: BlackJackGame = self.view

            async def compare_hands():
                if view.p_hand_total < view.d_hand_total <= 21:
                    user_lost_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_intr.user.name} - Bet: {view.bet:,}",
                        colour=0xFF0000,
                    )

                    user_lost_embed.add_field(
                        name="Your hand",
                        value=f"{''.join(view.p_hand)}\n" f"Total: {view.p_hand_total}",
                        inline=True,
                    )
                    user_lost_embed.add_field(
                        name="WIN",
                        value=f"{''.join(view.d_hand)}\n" f"Total: {view.d_hand_total}",
                        inline=True,
                    )
                    user_lost_embed.add_field(
                        name="Profit", value=f"{-view.bet:,} bits", inline=False
                    )
                    user_lost_embed.add_field(
                        name="Bits", value=f"{view.user.get_field('purse'):,} bits"
                    )
                    await stand_intr.response.edit_message(embed=user_lost_embed, view=None)

                    await view.user.update_game(in_game=False, interaction=stand_intr)
                    bot = User(1016054559581413457)
                    await bot.load()
                    await bot.inc_purse(amount=view.bet)

                elif view.d_hand_total == view.p_hand_total:
                    await view.user.inc_purse(amount=view.bet)
                    push_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_intr.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.light_gray(),
                    )
                    push_embed.add_field(
                        name="PUSH",
                        value=f"{''.join(view.p_hand)}\n" f"Total: {view.p_hand_total}",
                        inline=True,
                    )
                    push_embed.add_field(
                        name="PUSH",
                        value=f"{''.join(view.d_hand)}\n" f"Total: {view.d_hand_total}",
                        inline=True,
                    )
                    push_embed.add_field(name="Profit", value=f"0 bits", inline=False)
                    push_embed.add_field(
                        name="Bits", value=f"{view.user.get_field('purse'):,} bits"
                    )
                    await stand_intr.response.edit_message(embed=push_embed, view=None)
                    await view.user.update_game(in_game=False, interaction=stand_intr)

                else:
                    await view.user.inc_purse(amount=view.bet * 2)

                    dealer_lost_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_intr.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.green(),
                    )
                    dealer_lost_embed.add_field(
                        name="WIN",
                        value=f"{''.join(view.p_hand)}\n" f"Total: {view.p_hand_total}",
                        inline=True,
                    )
                    dealer_lost_embed.add_field(
                        name="Dealer's hand",
                        value=f"{''.join(view.d_hand)}\n" f"Total: {view.d_hand_total}",
                        inline=True,
                    )
                    dealer_lost_embed.add_field(
                        name="Profit", value=f"{view.bet * 2:,} bits", inline=False
                    )
                    dealer_lost_embed.add_field(
                        name="Bits", value=f"{view.user.get_field('purse'):,} bits"
                    )
                    await stand_intr.response.edit_message(embed=dealer_lost_embed, view=None)
                    await view.user.update_game(in_game=False, interaction=stand_intr)

            while view.d_hand_total < 17:
                view.draw_card(player=False)
                if view.d_hand_total > 21:
                    await view.user.inc_purse(amount=view.bet * 2)
                    await view.user.update_game(in_game=False, interaction=stand_intr)
                    dealer_bust_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_intr.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.green(),
                    )

                    dealer_bust_embed.add_field(
                        name="Your hand",
                        value=f"{''.join(view.p_hand)}\n" f"Total: {view.p_hand_total}",
                        inline=True,
                    )
                    dealer_bust_embed.add_field(
                        name="BUSTED",
                        value=f"{''.join(view.d_hand)}\n" f"Total: {view.d_hand_total}",
                        inline=True,
                    )
                    dealer_bust_embed.add_field(
                        name="Profit", value=f"{view.bet * 2:,} bits", inline=False
                    )
                    dealer_bust_embed.add_field(
                        name="Bits", value=f"{view.user.get_field('purse'):,} bits"
                    )
                    await stand_intr.response.edit_message(embed=dealer_bust_embed, view=None)
                    return
            await compare_hands()


async def setup(bot):
    await bot.add_cog(BlackJack(bot))
