import discord
import pydealer
import asyncio
import sys
import os

from cococap.user import User
from utils.messages import Cembed, button_check
from discord.ext import commands
from discord import app_commands
from utils.utils import check_bet

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)


# Function for formatting cards to give points values if they are face cards
def format_cards(card_input):
    """Format a card and determine its worth."""
    suit_emoji = f":{card_input.suit.lower()}:"
    name = (
        card_input.value[0]
        if card_input.value in ["King", "Queen", "Jack", "Ace"]
        else card_input.value
    )
    card_worth = (
        10
        if card_input.value in ["King", "Queen", "Jack"]
        else 11 if card_input.value == "Ace" else int(card_input.value)
    )
    formatted_card = f"{name}{suit_emoji}"
    return formatted_card, card_worth


def create_blackjack_embed(
    title, user_name, bet, player_hand, player_total, dealer_hand, dealer_total, color, footer=None
):
    """Create a blackjack embed with common fields."""
    embed = Cembed(
        title=f"Blackjack | User: {user_name} - Bet: {bet:,}",
        colour=color,
    )
    embed.add_field(
        name="Your hand",
        value=f"{''.join(player_hand)}\nTotal: {player_total}",
        inline=True,
    )
    embed.add_field(
        name="Dealer's hand",
        value=f"{''.join(dealer_hand)}\nTotal: {dealer_total}",
        inline=True,
    )
    if footer:
        embed.set_footer(text=footer)
    return embed


def adjust_for_aces(total, aces, aces_subtracted):
    """Adjust the total for aces if it exceeds 21."""
    while total > 21 and aces > aces_subtracted:
        total -= 10
        aces_subtracted += 1
    return total, aces_subtracted


class BlackJack(commands.Cog, name="Blackjack"):
    """Basic Blackjack. HIT, STAND, FOLD, or DOUBLE DOWN!"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="blackjack")
    @app_commands.describe(bet="amount of bits you want to bet | use max for all bits in purse")
    async def blackjack(self, interaction: discord.Interaction, bet: str):
        """Classic blackjack. Get as close to 21 as possible, but not over."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        if bet == "max":
            if user.get_field("settings")["disable_max_bet"]:
                failed_embed = Cembed(
                    title="Max Bet Disabled",
                    desc="You have disabled betting your purse to protect yourself financially. I won't tell you how to reenable it.",
                    color=discord.Color.red(),
                    interaction=interaction,
                    activity="blackjack",
                )
                await interaction.response.send_message(embed=failed_embed, ephemeral=True)
                return
            bet = user.get_field("purse")
        else:
            bet = int(bet)

        message, passed = await check_bet(balance=user.get_field("purse"), bet=bet)
        if passed is False:
            failed_embed = Cembed(
                title="Invalid Bet",
                desc=message,
                color=discord.Color.red(),
                interaction=interaction,
                activity="blackjack",
            )
            await interaction.response.send_message(embed=failed_embed, ephemeral=True)
            return

        await user.inc_purse(-bet)
        await user.update_game(in_game=True, interaction=interaction)

        view = BlackJack.BlackJackGame(interaction=interaction, user=user, bet=bet)
        await interaction.response.send_message(embed=view.blackjack_embed, view=view)

    class HitButton(discord.ui.Button):
        def __init__(self, interaction):
            super().__init__(label="Hit", style=discord.ButtonStyle.blurple)
            self.interaction = interaction

        async def callback(self, hit_interaction: discord.Interaction):
            assert self.view is not None
            if not await button_check(self.interaction, [hit_interaction.user.id]):
                return
            view: BlackJack.BlackJackGame = self.view

            game_state = view.draw_card(player=True)

            match game_state:
                case "safe":
                    hit_embed = create_blackjack_embed(
                        title="Blackjack",
                        user_name=hit_interaction.user.name,
                        bet=view.bet,
                        player_hand=view.p_hand,
                        player_total=view.player_hand_total,
                        dealer_hand=view.d_hand,
                        dealer_total=view.d_hand_total,
                        color=discord.Color.blue(),
                        footer="You have 90 seconds to use a command",
                    )
                    await hit_interaction.response.edit_message(embed=hit_embed)
                case "lost":
                    while view.d_hand_total < 17:
                        view.draw_card(player=False)
                    lose_embed = create_blackjack_embed(
                        title="Blackjack",
                        user_name=hit_interaction.user.name,
                        bet=view.bet,
                        player_hand=view.p_hand,
                        player_total=view.player_hand_total,
                        dealer_hand=view.d_hand,
                        dealer_total=view.d_hand_total,
                        color=0xFF0000,
                    )
                    lose_embed.add_field(name="Profit", value=f"{-view.bet:,} bits", inline=False)
                    lose_embed.add_field(
                        name="Bits", value=f"{view.user.get_field('purse'):,} bits"
                    )

                    await hit_interaction.response.edit_message(embed=lose_embed, view=None)

                    await view.user.update_game(in_game=False, interaction=hit_interaction)
                    bot = User(1016054559581413457)
                    await bot.load()
                    await bot.inc_purse(amount=view.bet)

    class FoldButton(discord.ui.Button):
        def __init__(self, interaction):
            super().__init__(label="Fold", style=discord.ButtonStyle.blurple)
            self.interaction = interaction

        async def callback(self, fold_interaction: discord.Interaction):
            if not await button_check(self.interaction, [fold_interaction.user.id]):
                return
            assert self.view is not None
            view: BlackJack.BlackJackGame = self.view

            # Give the user half of their bet back
            await view.user.inc_purse(amount=round(view.bet / 2))

            # Keep half of your bet
            while view.d_hand_total < 17:
                view.draw_card(player=False)
            fold_embed = discord.Embed(
                title=f"Blackjack | User: {fold_interaction.user.name} - Bet: {view.bet:,}",
                colour=0xFF0000,
            )
            fold_embed.add_field(
                name="FOLD",
                value=f"{''.join(view.p_hand)}\n" f"Total: {view.player_hand_total}",
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
            await fold_interaction.response.edit_message(embed=fold_embed, view=None)
            await asyncio.sleep(1)

            await view.user.update_game(in_game=False, interaction=fold_interaction)
            bot = User(1016054559581413457)
            await bot.load()
            await bot.inc_purse(amount=round(view.bet / 2))

    class StandButton(discord.ui.Button):
        def __init__(self, interaction):
            super().__init__(label="Stand", style=discord.ButtonStyle.blurple)
            self.interaction = interaction

        async def callback(self, stand_interaction: discord.Interaction):
            if not await button_check(self.interaction, [stand_interaction.user.id]):
                return
            assert self.view is not None
            view: BlackJack.BlackJackGame = self.view

            async def compare_hands():
                if view.player_hand_total < view.d_hand_total <= 21:
                    user_lost_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_interaction.user.name} - Bet: {view.bet:,}",
                        colour=0xFF0000,
                    )

                    user_lost_embed.add_field(
                        name="Your hand",
                        value=f"{''.join(view.p_hand)}\n" f"Total: {view.player_hand_total}",
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
                    await stand_interaction.response.edit_message(embed=user_lost_embed, view=None)

                    await view.user.update_game(in_game=False, interaction=stand_interaction)
                    bot = User(1016054559581413457)
                    await bot.load()
                    await bot.inc_purse(amount=view.bet)

                elif view.d_hand_total == view.player_hand_total:
                    await view.user.inc_purse(amount=view.bet)
                    push_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_interaction.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.light_gray(),
                    )
                    push_embed.add_field(
                        name="PUSH",
                        value=f"{''.join(view.p_hand)}\n" f"Total: {view.player_hand_total}",
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
                    await stand_interaction.response.edit_message(embed=push_embed, view=None)
                    await view.user.update_game(in_game=False, interaction=stand_interaction)

                else:
                    await view.user.inc_purse(amount=view.bet * 2)

                    dealer_lost_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_interaction.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.green(),
                    )
                    dealer_lost_embed.add_field(
                        name="WIN",
                        value=f"{''.join(view.p_hand)}\n" f"Total: {view.player_hand_total}",
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
                    await stand_interaction.response.edit_message(
                        embed=dealer_lost_embed, view=None
                    )
                    await view.user.update_game(in_game=False, interaction=stand_interaction)

            while view.d_hand_total < 17:
                view.draw_card(player=False)
                if view.d_hand_total > 21:
                    await view.user.inc_purse(amount=view.bet * 2)
                    await view.user.update_game(in_game=False, interaction=stand_interaction)
                    dealer_bust_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_interaction.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.green(),
                    )

                    dealer_bust_embed.add_field(
                        name="Your hand",
                        value=f"{''.join(view.p_hand)}\n" f"Total: {view.player_hand_total}",
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
                    await stand_interaction.response.edit_message(
                        embed=dealer_bust_embed, view=None
                    )
                    return
            await compare_hands()

    class BlackJackGame(discord.ui.View):
        def __init__(self, interaction: discord.Interaction, user: User, bet: int):
            super().__init__()
            self.user: User = user

            buttons = (
                BlackJack.HitButton(interaction),
                BlackJack.StandButton(interaction),
                BlackJack.FoldButton(interaction),
            )
            for button in buttons:  # Add the 3 buttons to the view
                self.add_item(button)

            self.deck = pydealer.Deck()  # Create a deck
            self.deck.shuffle()  # Shuffle the deck

            self.p_hand = []
            self.d_hand = []  # Create defaults for totals and formatted hands
            self.p_aces = 0
            self.p_aces_converted = 0
            self.player_hand_total = 0
            self.d_aces = 0
            self.d_aces_converted = 0
            self.d_hand_total = 0

            self.draw_card(player=True)
            self.draw_card(player=True)
            self.draw_card(player=False)

            if self.player_hand_total > 21:  # If player hand goes over 21 and the player has aces
                if self.p_aces > 0 and (
                    self.p_aces > self.p_aces_converted
                ):  # If the player hasn't - the ace yet
                    self.player_hand_total -= 10
                    self.p_aces_converted += 1

            if self.d_hand_total > 21:  # If dealer hand goes over 21 and the dealer has aces
                if self.d_aces > 0 and (
                    self.d_aces > self.d_aces_converted
                ):  # If the dealer hasn't - the ace yet
                    self.d_hand_total -= 10
                    self.d_aces_converted += 1

            self.blackjack_embed = create_blackjack_embed(
                title="Blackjack",
                user_name=interaction.user.name,
                bet=bet,
                player_hand=self.p_hand,
                player_total=self.player_hand_total,
                dealer_hand=self.d_hand,
                dealer_total=self.d_hand_total,
                color=discord.Color.blue(),
                footer="You have 90 seconds to play",
            )

        def p_draw_card(self):
            """Draw a card and add it to the player's or dealer's hand."""
            drawn_card = self.deck.deal(1)[0]
            formatted_card, points = format_cards(drawn_card)

            self.player_hand_total += points
            self.p_hand.append(formatted_card)
            if formatted_card[0] == "A":
                self.p_aces += 1
            self.player_hand_total, self.p_aces_converted = adjust_for_aces(
                self.player_hand_total, self.p_aces, self.p_aces_converted
            )
            return "lost" if self.player_hand_total > 21 else "safe"

        def d_draw_card(self):
            """Draw a card and add it to the dealer's hand."""
            drawn_card = self.deck.deal(1)
            formatted_card, points = format_cards(drawn_card[0])

            self.d_hand_total += points
            self.d_hand.append(formatted_card)
            if formatted_card[0] == "A":
                self.d_aces += 1

            if self.d_hand_total > 21:  # If the dealers hand goes over 21
                if self.d_aces > self.d_aces_converted:  # If dealer has aces left to subtract
                    self.d_hand_total -= 10
                    self.d_aces_converted += 1
                else:  # Dealer is over 21 and has no aces left
                    return "dealer lost"
            else:  # Dealer is not over 21 and is safe
                return "safe"


async def setup(bot):
    await bot.add_cog(BlackJack(bot))
