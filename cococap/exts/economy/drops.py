import discord
import random
import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient
from discord.ext import commands, tasks
from discord import TextChannel, app_commands
from random import randint
from datetime import datetime
from pytz import timezone

from cococap.user import User
from cococap import instance, args
from cococap.constants import GamblingChannels, URI
from bson import ObjectId

log = logging.getLogger(__name__)


client = AsyncIOMotorClient(URI)  # Are we creating a second instance here? Shouldn't be probably...
collection = client.discordbot.special_entities

DROP_MAX = 20000
DROP_MIN = 10000
DROP_AVERAGE = int((DROP_MIN + DROP_MAX) / 2)


def drop_double(amount):
    odds = random.randint(0, 100)
    if odds in range(0, 5):  # 5% chance for the drop to be double upon claim
        amount *= 2
        description = f"claimed a **DOUBLE** drop! **+{amount:,}** bits"
        color = 0xCC8C16
    else:
        description = f"claimed a drop! **+{amount:,}** bits"
        color = 0xF0B57A
    return description, amount, color


class ClaimDropButtons(discord.ui.View):
    def __init__(self, drop: "Drop", megadrop: bool, *, timeout):
        super().__init__(timeout=timeout)
        self.claimed = False
        self.drop = drop
        self.is_megadrop = megadrop

    async def on_timeout(self) -> None:
        if self.claimed:
            return

        await self.drop.message.edit(embed=self.drop.expired_embed, view=None)

        if self.is_megadrop:
            update_data = {"$inc": {"times_missed": 1}}
        else:
            update_data = {
                "$inc": {
                    "amount": self.drop.amount,
                    "total_drops": 1,
                    "total_drops_missed": 1,
                    "counter": 1,
                }
            }

        await collection.update_one({"_id": ObjectId("65b76d73ee9f83c970604935")}, update_data)

    @discord.ui.button(label="CLAIM", emoji="📦", style=discord.ButtonStyle.green)
    async def claim_button(self, claim_interaction: discord.Interaction, button: discord.ui.Button):
        # Load the user
        user = User(claim_interaction.user.id)
        await user.load()

        user._document.drops_claimed += 1
        await user.save()

        megadrop = await collection.find_one({"_id": ObjectId("65b76d73ee9f83c970604935")})

        if self.is_megadrop:
            claimed_embed = discord.Embed(
                title="🎉 THE MEGADROP HAS BEEN CLAIMED! 🎉",
                description=f"{claim_interaction.user.name} {self.drop.description}\n"
                f"You have claimed **{user._document.drops_claimed:,}** drops 📦",
                color=self.drop.color,
            )
            claimed_embed.add_field(
                name="Drops Cumulated",
                value=f"This megadrop was a combination of "
                f"**{megadrop['total_drops_missed']:,}** drops",
            )
            claimed_embed.add_field(
                name="Times Missed",
                value=f"This megadrop had gone unclaimed **{megadrop['times_missed']}** " f"times.",
            )

            last_winner: discord.Member = claim_interaction.guild.get_member(
                megadrop["last_winner"]
            )
            claimed_embed.add_field(
                name="Last Winner",
                value=f"The last winner was {last_winner.mention}",
                inline=False,
            )
            claimed_embed.set_footer(
                text=f"The megadrop has been growing since: {megadrop['date_started']}"
            )

            now_time = datetime.now(timezone("US/Eastern"))
            date_started = datetime.strftime(now_time, "%m-%d-%Y")

            update_data = {
                "$set": {
                    "last_winner": claim_interaction.user.id,
                    "date_started": date_started,
                    "amount": 0,
                    "total_drops": 0,
                    "total_drops_missed": 0,
                    "counter": 0,
                    "times_missed": 0,
                }
            }

            await collection.update_one({"_id": ObjectId("65b76d73ee9f83c970604935")}, update_data)

        else:
            claimed_embed = discord.Embed(
                title="This drop has been claimed!",
                description=f"{claim_interaction.user.name} {self.drop.description}\n"
                f"You have claimed **{user._document.drops_claimed:,}** drops 📦",
                color=self.drop.color,
            )
            claimed_embed.set_footer(text="Drops happen randomly and last for 30 minutes!")
            update_data = {
                "$inc": {
                    "total_drops": 1,
                    "counter": 1,
                }
            }
            await collection.update_one({"_id": ObjectId("65b76d73ee9f83c970604935")}, update_data)

        await user.inc_purse(amount=int(self.drop.amount))
        await claim_interaction.response.edit_message(embed=claimed_embed, view=None)
        self.claimed = True


class Drop:
    def __init__(self, channel: discord.TextChannel, amount):
        self.channel = channel
        self.description, self.amount, self.color = drop_double(amount)

        self.embed = discord.Embed(  # Embed for a new drop appearing
            title="A drop has appeared! 📦",
            description=f"This drop contains **{amount:,}** bits!",
            color=0x946C44,
        )
        self.embed.set_footer(text="Click the button below to claim!")

        self.expired_embed = discord.Embed(  # Embed for when a drop expires after 1 hour
            title="Drop expired.",
            description=f"This **{self.amount:,}** bit drop has been added to the *Mega Drop*.",
            color=0x484A4A,
        )
        self.expired_embed.set_footer(text="Do /megadrop to check the current pot!")

        self.timeout = 1800  # 30 minutes for the drop to be claimed

    async def release_drop(self):
        self.message = await self.channel.send(
            embed=self.embed,
            view=ClaimDropButtons(self, False, timeout=self.timeout),
        )


class MegaDrop(Drop):
    def __init__(self, channel: TextChannel, amount: int):
        super().__init__(channel, amount)
        # Get the megadrop from the database

        self.embed = discord.Embed(
            title="⚠️ THE MEGADROP HAS APPEARED ⚠️",
            description=f"This drop contains **{amount:,}** bits!!",
            color=0x946C44,
        )
        self.embed.set_footer(text="Click the button below to claim!")

        self.expired_embed = discord.Embed(
            title="MEGADROP EXPIRED.",
            description=f"The megadrop has gone back into hiding...",
            color=0x484A4A,
        )
        self.expired_embed.set_footer(text="Do /megadrop to see its current status.")

    async def release_drop(self):
        megadrop = await collection.find_one({"_id": ObjectId("65b76d73ee9f83c970604935")})
        timeout = 900 + (megadrop["times_missed"] * 900)
        self.message = await self.channel.send(
            embed=self.embed,
            view=ClaimDropButtons(self, True, timeout=timeout),
        )


class DropsCog(commands.Cog, name="Drops"):
    """Cog related to Drops and the Mega Drop"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        if args.drops:
            log.info("Drops arg passed, dropping drops :D")
            self.drop_task.start()

    async def cog_unload(self):
        self.drop_task.cancel()

    @tasks.loop(minutes=randint(30, 60), reconnect=True)
    async def drop_task(self):
        guild: discord.Guild = discord.Object(id=856915776345866240)
        channels = [
            GamblingChannels.DREAMSCAPE.value,
            GamblingChannels.HEAVEN.value,
            GamblingChannels.NIGHTMARE.value,
            GamblingChannels.PLANETARIUM.value,
            GamblingChannels.THERAPY.value,
            GamblingChannels.PARADISE.value,
        ]

        # Pick a random channel from one of the channels
        channel = guild.get_channel(random.choice(channels))
        drop_amount = randint(DROP_MIN, DROP_MAX)
        drop = Drop(channel, drop_amount)

        megadrop = await collection.find_one({"_id": ObjectId("65b76d73ee9f83c970604935")})
        # If the counter is above 150
        if megadrop["counter"] >= 150:
            # Roll a random number to release the mega drop
            roll = randint(1, 100)
            if roll in range(1, 2):
                drop = MegaDrop(channel, megadrop.amount)
                await collection.update_one(
                    {"_id": ObjectId("65b76d73ee9f83c970604935")}, {"$set": {"counter": 0}}
                )
        await drop.release_drop()

        # Set next drop to come out 1-2 hours from now
        self.drop_task.change_interval(minutes=randint(60, 120))

    @drop_task.before_loop
    async def before_drop_tast(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(randint(1200, 2400))

    @app_commands.command(name="megadrop")
    async def megadrop_status(self, interaction: discord.Interaction):
        """Check the current status of the Mega Drop"""
        megadrop = await collection.find_one({"_id": ObjectId("65b76d73ee9f83c970604935")})
        status_embed = discord.Embed(title="📦 MEGADROP STATUS 📦", color=0x45FFB1)
        status_embed.add_field(name="Current Pot", value=f"{megadrop['amount']:,} bits")
        status_embed.add_field(
            name="Drops Cumulated",
            value=f"The megadrop has accumulated " f"**{megadrop['total_drops_missed']:,}** drops",
        )
        status_embed.add_field(
            name="Times Missed",
            value=f"The megadrop has gone unclaimed **{megadrop['times_missed']}** times.",
            inline=False,
        )
        guild: discord.Guild = discord.Object(id=856915776345866240)
        last_winner: discord.Member = guild.get_member(megadrop["last_winner"])
        status_embed.add_field(name="Last Winner", value=last_winner.mention, inline=True)

        status_embed.set_footer(
            text=f"The megadrop has been growing since: {megadrop['date_started']}"
        )
        await interaction.response.send_message(embed=status_embed)


async def setup(bot):
    await bot.add_cog(DropsCog(bot))
