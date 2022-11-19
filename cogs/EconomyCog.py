import discord.utils
import asyncio
import math
import pathlib
from discord import app_commands
from discord.app_commands import Choice
from cogs.ErrorHandler import registered
from oldClassLibrary import *
from classLibrary import *

project_files = pathlib.Path.cwd() / 'projfiles'
with open(project_files / 'words.txt', 'r') as f:
    words = f.readlines()


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
    for user in economy_users:  # Once circulation is done calculating, we can calculate percent holdings
        economy_users[user]['percent_of_economy'] = round((economy_users[user]['networth'] / circulation) * 100, 2)

    return circulation, economy_users


def create_rank_string(interaction, index, user, xp, mode: int, advanced: bool = False):
    match mode:
        case 0:  # IF THE MODE IS SET TO BITS
            if advanced:
                circulation, economy_users = calculate_economy_share(interaction=interaction)
                user_percent_of_economy = economy_users[user.id]['percent_of_economy']
                return f"{index}. {user.name} - {'{:,}'.format(user.bank + user.money)} | `{user_percent_of_economy}%`"
            return f"{index}. {user.name} - {'{:,}'.format(user.bank + user.money)}"
        case 1:  # IF THE MODE IS SET TO any XP MODE
            if advanced:
                return f"{index}. {user.name} - Level {'{:,}'.format(int(math.sqrt(xp).__floor__() / 10))} | `{'{:,}'.format(xp)} xp`"
            return f"{index}. {user.name} - Level {'{:,}'.format(int(math.sqrt(xp).__floor__() / 10))}"
        case 2:  # IF THE MODE IS SET TO DROPS
            if advanced:
                return f"{index}. {user.name} - {user.drops_claimed} " \
                       f"drops | `~{'{:,}'.format(user.drops_claimed * 17500)} bits`"
            return f"{index}. {user.name} - {user.drops_claimed} drops claimed"


class EconomyCog(commands.Cog, name='Economy'):
    """Your primary stop for making and losing bits!"""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.checks.cooldown(1, 60)
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
            user.update_balance(beg_amount)

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
        reward = (len(word) * (10*len(word)**2) + 300)
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
                correct_word_embed.add_field(name="Reward", value=f"**{reward:,}** bits")
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
    @app_commands.command(name="profile", description="Check your profile, pets, etc.")
    async def bits(self, interaction: discord.Interaction):
        user = RequestUser(interaction.user.id, interaction=interaction)

        class ProfileSwitchMenu(discord.ui.View):
            def __init__(self):
                super().__init__()

            pet_menu = discord.SelectOption(label="Pets", value="pets", emoji="🐾")
            profile_menu = discord.SelectOption(label="Profile", value="profile", emoji="👤")
            select_options = [profile_menu, pet_menu]

            @discord.ui.select(options=select_options, placeholder="Select a menu")
            async def select_menu(self, select_interaction: discord.Interaction, select: discord.ui.Select):
                switch_embed = None  # Initialize an embed to switch to
                if select_interaction.user != interaction.user:
                    return
                if select.values[0] == 'pets':
                    switch_embed = user.active_pet.pet_embed
                elif select.values[0] == 'profile':
                    switch_embed = profile_embed
                await select_interaction.response.edit_message(embed=switch_embed, view=self)

        bits = user.instance.money
        bank = user.instance.bank
        tokens = user.instance.tokens
        level = (math.sqrt(user.instance.xp / 100)).__floor__()
        profile_embed = discord.Embed(title=f"{user.rank.capitalize()} *{interaction.user.name}*",
                                      color=discord.Color.from_str("0x262625"))
        profile_embed.set_author(name=f"{interaction.user.name} - profile", icon_url=interaction.user.display_avatar)
        profile_embed.add_field(name="PROGRESS", value=f"**Level**: {level}\n"
                                                       f"**XP**: {user.instance.xp}/{int(((level + 1) ** 2) * 100)}\n"
                                                       f"**Area**: *coming soon*")
        profile_embed.add_field(name="SKILLS", value=f":crossed_swords: **COMBAT**: *coming soon*\n"
                                                     f":pick: **MINING**: *coming soon*\n"
                                                     f":evergreen_tree: **FORAGING**: *coming soon*\n"
                                                     f":fishing_pole_and_fish: **FISHING**: *coming soon*",
                                inline=False)
        profile_embed.add_field(name="EQUIPMENT", value=f"*coming soon*\n"
                                                        f"*coming soon*\n"
                                                        f"*coming soon*")
        profile_embed.add_field(name="MONEY", value=f":money_with_wings: **BITS**: {'{:,}'.format(bits)}\n"
                                                    f":bank: **BANK**: {'{:,}'.format(bank)}\n"
                                                    f":coin: **TOKENS**: {'{:,}'.format(tokens)}")
        profile_embed.set_footer(text="Use /beg, /work, or /unscramble to get bits")
        profile_embed.set_thumbnail(url=interaction.user.display_avatar)
        await interaction.response.send_message(embed=profile_embed, view=ProfileSwitchMenu())

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
        Choice(name='fishing', value=4),
        Choice(name='drops', value=5)])
    async def top(self, interaction: discord.Interaction, category: Choice[int], advanced: bool | None):
        leaderboard_attributes = {
            0: {
                "column": mm.Users.money + mm.Users.bank,
                "title": ":money_with_wings: BITS LEADERBOARD :money_with_wings:",
                "color": discord.Color.blue(),
                "circulation": 0
            },
            1: {
                "column": mm.Users.combat_xp,
                "title": ":crossed_swords: COMBAT LEADERBOARD :crossed_swords:",
                "color": discord.Color.dark_red()
            },
            2: {
                "column": mm.Users.mining_xp,
                "title": ":pick: MINING LEADERBOARD :pick:",
                "color": discord.Color.dark_orange()
            },
            3: {
                "column": mm.Users.foraging_xp,
                "title": ":evergreen_tree: FORAGING LEADERBOARD :evergreen_tree:",
                "color": discord.Color.dark_green()
            },
            4: {
                "column": mm.Users.fishing_xp,
                "title": ":fishing_pole_and_fish: FISHING LEADERBOARD :fishing_pole_and_fish:",
                "color": discord.Color.dark_blue()
            },
            5: {
                "column": mm.Users.drops_claimed,
                "title": ":package: DROPS LEADERBOARD :package:",
                "color": discord.Color.from_str("0xcc8c16")
            }
        }
        category_index = leaderboard_attributes[category.value]
        description = ''
        user_place = None
        add_circulation = False

        query = mm.Users.select().order_by(category_index['column'].desc())

        INDEX_START = 1
        index = INDEX_START
        for user in query.objects():
            discordMemberObject = interaction.guild.get_member(user.id)
            if discordMemberObject.bot:  # Detect if the user is the bot in Discord
                continue  # Move on to next interation in the loop
            if category.value == 0:
                category_index['circulation'] += user.money + user.bank  # Add user money and bank to circulation
            rank_string = None

            match category.value:
                case 0:
                    rank_string = create_rank_string(interaction, index, user, None,
                                                     mode=0, advanced=advanced)
                    add_circulation = True
                case 1:
                    rank_string = create_rank_string(interaction, index, user, xp=user.combat_xp,
                                                     mode=1, advanced=advanced)
                case 2:
                    rank_string = create_rank_string(interaction, index, user, xp=user.mining_xp,
                                                     mode=1, advanced=advanced)
                case 3:
                    rank_string = create_rank_string(interaction, index, user, xp=user.foraging_xp,
                                                     mode=1, advanced=advanced)
                case 4:
                    rank_string = create_rank_string(interaction, index, user, xp=user.fishing_xp,
                                                     mode=1, advanced=advanced)
                case 5:
                    rank_string = create_rank_string(interaction, index, user, None, mode=2, advanced=advanced)

            if index <= 10 and (user.id == interaction.user.id):  # If loop is over command user and still in top 10 :)
                description += f"**{rank_string}**\n"
            elif index > 10 and (user.id == interaction.user.id):  # If loop is over command user and not in top 10 :(
                user_place = f"**{rank_string}**"
            elif index <= 10 and (user.id != interaction.user.id):  # If loop is anyone else and still in top 10
                description += f"{rank_string}\n"
            elif index > 10 and user_place:  # Break if we find the user
                break
            else:
                pass
            index += 1
        if user_place:  # If the user didn't place top 10
            description += '\n' + 'Your rank:' + '\n' + user_place
        top_embed = discord.Embed(
            title=category_index['title'],
            description=description,
            color=category_index['color']
        )
        if add_circulation:
            top_embed.add_field(
                name="Current Circulation",
                value=f"There are currently **{'{:,}'.format(category_index['circulation'])}** bits in the economy."
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
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        user = RequestUser(interaction.user.id, interaction=interaction)
        if amount in ['all', 'max']:
            amount = user.instance.bank
        amount = int(amount)
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
            user.instance.money -= int(amount)
            user.instance.save()
            payee_in_database = mm.Users.get_by_id(payee.id)
            payee_in_database.money += int(amount)
            payee_in_database.save()
            embed = discord.Embed(colour=discord.Color.purple())
            embed.add_field(name="Payment sent!",
                            value=f"You have sent {payee.mention} **{'{:,}'.format(int(amount))}** bits")
            await interaction.response.send_message(embed=embed)
        except pw.DoesNotExist:
            embed = discord.Embed(title="This user is not yet registered.")
            await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
