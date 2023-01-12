import discord  # Discord imports
from discord.ext import commands, tasks
from discord import app_commands
import random  # Random imports
from random import randint
from datetime import datetime  # Time imports for formatting and retrieving date
from pytz import timezone
import asyncio
import json  # File handling imports
from exts.error import registered  # File imports
from classLibrary import RequestUser
from utils import seconds_until_tasks
import utils.models as mM


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


DROP_MAX = 20000
DROP_MIN = 10000
DROP_AVERAGE = int((DROP_MIN + DROP_MAX) / 2)


class Drop:
    def __init__(self, channel: discord.TextChannel, amount, ismegadrop):
        self.channel = channel
        self.isMegadrop = ismegadrop
        self.description, self.amount, self.color = drop_double(amount)

        if self.isMegadrop:  # Mega drop, run special init method
            self.instance: mM.Megadrop = mM.Megadrop.get(id=1)

            self.embed = discord.Embed(  # Megadrop embed
                title="⚠️ THE MEGADROP HAS APPEARED ⚠️",
                description=f"This drop contains **{'{:,}'.format(amount)}** bits!!",
                color=0x946c44)
            self.embed.set_footer(text="Click the button below to claim!")

            self.expired_embed = discord.Embed(
                title="MEGADROP EXPIRED.",
                description=f"The megadrop has gone back into hiding...",
                color=0x484a4a)
            self.expired_embed.set_footer(text="Do /megadrop to see its current status.")

            self.timeout = 900 + (self.instance.times_missed * 900)

        else:  # It's not a mega drop, initialize as normal

            self.embed = discord.Embed(  # Embed for a new drop appearing
                title="A drop has appeared! 📦",
                description=f"This drop contains **{'{:,}'.format(amount)}** bits!",
                color=0x946c44)
            self.embed.set_footer(text="Click the button below to claim!")

            self.expired_embed = discord.Embed(  # Embed for when a drop expires after 1 hour
                title="Drop expired.",
                description=f"This **{'{:,}'.format(self.amount)}** bit drop has been added to the *Mega Drop*.",
                color=0x484a4a)
            self.expired_embed.set_footer(text="Do /megadrop to check the current pot!")

            self.timeout = 1800  # 30 minutes for the drop to be claimed

    async def prep_claim(self, drop):
        class ClaimDropButtons(discord.ui.View):

            def __init__(self, ismegadrop, *, timeout=self.timeout):
                super().__init__(timeout=timeout)
                self.claimed = False
                self.isMegadrop = ismegadrop
                self.megadrop: mM.Megadrop = mM.Megadrop.get(id=1)

            async def on_timeout(self) -> None:
                if self.claimed:
                    return

                await message.edit(embed=drop.expired_embed, view=None)

                if self.isMegadrop:
                    self.megadrop.times_missed += 1

                else:
                    self.megadrop.amount += drop.amount
                    self.megadrop.total_drops += 1
                    self.megadrop.total_drops_missed += 1
                    self.megadrop.COUNTER += 1

                self.megadrop.save()

            @discord.ui.button(label="CLAIM", emoji='📦', style=discord.ButtonStyle.green)
            async def claim_button(self, claim_interaction: discord.Interaction, button: discord.ui.Button):
                user = RequestUser(claim_interaction.user.id, interaction=claim_interaction)
                user.instance.drops_claimed += 1
                user.instance.save()

                if self.isMegadrop:
                    claimed_embed = discord.Embed(
                        title="🎉 THE MEGADROP HAS BEEN CLAIMED! 🎉",
                        description=f"{claim_interaction.user.name} {drop.description}\n"
                                    f"You have claimed **{'{:,}'.format(user.instance.drops_claimed)}** drops 📦",
                        color=drop.color
                    )
                    claimed_embed.add_field(name="Drops Cumulated",
                                            value=f"This megadrop was a combination of "
                                                  f"**{'{:,}'.format(self.megadrop.total_drops_missed)}** drops")
                    claimed_embed.add_field(name="Times Missed",
                                            value=f"This megadrop had gone unclaimed **{self.megadrop.times_missed}** "
                                                  f"times.")
                    claimed_embed.add_field(name="Last Winner",
                                            value=f"The last winner was {self.megadrop.last_winner}", inline=False)
                    claimed_embed.set_footer(text=f"The megadrop has been growing since: {self.megadrop.date_started}")
                    self.megadrop.last_winner = claim_interaction.user.name  # last winner is user who claimed it
                    self.megadrop.amount = self.megadrop.total_drops \
                        = self.megadrop.total_drops_missed = self.megadrop.times_missed = self.megadrop.COUNTER = 0
                    fmt = "%m-%d-%Y"  # Put current date into a format
                    now_time = datetime.now(timezone('US/Eastern'))
                    self.megadrop.date_started = now_time.strftime(fmt)

                else:
                    claimed_embed = discord.Embed(
                        title="This drop has been claimed!",
                        description=f"{claim_interaction.user.name} {drop.description}\n"
                                    f"You have claimed **{'{:,}'.format(user.instance.drops_claimed)}** drops 📦",
                        color=drop.color
                    )
                    claimed_embed.set_footer(text="Drops happen randomly and last for 30 minutes!")
                    self.megadrop.total_drops += 1
                    self.megadrop.COUNTER += 1

                self.megadrop.save()
                user.update_balance(int(drop.amount))
                await claim_interaction.response.edit_message(embed=claimed_embed, view=None)
                self.claimed = True

        message = await self.channel.send(embed=drop.embed, view=ClaimDropButtons(self.isMegadrop))


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
        drop_amount = randint(DROP_MIN, DROP_MAX)
        drop = Drop(channel, drop_amount, False)

        fmt = "%m-%d-%Y"  # Put current date into a format and add to bottom of embed
        now_time = datetime.now(timezone('US/Eastern'))
        megadrop, created = mM.Megadrop.get_or_create(id=1, defaults={"date_started": datetime.strftime(now_time, fmt)})
        if megadrop.COUNTER >= 150:
            roll = randint(1, 100)
            if roll in range(1, 2):
                # RELEASE MEGA DROP
                drop = Drop(channel, megadrop.amount, True)
                megadrop.COUNTER = 0
                megadrop.save()
        await drop.prep_claim(drop)
        self.drop_task.change_interval(minutes=randint(60, 120))  # Set next drop to come out 1-2 hours from now

    @drop_task.before_loop
    async def before_drop_tast(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(seconds_until_tasks())

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="megadrop", description="Check the current status of the Mega Drop")
    async def megadrop_status(self, interaction: discord.Interaction):
        megadrop: mM.Megadrop = mM.Megadrop.get(id=1)
        status_embed = discord.Embed(
            title="📦 MEGADROP STATUS 📦",
            color=0x45ffb1
        )
        status_embed.add_field(name="Current Pot",
                               value=f"{'{:,}'.format(megadrop.amount)} bits")
        status_embed.add_field(name="Drops Cumulated",
                               value=f"The megadrop has accumulated "
                                     f"**{'{:,}'.format(megadrop.total_drops_missed)}** drops")
        status_embed.add_field(name="Times Missed",
                               value=f"The megadrop has gone unclaimed **{megadrop.times_missed}** times.",
                               inline=False)
        status_embed.add_field(name="Last Winner",
                               value=megadrop.last_winner, inline=True)

        status_embed.set_footer(text=f"The megadrop has been growing since: {megadrop.date_started}")
        await interaction.response.send_message(embed=status_embed)


async def setup(bot):
    await bot.add_cog(DropsCog(bot))
