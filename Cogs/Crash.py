import asyncio
from random import randint
import discord
from discord.ext import commands
from Cogs.ErrorHandler import in_game, registered


class Crash(commands.Cog, name='Crash'):
    """This module is currently disabled."""
    def __init__(self, bot):
        self.bot = bot

    @registered()
    @in_game()
    @commands.command(enabled=False)
    async def crash(self, ctx, bet: int):
        # Loop to increase multiplier
        async def crash_loop(status, multiplier):
            while status is True:
                # Embed that will change during the game
                crash_embed = discord.Embed(
                    title="Crash!",
                    description=f"Current multiplier: **{multiplier}x**",
                    color=discord.Color.green()
                )
                await sent_embed.edit(embed=crash_embed)
                # Roll for odds of losing
                roll = randint(0, 10)
                await asyncio.sleep(1)
                # If the roll is 10% roll
                if roll in range(0):
                    # This needs to be updated to have user class
                    db_query_for_user = await self.bot.mongo_client['discordbot']['users'].find_one({"_id": ctx.author.id})
                    losing_embed = discord.Embed(
                        title=f"Crash!",
                        description=f"Crashed at **{multiplier}x**.\nYou now have {db_query_for_user['money']} bits.",
                        color=discord.Color.red()
                    )
                    await sent_embed.edit(embed=losing_embed)
                    # Set game status to false
                    await self.bot.mongo_client['discordbot']['users'].update_one({"_id": ctx.author.id},
                                                                                  {"$set": {"in_game": False}})
                    # Give the house the money
                    await self.bot.mongo_client['discordbot']['users'].update_one({"isBot": True},
                                                                                  {"$inc": {"money": bet}})
                    crashLoop.status = False
                    crashLoop.cancel()
                    stopLoop.cancel()
                else:
                    # Increase multiplier by 2 and round it
                    multiplier += 0.2
                    multiplier = round(multiplier, 1)
                    crashLoop.set_result(multiplier)

        async def stop_response(multiplier):
            # Correct responses to end the game
            responses = ["-stop", "stop", "-s", "s"]

            def check(m):
                return m.content in responses and m.author == ctx.author and m.channel == ctx.channel

            # Wait for a stop message
            stop_command = await self.bot.wait_for(event="message", check=check)
            if stop_command.content in responses:
                crashLoop.cancel()
                await self.bot.mongo_client['discordbot']['users'].update_one({"_id": ctx.author.id},
                                                                              {"$inc": {"money": bet * multiplier}})
                db_query_for_user = await self.bot.mongo_client['discordbot']['users'].find_one({"_id": ctx.author.id})
                stop_embed = discord.Embed(
                    title=f"Crash!",
                    description=f"Stopped at {multiplier}x! You now have {db_query_for_user['money']} bits.",
                    color=discord.Color.green()
                )
                await self.bot.mongo_client['discordbot']['users'].update_one({"_id": ctx.author.id},
                                                                              {"$set": {"in_game": False}})
                await sent_embed.edit(embed=stop_embed)
                stopLoop.cancel()

        # If Bet CHECK is failed, stop else continue
        if await HighLow.bet_checks(bet, ctx) is True:
            pass
        else:
            # Subtract from their bits
            await self.bot.mongo_client['discordbot']['users'].update_one({"_id": ctx.author.id},
                                                                          {"$inc": {"money": -bet}})
            # Set their in_game status to True to prevent them from playing other games
            await self.bot.mongo_client['discordbot']['users'].update_one({"_id": ctx.author.id},
                                                                          {"$set": {"in_game": True}})
            updated_status = await self.bot.mongo_client['discordbot']['users'].find_one({"_id": ctx.author.id})
            updated_status = updated_status["in_game"]
            # multiplier that will go up if 80% roll
            initial_multiplier = 1
            # Embed that edits with each roll
            crash_embed = discord.Embed(
                title="Crash!",
                description=f"Current multiplier: **{initial_multiplier}x**",
                color=discord.Color.green()
            )
            sent_embed = await ctx.send(embed=crash_embed)
            crashLoop = asyncio.create_task(crash_loop(updated_status, initial_multiplier))
            stopLoop = asyncio.create_task(stop_response(crashLoop))


async def setup(bot):
    await bot.add_cog(Crash(bot))