import discord
import pydealer
import asyncio
import sys
import os

from cococap.user import User
from cococap.utils.messages import Cembed, button_check
from discord.ext import commands
from discord import app_commands
from cococap.utils.utils import check_bet

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)


# Function for formatting cards to give points values if they are face cards
def format_cards(card_input):
    suit_emoji = str(":" + str(card_input.suit).lower() + ":")
    if card_input.value in ["King", "Queen", "Jack"]:
        # Sets the value to be the first letter of the face card
        card_input.value = card_input.value[0]
        card_worth = 10  # Face cards are worth 10
    elif card_input.value == "Ace":
        # Sets the value to be the first letter of the Ace
        card_input.value = card_input.value[0]
        card_worth = 11  # Aces start as worth 11
    else:  # If the card is just a number card
        card_worth = int(card_input.value)
    # Format the card a discord embed
    formatted_card = f"{card_input.value}{suit_emoji}"
    return formatted_card, card_worth


class BlackJack(commands.Cog, name="Blackjack"):
    """Basic Black Jack. HIT, STAND, FOLD, or DOUBLE DOWN!"""

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
                    hit_embed = Cembed(
                        title=f"Blackjack | User: {hit_interaction.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.blue(),
                        interaction=hit_interaction,
                        activity="blackjack",
                    )
                    hit_embed.add_field(
                        name="Your hand",
                        value=f"{''.join(view.player_embed_hand)}\n"
                        f"Total: {view.player_hand_total}",
                        inline=True,
                    )
                    hit_embed.add_field(
                        name="Dealer's hand",
                        value=f"{''.join(view.dealer_embed_hand)}\n"
                        f"Total: {view.dealer_hand_total}",
                        inline=True,
                    )
                    hit_embed.set_footer(text="You have 90 seconds to use a command")
                    await hit_interaction.response.edit_message(embed=hit_embed)
                case "lost":
                    while view.dealer_hand_total < 17:
                        view.draw_card(player=False)
                    lose_embed = Cembed(
                        title=f"Blackjack | User: {hit_interaction.user.name} - Bet: {view.bet:,}",
                        colour=0xFF0000,
                        interaction=hit_interaction,
                        activity="blackjack",
                    )
                    lose_embed.add_field(
                        name="BUSTED",
                        value=f"{''.join(view.player_embed_hand)}\n"
                        f"Total: {view.player_hand_total}",
                        inline=True,
                    )
                    lose_embed.add_field(
                        name="Dealer's hand",
                        value=f"{''.join(view.dealer_embed_hand)}\n"
                        f"Total: {view.dealer_hand_total}",
                        inline=True,
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
            while view.dealer_hand_total < 17:
                view.draw_card(player=False)
            fold_embed = discord.Embed(
                title=f"Blackjack | User: {fold_interaction.user.name} - Bet: {view.bet:,}",
                colour=0xFF0000,
            )
            fold_embed.add_field(
                name="FOLD",
                value=f"{''.join(view.player_embed_hand)}\n" f"Total: {view.player_hand_total}",
                inline=True,
            )
            fold_embed.add_field(
                name="WIN",
                value=f"{''.join(view.dealer_embed_hand)}\n" f"Total: {view.dealer_hand_total}",
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
                if view.player_hand_total < view.dealer_hand_total <= 21:
                    user_lost_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_interaction.user.name} - Bet: {view.bet:,}",
                        colour=0xFF0000,
                    )

                    user_lost_embed.add_field(
                        name="Your hand",
                        value=f"{''.join(view.player_embed_hand)}\n"
                        f"Total: {view.player_hand_total}",
                        inline=True,
                    )
                    user_lost_embed.add_field(
                        name="WIN",
                        value=f"{''.join(view.dealer_embed_hand)}\n"
                        f"Total: {view.dealer_hand_total}",
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

                elif view.dealer_hand_total == view.player_hand_total:
                    await view.user.inc_purse(amount=view.bet)
                    push_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_interaction.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.light_gray(),
                    )
                    push_embed.add_field(
                        name="PUSH",
                        value=f"{''.join(view.player_embed_hand)}\n"
                        f"Total: {view.player_hand_total}",
                        inline=True,
                    )
                    push_embed.add_field(
                        name="PUSH",
                        value=f"{''.join(view.dealer_embed_hand)}\n"
                        f"Total: {view.dealer_hand_total}",
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
                        value=f"{''.join(view.player_embed_hand)}\n"
                        f"Total: {view.player_hand_total}",
                        inline=True,
                    )
                    dealer_lost_embed.add_field(
                        name="Dealer's hand",
                        value=f"{''.join(view.dealer_embed_hand)}\n"
                        f"Total: {view.dealer_hand_total}",
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

            while view.dealer_hand_total < 17:
                view.draw_card(player=False)
                if view.dealer_hand_total > 21:
                    await view.user.inc_purse(amount=view.bet * 2)
                    await view.user.update_game(in_game=False, interaction=stand_interaction)
                    dealer_bust_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_interaction.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.green(),
                    )

                    dealer_bust_embed.add_field(
                        name="Your hand",
                        value=f"{''.join(view.player_embed_hand)}\n"
                        f"Total: {view.player_hand_total}",
                        inline=True,
                    )
                    dealer_bust_embed.add_field(
                        name="BUSTED",
                        value=f"{''.join(view.dealer_embed_hand)}\n"
                        f"Total: {view.dealer_hand_total}",
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
            self.bet = bet
            self.user: User = user

            buttons = (BlackJack.HitButton(interaction), BlackJack.StandButton(interaction), BlackJack.FoldButton(interaction))
            for button in buttons:  # Add the 4 buttons to the view
                self.add_item(button)

            self.deck = pydealer.Deck()  # Create a deck
            self.deck.shuffle()  # Shuffle the deck

            self.player_embed_hand = []
            self.dealer_embed_hand = []  # Create defaults for totals and formatted hands
            self.player_aces = 0
            self.player_aces_subtracted = 0
            self.player_hand_total = 0
            self.dealer_aces = 0
            self.dealer_aces_subtracted = 0
            self.dealer_hand_total = 0

            self.draw_card(player=True)
            self.draw_card(player=True)
            self.draw_card(player=False)

            if self.player_hand_total > 21:  # If player hand goes over 21 and the player has aces
                if self.player_aces > 0 and (
                    self.player_aces > self.player_aces_subtracted
                ):  # If the player hasn't - the ace yet
                    self.player_hand_total -= 10
                    self.player_aces_subtracted += 1

            if self.dealer_hand_total > 21:  # If dealer hand goes over 21 and the dealer has aces
                if self.dealer_aces > 0 and (
                    self.dealer_aces > self.dealer_aces_subtracted
                ):  # If the dealer hasn't - the ace yet
                    self.dealer_hand_total -= 10
                    self.dealer_aces_subtracted += 1

            self.blackjack_embed = Cembed(
                title=f"Blackjack | User: {interaction.user.name} - Bet: {self.bet:,}",
                colour=discord.Color.blue(),
                interaction=interaction,
                activity="blackjack",
            )
            self.blackjack_embed.add_field(
                name="Your hand",
                value=f"{''.join(self.player_embed_hand)}\n" f"Total: {self.player_hand_total}",
                inline=True,
            )
            self.blackjack_embed.add_field(
                name="Dealer's hand",
                value=f"{''.join(self.dealer_embed_hand)}\n" f"Total: {self.dealer_hand_total}",
                inline=True,
            )
            self.blackjack_embed.set_footer(text="You have 90 seconds to play")

        def draw_card(self, player: bool):  # Function for drawing a card and adding it to a hand
            # Draw a card from the deck we are working with
            drawn_card = self.deck.deal(1)
            formatted_card, points = format_cards(drawn_card[0])
            if player:
                self.player_hand_total += points
                self.player_embed_hand.append(formatted_card)
                if formatted_card[0] == "A":
                    self.player_aces += 1

                if self.player_hand_total > 21:  # If the players hand goes over 21
                    if (
                        self.player_aces > self.player_aces_subtracted
                    ):  # If player has aces left to subtract
                        self.player_hand_total -= 10
                        self.player_aces_subtracted += 1
                        return "safe"
                    else:  # Player is over 21 and has no aces left
                        return "lost"
                else:  # Player is over 21 and has no aces left
                    return "safe"
            else:
                self.dealer_hand_total += points
                self.dealer_embed_hand.append(formatted_card)
                if formatted_card[0] == "A":
                    self.dealer_aces += 1

                if self.dealer_hand_total > 21:  # If the dealers hand goes over 21
                    if (
                        self.dealer_aces > self.dealer_aces_subtracted
                    ):  # If dealer has aces left to subtract
                        self.dealer_hand_total -= 10
                        self.dealer_aces_subtracted += 1
                    else:  # Dealer is over 21 and has no aces left
                        return "dealer lost"
                else:  # Dealer is not over 21 and is safe
                    return "safe"


async def setup(bot):
    await bot.add_cog(BlackJack(bot))
