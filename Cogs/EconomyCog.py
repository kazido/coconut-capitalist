import typing
from typing import Union
from random import shuffle
from PIL import Image, ImageFont, ImageDraw
from io import BytesIO
import asyncio
import math
import pathlib
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
from Cogs.ErrorHandler import registered, missing_perks
from ClassLibrary import *
from ClassLibrary2 import *

project_files = pathlib.Path.cwd() / 'EconomyBotProjectFiles'
with open(project_files / 'words.txt', 'r') as f:
    words = f.readlines()


class EconomyCog(commands.Cog, name='Economy'):
    """Your primary stop for making and losing bits!"""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="beg", description="Beg for some money! Must have less than 10000 bits.")
    async def beg(self, interaction: discord.Interaction):
        user = RequestUser(interaction.user.id, interaction=interaction)  # Initialize user object upon request
        titles = ["Begging is for poor people...", "You're already rich!", "Really?"]  # Possible embed titles
        max_balance = 10000
        user_total_balance = user.instance.money + user.instance.bank
        if user_total_balance >= max_balance:  # If user has 10000 bits or more in their purse or bank

            embed = discord.Embed(
                title=random.choice(titles),
                description=f"You cannot beg if you have more than 10,000 bits\n"
                            f"You have **{'{:,}'.format(user_total_balance)}** bits",
                color=discord.Color.red()
            )

            embed.set_footer(text=f"User: {interaction.user.name}")
            await interaction.response.send_message(embed=embed)
        else:
            beg_amount = randint(100, 500)  # Randomly generate how many bits they will get
            await user.update_balance(beg_amount)

            embed = discord.Embed(
                title=f"Someone kind dropped {beg_amount} bits in your cup.",
                description=f"You now have {'{:,}'.format(user_total_balance + beg_amount)} bits.",
                color=discord.Color.green()
            )

            embed.set_footer(text=f"User: {interaction.user.name}")
            await interaction.response.send_message(embed=embed)

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="unscramble", description="Try to unscramble a word for some bits. "
                                                         "The longer the word, the more bits you get!")
    async def unscramble(self, interaction: discord.Interaction):
        user = RequestUser(interaction.user.id, interaction=interaction)  # Initialize user object upon request

        def get_word():  # Function to pick a word from the word list
            random_word = random.choice(words)
            for letter in random_word:  # If any letter in the word is uppercase, rerun the function
                if letter.isupper():
                    return get_word()
            while len(random_word) < 4:  # If the word is shorter than 4 letters, rerun the function
                return get_word()
            random_word = list(random_word)
            random_word.remove('\n')
            random_word = ''.join(letter for letter in random_word)
            shuffled_word = ''.join(random.sample(random_word, len(random_word)))
            while shuffled_word == random_word:
                shuffled_word = ''.join(random.sample(random_word, len(random_word)))
            return random_word, shuffled_word

        word, scrambled_word = get_word()
        time_limit = 1.4 ** len(word)
        reward = len(word) * 70
        unscramble_prompt_embed = discord.Embed(
            title="Unscramble!",
            description=f"You will have {time_limit.__round__()} seconds to unscramble the following word!",
            color=0xa0a39d
        )
        shuffled_word_embed = discord.Embed(
            title="Unscramble!",
            description=f"You will have {time_limit.__round__()} seconds to unscramble the following word!\n"
                        f"***{scrambled_word}***",
            color=0xa0a39d
        )
        await interaction.response.send_message(embed=unscramble_prompt_embed)
        await asyncio.sleep(2)
        await interaction.edit_original_response(embed=shuffled_word_embed)

        def check(m):
            return m.content.lower() == word and m.author == interaction.user and m.channel == interaction.channel

        try:  # Waits for a guess at the correct word
            guess = await self.bot.wait_for("message", timeout=time_limit.__round__(), check=check)
            embed = None
            if guess.content.lower() == word:  # If they type in the correct word
                correct_word_embed = discord.Embed(
                    title="Unscramble!",
                    description=f"Correct!\n"
                                f"***{scrambled_word}*** - {word}",
                    color=0xa0f09c
                )
                correct_word_embed.add_field(name="Reward", value=f"**{reward}** bits")
                embed = correct_word_embed
                user.update_balance(reward)
        except asyncio.TimeoutError:
            too_slow_embed = discord.Embed(
                title="Unscramble!",
                description=f"Too slow!\n"
                            f"***{scrambled_word}*** - {word}",
                color=0xa8332f
            )
            too_slow_embed.set_footer(text=f"User: {interaction.user.name}")
            embed = too_slow_embed
        embed.set_footer(text=f"User: {interaction.user.name}")
        await interaction.edit_original_response(embed=embed)

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="balance", description="Check your balance!")
    async def bits(self, interaction: discord.Interaction):
        user = RequestUser(interaction.user.id, interaction=interaction)
        bits = user.instance.money
        bank = user.instance.bank
        tokens = user.instance.tokens
        level = (math.sqrt(user.instance.xp / 100)).__floor__()
        embed = discord.Embed(title=f"{user.rank.capitalize()} *{interaction.user.name}*", color=discord.Color.yellow())
        embed.set_author(name=f"{interaction.user.name} - profile", icon_url=interaction.user.display_avatar)
        embed.add_field(name="PROGRESS", value=f"**Level**: {level}\n"
                                               f"**XP**: {user.instance.xp}/{int(((level + 1) ** 2) * 100)}\n"
                                               f"**Area**: COMING SOON",
                        inline=False)
        embed.add_field(name="SKILLS", value=f":crossed_swords: **COMBAT**: COMING SOON\n"
                                             f":pick: **MINING**: COMING SOON\n"
                                             f":evergreen_tree: **FORAGING**: COMING SOON\n"
                                             f":fishing_pole_and_fish: **FISHING**: COMING SOON",
                        inline=False)
        embed.add_field(name="EQUIPMENT", value=f"COMING SOON\n"
                                                f"COMING SOON\n"
                                                f"COMING SOON")
        embed.add_field(name="MONEY", value=f":money_with_wings: **BITS**: {'{:,}'.format(bits)}\n"
                                            f":bank: **BANK**: {'{:,}'.format(bank)}\n"
                                            f":coin: **TOKENS**: {'{:,}'.format(tokens)}")
        embed.set_footer(text="Use -beg, -work, or -unscramble to get bits")
        await interaction.response.send_message(embed=embed)

    # Command for the richest members in the server
    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="top", description="See the top 10 players in each category!")
    @app_commands.describe(category='category of leaderboard')
    @app_commands.choices(category=[
        Choice(name='bits', value=0),
        Choice(name='combat', value=1),
        Choice(name='mining', value=2),
        Choice(name='foraging', value=3),
        Choice(name='fishing', value=4)
    ])
    async def top(self, interaction: discord.Interaction, category: Choice[int]):
        top_embed = title = color = column = None
        description = ''
        prefix = ''
        unit = 'xp'
        match category.value:
            case 0:
                column = mm.Users.money + mm.Users.bank
                title = ":money_with_wings: BITS LEADERBOARD :money_with_wings:"
                color = discord.Color.blue()
                prefix = '$'
                unit = ''
            case 1:
                column = mm.Users.combat_xp
                title = ":crossed_swords: COMBAT LEADERBOARD :crossed_swords:"
                color = discord.Color.dark_red()
            case 2:
                column = mm.Users.mining_xp
                title = ":pick: MINING LEADERBOARD :pick:"
                color = discord.Color.dark_orange()
            case 3:
                column = mm.Users.foraging_xp
                title = ":evergreen_tree: FORAGING LEADERBOARD :evergreen_tree:"
                color = discord.Color.dark_green()
            case 4:
                column = mm.Users.fishing_xp
                title = ":fishing_pole_and_fish: FISHING LEADERBOARD :fishing_pole_and_fish:"
                color = discord.Color.dark_blue()

        query = mm.Users.select().order_by(column.desc())
        index = 1
        circulation = 0
        attribute = user_place = None
        user_in_top_10 = False
        for user in query.objects():
            if user.id == 956000805578768425:
                continue
            circulation += user.money + user.bank
            if index > 10 and user_in_top_10:
                break
            elif index > 10 and user_in_top_10 is False and user.id == interaction.user.id:
                user_place = f"**{index}. {user.name} - {prefix}{'{:,}'.format(attribute)} {unit}**\n"
                break
            elif index > 10 and user_in_top_10 is False:
                continue
            match title:
                case ":money_with_wings: BITS LEADERBOARD :money_with_wings:":
                    attribute = user.bank + user.money
                case ":crossed_swords: COMBAT LEADERBOARD :crossed_swords:":
                    attribute = user.combat_xp
                case ":pick: MINING LEADERBOARD :pick:":
                    attribute = user.mining_xp
                case ":evergreen_tree: FORAGING LEADERBOARD :evergreen_tree:":
                    attribute = user.foraging_xp
                case ":fishing_pole_and_fish: FISHING LEADERBOARD :fishing_pole_and_fish:":
                    attribute = user.fishing_xp
            if user.id == interaction.user.id:
                user_in_top_10 = True
                description += f"**{index}. {user.name} - {prefix}{'{:,}'.format(attribute)} {unit}**\n"
            else:
                description += f"{index}. {user.name} - {prefix}{'{:,}'.format(attribute)} {unit}\n"
            index += 1
        if user_place:
            description += '\n' + 'Your rank:' + '\n' + user_place
        top_embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        await interaction.response.send_message(embed=top_embed)

    # Daily command, should give x amount of credits per day.
    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="daily", description="Get some tokens every 21 hours to rank up.")
    async def daily(self, interaction: discord.Interaction):
        # Initialize user object to grab from database
        user = RequestUser(interaction.user.id, interaction=interaction)
        await user.check_ins(interaction, 'daily')

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name='work', description="Work every 6 hours to earn some bits.")
    async def work(self, interaction: discord.Interaction):
        user = RequestUser(interaction.user.id, interaction=interaction)
        await user.check_ins(interaction, 'work')

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="deposit", description="Deposit some money into the bank for safekeeping.")
    @app_commands.describe(amount='amount of bits to deposit | enter max for all')
    async def deposit(self, interaction: discord.Interaction, amount: int | None):
        user = RequestUser(interaction.user.id, interaction=interaction)
        if not amount:
            amount = user.instance.money
        if int(amount) > user.instance.money:
            await interaction.response.send_message(f"You don't have enough bits to deposit. "
                                                    f"Balance: {'{:,}'.format(user.instance.money)} bits")
            return
        elif int(amount) == 0:
            await interaction.response.send_message("You cannot deposit **0** bits...")
            return
        elif int(amount) < 0:
            await interaction.response.send_message("You cannot deposit negative bits either!")
            return
        elif int(amount) < 250:
            await interaction.response.send_message("Sorry, deposits must be over 250 bits.")
            return
        elif type(amount) == str:
            await interaction.response.send_message("Please input an amount to deposit.")
        else:
            user.instance.money -= amount
            user.instance.bank += amount
            embed = discord.Embed(colour=discord.Color.dark_blue())
            embed.add_field(name="Deposit made!", value=f"You have deposited **{'{:,}'.format(amount)}** bits")
            await interaction.response.send_message(embed=embed)
            user.instance.save()

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="withdraw", description="Withdraw bits from the bank.")
    @app_commands.describe(amount='amount of bits you want to withdraw')
    async def withdraw(self, interaction: discord.Interaction, amount: int):
        user = RequestUser(interaction.user.id, interaction=interaction)
        warning_embed = discord.Embed(title="Are you sure?",
                                      description="Withdrawing just to gamble more might not be a good idea.",
                                      color=discord.Color.dark_red())
        warning_embed.set_footer(text=f"User: {interaction.user.name}")

        class WithdrawButtons(discord.ui.View):
            def __init__(self, *, timeout=180):
                super().__init__(timeout=timeout)

            @discord.ui.button(label="Yes, withdraw", style=discord.ButtonStyle.green)
            async def green_button(self, confirm_interaction: discord.Interaction, button: discord.ui.Button):
                if confirm_interaction.user != interaction.user:
                    return
                if int(amount) > user.instance.bank:
                    await confirm_interaction.response.send_message(f"You don't have that many bits in your account. "
                                                            f"Bank Balance: {'{:,}'.format(user.instance.bank)} bits")
                    return
                user.instance.bank -= amount
                user.instance.money += amount
                withdraw_embed = discord.Embed(colour=discord.Color.dark_blue())
                withdraw_embed.add_field(name="Withdrawal made!",
                                         value=f"You withdrew **{'{:,}'.format(amount)}** bits")
                withdraw_embed.set_author(name=f"{interaction.user.name} - "
                                               f"withdrawal", icon_url=interaction.user.display_avatar)
                await confirm_interaction.response.edit_message(embed=withdraw_embed, view=None)
                user.instance.save()

            @discord.ui.button(label="No", style=discord.ButtonStyle.red)
            async def red_button(self, deny_interaction: discord.Interaction, button: discord.ui.Button):
                if deny_interaction.user != interaction.user:
                    return
                cancel_embed = discord.Embed(title="Withdraw cancelled",
                                             description="Withdraw was either cancelled or timed out.")
                cancel_embed.set_author(name=f"{interaction.user.name} - "
                                             f"withdrawal", icon_url=interaction.user.display_avatar)
                await deny_interaction.response.edit_message(embed=cancel_embed, view=None)
                await asyncio.sleep(3)

        if int(amount) > user.instance.bank:
            await interaction.response.send_message(f"You don't have that many bits in your account. "
                           f"Bank Balance: {'{:,}'.format(user.instance.bank)} bits")
            return
        elif int(amount) == 0:
            await interaction.response.send_message("You cannot withdraw **0** bits...")
            return
        elif int(amount) < 0:
            await interaction.response.send_message("You cannot withdraw negative bits either!")
            return

        await interaction.response.send_message(embed=warning_embed, view=WithdrawButtons())

    @registered()
    @missing_perks()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="pay", description="Pay someone else some bits, if you're feeling nice!")
    @app_commands.describe(payee='discord user you want to pay', amount='amount of bits to pay the user')
    async def pay(self, interaction: discord.Interaction, payee: discord.Member, amount: int):
        user = RequestUser(interaction.user.id, interaction=interaction)
        # If they try to bet more than they have in their account.
        if int(amount) < 100:
            titles = ["Pyramid schemes are not allowed",
                      "Trying to break the system, are we?",
                      "This is what we call pulling a *Botski*"]
            embed = discord.Embed(
                title=random.choice(titles),
                description="To avoid '*beg farming*' tactics, you can only send someone amounts over **100**",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            return
        elif int(amount) > user.instance.money:
            await interaction.response.send_message(f"You don't have enough bits to send. Balance: "
                                                    f"{'{:,}'.format(user.instance.money)} bits")
            return
        elif int(amount) == 0:
            await interaction.response.send_message("You cannot send someone **0** bits...")
            return
        elif int(amount) < 0:
            await interaction.response.send_message("You cannot send someone negative bits either!")
            return
        try:
            payee_in_database = mm.Users.get_by_id(payee.id)
            user.instance.money -= amount
            payee_in_database.money += amount
            embed = discord.Embed(colour=discord.Color.purple())
            embed.add_field(name="Payment sent!",
                            value=f"You have sent {payee.mention} **{'{:,}'.format(int(amount))}** bits")
            await interaction.response.send_message(embed=embed)
            user.instance.save()
            payee_in_database.save()
        except pw.DoesNotExist:
            embed = discord.Embed(title="This user is not yet registered.")
            await interaction.response.send_message(embed=embed)

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="economy", description="Check to see the total amount of bits in circulation "
                                                      "and how much of it you own!")
    async def economy(self, interaction: discord.Interaction):
        column = mm.Users.money + mm.Users.bank
        query = mm.Users.select().order_by(column.desc())
        circulation = 0
        user_money = 0
        for user in query.objects():
            discord_user = interaction.client.get_user(user.id)
            networth = user.bank + user.money
            if discord_user.bot:
                networth = 0
            elif user.id == interaction.user.id:
                user_money = networth
            elif networth == 0:
                pass
            circulation += networth
        embed = discord.Embed(
            title="Current Circulation",
            description=f"There are currently **{'{:,}'.format(circulation)}** bits floating around the server",
            color=discord.Color.blue()
        )
        percent_holdings = round((user_money / circulation) * 100, 2)
        if percent_holdings > 50:
            embed = discord.Embed(
                title="Current Circulation",
                description=f"There are currently **{'{:,}'.format(circulation)}** bits floating around the server",
                color=discord.Color.dark_red()
            )
        embed.add_field(name=f"{interaction.user.name}'s Ownership",
                        value=f"{percent_holdings}% of circulation")
        embed.set_footer(text="Note: does not include bits the house has made.")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
