import discord  # Discord imports
from discord.ext import commands, tasks
from discord import app_commands
import random  # Random imports
from random import randint
from datetime import datetime  # Time imports for formatting and retrieving date
from pytz import timezone
import asyncio
import json  # File handling imports
from cogs.ErrorHandler import registered  # File imports
from ClassLibrary2 import RequestUser, megadrop
from utils import seconds_until_tasks


def drop_double(amount):
    odds = random.randint(0, 100)
    if odds in range(0, 5):  # 5% chance for the drop to be double upon claim
        amount *= 2
        description = f"claimed a **DOUBLE** drop! **+{'{:,}'.format(amount)}** bits"
        color = 0xcc8c16
    else:
        description = f"claimed a drop! **+{'{:,}'.format(amount)}** bits"
        color = 0xf0b57a
    return description, amount, color


class Drop:
    def __init__(self, channel: discord.TextChannel, amount):
        self.channel = channel
        self.description, self.amount, self.color = drop_double(amount)
        self.embed = discord.Embed(  # Embed for a new drop appearing
            title="A drop has appeared! 📦",
            description=f"This drop contains **{'{:,}'.format(self.amount)}** bits!",
            color=0x946c44)
        self.embed.set_footer(text="Click the button below to claim!")
        self.expired_embed = discord.Embed(  # Embed for when a drop expires after 1 hour
            title="This drop expired!",
            description=f"This **{'{:,}'.format(self.amount)}** bit drop has been added to the *Mega Drop*.",
            color=0x484a4a)
        self.expired_embed.set_footer(text="Do /megadrop to check the current pot!")

    async def prep_claim(self, drop):
        class ClaimDropButtons(discord.ui.View):

            def __init__(self, *, timeout=3600):
                super().__init__(timeout=timeout)
                self.claimed = False

            async def on_timeout(self) -> None:
                if self.claimed:
                    return
                await message.edit(embed=drop.expired_embed, view=None)
                megadrop['megadrop']['amount'] += drop.amount
                megadrop['megadrop']['total_drops_missed'] += 1
                megadrop['megadrop']['total_drops'] += 1

            @discord.ui.button(label="CLAIM", style=discord.ButtonStyle.green)
            async def claim_button(self, claim_interaction: discord.Interaction, button: discord.ui.Button):
                user = RequestUser(claim_interaction.user.id, interaction=claim_interaction)
                user.instance.drops_claimed += 1
                user.instance.save()
                claimed_embed = discord.Embed(
                    title="This drop has been claimed!",
                    description=f"{claim_interaction.user.name} {drop.description}\n"
                                f"You have claimed {user.instance.drops_claimed}",
                    color=drop.color
                )
                claimed_embed.set_footer(text="Drops happen randomly and last for an hour!")
                user.update_balance(int(drop.amount))
                megadrop['megadrop']['total_drops'] += 1
                await claim_interaction.response.edit_message(embed=claimed_embed, view=None)
                self.claimed = True

        message = await self.channel.send(embed=drop.embed, view=ClaimDropButtons())


class DropsCog(commands.Cog, name='Drops'):
    """Cog related to Drops and the Mega Drop"""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree
        self.drop_task.start()

    @tasks.loop(minutes=randint(30, 60))
    async def drop_task(self):
        guild = self.bot.get_guild(856915776345866240)  # Guild to send the drops in
        channels = [858549045613035541, 959271607241683044, 961471869725343834,  # All channels drops can be sent to
                    961045401803317299, 962171274073899038, 962171351794327562]
        channel = guild.get_channel(random.choice(channels))  # Pick a random channel from one of the channels
        drop_amount = randint(10000, 25000)
        drop = Drop(channel, drop_amount)
        await drop.prep_claim(drop)
        DropsCog.drop_task.change_interval(minutes=randint(60, 120))  # Set next drop to come out 1-2 hours from now

    @drop_task.before_loop
    async def before_drop_tast(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(seconds_until_tasks())

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="megadrop", description="Check the current status of the Mega Drop")
    async def megadrop_status(self, interaction: discord.Interaction):
        status_embed = discord.Embed(
            title="Current Mega Drop",
            color=discord.Color.from_str("0xdb4f4b")
        )
        status_embed.add_field(name="Drop Begin Date", value=megadrop['megadrop']['date_started'])
        status_embed.add_field(name="Drop Value", value=f"**{'{:,}'.format(megadrop['megadrop']['amount'])}** bits")
        status_embed.add_field(name="Drops Missed", value=f"{megadrop['megadrop']['total_drops_missed']} drops"
                                                          f"/{megadrop['megadrop']['total_drops']} total drops")
        status_embed.add_field(name="Times Missed", value=megadrop['megadrop']['times_missed'])

        fmt = "%m-%d-%Y %H:%M:%S"  # Put current date into a format and add to bottom of embed
        now_time = datetime.now(timezone('US/Eastern'))
        status_embed.set_footer(text=now_time.strftime(fmt=fmt))
        await interaction.response.send_message(embed=status_embed, view=None)


async def setup(bot):
    await bot.add_cog(DropsCog(bot))
