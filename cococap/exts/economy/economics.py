import asyncio
import math
import random
import discord
import randfacts

from random import randint
from discord import app_commands, Interaction
from discord.app_commands import Choice
from discord.ext import commands

from cococap.user import User
from cococap.item_models import Pets
from cococap.utils.messages import Cembed

from cococap.exts.economy.drops import DROP_AVERAGE
from cococap.constants import DiscordGuilds, TOO_RICH_TITLES


def calculate_economy_share(interaction):
    economy_users = {}
    column = mm.Users.money + mm.Users.bank
    query = mm.Users.select().order_by(column.desc())
    circulation = 0
    for user in query.objects():  # Loop through all users and add their networths to the database
        discordMemberObject = interaction.client.get_user(user.id)
        user_networth = user.bank + user.money
        if discordMemberObject.bot:
            continue
        else:
            economy_users[user.id] = {}
            economy_users[user.id]["networth"] = user_networth
        circulation += user_networth
    for (
        user
    ) in economy_users:  # Once circulation is done calculating, we can calculate percent holdings
        economy_users[user]["percent_of_economy"] = round(
            (economy_users[user]["networth"] / circulation) * 100, 2
        )

    return circulation, economy_users


def create_rank_string(interaction, index, user, xp, mode: int, advanced: bool = False):
    match mode:
        case 0:  # IF THE MODE IS SET TO BITS
            if advanced:
                circulation, economy_users = calculate_economy_share(interaction=interaction)
                user_percent_of_economy = economy_users[user.id]["percent_of_economy"]
                return f"{index}. {user.name} - {'{:,}'.format(user.bank + user.money)} | `{user_percent_of_economy}%`"
            return f"{index}. {user.name} - {'{:,}'.format(user.bank + user.money)}"
        case 1:  # IF THE MODE IS SET TO any XP MODE
            if advanced:
                return f"{index}. {user.name} - Level {'{:,}'.format(int(math.sqrt(xp).__floor__() / 10))} | `{'{:,}'.format(xp)} xp`"
            return (
                f"{index}. {user.name} - Level {'{:,}'.format(int(math.sqrt(xp).__floor__() / 10))}"
            )
        case 2:  # IF THE MODE IS SET TO DROPS
            if advanced:
                return (
                    f"{index}. {user.name} - {user.drops_claimed} "
                    f"drops | `~{'{:,}'.format(user.drops_claimed * DROP_AVERAGE)} bits`"
                )
            return f"{index}. {user.name} - {user.drops_claimed} drops claimed"


class EconomyCog(commands.Cog, name="Economy"):
    """Your primary stop for making and losing bits!"""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

    @app_commands.guilds(DiscordGuilds.PRIMARY_GUILD.value)
    @app_commands.command(name="profile", description="Check your profile, pets, etc.")
    async def bits(self, interaction: discord.Interaction):
        user = User(interaction.user.id)
        await user.load()

        rank = await user.get_user_rank()
        zone = user.get_zone()

        embed = Cembed(
            title=f"You are: `{rank.display_name}`",
            color=discord.Color.blue(),
            interaction=interaction,
            activity="profile",
        )

        skills = [
            {"emoji": ":crossed_swords:", "name": "COMBAT"},
            {"emoji": ":pick:", "name": "MINING"},
            {"emoji": ":evergreen_tree:", "name": "FORAGING"},
            {"emoji": ":fishing_pole_and_fish:", "name": "FISHING"},
            {"emoji": ":corn:", "name": "FARMING"},
        ]

        embed.add_field(
            name="Balances",
            value=f":money_with_wings: **BITS**: {user.get_field('purse'):,}\n"
            f":bank: **BANK**: {user.get_field('bank'):,}\n"
            f":coin: **TOKENS**: {user.get_field('tokens'):,}",
        )
        embed.set_footer(text=f"You are currently in {zone.display_name}")
        embed.set_thumbnail(url=interaction.user.display_avatar)
        await interaction.response.send_message(embed=embed)

    @app_commands.guilds(DiscordGuilds.PRIMARY_GUILD.value)
    @app_commands.command(name="beg")
    async def beg(self, interaction: Interaction):
        """Beg for some money! Must have less than 10,000 bits."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        max_balance = 10_000
        total_balance = user.get_field("purse") + user.get_field("bank")

        # If user has 10,000 bits or more in their purse or bank
        if total_balance >= max_balance:
            embed = Cembed(
                title=random.choice(TOO_RICH_TITLES),
                desc=f"You cannot beg if you have more than 10,000 bits\n"
                f"You have **{total_balance:,}** bits",
                color=discord.Color.red(),
                interaction=interaction,
                activity="begging",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        else:
            beg_amount = randint(100, 500)
            user.increase("money", beg_amount)

            embed = Cembed(
                title=f"Someone kind dropped {beg_amount} bits in your cup.",
                desc=f"You now have {'{:,}'.format(user.total_balance + beg_amount)} bits.",
                color=discord.Color.green(),
                interaction=interaction,
                activity="begging",
            )
            await interaction.response.send_message(embed=embed)


    # Command for the richest members in the server
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="top", description="See the top 10 players in each category!")
    @app_commands.describe(category="category of leaderboard")
    @app_commands.choices(
        category=[
            Choice(name="bits", value=0),
            Choice(name="combat", value=1),
            Choice(name="mining", value=2),
            Choice(name="foraging", value=3),
            Choice(name="fishing", value=4),
            Choice(name="drops", value=5),
        ]
    )
    async def top(
        self,
        interaction: discord.Interaction,
        category: Choice[int],
        advanced: bool | None,
    ):
        leaderboard_attributes = {
            0: {
                "column": mm.Users.money + mm.Users.bank,
                "title": ":money_with_wings: BITS LEADERBOARD :money_with_wings:",
                "color": discord.Color.blue(),
                "circulation": 0,
            },
            1: {
                "column": mm.Users.combat_xp,
                "title": ":crossed_swords: COMBAT LEADERBOARD :crossed_swords:",
                "color": discord.Color.dark_red(),
            },
            2: {
                "column": mm.Users.mining_xp,
                "title": ":pick: MINING LEADERBOARD :pick:",
                "color": discord.Color.dark_orange(),
            },
            3: {
                "column": mm.Users.foraging_xp,
                "title": ":evergreen_tree: FORAGING LEADERBOARD :evergreen_tree:",
                "color": discord.Color.dark_green(),
            },
            4: {
                "column": mm.Users.fishing_xp,
                "title": ":fishing_pole_and_fish: FISHING LEADERBOARD :fishing_pole_and_fish:",
                "color": discord.Color.dark_blue(),
            },
            5: {
                "column": mm.Users.drops_claimed,
                "title": ":package: DROPS LEADERBOARD :package:",
                "color": discord.Color.from_str("0xcc8c16"),
            },
        }
        category_index = leaderboard_attributes[category.value]
        description = ""
        user_place = None
        add_circulation = False

        query = mm.Users.select().order_by(category_index["column"].desc())

        INDEX_START = 1
        index = INDEX_START
        footer = None
        for user in query.objects():
            discordMemberObject = interaction.guild.get_member(user.id)
            if discordMemberObject.bot:  # Detect if the user is the bot in Discord
                footer = f"The house has made: {user.money:,} bits"
                continue  # Move on to next interation in the loop
            if category.value == 0:
                category_index["circulation"] += (
                    user.money + user.bank
                )  # Add user money and bank to circulation
                if index == 1:  # If the user is number one
                    role_to_add = discord.utils.get(interaction.guild.roles, name="RICHEST!")
                    for users in interaction.guild.members:
                        if (
                            role_to_add in users.roles
                        ):  # Remove the RICHEST! role from all other users
                            await users.remove_roles(role_to_add)
                    user_in_discord = discord.utils.get(interaction.guild.members, id=user.id)
                    await user_in_discord.add_roles(role_to_add)
            rank_string = None

            match category.value:
                case 0:
                    rank_string = create_rank_string(
                        interaction, index, user, None, mode=0, advanced=advanced
                    )
                    add_circulation = True
                case 1:
                    rank_string = create_rank_string(
                        interaction,
                        index,
                        user,
                        xp=user.combat_xp,
                        mode=1,
                        advanced=advanced,
                    )
                case 2:
                    rank_string = create_rank_string(
                        interaction,
                        index,
                        user,
                        xp=user.mining_xp,
                        mode=1,
                        advanced=advanced,
                    )
                case 3:
                    rank_string = create_rank_string(
                        interaction,
                        index,
                        user,
                        xp=user.foraging_xp,
                        mode=1,
                        advanced=advanced,
                    )
                case 4:
                    rank_string = create_rank_string(
                        interaction,
                        index,
                        user,
                        xp=user.fishing_xp,
                        mode=1,
                        advanced=advanced,
                    )
                case 5:
                    rank_string = create_rank_string(
                        interaction, index, user, None, mode=2, advanced=advanced
                    )

            if index <= 10 and (
                user.id == interaction.user.id
            ):  # If loop is over command user and still in top 10 :)
                description += f"**{rank_string}**\n"
            elif index > 10 and (
                user.id == interaction.user.id
            ):  # If loop is over command user and not in top 10 :(
                user_place = f"**{rank_string}**"
            elif index <= 10 and (
                user.id != interaction.user.id
            ):  # If loop is anyone else and still in top 10
                description += f"{rank_string}\n"
            elif index > 10 and user_place:  # Break if we find the user
                break
            else:
                pass
            index += 1
        if user_place:  # If the user didn't place top 10
            description += "\n" + "Your rank:" + "\n" + user_place
        top_embed = discord.Embed(
            title=category_index["title"],
            description=description,
            color=category_index["color"],
        )
        top_embed.set_footer(text=footer)
        if add_circulation:
            top_embed.add_field(
                name="Current Circulation",
                value=f"There are currently **{'{:,}'.format(category_index['circulation'])}** bits in the economy.",
            )
        await interaction.response.send_message(embed=top_embed)

    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="check-in")
    async def check_in(self, interaction: discord.Interaction):
        """Claim your work, daily, and weekly!"""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        class CheckInMenu(discord.ui.View):
            def __init__(self, *, timeout: float | None = 180):
                super().__init__(timeout=timeout)
                self.embed = Cembed(
                    title="Check-ins",
                    desc="Come back often to claim your rewards.",
                    color=discord.Color.dark_blue(),
                    interaction=interaction,
                    activity="checking in",
                )
                self.commands = {
                    "work": self.work_button,
                    "daily": self.daily_button,
                    "weekly": self.weekly_button,
                }
                for command_type in self.commands.keys():
                    ready, cooldown = user.check_cooldown(command_type)
                    self.embed.add_field(
                        name=command_type.capitalize(),
                        value="*Ready!*" if ready else f"{cooldown}",
                    )
                self.prepare_buttons()

            def prepare_buttons(self):
                # Check the readiness of each command and add it to the embed
                for enum, (command_type, command) in enumerate(self.commands.items()):
                    ready, cooldown = user.check_cooldown(command_type)
                    command.disabled = False if ready else True
                    command.style = (
                        discord.ButtonStyle.blurple if ready else discord.ButtonStyle.gray
                    )
                    command.emoji = "✅" if ready else "❌"

            @discord.ui.button(label="Work")
            async def work_button(self, interaction: Interaction, button: discord.ui.Button):
                rank = await user.get_user_rank()
                wage = rank.wage
                description = f":money_with_wings: **+{wage:,} bits**"

                # If the user has a pet, we need to apply the bits multiplier
                active_pet = user.get_active_pet()
                if active_pet is None:
                    await user.inc_purse(wage)
                else:
                    pet_data = Pets.get_by_id(active_pet["pet_id"])
                    pet_bonus = pet_data.work_bonus
                    pet_emoji = pet_data.emoji
                    description += f"\n{pet_emoji} **+{int(pet_bonus):,} bits**"
                    await user.inc_purse(wage + pet_bonus)

                self.embed.set_field_at(0, name="Work", value=description)
                # Put the command on cooldown!
                await user.set_cooldown("work")
                self.prepare_buttons()
                await interaction.response.edit_message(embed=self.embed, view=self)

            @discord.ui.button(label="Daily")
            async def daily_button(self, interaction: Interaction, button: discord.ui.Button):
                zone = user.get_zone()
                wage = 1 + zone.token_bonus
                description = f"**:coin: +{wage} tokens**"

                # Add bonus tokens if the user has an active pet
                active_pet = user.get_active_pet()
                if active_pet:
                    pet_data = Pets.get_by_id(active_pet["pet_id"])
                    pet_bonus = pet_data.daily_bonus
                    pet_emoji = pet_data.emoji
                    description += f"\n{pet_emoji} **+{int(pet_bonus)} tokens**"
                    await user.inc_tokens(tokens=wage + pet_bonus)
                else:
                    await user.inc_tokens(tokens=wage)

                # Calculate and add bank interest rate
                interest = 0.003 + 0.027 * (math.e ** (-(user.get_field("bank") / 20_000_000)))
                bonus = user.get_field("bank") * interest
                description += f"\n**:bank: +{int(bonus):,} bits**"
                await user.inc_bank(amount=int(bonus))

                # Update the embed
                self.embed.set_field_at(1, name="Daily", value=description)
                self.embed.add_field(
                    name=f"Random Fact", value=f"{randfacts.get_fact()}", inline=False
                )

                # Put the command on cooldown!
                await user.set_cooldown("daily")
                self.prepare_buttons()
                await interaction.response.edit_message(embed=self.embed, view=self)

            @discord.ui.button(label="Weekly", disabled=True)
            async def weekly_button(self, interaction: Interaction, button: discord.ui.Button):
                pass

        menu = CheckInMenu()

        await interaction.response.send_message(embed=menu.embed, view=menu)
        return

    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="deposit")
    @app_commands.describe(amount="amount of bits to deposit | enter max for all")
    async def deposit(self, interaction: discord.Interaction, amount: int | None):
        """Deposit some money into the bank for safekeeping."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        if not amount:
            amount = user.get_field("purse")
        if int(amount) > user.get_field("purse"):
            await interaction.response.send_message(
                f"You don't have enough bits to deposit. "
                f"Balance: {user.get_field('purse'):,} bits"
            )
            return
        elif int(amount) == 0:
            await interaction.response.send_message(
                "You cannot deposit **0** bits...", ephemeral=True
            )
            return
        elif int(amount) < 0:
            await interaction.response.send_message(
                "You cannot deposit negative bits either!", ephemeral=True
            )
            return
        elif int(amount) < 250:
            await interaction.response.send_message(
                "Sorry, deposits must be over 250 bits.", ephemeral=True
            )
            return
        elif type(amount) == str:
            await interaction.response.send_message(
                "Please input an amount to deposit.", ephemeral=True
            )
        else:
            await user.inc_purse(amount=-amount)
            await user.inc_bank(amount=amount)
            embed = Cembed(
                colour=discord.Color.dark_blue(), interaction=interaction, activity="depositing"
            )
            embed.add_field(
                name="Deposit made!",
                value=f"You have deposited **{'{:,}'.format(amount)}** bits",
            )
            embed.set_author(
                name=f"{interaction.user.name} - deposit", icon_url=interaction.user.display_avatar
            )
            await interaction.response.send_message(embed=embed)

    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="withdraw", description="Withdraw bits from the bank.")
    @app_commands.describe(amount="amount of bits you want to withdraw")
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        bank = user.get_field("bank")
        if amount in ["all", "max"]:
            amount = bank
        amount = int(amount)

        # Validate the withdraw amount
        if int(amount) > bank:
            await interaction.response.send_message(
                f"You don't have that many bits in your account. " f"Bank Balance: {bank:,} bits",
                ephemeral=True,
            )
            return
        elif int(amount) == 0:
            await interaction.response.send_message(
                "You cannot withdraw **0** bits...", ephemeral=True
            )
            return
        elif int(amount) < 0:
            await interaction.response.send_message(
                "You cannot withdraw negative bits either!", ephemeral=True
            )
            return

        settings = user.get_field("settings")
        if settings["withdraw_warning"]:
            warning_embed = Cembed(
                title="Are you sure?",
                desc="Withdrawing just to gamble more might not be a good idea.",
                color=discord.Color.dark_red(),
                interaction=interaction,
                activity="withdrawing",
            )
            warning_embed.set_footer(text=f"User: {interaction.user.name}")

            class WithdrawButtons(discord.ui.View):
                def __init__(self, *, timeout=180):
                    super().__init__(timeout=timeout)

                @discord.ui.button(label="Yes, withdraw", style=discord.ButtonStyle.green)
                async def green_button(
                    self,
                    confirm_interaction: discord.Interaction,
                    button: discord.ui.Button,
                ):
                    if confirm_interaction.user != interaction.user:
                        return

                    await user.inc_bank(amount=-amount)
                    await user.inc_purse(amount=amount)
                    withdraw_embed = Cembed(
                        colour=discord.Color.dark_blue(),
                        interaction=confirm_interaction,
                        activity="withdrawing",
                    )
                    withdraw_embed.add_field(
                        name="Withdrawal made!",
                        value=f"You withdrew **{'{:,}'.format(amount)}** bits",
                    )
                    await confirm_interaction.response.edit_message(embed=withdraw_embed, view=None)
                    return

                @discord.ui.button(label="No", style=discord.ButtonStyle.red)
                async def red_button(
                    self, deny_interaction: discord.Interaction, button: discord.ui.Button
                ):
                    if deny_interaction.user != interaction.user:
                        return
                    cancel_embed = Cembed(
                        title="Withdraw cancelled",
                        desc="Withdraw was either cancelled or timed out.",
                        interaction=deny_interaction,
                        activity="cancelled withdraw",
                    )
                    await deny_interaction.response.edit_message(embed=cancel_embed, view=None)
                    await asyncio.sleep(3)
                    return

            await interaction.response.send_message(embed=warning_embed, view=WithdrawButtons())
        else:
            await user.inc_bank(amount=-amount)
            await user.inc_purse(amount=amount)
            withdraw_embed = Cembed(
                colour=discord.Color.dark_blue(), interaction=interaction, activity="withdrawing"
            )
            withdraw_embed.add_field(
                name="Withdrawal made!",
                value=f"You withdrew **{'{:,}'.format(amount)}** bits",
            )
            await interaction.response.send_message(embed=withdraw_embed, view=None)
            return

    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="pay")
    @app_commands.describe(recipient="discord user you want to pay", amount="amount")
    async def pay(self, interaction: discord.Interaction, recipient: discord.Member, amount: int):
        """Pay someone else some bits, if you're feeling nice!"""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        # If they try to bet more than they have in their account.
        if int(amount) < 100:
            titles = [
                "Pyramid schemes are not allowed",
                "Trying to break the system, are we?",
                "This is what we call pulling a *Botski*",
            ]
            embed = Cembed(
                title=random.choice(titles),
                desc="To avoid '*beg farming*' tactics, you can only send someone amounts over **100**",
                color=discord.Color.red(),
                interaction=interaction,
                activity="paying",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        elif int(amount) > user.get_field("purse"):
            await interaction.response.send_message(
                f"You don't have enough bits to send. Balance: "
                f"{user.get_field('purse'):,} bits",
                ephemeral=True,
            )
            return
        elif int(amount) == 0:
            await interaction.response.send_message(
                "You cannot send someone **0** bits...", ephemeral=True
            )
            return
        elif int(amount) < 0:
            await interaction.response.send_message(
                "You cannot send someone negative bits either!", ephemeral=True
            )
            return
        payee = User(recipient.id)
        await payee.load()
        await user.inc_purse(amount=int(-amount))
        await payee.inc_purse(amount=amount)

        embed = Cembed(colour=discord.Color.purple())
        embed.add_field(
            name="Payment sent!",
            value=f"You have sent {recipient.mention} **{int(amount):,}** bits",
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
