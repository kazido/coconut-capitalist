import typing
from discord.ext import commands
import asyncio
from Cogs.ErrorHandler import in_game, registered
from ClassLibrary import *
from Cogs.EconomyCog import get_role
from random import randint


class HighLow(commands.Cog, name="HighLow"):
    """Guess if the next number will be high (6-10) or low (1-5)"""
    def __init__(self, bot):
        self.bot = bot

    @in_game()
    @registered()
    @commands.command(aliases=["hl", "highlow"], name="High Low", description="Guess if the number will be high (6-10) "
                                                                              "or low (1-5).", brief="-highlow (bet)")
    async def high_low(self, ctx, bet: int | typing.Literal['max']):
        user = User(ctx)
        if bet == 'max':
            bet = await user.check_balance('bits')
        else:
            pass

        async def high_low_game():
            # Subtract their bet from their bits
            await user.update_balance(-bet)
            # Set their in_game status to True to prevent them from playing other games
            await user.game_status_to_true()
            multiplier = 0
            await ctx.send("Guess if the number is **-high** or **-low**.")
            # Loop through the game. Only stopped if the user loses or uses the -stop command
            user_in_database = await self.bot.db.find_one({"_id": user.user_id})
            while user_in_database["in_game"] is True:
                updated_money = await user.check_balance('bits')
                num = randint(1, 10)
                responses = ['-stop', '-high', '-low', '-h', '-l']

                def check(m):
                    return m.content.lower() in responses and m.author == ctx.author and m.channel == ctx.channel

                # Waits for a response after asking for high or low. Can be high, low, or stop
                try:
                    guess = await self.bot.wait_for("message", timeout=90.0, check=check)
                except asyncio.TimeoutError:
                    await user.game_status_to_false()
                    break
                # Creating the embeds for winning and losing
                stop_embed = discord.Embed(
                    title=f"Highlow | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
                    color=discord.Color.green()
                )
                stop_embed.add_field(name="Stopped at", value=f"**{'{:,}'.format(multiplier)}x**", inline=True)
                stop_embed.add_field(name="Profit", value=f"**{'{:,}'.format(bet * multiplier)}** bits", inline=True)
                stop_embed.add_field(name="Bits",
                                     value=f"You have {'{:,}'.format(updated_money + (bet * multiplier))} bits",
                                     inline=False)
                # Simple high low checker
                if num in range(1, 6):
                    correct_responses = ['-low', '-l']
                else:
                    correct_responses = ['-high', '-h']
                if guess.content.lower() in correct_responses:
                    # Separate embeds to avoid having multiplier say "0x"
                    if multiplier == 0:
                        multiplier = 2
                    else:
                        multiplier *= 2
                    embed = discord.Embed(
                        title=f"Highlow | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
                        color=discord.Color.green())
                    embed.add_field(name="Correct!", value=f"The number was **{num}**", inline=True)
                    embed.add_field(name="Multiplier", value=f"**{multiplier}x**", inline=True)
                    embed.add_field(name="Continue", value="Use **-low** or **-high**", inline=False)
                    embed.set_footer(text=f"Use -stop to stop")
                    await ctx.send(embed=embed)
                    await asyncio.sleep(0.2)
                # IF they use -stop command
                elif guess.content == '-stop':
                    await user.update_balance(bet * multiplier)
                    await user.game_status_to_false()
                    stop_embed.set_footer(text="XP: coming soon")
                    await ctx.send(embed=stop_embed)
                    break
                # If they lose the game
                else:
                    lost_game_money = await user.check_balance('bits')
                    losing_embed = discord.Embed(
                        title=f"Highlow | User: {ctx.author.name} - Bet: {'{:,}'.format(bet)}",
                        color=discord.Color.red()
                    )
                    losing_embed.add_field(name="Incorrect!", value=f"The number was **{num}**", inline=True)
                    losing_embed.add_field(name="Profit", value=f"**{'{:,}'.format(-bet)}** bits", inline=True)
                    losing_embed.add_field(name="Bits", value=f"You have {'{:,}'.format(lost_game_money)} bits",
                                           inline=False)
                    losing_embed.set_footer(text=f"XP: coming soon.")
                    await ctx.send(embed=losing_embed)
                    await user.game_status_to_false()
                    # This line adds the lost money to the house.
                    await self.bot.db.update_one({"_id": 956000805578768425}, {"$inc": {"money": bet}})
                    break

        message, passed = await user.bet_checks(bet)
        if passed is False:
            await ctx.send(message)
        else:
            # Start the game if both checks are passed
            await high_low_game()
        lucky_drop = randint(0, 5000)
        if lucky_drop == 1:
            await user.update_tokens(1)
            await ctx.reply("**RARE** You just found a token!")
        elif lucky_drop in range(2, 10):
            bits = randint(250, 750)
            await user.update_balance(bits)
            await ctx.reply(f"**UNCOMMON** You just found {'{:,}'.format(bits)} bits!")


async def setup(bot):
    await bot.add_cog(HighLow(bot))
