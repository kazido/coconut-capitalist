import typing
import pydealer
from classLibrary import RequestUser
import asyncio
from cogs.ErrorHandler import registered
from random import randint
from discord import app_commands
import discord
from discord.ext import commands


def format_face_cards(card_input):  # Function for formatting cards to give points values if they are face cards
    emoji = str(":" + str(card_input.suit).lower() + ":")
    face_cards = ["King", "Queen", "Jack"]
    if card_input.value in face_cards:
        card_input.value = card_input.value[0]
        card_worth = 10
    elif card_input.value == "Ace":
        card_input.value = card_input.value[0]
        card_worth = 11
    else:
        card_worth = int(card_input.value)
    new_card = f"{card_input.value}{emoji}"
    return new_card, card_worth

def draw_card(hand, from_deck):  # Function for drawing a card and adding it to a hand
    drawn_card = from_deck.deal(1)
    hand += drawn_card
    dc_card, dc_points = format_face_cards(drawn_card[0])
    return dc_points, dc_card

class BlackJack(commands.Cog, name="Blackjack"):
    """Basic Black Jack. Hit, stand, fold."""

    def __init__(self, bot):
        self.bot = bot

    # @registered()
    # @app_commands.guilds(856915776345866240, 977351545966432306)
    # @app_commands.command(name="blackjack",
    #                       description="Classic blackjack. Get as close to 21 as possible, but not over.")
    # @app_commands.describe(bet='amount of bits you want to bet | use max for all bits in purse')
    # async def blackjack(self, interaction: discord.Interaction, bet: str):
    #     user = RequestUser(interaction.user.id, interaction=interaction)
    #     if bet == 'max':
    #         bet = user.instance.money
    #     else:
    #         bet = int(bet)
    #
    #     message, passed = user.bet_checks(bet)
    #     if passed is False:
    #         bet_checks_failed_embed = discord.Embed(
    #             title="Invalid Bet",
    #             description=message,
    #             color=discord.Color.red()
    #         )
    #         await interaction.response.send_message(embed=bet_checks_failed_embed)
    #         return
    #
    #     user.update_balance(-bet)
    #     """TESTING"""
    #     # user.update_game_status(True)
    #
    #     deck = pydealer.Deck()  # Create a deck and shuffle it
    #     deck.shuffle()
    #
    #     opening_user_deal = deck.deal(2)  # Deal 2 sets of 2 cards
    #     opening_dealer_deal = deck.deal(1)
    #
    #     user_hand = dealer_hand = pydealer.Stack()  # Create a hand for the user and the dealer
    #
    #     user_hand += opening_user_deal  # Add each deal to respective hand
    #     dealer_hand += opening_dealer_deal
    #
    #     user_deal_list = dealer_deal_list = []   # Create defaults for totals and formatted hands
    #     aces = aces_subtracted = user_hand_total = dealer_hand_total = 0
    #
    #     for card in user_hand:  # Add points and format the card into card:emoji
    #         card, points = format_face_cards(card)
    #         if card[0] == "A":
    #             aces += 1
    #         user_deal_list.append(card)
    #         user_hand_total += points
    #
    #     if user_hand_total > 21:
    #         user_hand_total -= 10
    #         aces_subtracted += 1
    #
    #     for card in dealer_hand:  # Add points and format the card into card:emoji
    #         card, points = format_face_cards(card)
    #         dealer_deal_list.append(card)
    #         dealer_hand_total += points
    #
    #     embed = discord.Embed(
    #         title=f"Blackjack | User: {interaction.user.name} - Bet: {'{:,}'.format(bet)}",
    #         colour=discord.Color.blue()
    #     )
    #     embed.add_field(name="Your hand", value=f"{''.join(user_deal_list)}\n"
    #                                             f"Total: {user_hand_total}", inline=True)
    #     embed.add_field(name="Dealer's hand", value=f"{''.join(dealer_deal_list)}\n"
    #                                                 f"Total: {dealer_hand_total}", inline=True)
    #     embed.set_footer(text="You have 90 seconds to use a command")
    #
    # class HitButton(discord.ui.Button):
    #     def __init__(self):
    #         super().__init__()
    #
    #     def callback(self, hit_interaction: discord.Interaction):
    #         score, drawn_card = draw_card(user_hand, deck)
    #         user_hand_total += score
    #         user_deal_list.append(drawn_card)
    #         if drawn_card[0] == 'A':
    #             aces += 1
    #
    #         if user_hand_total > 21:
    #             if aces_subtracted <= aces - 1:
    #                 user_hand_total -= (10 * (aces - aces_subtracted))
    #                 aces_subtracted += aces
    #                 hit_embed = discord.Embed(
    #                     title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
    #                     colour=discord.Color.blue())
    #
    #                 hit_embed.add_field(name="Your hand", value=f"{''.join(user_deal_list)}\n"
    #                                                             f"Total: {user_hand_total}", inline=True)
    #                 hit_embed.add_field(name="Dealer's hand", value=f"{''.join(dealer_deal_list)}\n"
    #                                                                 f"Total: {dealer_hand_total}", inline=True)
    #                 hit_embed.add_field(name="Commands", value="**-stand** to see dealers cards\n"
    #                                                            "**-hit** draw another card\n"
    #                                                            "**-fold** give up but you lose half of your bet",
    #                                     inline=False)
    #                 hit_embed.set_footer(text="You have 90 seconds to use a command")
    #
    #                 await msg.edit(embed=hit_embed)
    #             else:
    #                 score, drawn_card = draw_card(dealer_hand, deck)
    #                 dealer_hand_total += score
    #                 dealer_deal_list.append(drawn_card)
    #                 if dealer_hand_total >= 17:
    #                     pass
    #                 else:
    #                     score, drawn_card = draw_card(dealer_hand, deck)
    #                     dealer_hand_total += score
    #                     dealer_deal_list.append(drawn_card)
    #                 lose_embed = discord.Embed(
    #                     title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
    #                     colour=0xff0000)
    #
    #                 lose_embed.add_field(name="BUSTED", value=f"{''.join(user_deal_list)}\n"
    #                                                           f"Total: {user_hand_total}", inline=True)
    #                 lose_embed.add_field(name="Dealer's hand", value=f"{''.join(dealer_deal_list)}\n"
    #                                                                  f"Total: {dealer_hand_total}", inline=True)
    #                 lose_embed.add_field(name="Profit", value=f"{'{:,}'.format(-bet)} bits", inline=False)
    #                 lose_embed.add_field(name="Bits",
    #                                      value=f"{'{:,}'.format(await user.check_balance('bits'))} bits")
    #                 lose_embed.set_footer(text="You earned *coming soon* xp")
    #                 await msg.edit(embed=lose_embed)
    #                 await self.bot.db.update_one({"isBot": True}, {"$inc": {"money": bet}})
    #                 await user.game_status_to_false()
    #                 break
    #         else:
    #             hit_embed = discord.Embed(
    #                 title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
    #                 colour=discord.Color.blue())
    #
    #             hit_embed.add_field(name="Your hand", value=f"{''.join(user_deal_list)}\n"
    #                                                         f"Total: {user_hand_total}", inline=True)
    #             hit_embed.add_field(name="Dealer's hand", value=f"{''.join(dealer_deal_list)}\n"
    #                                                             f"Total: {dealer_hand_total}", inline=True)
    #             hit_embed.add_field(name="Commands", value="**-stand** to see dealers cards\n"
    #                                                        "**-hit** draw another card\n"
    #                                                        "**-fold** give up but you lose half of your bet",
    #                                 inline=False)
    #             hit_embed.set_footer(text="You have 90 seconds to use a command")
    #
    #             await msg.edit(embed=hit_embed)
    #
    # class FoldButton(discord.ui.Button):
    #     def __init__(self):
    #         super().__init__()
    #
    #     def callback(self, hit_interaction: discord.Interaction):
    #         await user.update_balance(round(bet / 2))
    #         points, card = draw_card(dealer_hand, deck)
    #         dealer_hand_total += points
    #         dealer_deal_list.append(card)
    #         # Keep half of your bet
    #         if dealer_hand_total >= 17:
    #             pass
    #         else:
    #             points, card = draw_card(dealer_hand, deck)
    #             dealer_hand_total += points
    #             dealer_deal_list.append(card)
    #         fold_embed = discord.Embed(
    #             title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
    #             colour=0xff0000)
    #
    #         fold_embed.add_field(name="FOLD", value=f"{''.join(user_deal_list)}\n"
    #                                                 f"Total: {user_hand_total}",
    #                              inline=True)
    #         fold_embed.add_field(name="WIN", value=f"{''.join(dealer_deal_list)}\n"
    #                                                f"Total: {dealer_hand_total}",
    #                              inline=True)
    #         fold_embed.add_field(name="Profit", value=f"{'{:,}'.format(round(-bet / 2))} bits", inline=False)
    #         fold_embed.add_field(name="Bits", value=f"{'{:,}'.format(await user.check_balance('bits'))} bits")
    #         fold_embed.set_footer(text="You earned *coming soon* xp")
    #         await msg.edit(embed=fold_embed)
    #         await self.bot.db.update_one({"isBot": True}, {"$inc": {"money": round(bet / 2)}})
    #         await user.game_status_to_false()
    #         break
    #
    # class DoubleDownButton(discord.ui.Button):
    #     def __init__(self):
    #         super().__init__()
    #
    #     def callback(self, hit_interaction: discord.Interaction):
    #
    # class StandButton(discord.ui.Button):
    #     def __init__(self):
    #         super().__init__()
    #
    #     def callback(self, hit_interaction: discord.Interaction):
    #         points, card = draw_card(dealer_hand, deck)
    #         dealer_hand_total += points
    #         dealer_deal_list.append(card)
    #
    #         async def compare():
    #             if user_hand_total < dealer_hand_total <= 21:
    #                 user_lost_embed = discord.Embed(
    #                     title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
    #                     colour=0xff0000)
    #
    #                 user_lost_embed.add_field(name="Your hand", value=f"{''.join(user_deal_list)}\n"
    #                                                                   f"Total: {user_hand_total}",
    #                                           inline=True)
    #                 user_lost_embed.add_field(name="WIN", value=f"{''.join(dealer_deal_list)}\n"
    #                                                             f"Total: {dealer_hand_total}",
    #                                           inline=True)
    #                 user_lost_embed.add_field(name="Profit", value=f"{'{:,}'.format(-bet)} bits", inline=False)
    #                 user_lost_embed.add_field(name="Bits",
    #                                           value=f"{'{:,}'.format(await user.check_balance('bits'))} bits")
    #                 user_lost_embed.set_footer(text="You earned *coming soon* xp")
    #                 await msg.edit(embed=user_lost_embed)
    #                 await self.bot.db.update_one({"isBot": True}, {"$inc": {"money": bet}})
    #                 await user.game_status_to_false()
    #             elif dealer_hand_total == user_hand_total:
    #                 await user.update_balance(bet)
    #                 push_embed = discord.Embed(
    #                     title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
    #                     colour=discord.Color.light_gray())
    #                 push_embed.add_field(name="PUSH", value=f"{''.join(user_deal_list)}\n"
    #                                                         f"Total: {user_hand_total}",
    #                                      inline=True)
    #                 push_embed.add_field(name="PUSH", value=f"{''.join(dealer_deal_list)}\n"
    #                                                         f"Total: {dealer_hand_total}",
    #                                      inline=True)
    #                 push_embed.add_field(name="Profit", value=f"0 bits", inline=False)
    #                 push_embed.add_field(name="Bits",
    #                                      value=f"{'{:,}'.format(await user.check_balance('bits'))} bits")
    #                 push_embed.set_footer(text="You earned *coming soon* xp")
    #                 await msg.edit(embed=push_embed)
    #                 await user.game_status_to_false()
    #             else:
    #                 await user.update_balance(bet * 2)
    #                 dealer_lost_embed = discord.Embed(
    #                     title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
    #                     colour=discord.Color.green())
    #
    #                 dealer_lost_embed.add_field(name="Your hand", value=f"{''.join(user_deal_list)}\n"
    #                                                                     f"Total: {user_hand_total}",
    #                                             inline=True)
    #                 dealer_lost_embed.add_field(name="Dealer's hand", value=f"{''.join(dealer_deal_list)}\n"
    #                                                                         f"Total: {dealer_hand_total}",
    #                                             inline=True)
    #                 dealer_lost_embed.add_field(name="Profit", value=f"{'{:,}'.format(bet * 2)} bits",
    #                                             inline=False)
    #                 dealer_lost_embed.add_field(name="Bits",
    #                                             value=f"{'{:,}'.format(await user.check_balance('bits'))} bits")
    #                 dealer_lost_embed.set_footer(text="You earned *coming soon* xp")
    #                 await msg.edit(embed=dealer_lost_embed)
    #                 await user.game_status_to_false()
    #
    #         if dealer_hand_total >= 17:
    #             await compare()
    #         else:
    #             points, card = draw_card(dealer_hand, deck)
    #             dealer_hand_total += points
    #             dealer_deal_list.append(card)
    #             if dealer_hand_total > 21:
    #                 await user.update_balance(bet * 2)
    #                 dealer_bust_embed = discord.Embed(
    #                     title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
    #                     colour=discord.Color.green())
    #
    #                 dealer_bust_embed.add_field(name="Your hand", value=f"{''.join(user_deal_list)}\n"
    #                                                                     f"Total: {user_hand_total}",
    #                                             inline=True)
    #                 dealer_bust_embed.add_field(name="BUSTED", value=f"{''.join(dealer_deal_list)}\n"
    #                                                                  f"Total: {dealer_hand_total}", inline=True)
    #                 dealer_bust_embed.add_field(name="Profit", value=f"{'{:,}'.format(bet * 2)} bits",
    #                                             inline=False)
    #                 dealer_bust_embed.add_field(name="Bits",
    #                                             value=f"{'{:,}'.format(await user.check_balance('bits'))} bits")
    #                 dealer_bust_embed.set_footer(text="You earned *coming soon* xp")
    #                 await msg.edit(embed=dealer_bust_embed)
    #                 await user.game_status_to_false()
    #                 break
    #             else:
    #                 await compare()
    #         await user.game_status_to_false()
    #         break
    #
    # class BlackJackGame(discord.ui.View):
    #     def __init__(self):
    #         buttons = (BlackJack.HitButton(), BlackJack.StandButton(),
    #                    BlackJack.StandButton(), BlackJack.DoubleDownButton())
    #         super().__init__()
    #         for button in buttons:
    #             self.add_item(button)


async def setup(bot):
    await bot.add_cog(BlackJack(bot))
