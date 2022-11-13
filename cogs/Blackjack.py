import typing
import pydealer
from ClassLibrary import *
import asyncio
from cogs.ErrorHandler import registered
from random import randint


class BlackJack(commands.Cog, name="Blackjack"):
    """Basic Black Jack. Hit, stand, fold."""

    def __init__(self, bot):
        self.bot = bot

    @registered()
    @commands.command(aliases=["bj", "blackj", "bjack"], name="Blackjack", description="Classic blackjack. Get as "
                                                                                       "close to 21 as possible, "
                                                                                       "but not over.",
                      brief="-blackjack (bet)")
    async def blackjack(self, ctx, bet: int | typing.Literal['max']):
        user = User(ctx)
        if bet == 'max':
            bet = await user.check_balance('bits')
        else:
            pass

        async def blackjack_game():
            await user.update_balance(-bet)
            await user.game_status_to_true()
            # Create a deck and shuffle it
            deck = pydealer.Deck()
            deck.shuffle()
            # Deal 2 sets of 2 cards
            opening_user_deal = deck.deal(2)
            opening_dealer_deal = deck.deal(1)
            # Create a hand for the user and the dealer
            user_hand = pydealer.Stack()
            dealer_hand = pydealer.Stack()
            # Add each deal to respective hand
            user_hand += opening_user_deal
            dealer_hand += opening_dealer_deal
            # Create defaults for totals and formatted hands
            user_hand_total, user_deal_list = 0, []
            dealer_hand_total, dealer_deal_list = 0, []
            aces = 0
            aces_subtracted = 0

            def format_cards(card):
                emoji = str(":" + str(card.suit).lower() + ":")
                face_cards = ["King", "Queen", "Jack"]
                if card.value in face_cards:
                    card.value = card.value[0]
                    card_worth = 10
                elif card.value == "Ace":
                    card.value = card.value[0]
                    card_worth = 11
                else:
                    card_worth = int(card.value)
                new_card = f"{card.value}{emoji}"
                return new_card, card_worth

            def draw_card(hand, from_deck):
                drawn_card = from_deck.deal(1)
                hand += drawn_card
                dc_card, dc_points = format_cards(drawn_card[0])
                return dc_points, dc_card

            # Add points and format the card into card:emoji
            for x in user_hand:
                card, points = format_cards(x)
                if card[0] == "A":
                    aces += 1
                user_deal_list.append(card)
                user_hand_total += points
            # Add points and format the card into card:emoji
            for x in dealer_hand:
                card, points = format_cards(x)
                dealer_deal_list.append(card)
                dealer_hand_total += points
            if user_hand_total > 21:
                print(aces)
                print(aces_subtracted)
                user_hand_total -= 10
                aces_subtracted += 1
            embed = discord.Embed(
                title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
                colour=discord.Color.blue())

            embed.add_field(name="Your hand", value=f"{''.join(user_deal_list)}\n"
                                                    f"Total: {user_hand_total}", inline=True)
            embed.add_field(name="Dealer's hand", value=f"{''.join(dealer_deal_list)}\n"
                                                        f"Total: {dealer_hand_total}", inline=True)
            embed.add_field(name="Commands", value="**-stand** to see dealers cards\n"
                                                   "**-hit** draw another card\n"
                                                   "**-fold** give up but you lose half of your bet",
                            inline=False)
            embed.set_footer(text="You have 90 seconds to use a command")
            msg = await ctx.send(embed=embed)
            while user_hand_total <= 21 and dealer_hand_total <= 21:
                responses = ['-hit', '-stand', '-fold']

                def check(m):
                    return m.content.lower() in responses and m.author == ctx.author and m.channel == ctx.channel

                # Waits for a command from user
                try:
                    command = await self.bot.wait_for("message", timeout=90.0, check=check)
                except asyncio.TimeoutError:
                    await user.game_status_to_false()
                    break
                if command.content.lower() == "-hit":
                    points, card = draw_card(user_hand, deck)
                    user_hand_total += points
                    user_deal_list.append(card)
                    if card[0] == 'A':
                        aces += 1

                    if user_hand_total > 21:
                        if aces_subtracted <= aces - 1:
                            user_hand_total -= (10 * (aces - aces_subtracted))
                            aces_subtracted += aces
                            hit_embed = discord.Embed(
                                title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
                                colour=discord.Color.blue())

                            hit_embed.add_field(name="Your hand", value=f"{''.join(user_deal_list)}\n"
                                                                        f"Total: {user_hand_total}", inline=True)
                            hit_embed.add_field(name="Dealer's hand", value=f"{''.join(dealer_deal_list)}\n"
                                                                            f"Total: {dealer_hand_total}", inline=True)
                            hit_embed.add_field(name="Commands", value="**-stand** to see dealers cards\n"
                                                                       "**-hit** draw another card\n"
                                                                       "**-fold** give up but you lose half of your bet",
                                                inline=False)
                            hit_embed.set_footer(text="You have 90 seconds to use a command")

                            await msg.edit(embed=hit_embed)
                        else:
                            points, card = draw_card(dealer_hand, deck)
                            dealer_hand_total += points
                            dealer_deal_list.append(card)
                            if dealer_hand_total >= 17:
                                pass
                            else:
                                points, card = draw_card(dealer_hand, deck)
                                dealer_hand_total += points
                                dealer_deal_list.append(card)
                            lose_embed = discord.Embed(
                                title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
                                colour=0xff0000)

                            lose_embed.add_field(name="BUSTED", value=f"{''.join(user_deal_list)}\n"
                                                                      f"Total: {user_hand_total}", inline=True)
                            lose_embed.add_field(name="Dealer's hand", value=f"{''.join(dealer_deal_list)}\n"
                                                                             f"Total: {dealer_hand_total}", inline=True)
                            lose_embed.add_field(name="Profit", value=f"{'{:,}'.format(-bet)} bits", inline=False)
                            lose_embed.add_field(name="Bits",
                                                 value=f"{'{:,}'.format(await user.check_balance('bits'))} bits")
                            lose_embed.set_footer(text="You earned *coming soon* xp")
                            await msg.edit(embed=lose_embed)
                            await self.bot.db.update_one({"isBot": True}, {"$inc": {"money": bet}})
                            await user.game_status_to_false()
                            break
                    else:
                        hit_embed = discord.Embed(
                            title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
                            colour=discord.Color.blue())

                        hit_embed.add_field(name="Your hand", value=f"{''.join(user_deal_list)}\n"
                                                                    f"Total: {user_hand_total}", inline=True)
                        hit_embed.add_field(name="Dealer's hand", value=f"{''.join(dealer_deal_list)}\n"
                                                                        f"Total: {dealer_hand_total}", inline=True)
                        hit_embed.add_field(name="Commands", value="**-stand** to see dealers cards\n"
                                                                   "**-hit** draw another card\n"
                                                                   "**-fold** give up but you lose half of your bet",
                                            inline=False)
                        hit_embed.set_footer(text="You have 90 seconds to use a command")

                        await msg.edit(embed=hit_embed)
                elif command.content.lower() == "-stand":
                    points, card = draw_card(dealer_hand, deck)
                    dealer_hand_total += points
                    dealer_deal_list.append(card)

                    async def compare():
                        if user_hand_total < dealer_hand_total <= 21:
                            user_lost_embed = discord.Embed(
                                title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
                                colour=0xff0000)

                            user_lost_embed.add_field(name="Your hand", value=f"{''.join(user_deal_list)}\n"
                                                                              f"Total: {user_hand_total}",
                                                      inline=True)
                            user_lost_embed.add_field(name="WIN", value=f"{''.join(dealer_deal_list)}\n"
                                                                        f"Total: {dealer_hand_total}",
                                                      inline=True)
                            user_lost_embed.add_field(name="Profit", value=f"{'{:,}'.format(-bet)} bits", inline=False)
                            user_lost_embed.add_field(name="Bits",
                                                      value=f"{'{:,}'.format(await user.check_balance('bits'))} bits")
                            user_lost_embed.set_footer(text="You earned *coming soon* xp")
                            await msg.edit(embed=user_lost_embed)
                            await self.bot.db.update_one({"isBot": True}, {"$inc": {"money": bet}})
                            await user.game_status_to_false()
                        elif dealer_hand_total == user_hand_total:
                            await user.update_balance(bet)
                            push_embed = discord.Embed(
                                title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
                                colour=discord.Color.light_gray())
                            push_embed.add_field(name="PUSH", value=f"{''.join(user_deal_list)}\n"
                                                                    f"Total: {user_hand_total}",
                                                 inline=True)
                            push_embed.add_field(name="PUSH", value=f"{''.join(dealer_deal_list)}\n"
                                                                    f"Total: {dealer_hand_total}",
                                                 inline=True)
                            push_embed.add_field(name="Profit", value=f"0 bits", inline=False)
                            push_embed.add_field(name="Bits",
                                                 value=f"{'{:,}'.format(await user.check_balance('bits'))} bits")
                            push_embed.set_footer(text="You earned *coming soon* xp")
                            await msg.edit(embed=push_embed)
                            await user.game_status_to_false()
                        else:
                            await user.update_balance(bet * 2)
                            dealer_lost_embed = discord.Embed(
                                title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
                                colour=discord.Color.green())

                            dealer_lost_embed.add_field(name="Your hand", value=f"{''.join(user_deal_list)}\n"
                                                                                f"Total: {user_hand_total}",
                                                        inline=True)
                            dealer_lost_embed.add_field(name="Dealer's hand", value=f"{''.join(dealer_deal_list)}\n"
                                                                                    f"Total: {dealer_hand_total}",
                                                        inline=True)
                            dealer_lost_embed.add_field(name="Profit", value=f"{'{:,}'.format(bet * 2)} bits",
                                                        inline=False)
                            dealer_lost_embed.add_field(name="Bits",
                                                        value=f"{'{:,}'.format(await user.check_balance('bits'))} bits")
                            dealer_lost_embed.set_footer(text="You earned *coming soon* xp")
                            await msg.edit(embed=dealer_lost_embed)
                            await user.game_status_to_false()

                    if dealer_hand_total >= 17:
                        await compare()
                    else:
                        points, card = draw_card(dealer_hand, deck)
                        dealer_hand_total += points
                        dealer_deal_list.append(card)
                        if dealer_hand_total > 21:
                            await user.update_balance(bet * 2)
                            dealer_bust_embed = discord.Embed(
                                title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
                                colour=discord.Color.green())

                            dealer_bust_embed.add_field(name="Your hand", value=f"{''.join(user_deal_list)}\n"
                                                                                f"Total: {user_hand_total}",
                                                        inline=True)
                            dealer_bust_embed.add_field(name="BUSTED", value=f"{''.join(dealer_deal_list)}\n"
                                                                             f"Total: {dealer_hand_total}", inline=True)
                            dealer_bust_embed.add_field(name="Profit", value=f"{'{:,}'.format(bet * 2)} bits",
                                                        inline=False)
                            dealer_bust_embed.add_field(name="Bits",
                                                        value=f"{'{:,}'.format(await user.check_balance('bits'))} bits")
                            dealer_bust_embed.set_footer(text="You earned *coming soon* xp")
                            await msg.edit(embed=dealer_bust_embed)
                            await user.game_status_to_false()
                            break
                        else:
                            await compare()
                    await user.game_status_to_false()
                    break
                elif command.content.lower() == "-fold":
                    await user.update_balance(round(bet / 2))
                    points, card = draw_card(dealer_hand, deck)
                    dealer_hand_total += points
                    dealer_deal_list.append(card)
                    # Keep half of your bet
                    if dealer_hand_total >= 17:
                        pass
                    else:
                        points, card = draw_card(dealer_hand, deck)
                        dealer_hand_total += points
                        dealer_deal_list.append(card)
                    fold_embed = discord.Embed(
                        title=f"Blackjack | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
                        colour=0xff0000)

                    fold_embed.add_field(name="FOLD", value=f"{''.join(user_deal_list)}\n"
                                                            f"Total: {user_hand_total}",
                                         inline=True)
                    fold_embed.add_field(name="WIN", value=f"{''.join(dealer_deal_list)}\n"
                                                           f"Total: {dealer_hand_total}",
                                         inline=True)
                    fold_embed.add_field(name="Profit", value=f"{'{:,}'.format(round(-bet / 2))} bits", inline=False)
                    fold_embed.add_field(name="Bits", value=f"{'{:,}'.format(await user.check_balance('bits'))} bits")
                    fold_embed.set_footer(text="You earned *coming soon* xp")
                    await msg.edit(embed=fold_embed)
                    await self.bot.db.update_one({"isBot": True}, {"$inc": {"money": round(bet / 2)}})
                    await user.game_status_to_false()
                    break

        message, passed = await user.bet_checks(bet)
        if passed is False:
            await ctx.send(message)
        else:
            await blackjack_game()

        lucky_drop = randint(0, 3500)
        if lucky_drop == 1:
            await user.update_tokens(1)
            await ctx.reply("**RARE** You just found a token!")
        elif lucky_drop in range(2, 10):
            bits = randint(250, 750)
            await user.update_balance(bits)
            await ctx.reply(f"**UNCOMMON** You just found {'{:,}'.format(bits)} bits!")


async def setup(bot):
    await bot.add_cog(BlackJack(bot))
