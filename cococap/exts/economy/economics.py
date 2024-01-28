import asyncio
import math
import random
from typing import Any, Coroutine, Optional
import discord
import randfacts

from random import randint
from discord import app_commands, Interaction
from discord.app_commands import Choice
from discord.ext import commands

from cococap.user import User
from cococap.item_models import Areas, Pets
from cococap.utils.menus import Menu

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
    @app_commands.command(name="play")
    async def play(self, interaction: Interaction):
        """The general play command which gives access to all functions of the bot."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        # PROFILE MENU ---------------------------------------------------------------
        class MainMenu(Menu):
            def __init__(self, embed):
                super().__init__(timeout=60, embed=embed)

            @discord.ui.button(label="Check-ins", emoji="✅", style=discord.ButtonStyle.blurple)
            async def check_in_button(
                self, interaction: discord.Interaction, button: discord.ui.Button
            ):
                await interaction.response.edit_message(
                    embed=check_in_menu.embed, view=check_in_menu
                )

            # CHECKINS MENU ---------------------------------------------------------------

            class WorkButton(discord.ui.Button):
                def __init__(self, ready):
                    super().__init__(
                        label="Work",
                        emoji="✅" if ready else "❌",
                        style=discord.ButtonStyle.green if ready else discord.ButtonStyle.gray,
                        disabled=False if ready else True,
                    )

                async def callback(self, interaction: Interaction):
                    await EconomyCog.work(interaction)

        embed = discord.Embed(
            title=f"{user.get_user_rank().display_name} *{user.document.name}*",
            color=discord.Color.blue(),
        )
        embed.set_author(
            name=f"{user.document.name} - profile",
            icon_url=interaction.user.display_avatar,
        )
        embed.add_field(
            name="CURRENT AREA",
            value=f"**Area**: {Areas.get_by_id(user.get_field('zone')).display_name}",
            inline=False,
        )

        embed.add_field(
            name="MONEY",
            value=f":money_with_wings: **BITS**: {user.get_field('purse'):,}\n"
            f":bank: **BANK**: {user.get_field('bank'):,}\n"
            f":coin: **TOKENS**: {user.get_field('tokens'):,}",
        )
        embed.set_thumbnail(url=interaction.user.display_avatar)

        main_menu = MainMenu(embed=embed)
        check_in_menu = CheckInMenu(prev_menu=main_menu)

        await interaction.response.send_message(embed=embed, view=MainMenu(embed=embed))

    @app_commands.guilds(DiscordGuilds.PRIMARY_GUILD.value)
    @app_commands.command(name="beg")
    async def beg(self, interaction: Interaction):
        """Beg for some money! Must have less than 10,000 bits."""

        # Initialize user object upon request
        user: Users = Users.new(interaction.user.id, interaction)
        max_balance = 10000

        # If user has 10,000 bits or more in their purse or bank
        if user.total_balance >= max_balance:
            embed = discord.Embed(
                title=random.choice(TOO_RICH_TITLES),
                description=f"You cannot beg if you have more than 10,000 bits\n"
                f"You have **{'{:,}'.format(user.total_balance)}** bits",
                color=discord.Color.red(),
            ).set_footer(text=f"User: {interaction.user.name}")

            await interaction.response.send_message(embed=embed)

        else:
            beg_amount = randint(100, 500)
            user.increase("money", beg_amount)

            embed = discord.Embed(
                title=f"Someone kind dropped {beg_amount} bits in your cup.",
                description=f"You now have {'{:,}'.format(user.total_balance + beg_amount)} bits.",
                color=discord.Color.green(),
            ).set_footer(text=f"User: {interaction.user.name}")

            await interaction.response.send_message(embed=embed)

    #
    # @app_commands.guilds(856915776345866240, 977351545966432306)
    # @app_commands.command(
    #     name="unscramble",
    #     description="Try to unscramble a word for some bits. "
    #     "The longer the word, the more bits you get!",
    # )
    # async def unscramble(self, interaction: discord.Interaction):
    #     user = RequestUser(
    #         interaction.user.id, interaction=interaction
    #     )  # Initialize user object upon request

    #     def get_word():  # Function to pick a word from the word list
    #         random_word = random.choice(words)
    #         for (
    #             letter
    #         ) in (
    #             random_word
    #         ):  # If any letter in the word is uppercase, rerun the function
    #             if letter.isupper():
    #                 return get_word()
    #         while (
    #             len(random_word) < 4
    #         ):  # If the word is shorter than 4 letters, rerun the function
    #             return get_word()
    #         random_word = list(random_word)
    #         random_word.remove("\n")
    #         random_word = "".join(letter for letter in random_word)
    #         shuffled_word = "".join(random.sample(random_word, len(random_word)))
    #         while shuffled_word == random_word:
    #             shuffled_word = "".join(random.sample(random_word, len(random_word)))
    #         return random_word, shuffled_word

    #     word, scrambled_word = get_word()
    #     time_limit = 1.4 ** len(word)
    #     reward = len(word) * (10 * len(word) ** 2) + 300
    #     unscramble_prompt_embed = discord.Embed(
    #         title="Unscramble!",
    #         description=f"You will have {time_limit.__round__()} seconds to unscramble the following word!",
    #         color=0xA0A39D,
    #     )
    #     shuffled_word_embed = discord.Embed(
    #         title="Unscramble!",
    #         description=f"You will have {time_limit.__round__()} seconds to unscramble the following word!\n"
    #         f"***{scrambled_word}***",
    #         color=0xA0A39D,
    #     )
    #     await interaction.response.send_message(embed=unscramble_prompt_embed)
    #     await asyncio.sleep(2)
    #     await interaction.edit_original_response(embed=shuffled_word_embed)

    #     def check(m):
    #         return (
    #             m.content.lower() == word
    #             and m.author == interaction.user
    #             and m.channel == interaction.channel
    #         )

    #     try:  # Waits for a guess at the correct word
    #         guess = await self.bot.wait_for(
    #             "message", timeout=time_limit.__round__(), check=check
    #         )
    #         embed = None
    #         if guess.content.lower() == word:  # If they type in the correct word
    #             correct_word_embed = discord.Embed(
    #                 title="Unscramble!",
    #                 description=f"Correct!\n" f"***{scrambled_word}*** - {word}",
    #                 color=0xA0F09C,
    #             )
    #             correct_word_embed.add_field(
    #                 name="Reward", value=f"**{reward:,}** bits"
    #             )
    #             embed = correct_word_embed
    #             user.update_balance(reward)
    #     except asyncio.TimeoutError:
    #         too_slow_embed = discord.Embed(
    #             title="Unscramble!",
    #             description=f"Too slow!\n" f"***{scrambled_word}*** - {word}",
    #             color=0xA8332F,
    #         )
    #         too_slow_embed.set_footer(text=f"User: {interaction.user.name}")
    #         embed = too_slow_embed
    #     embed.set_footer(text=f"User: {interaction.user.name}")
    #     await interaction.edit_original_response(embed=embed)

    @app_commands.guilds(DiscordGuilds.PRIMARY_GUILD.value)
    @app_commands.command(name="profile", description="Check your profile, pets, etc.")
    async def bits(self, interaction: discord.Interaction):
        user_data = get_user_data(interaction.user.id, backrefs=True)
        user_name = get_user_name(interaction.user.id)
        user_rank = get_user_rank(interaction.user.id, interaction)

        profile_embed = discord.Embed(
            title=f"{user_rank['display_name']} *{user_name}*",
            color=discord.Color.from_str("0x262625"),
        )

        profile_embed.set_author(
            name=f"{user_name} - profile", icon_url=interaction.user.display_avatar
        )

        profile_embed.add_field(
            name="CURRENT AREA",
            value=f"**Area**: {user_data['area_id']['display_name']}",
        )

        skills = [
            {"emoji": ":crossed_swords:", "name": "COMBAT", "class": Combat},
            {"emoji": ":pick:", "name": "MINING", "class": Mining},
            {"emoji": ":evergreen_tree:", "name": "FORAGING", "class": Foraging},
            {"emoji": ":fishing_pole_and_fish:", "name": "FISHING", "class": Fishing},
            {"emoji": ":corn:", "name": "FARMING", "class": Farming},
        ]

        profile_embed.add_field(
            name="MONEY",
            value=f":money_with_wings: **BITS**: {user_data['money']:,}\n"
            f":bank: **BANK**: {user_data['bank']:,}\n"
            f":coin: **TOKENS**: {user_data['tokens']:,}",
        )
        profile_embed.set_footer(text="Use /work to get bits")
        profile_embed.set_thumbnail(url=interaction.user.display_avatar)
        await interaction.response.send_message(embed=profile_embed)

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
                self.embed = discord.Embed(
                    title="Check-ins",
                    description="Come back often to claim your rewards.",
                    color=discord.Color.dark_blue(),
                )
                self.embed.set_author(
                    name=f"{user.get_field('name')} - checking in",
                    icon_url=interaction.user.display_avatar,
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
                rank = user.get_user_rank()
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
                zone = Areas.get_by_id(user.get_field("zone"))
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

                # Add appropriate fields
                # # self.embed.add_field(
                #     name="Your Tokens",
                #     value=f"You have **{int(user.get_field('tokens')):,}** tokens",
                # )

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
            await interaction.response.send_message("You cannot deposit **0** bits...", ephemeral=True)
            return
        elif int(amount) < 0:
            await interaction.response.send_message("You cannot deposit negative bits either!", ephemeral=True)
            return
        elif int(amount) < 250:
            await interaction.response.send_message("Sorry, deposits must be over 250 bits.", ephemeral=True)
            return
        elif type(amount) == str:
            await interaction.response.send_message("Please input an amount to deposit.", ephemeral=True)
        else:
            await user.inc_purse(amount=-amount)
            await user.inc_bank(amount=amount)
            embed = discord.Embed(colour=discord.Color.dark_blue())
            embed.add_field(
                name="Deposit made!",
                value=f"You have deposited **{'{:,}'.format(amount)}** bits",
            )
            embed.set_author(name=f"{interaction.user.name} - deposit", icon_url=interaction.user.display_avatar)
            await interaction.response.send_message(embed=embed)

    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="withdraw", description="Withdraw bits from the bank.")
    @app_commands.describe(amount="amount of bits you want to withdraw")
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        
        bank = user.get_field('bank')
        if amount in ["all", "max"]: amount = bank
        amount = int(amount)
        
        # Validate the withdraw amount
        if int(amount) > bank:
            await interaction.response.send_message(
                f"You don't have that many bits in your account. "
                f"Bank Balance: {bank:,} bits", ephemeral=True
            )
            return
        elif int(amount) == 0:
            await interaction.response.send_message("You cannot withdraw **0** bits...", ephemeral=True)
            return
        elif int(amount) < 0:
            await interaction.response.send_message("You cannot withdraw negative bits either!", ephemeral=True)
            return
        
        settings = user.get_field('settings')
        if settings['withdraw_warning']:
            warning_embed = discord.Embed(
                title="Are you sure?",
                description="Withdrawing just to gamble more might not be a good idea.",
                color=discord.Color.dark_red(),
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
                    withdraw_embed = discord.Embed(colour=discord.Color.dark_blue())
                    withdraw_embed.add_field(
                        name="Withdrawal made!",
                        value=f"You withdrew **{'{:,}'.format(amount)}** bits",
                    )
                    withdraw_embed.set_author(
                        name=f"{interaction.user.name} - " f"withdrawal",
                        icon_url=interaction.user.display_avatar,
                    )
                    await confirm_interaction.response.edit_message(embed=withdraw_embed, view=None)
                    return

                @discord.ui.button(label="No", style=discord.ButtonStyle.red)
                async def red_button(
                    self, deny_interaction: discord.Interaction, button: discord.ui.Button
                ):
                    if deny_interaction.user != interaction.user:
                        return
                    cancel_embed = discord.Embed(
                        title="Withdraw cancelled",
                        description="Withdraw was either cancelled or timed out.",
                    )
                    cancel_embed.set_author(
                        name=f"{interaction.user.name} - " f"withdrawal",
                        icon_url=interaction.user.display_avatar,
                    )
                    await deny_interaction.response.edit_message(embed=cancel_embed, view=None)
                    await asyncio.sleep(3)
                    
            await interaction.response.send_message(embed=warning_embed, view=WithdrawButtons())
            
        await user.inc_bank(amount=-amount)
        await user.inc_purse(amount=amount)
        withdraw_embed = discord.Embed(colour=discord.Color.dark_blue())
        withdraw_embed.add_field(
            name="Withdrawal made!",
            value=f"You withdrew **{'{:,}'.format(amount)}** bits",
        )
        withdraw_embed.set_author(
            name=f"{interaction.user.name} - " f"withdrawal",
            icon_url=interaction.user.display_avatar,
        )
        await interaction.response.send_message(embed=withdraw_embed, view=None)
        return

    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(
        name="pay", description="Pay someone else some bits, if you're feeling nice!"
    )
    @app_commands.describe(
        payee="discord user you want to pay", amount="amount of bits to pay the user"
    )
    async def pay(self, interaction: discord.Interaction, payee: discord.Member, amount: int):
        user = RequestUser(interaction.user.id, interaction=interaction)
        # If they try to bet more than they have in their account.
        if int(amount) < 100:
            titles = [
                "Pyramid schemes are not allowed",
                "Trying to break the system, are we?",
                "This is what we call pulling a *Botski*",
            ]
            embed = discord.Embed(
                title=random.choice(titles),
                description="To avoid '*beg farming*' tactics, you can only send someone amounts over **100**",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed)
            return
        elif int(amount) > user.instance.money:
            await interaction.response.send_message(
                f"You don't have enough bits to send. Balance: "
                f"{'{:,}'.format(user.instance.money)} bits"
            )
            return
        elif int(amount) == 0:
            await interaction.response.send_message("You cannot send someone **0** bits...")
            return
        elif int(amount) < 0:
            await interaction.response.send_message("You cannot send someone negative bits either!")
            return
        try:
            user.instance.money -= int(amount)
            user.instance.save()
            payee_in_database = mm.Users.get_by_id(payee.id)
            payee_in_database.money += int(amount)
            payee_in_database.save()
            embed = discord.Embed(colour=discord.Color.purple())
            embed.add_field(
                name="Payment sent!",
                value=f"You have sent {payee.mention} **{'{:,}'.format(int(amount))}** bits",
            )
            await interaction.response.send_message(embed=embed)
        except pw.DoesNotExist:
            embed = discord.Embed(title="This user is not yet registered.")
            await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
