from discord.ext import commands
import discord
from discord import app_commands
from random import randint
from exts.ErrorHandler import registered
import asyncio
from ClassLibrary import RequestUser
import typing
import pydealer
import sys
import os
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

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="blackjack",
                          description="Classic blackjack. Get as close to 21 as possible, but not over.")
    @app_commands.describe(bet='amount of bits you want to bet | use max for all bits in purse')
    async def blackjack(self, interaction: discord.Interaction, bet: str):
        user = RequestUser(interaction.user.id, interaction=interaction)
        if bet == 'max':
            bet = user.instance.money
        else:
            bet = int(bet)

        message, passed = user.bet_checks(bet)
        if passed is False:
            bet_checks_failed_embed = discord.Embed(
                title="Invalid Bet",
                description=message,
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=bet_checks_failed_embed)
            return

        user.update_balance(-bet)
        """TESTING"""
        # user.update_game_status(True)
        view = BlackJack.BlackJackGame(
            interaction=interaction, user=user, bet=bet)
        await interaction.response.send_message(embed=view.blackjack_embed, view=view)

    class HitButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Hit", style=discord.ButtonStyle.blurple)

        async def callback(self, hit_interaction: discord.Interaction):
            assert self.view is not None
            view: BlackJack.BlackJackGame = self.view

            game_state = view.draw_card(player=True)

            match game_state:
                case 'safe':
                    hit_embed = discord.Embed(
                        title=f"Blackjack | User: {hit_interaction.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.blue())
                    hit_embed.add_field(name="Your hand", value=f"{''.join(view.player_embed_hand)}\n"
                                                                f"Total: {view.player_hand_total}", inline=True)
                    hit_embed.add_field(name="Dealer's hand", value=f"{''.join(view.dealer_embed_hand)}\n"
                                                                    f"Total: {view.dealer_hand_total}", inline=True)
                    hit_embed.set_footer(
                        text="You have 90 seconds to use a command")
                    await hit_interaction.response.edit_message(embed=hit_embed)
                case 'lost':
                    while view.dealer_hand_total < 17:
                        view.draw_card(player=False)
                    lose_embed = discord.Embed(
                        title=f"Blackjack | User: {hit_interaction.user.name} - Bet: {view.bet:,}", colour=0xff0000)
                    lose_embed.add_field(name="BUSTED", value=f"{''.join(view.player_embed_hand)}\n"
                                                              f"Total: {view.player_hand_total}", inline=True)
                    lose_embed.add_field(name="Dealer's hand", value=f"{''.join(view.dealer_embed_hand)}\n"
                                                                     f"Total: {view.dealer_hand_total}",
                                         inline=True)
                    lose_embed.add_field(
                        name="Profit", value=f"{-view.bet:,} bits", inline=False)
                    lose_embed.add_field(
                        name="Bits", value=f"{view.user.instance.money:,} bits")
                    lose_embed.set_footer(text="You earned *coming soon* xp")

                    await hit_interaction.response.edit_message(embed=lose_embed, view=None)

                    view.user.update_game_status(False)
                    bot = RequestUser(956000805578768425, hit_interaction)
                    bot.instance.money += view.bet
                    bot.instance.save()

    class FoldButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Fold", style=discord.ButtonStyle.blurple)

        async def callback(self, fold_interaction: discord.Interaction):
            assert self.view is not None
            view: BlackJack.BlackJackGame = self.view

            # Give the user half of their bet back
            view.user.update_balance(round(view.bet / 2))

            # Keep half of your bet
            while view.dealer_hand_total < 17:
                view.draw_card(player=False)
            fold_embed = discord.Embed(
                title=f"Blackjack | User: {fold_interaction.user.name} - Bet: {view.bet:,}",
                colour=0xff0000)
            fold_embed.add_field(name="FOLD", value=f"{''.join(view.player_embed_hand)}\n"
                                                    f"Total: {view.player_hand_total}", inline=True)
            fold_embed.add_field(name="WIN", value=f"{''.join(view.dealer_embed_hand)}\n"
                                                    f"Total: {view.dealer_hand_total}", inline=True)
            fold_embed.add_field(
                name="Profit", value=f"{round(-view.bet / 2):,} bits", inline=False)
            fold_embed.add_field(
                name="Bits", value=f"{view.user.instance.money:,} bits")
            fold_embed.set_footer(text="*coming soon* is xp")
            await fold_interaction.response.edit_message(embed=fold_embed, view=None)
            await asyncio.sleep(1)

            view.user.update_game_status(False)
            bot = RequestUser(956000805578768425, fold_interaction)
            bot.instance.money += round(view.bet / 2)
            bot.instance.save()

    # class DoubleDownButton(discord.ui.Button):
    #     def __init__(self):
    #         super().__init__(label="Double", emoji="2️⃣", style=discord.ButtonStyle.red)
    #
    #     async def callback(self, double_interaction: discord.Interaction):
    #         assert self.view is not None
    #         view: BlackJack.BlackJackGame = self.view

    class StandButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Stand", style=discord.ButtonStyle.blurple)

        async def callback(self, stand_interaction: discord.Interaction):
            assert self.view is not None
            view: BlackJack.BlackJackGame = self.view

            async def compare_hands():
                if view.player_hand_total < view.dealer_hand_total <= 21:
                    user_lost_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_interaction.user.name} - Bet: {view.bet:,}",
                        colour=0xff0000)

                    user_lost_embed.add_field(name="Your hand", value=f"{''.join(view.player_embed_hand)}\n"
                                                                      f"Total: {view.player_hand_total}", inline=True)
                    user_lost_embed.add_field(name="WIN", value=f"{''.join(view.dealer_embed_hand)}\n"
                                                                f"Total: {view.dealer_hand_total}", inline=True)
                    user_lost_embed.add_field(
                        name="Profit", value=f"{-view.bet:,} bits", inline=False)
                    user_lost_embed.add_field(
                        name="Bits", value=f"{view.user.instance.money:,} bits")
                    user_lost_embed.set_footer(
                        text="You earned *coming soon* xp")
                    await stand_interaction.response.edit_message(embed=user_lost_embed, view=None)

                    view.user.update_game_status(False)
                    bot = RequestUser(956000805578768425, stand_interaction)
                    bot.instance.money += view.bet
                    bot.instance.save()

                elif view.dealer_hand_total == view.player_hand_total:
                    view.user.update_balance(view.bet)
                    push_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_interaction.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.light_gray())
                    push_embed.add_field(name="PUSH", value=f"{''.join(view.player_embed_hand)}\n"
                                                            f"Total: {view.player_hand_total}", inline=True)
                    push_embed.add_field(name="PUSH", value=f"{''.join(view.dealer_embed_hand)}\n"
                                                            f"Total: {view.dealer_hand_total}", inline=True)
                    push_embed.add_field(
                        name="Profit", value=f"0 bits", inline=False)
                    push_embed.add_field(
                        name="Bits", value=f"{view.user.instance.money:,} bits")
                    push_embed.set_footer(text="You earned *coming soon* xp")
                    await stand_interaction.response.edit_message(embed=push_embed, view=None)
                    view.user.update_game_status(False)

                else:
                    view.user.update_balance(view.bet * 2)

                    dealer_lost_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_interaction.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.green())
                    dealer_lost_embed.add_field(name="WIN", value=f"{''.join(view.player_embed_hand)}\n"
                                                                  f"Total: {view.player_hand_total}", inline=True)
                    dealer_lost_embed.add_field(name="Dealer's hand", value=f"{''.join(view.dealer_embed_hand)}\n"
                                                                            f"Total: {view.dealer_hand_total}",
                                                inline=True)
                    dealer_lost_embed.add_field(
                        name="Profit", value=f"{view.bet * 2:,} bits", inline=False)
                    dealer_lost_embed.add_field(
                        name="Bits", value=f"{view.user.instance.money:,} bits")
                    dealer_lost_embed.set_footer(
                        text="You earned *coming soon* xp")
                    await stand_interaction.response.edit_message(embed=dealer_lost_embed, view=None)
                    view.user.update_game_status(False)

            while view.dealer_hand_total < 17:
                view.draw_card(player=False)
                if view.dealer_hand_total > 21:
                    view.user.update_balance(view.bet * 2)
                    dealer_bust_embed = discord.Embed(
                        title=f"Blackjack | User: {stand_interaction.user.name} - Bet: {view.bet:,}",
                        colour=discord.Color.green())

                    dealer_bust_embed.add_field(name="Your hand", value=f"{''.join(view.player_embed_hand)}\n"
                                                                        f"Total: {view.player_hand_total}", inline=True)
                    dealer_bust_embed.add_field(name="BUSTED", value=f"{''.join(view.dealer_embed_hand)}\n"
                                                                     f"Total: {view.dealer_hand_total}", inline=True)
                    dealer_bust_embed.add_field(
                        name="Profit", value=f"{view.bet * 2:,} bits", inline=False)
                    dealer_bust_embed.add_field(
                        name="Bits", value=f"{view.user.instance.money:,} bits")
                    dealer_bust_embed.set_footer(
                        text="You earned *coming soon* xp")
                    await stand_interaction.response.edit_message(embed=dealer_bust_embed, view=None)
                    return
            await compare_hands()

    class BlackJackGame(discord.ui.View):
        def __init__(self, interaction: discord.Interaction, user: RequestUser, bet: int):
            super().__init__()
            self.bet = bet
            self.user = user

            buttons = (BlackJack.HitButton(),
                       BlackJack.StandButton(), BlackJack.FoldButton())
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
                        self.player_aces > self.player_aces_subtracted):  # If the player hasn't - the ace yet
                    self.player_hand_total -= 10
                    self.player_aces_subtracted += 1

            if self.dealer_hand_total > 21:  # If dealer hand goes over 21 and the dealer has aces
                if self.dealer_aces > 0 and (
                        self.dealer_aces > self.dealer_aces_subtracted):  # If the dealer hasn't - the ace yet
                    self.dealer_hand_total -= 10
                    self.dealer_aces_subtracted += 1

            self.blackjack_embed = discord.Embed(
                title=f"Blackjack | User: {interaction.user.name} - Bet: {'{:,}'.format(self.bet)}",
                colour=discord.Color.blue()
            )
            self.blackjack_embed.add_field(name="Your hand", value=f"{''.join(self.player_embed_hand)}\n"
                                                                   f"Total: {self.player_hand_total}", inline=True)
            self.blackjack_embed.add_field(name="Dealer's hand", value=f"{''.join(self.dealer_embed_hand)}\n"
                                                                       f"Total: {self.dealer_hand_total}", inline=True)
            self.blackjack_embed.set_footer(text="You have 90 seconds to play")

        def draw_card(self, player: bool):  # Function for drawing a card and adding it to a hand
            # Draw a card from the deck we are working with
            drawn_card = self.deck.deal(1)
            formatted_card, points = format_cards(drawn_card[0])
            if player:
                self.player_hand_total += points
                self.player_embed_hand.append(formatted_card)
                if formatted_card[0] == 'A':
                    self.player_aces += 1

                if self.player_hand_total > 21:  # If the players hand goes over 21
                    if self.player_aces > self.player_aces_subtracted:  # If player has aces left to subtract
                        self.player_hand_total -= 10
                        self.player_aces_subtracted += 1
                        return 'safe'
                    else:  # Player is over 21 and has no aces left
                        return 'lost'
                else:  # Player is over 21 and has no aces left
                    return 'safe'
            else:
                self.dealer_hand_total += points
                self.dealer_embed_hand.append(formatted_card)
                if formatted_card[0] == 'A':
                    self.dealer_aces += 1

                if self.dealer_hand_total > 21:  # If the dealers hand goes over 21
                    if self.dealer_aces > self.dealer_aces_subtracted:  # If dealer has aces left to subtract
                        self.dealer_hand_total -= 10
                        self.dealer_aces_subtracted += 1
                    else:  # Dealer is over 21 and has no aces left
                        return 'dealer lost'
                else:  # Dealer is not over 21 and is safe
                    return 'safe'


async def setup(bot):
    await bot.add_cog(BlackJack(bot))
