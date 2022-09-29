import typing
from typing import Union
from random import shuffle
from PIL import Image, ImageFont, ImageDraw
from io import BytesIO
import pathlib
from discord.ext import commands
from Cogs.ErrorHandler import registered
from ClassLibrary import *
import asyncio

project_files = pathlib.Path.cwd() / 'EconomyBotProjectFiles'
with open(project_files / 'words.txt', 'r') as f:
    words = f.readlines()


class EconomyCog(commands.Cog, name='Economy'):
    """Your primary stop for making and losing bits!"""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

    @registered()
    @commands.command(name="Beg", aliases=["search"], description="Beg for some money, only if you have < 25 bits.")
    async def beg(self, ctx):
        user = User(ctx)
        result = await user.check_balance('bits')
        titles = ["Begging is for poor people...", "You're already rich!", "Really?"]
        if result >= 25:
            random_title = randint(0, 2)
            embed = discord.Embed(
                title=titles[random_title],
                description=f"You cannot beg if you have more than 25 bits\n"
                            f"You have **{'{:,}'.format(result)}** bits",
                color=discord.Color.red()
            )
            embed.set_footer(text=f"User: {ctx.author.name}")
            await ctx.send(embed=embed)
        else:
            donation = randint(20, 100)
            await user.update_balance(donation)
            embed = discord.Embed(
                title=f"Someone kind dropped {donation} bits in your cup.",
                description=f"You now have {'{:,}'.format(result + donation)} bits.",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"User: {ctx.author.name}")
            await ctx.send(embed=embed)
        lucky_drop = randint(0, 7000)
        if lucky_drop == 1:
            await user.update_tokens(1)
            await ctx.reply("**RARE** You just found a token!")
        elif lucky_drop in range(2, 10):
            bits = randint(250, 750)
            await user.update_balance(bits)
            await ctx.reply(f"**UNCOMMON** You just found {'{:,}'.format(bits)} bits!")

    @registered()
    @commands.command(name="Unscramble", aliases=['unscr', 'unsc', 'uns'],
                      description="Try to unscramble a word for some bits. "
                                  "The longer the word, the more bits you get!")
    async def unscramble(self, ctx):
        user = User(ctx)

        def get_word():
            word = random.choice(words)
            for x in word:
                if x.isupper():
                    return get_word()
            while len(word) < 4:
                return get_word()
            shuffle_word_list = list(word)
            shuffle_word_list.remove('\n')
            unshuffled_word = ''.join(shuffle_word_list)
            shuffle(shuffle_word_list)
            shuffled_word = ''.join(shuffle_word_list)
            while shuffled_word == unshuffled_word:
                shuffle(shuffle_word_list)
                shuffled_word = ''.join(shuffle_word_list)
            return unshuffled_word, shuffled_word

        unscrambled_word, scrambled_word = get_word()
        time_limit = 1.4 ** len(unscrambled_word)
        reward = len(unscrambled_word) * 70
        embed = discord.Embed(
            title="Unscramble!",
            description=f"You will have {time_limit.__round__()} seconds to unscramble the following word!",
            color=0xa0a39d
        )
        word_embed = discord.Embed(
            title="Unscramble!",
            description=f"You will have {time_limit.__round__()} seconds to unscramble the following word!\n"
                        f"***{scrambled_word}***",
            color=0xa0a39d
        )
        message = await ctx.send(embed=embed)
        await asyncio.sleep(2)
        await message.edit(embed=word_embed)

        def check(m):
            return m.content.lower() == unscrambled_word and m.author == ctx.author and m.channel == ctx.channel

        # Waits for a response after asking for high or low. Can be high, low, or stop
        try:
            guess = await self.bot.wait_for("message", timeout=time_limit.__round__(), check=check)
            if guess.content.lower() == unscrambled_word:
                embed = discord.Embed(
                    title="Unscramble!",
                    description=f"Correct!\n"
                                f"***{scrambled_word}*** - {unscrambled_word}",
                    color=0xa0f09c
                )
                embed.add_field(name="Reward", value=f"**{reward}** bits")
                await user.update_balance(reward)
                lucky_drop = randint(0, 500)
                if lucky_drop == 1:
                    await user.update_tokens(1)
                    await ctx.reply("**RARE** You just found a token!")
                elif lucky_drop in range(2, 10):
                    bits = randint(250, 1000)
                    await user.update_balance(bits)
                    await ctx.reply(f"**UNCOMMON** You just found {'{:,}'.format(bits)} bits!")
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="Unscramble!",
                description=f"Too slow!\n"
                            f"***{scrambled_word}*** - {unscrambled_word}",
                color=0xa8332f
            )
        embed.set_footer(text=f"User: {ctx.author.name}")
        await message.edit(embed=embed)

    @registered()
    @commands.command(name="Balance", aliases=["money", "bal", "credits"], description="Check your balance!")
    async def bits(self, ctx):
        user = User(ctx=ctx)
        select_avatar_statement = """SELECT avatar FROM users WHERE user_id = ?"""
        user.cursor.execute(select_avatar_statement, [user.user_id])
        avatar = user.cursor.fetchall()[0][0]

        async def set_avatar(selected_gender, selected_number, interaction):
            update_avatar_statement = """UPDATE users SET avatar = ? WHERE user_id = ?"""
            user.cursor.execute(update_avatar_statement, [f'{selected_gender}.{selected_number}', user.user_id])
            user.sqliteConnection.commit()
            await interaction.response.edit_message(view=None)
            await bal_command(f'{selected_gender}.{selected_number}')

        async def bal_command(user_avatar):
            gender, number = user_avatar.split('.')[0], user_avatar.split('.')[1]

            image1 = Image.open(project_files / 'Templates' / 'blank_template.png')
            font = ImageFont.truetype(str(project_files / 'Fonts' / 'StaatlichesRegular.ttf'), 25)
            smallerfont = ImageFont.truetype(str(project_files / 'Fonts' / 'StaatlichesRegular.ttf'), 18)

            rank = f'{get_role(ctx).name}'
            name = f'{ctx.author.name} #{ctx.author.discriminator}'
            bits = await user.check_balance('bits')
            tokens = await user.check_balance('tokens')
            user.cursor.execute("""SELECT bank FROM users WHERE user_id = ?""", [user.user_id])
            bank = user.cursor.fetchall()[0][0]
            digging_level = 0
            fishing_level = 0
            mining_level = 0
            combat_level = 0

            image_editable = ImageDraw.Draw(image1)
            # # Draw pet
            # pet = await ctx.bot.dbpets.find_one({"owner_id": ctx.author.id, "active": True})
            # if pet:
            #     pet_sprite = Image.open(project_files / 'Sprites' / f'{pet["species"]}_sprite.png')
            #     pet_name = pet["name"]
            #     image1.paste(pet_sprite, (636, 70), pet_sprite)
            #     if len(pet_name) > 8:
            #         image_editable.text((677, 187), pet_name, (238, 131, 255), font=smallerfont, anchor='mm')
            #     else:
            #         image_editable.text((677, 187), pet_name, (238, 131, 255), font=font, anchor='mm')

            # Draw avatar
            avatar_to_draw = Image.open(project_files / 'Sprites' / f'{gender}_avatar_{number}.png')
            image1.paste(avatar_to_draw, (85, 45), avatar_to_draw)

            # Draw Name
            image_editable.text((203, 317), name, (255, 255, 255), font=font, anchor='mm')

            # Draw rank and tokens
            image_editable.text((678, 293), rank, (44, 255, 174), font=font, anchor='mm')
            image_editable.text((678, 370), '{:,}'.format(tokens), (44, 255, 174), font=font, anchor='mm')

            # Draw bits
            image_editable.text((489, 120), '{:,}'.format(bits), (255, 241, 138), font=font, anchor='mm')
            image_editable.text((489, 186), '{:,}'.format(bank), (255, 241, 138), font=font, anchor='mm')

            # Draw levels
            image_editable.text((116, 410), f"Rank {'{:,}'.format(digging_level)}", (197, 255, 176), font=font,
                                anchor='mm')
            image_editable.text((285, 410), f"Rank {'{:,}'.format(fishing_level)}", (168, 208, 255), font=font,
                                anchor='mm')
            image_editable.text((116, 509), f"Rank {'{:,}'.format(mining_level)}", (255, 211, 150), font=font,
                                anchor='mm')
            image_editable.text((285, 509), f"Rank {'{:,}'.format(combat_level)}", (255, 170, 170), font=font,
                                anchor='mm')

            with BytesIO() as image_binary:
                image1.save(image_binary, 'PNG')
                image_binary.seek(0)
                await ctx.send(file=discord.File(fp=image_binary, filename='image.png'))

        if avatar == "None":
            await ctx.send("Hey... It looks like you don't have an avatar selected yet.\n"
                           "Please pick one now!")
            await asyncio.sleep(0.3)

            class CharacterSelectButtons(discord.ui.View):
                def __init__(self, *, timeout=180):
                    super().__init__(timeout=timeout)

                async def on_timeout(self) -> None:
                    await message.delete()

                @discord.ui.button(label="1", style=discord.ButtonStyle.blurple)
                async def male_1(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user != ctx.author:
                        return
                    await set_avatar('male', '1', interaction)

                @discord.ui.button(label="2", style=discord.ButtonStyle.blurple)
                async def male_2(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user != ctx.author:
                        return
                    await set_avatar('male', '2', interaction)

                @discord.ui.button(label="3", style=discord.ButtonStyle.blurple)
                async def male_3(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user != ctx.author:
                        return
                    await set_avatar('male', '3', interaction)

                @discord.ui.button(label="4", style=discord.ButtonStyle.blurple, row=1)
                async def female_1(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user != ctx.author:
                        return
                    await set_avatar('female', '1', interaction)

                @discord.ui.button(label="5", style=discord.ButtonStyle.blurple, row=1)
                async def female_2(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user != ctx.author:
                        return
                    await set_avatar('female', '2', interaction)

                @discord.ui.button(label="6", style=discord.ButtonStyle.blurple, row=1)
                async def female_3(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user != ctx.author:
                        return
                    await set_avatar('female', '3', interaction)

            project_files = pathlib.Path.cwd() / 'EconomyBotProjectFiles'
            message = await ctx.send(
                file=discord.File(project_files / 'Templates' / 'CharacterSelect.png'),
                view=CharacterSelectButtons())
            return
        else:
            await bal_command(avatar)

        # role = get_role(ctx)
        # user = User(ctx)
        # bits = await user.check_balance('bits')
        # bank = await self.bot.db.find_one({"_id": user.user_id})
        # networth = bank['bank'] + bits
        # embed = discord.Embed(title=f"{role.name} *{ctx.author.name}*", color=discord.Color.yellow())
        # embed.add_field(name="Bits", value=f"You have **{'{:,}'.format(bits)}** bits", inline=False)
        # embed.add_field(name="Bank", value=f"**{'{:,}'.format(bank['bank'])}** bits")
        # embed.add_field(name="Networth", value=f"**{'{:,}'.format(networth)}** bits")
        # embed.add_field(name="Level", value=f"You are level *coming soon*", inline=False)
        # embed.set_footer(text="Use -beg, -work, or -unscramble to get bits")
        # await ctx.send(embed=embed)

    # Command for the richest members in the server
    @registered()
    @commands.command(name="Baltop", description="See the top 5 richest gamblers in the server!")
    async def bal_top(self, ctx):
        embed = discord.Embed(
            title="Richest Members",
            description="",
            color=discord.Color.blue()
        )
        x = 1
        # Adds each user to the leaderboard ONLY IF THEY HAVE bits // IF THEY AREN'T A BOT
        data = self.bot.db.aggregate([
            {"$addFields": {"sort_order": {"$sum": ["$money", "$bank"]}}},
            {"$sort": {"sort_order": -1}},
            {"$project": {"sort_order": 0}}
        ])
        top_users = await data.to_list(length=6)
        for users in top_users:
            discord_member = self.bot.get_user(users["_id"])
            networth = users['money'] + users['bank']
            # Sets a footer for the bits that the bot has made.
            if discord_member.bot:
                embed.set_footer(text=f"The house has made {'{:,}'.format(users['money'])} bits.")
                x -= 1
            elif networth == 0:
                pass
            else:
                embed.add_field(name=f"{x}. {discord_member.name}",
                                value=f"Networth: {'{:,}'.format(networth)} bits", inline=False)
            x += 1
        await ctx.send(embed=embed)

    @registered()
    @commands.command(name="Balrank", description="See where you stand on the leaderboard for bits.")
    async def balrank(self, ctx):
        ranks = self.bot.db.aggregate([
            {"$addFields": {"sort_order": {"$sum": ["$money", "$bank"]}}},
            {"$sort": {"sort_order": -1}},
            {"$project": {"sort_order": 0}}
        ])
        top_users = await ranks.to_list(length=None)
        bot_ahead = False
        for rank, users in enumerate(top_users, start=1):
            discord_member = self.bot.get_user(users["_id"])

            def eval_networth(user):
                networth = user['money'] + user['bank']
                return networth

            if discord_member.bot:
                bot_ahead = True
            elif str(users['_id']) == str(ctx.author.id):
                if bot_ahead:
                    rank -= 1
                ahead = top_users[rank - 1]
                try:
                    behind = top_users[rank + 1]
                except IndexError:
                    two_ahead = top_users[rank - 2]
                    rank_embed = discord.Embed(
                        title=f"You are currently #{rank}",
                        description=f"*#{rank - 2}* | {self.bot.get_user(two_ahead['_id']).name} - {'{:,}'.format(eval_networth(two_ahead))} bits\n "
                                    f"*#{rank - 1}* | {self.bot.get_user(ahead['_id']).name} - {'{:,}'.format(eval_networth(ahead))} bits\n"
                                    f"*#{rank}* | **You - {'{:,}'.format(eval_networth(users))} bits**\n",
                        color=0x5100ff)
                else:
                    if rank == 1:
                        two_behind = top_users[rank + 2]
                        rank_embed = discord.Embed(
                            title=f"You are currently #{rank}",
                            description=f"*#{rank}* | **You - {'{:,}'.format(eval_networth(users))} bits**\n"
                                        f"*#{rank + 1}* | {self.bot.get_user(behind['_id']).name} - {'{:,}'.format(eval_networth(behind))} bits\n"
                                        f"*#{rank + 2}* | {self.bot.get_user(two_behind['_id']).name} - {'{:,}'.format(eval_networth(two_behind))} bits",
                            color=0x5100ff)
                    else:
                        rank_embed = discord.Embed(
                            title=f"You are currently #{rank}",
                            description=f"*#{rank - 1}* | {self.bot.get_user(ahead['_id']).name} - {'{:,}'.format(eval_networth(ahead))} bits\n"
                                        f"*#{rank}* | **You - {'{:,}'.format(eval_networth(users))} bits**\n"
                                        f"*#{rank + 1}* | {self.bot.get_user(behind['_id']).name} - {'{:,}'.format(eval_networth(behind))} bits",
                            color=0x5100ff)
                rank_embed.set_footer(text=f"Requested by: {ctx.author.name}")
                await ctx.send(embed=rank_embed)

    # Daily command, should give x amount of credits per day.
    @registered()
    @commands.command(name="Daily", description="Get some bits every day, to feed your gambling addiction.")
    async def daily(self, ctx):
        # Initialize user object to grab from database
        user = User(ctx)
        await user.daily()

    @registered()
    @commands.command(name='Work', description="Work to earn some bits. Wage increased by role.")
    async def work(self, ctx):
        user = User(ctx)
        await user.work()

    @registered()
    @commands.command(name="Deposit", description="Deposit some money into the bank for safekeeping.",
                      brief="-deposit (amount to deposit)")
    async def deposit(self, ctx, amount: Union[int, str]):
        user1 = User(ctx)
        select_user_money_statement = """SELECT bits FROM users WHERE user_id = ?"""
        user1.cursor.execute(select_user_money_statement, [user1.user_id])
        money = user1.cursor.fetchall()[0][0]
        if amount == 'max':
            amount = await user1.check_balance('bits')
        if int(amount) > money:
            await ctx.send(f"You don't have enough bits to deposit. "
                           f"Balance: {'{:,}'.format(money)} bits")
            return
        elif int(amount) == 0:
            await ctx.send("You cannot deposit **0** bits...")
            return
        elif int(amount) < 0:
            await ctx.send("You cannot deposit negative bits either!")
            return
        elif int(amount) < 250:
            await ctx.send("Sorry, deposits must be over 250 bits.")
            return
        elif type(amount) == str:
            await ctx.send("Please input an amount to deposit.")
        else:
            await user1.update_balance(-int(amount))
            await user1.update_balance(int(amount), bank=True)
            embed = discord.Embed(colour=discord.Color.dark_blue())
            embed.add_field(name="Deposit made!", value=f"You have deposited **{'{:,}'.format(amount)}** bits")
            await ctx.send(embed=embed)

    @registered()
    @commands.command(name="Withdraw", description="Withdraw bits from the bank.", brief="-withdraw (amount)")
    async def withdraw(self, ctx, amount: int | typing.Literal['all']):
        user = User(ctx)
        select_user_bank_statement = """SELECT bank FROM users WHERE user_id = ?"""
        user.cursor.execute(select_user_bank_statement, [user.user_id])
        bank = user.cursor.fetchall()[0][0]

        warning_embed = discord.Embed(title="Are you sure?",
                                      description="Withdrawing just to gamble more might not be a good idea.",
                                      color=discord.Color.dark_red())
        warning_embed.set_footer(text=f"User: {ctx.author.name}")

        class WithdrawButtons(discord.ui.View):
            def __init__(self, *, timeout=180):
                super().__init__(timeout=timeout)

            @discord.ui.button(label="Yes, withdraw", style=discord.ButtonStyle.green)
            async def green_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                await user.update_balance(int(amount))
                await user.update_balance(-int(amount), bank=True)
                withdraw_embed = discord.Embed(colour=discord.Color.dark_blue())
                withdraw_embed.add_field(name="Withdrawal made!",
                                         value=f"You withdrew **{'{:,}'.format(amount)}** bits")
                withdraw_embed.set_footer(text=f"User: {ctx.author.name}")
                await interaction.response.edit_message(embed=withdraw_embed, view=None)

            @discord.ui.button(label="No", style=discord.ButtonStyle.red)
            async def red_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                cancel_embed = discord.Embed(title="Withdraw cancelled",
                                             description="Withdraw was either cancelled or timed out.")
                cancel_embed.set_footer(text=f"User: {ctx.author.name}")
                await interaction.response.edit_message(embed=cancel_embed, view=None)
                await asyncio.sleep(3)

        if int(amount) > bank:
            await ctx.send(f"You don't have that many bits in your account. "
                           f"Bank Balance: {'{:,}'.format(bank)} bits")
            return
        elif int(amount) == 0:
            await ctx.send("You cannot withdraw **0** bits...")
            return
        elif int(amount) < 0:
            await ctx.send("You cannot withdraw negative bits either!")
            return

        await ctx.send(embed=warning_embed, view=WithdrawButtons())

    @registered()
    @commands.command(name="Pay", description="Pay someone else some bits, if you're feeling nice!",
                      brief="-pay @user amount")
    async def pay(self, ctx, user_to_pay: discord.Member, amount):
        user = User(ctx)
        accepted_roles = ["Citizen", "Educated", "Cultured", "Weathered", "Wise", "Expert"]
        role = get_role(ctx)
        if role.name not in accepted_roles:
            embed = discord.Embed(
                title="Perk not yet unlocked!",
                description="You unlock this perk at **Citizen** rank",
                color=discord.Color.red()
            )
            embed.set_footer(text=f"User: {ctx.author.name}")
            await ctx.send(embed=embed)
            return
        select_user_money_statement = """SELECT bits FROM users WHERE user_id = ?"""
        user.cursor.execute(select_user_money_statement, [user.user_id])
        money = user.cursor.fetchall()[0][0]
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
            await ctx.send(embed=embed)
            return
        elif int(amount) > money:
            await ctx.send(f"You don't have enough bits to send. Balance: "
                           f"{'{:,}'.format(money)} bits")
            return
        elif int(amount) == 0:
            await ctx.send("You cannot send someone **0** bits...")
            return
        elif int(amount) < 0:
            await ctx.send("You cannot send someone negative bits either!")
            return
        user.cursor.execute("""SELECT * FROM users WHERE user_id = ?""", [user_to_pay.id])
        if len(user.cursor.fetchall()) == 0:
            embed = discord.Embed(title="This user is not yet registered.")
            await ctx.send(embed=embed)
        else:
            await user.update_balance(-int(amount))
            user.cursor.execute("""UPDATE users SET bits = bits + ? WHERE user_id = ?""", [int(amount), user_to_pay.id])
            user.sqliteConnection.commit()
            embed = discord.Embed(colour=discord.Color.purple())
            embed.add_field(name="Payment sent!",
                            value=f"You have sent {user_to_pay.mention} **{'{:,}'.format(int(amount))}** bits")
            await ctx.send(embed=embed)

    @registered()
    @commands.command(name="Economy", description="Check to see the total amount of bits in circulation, "
                                                  "and how much of it you own!", brief="-economy", aliases=["econ"])
    async def economy(self, ctx):
        data = self.bot.db.aggregate([
            {"$addFields": {"sort_order": {"$sum": ["$money", "$bank"]}}},
            {"$sort": {"sort_order": -1}},
            {"$project": {"sort_order": 0}}
        ])
        all_users = await data.to_list(length=None)
        circulation = 0
        user_money = 0
        for users in all_users:
            discord_user = self.bot.get_user(users['_id'])
            networth = users['money'] + users['bank']
            if discord_user.bot:
                networth = 0
            elif users['_id'] == ctx.author.id:
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
        embed.add_field(name=f"{ctx.author.name}'s Ownership",
                        value=f"{percent_holdings}% of circulation")
        embed.set_footer(text="Note: does not include bits the house has made.")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
