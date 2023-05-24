from discord.ext import commands
import discord
from discord import app_commands
import requests
from bs4 import BeautifulSoup


class FunCommands(commands.Cog, name='Fun'):
    """All fun commands were moved to slash commands. Do / to see them!"""

    def __init__(self, bot):
        self.bot = bot

    fun_commands = discord.app_commands.Group(name="fun", description="Some fun commands to use.",
                                              guild_ids=[856915776345866240])

    @fun_commands.command(name="backwards", description="Repeats your message but backwards!")
    async def backwards(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(message[::-1])

    @fun_commands.command(name="shout", description="SHOUT your message!")
    async def shout(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(f"**{message.upper()}** -{interaction.user.name}")

    @fun_commands.command(name="yay", description="YAY!")
    async def yay(self, interaction: discord.Interaction):
        await interaction.response.send_message(f':balloon:')

    @fun_commands.command(name="status", description="Change the status of the bot")
    async def status(self, interaction: discord.Interaction, playing: str):
        game = discord.Game(playing.replace("playing", ""))
        await self.bot.change_presence(status=discord.Status.online, activity=game)
        await interaction.response.send_message(f"Economy Bot is now playing: **{playing.replace('playing', '')}**.")

    @app_commands.command(name="wiki", description="Check the wiki for Terraria!")
    # @app_commands.choices(game=[
    #     Choice(name='Terraria', value=1)
    # ])
    @app_commands.guilds(856915776345866240)
    async def wiki(self, interaction: discord.Interaction, item: str | None):
        # game: Choice[int], ADD THIS IN WHEN THERE ARE MUTLIPLE GAMES TO CHOOSE FROM
        game_urls = {
            "terraria": "https://terraria.wiki.gg/wiki/",
            "terrariasearch": "https://terraria.wiki.gg/index.php?search="
        }
        if item:
            # Get webpage for searching
            # response = requests.get(url=f"{game_urls[game.name.lower()+'search']}+{item.replace(' ', '+')}")  ^^^
            response = requests.get(
                url=f"{game_urls['terraria' + 'search']}+{item.replace(' ', '+')}")
            soup = BeautifulSoup(response.content, 'html.parser')
            # Get title and descriptions for the item
            title = soup.find(id="firstHeading")
            bs = soup.find_all("b")
            for x in bs:
                if x.text[0:14] == "Multiple pages":
                    embed = discord.Embed(
                        title=f"Could not locate - {item}",
                        description="Make sure you are typing in the **item name** exactly.\n"
                                    "If it's still not working, contact the **owner** of this bot, "
                                    "or just do /wiki for the **default wiki page**.",
                        color=discord.Color.red())
                    await interaction.response.send_message(embed=embed)
                    return
            if title.string == "Search results":
                embed = discord.Embed(
                    title=f"Could not locate - {item}",
                    description="Make sure you are typing in the item name exactly.\n"
                                "If it's still not working, contact the owner of this bot, "
                                "or just do /wiki for the default wiki page.",
                    color=discord.Color.red())
                await interaction.response.send_message(embed=embed)
                return
            description = soup.find("div", {"class": "mw-parser-output"})
            paragraphs = description.select('p')
            intro = '\n'.join([para.text for para in paragraphs[0:1]])
            # Get item sprites
            section_images = soup.find("div", {"class": "section images"})
            embed = discord.Embed(
                title=title.string,
                url=f"{game_urls['terraria' + 'search']}+{item.replace(' ', '+')}",
                description=f"{intro}",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Requested by {interaction.user.name}")
            try:
                sprite = section_images.find("img")
                embed.set_thumbnail(
                    url=f"https://terraria.wiki.gg{sprite['src']}")
                embed.set_author(name="Terraria Wiki",
                                 url=f"{game_urls['terraria']}",
                                 icon_url="https://terraria.wiki.gg/images/thumb/a/ac/Tree.png/25px-Tree.png")
            except AttributeError:
                sprite = None
        else:
            # response = requests.get(url=game_urls[game.name.lower()])  ^^^
            response = requests.get(url=f"{game_urls['terraria']}")
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.find(id="firstHeading")
            embed = discord.Embed(
                title=title.string, url=f"{game_urls['terraria']}",
                description="**Terraria** is a land of *adventure*! A land of *mystery*! "
                            "A land that's yours to shape, defend, and enjoy. "
                            "Your options in **Terraria** are limitless. "
                            "Are you an action gamer with an itchy trigger finger? A master builder? "
                            "A collector? An explorer? There's something for everyone.",
                color=discord.Color.green()
            )
            embed.set_footer(
                text="Use /wiki (item) to see the wiki page about an item!")
            embed.set_thumbnail(
                url="https://terraria.wiki.gg/images/thumb/a/ac/Tree.png/25px-Tree.png")
            embed.set_author(name="Terraria Wiki", url=f"{game_urls['terraria']}",
                             icon_url="https://terraria.wiki.gg/images/thumb/a/ac/Tree.png/25px-Tree.png")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="crafting", description="Check recipes for Terraria items.")
    @app_commands.guilds(856915776345866240)
    async def crafting(self, interaction: discord.Interaction, item: str | None):
        response = requests.get(
            url=f"https://terraria.wiki.gg/index.php?search={item.replace(' ', '+')}")
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find(id="firstHeading")
        section_images = soup.find("div", {"class": "section images"})
        embed = discord.Embed(
            title=title.string,
            url=f"https://terraria.wiki.gg/index.php?search={item.replace(' ', '+')}",
            color=discord.Color.blue()
        )
        try:
            sprite = section_images.find("img")
            embed.set_thumbnail(url=f"https://terraria.wiki.gg{sprite['src']}")
        except AttributeError:
            sprite = None
        # Get the crafting recipes
        data = []
        table = soup.find('table', attrs={'class': 'crafts'})
        table_body = table.find('tbody')

        rows = table_body.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            data.append([ele for ele in cols if ele])

        desktop_found = False
        for x in data[2:]:
            dont_add_me = False
            if len(x) == 3:
                embed.add_field(name="Crafting Station",
                                value=f"{x[2].replace('or', ' or ')}")
            for index, strings in enumerate(x):
                alphabet = 'abcdefghijklmnopqrstuvwxyz'
                prev = ''
                for letter in strings:
                    if letter.lower() in alphabet and prev == ')':
                        fixed_string = strings.replace(
                            f'){letter}', f')\n{letter}')
                        x.remove(x[index])
                        x.insert(index, fixed_string)
                    prev = letter
            if "\u2009" in x[0] and desktop_found is False:
                desktop_found = True
                new_string = x[0].replace("\u2009", "")
                new_string = new_string.replace("()", "")
                new_string = new_string.strip()
                x.remove(x[0])
                x.insert(0, new_string)
            if "\u2009" in x[0] and desktop_found is True:
                dont_add_me = True
            if dont_add_me is False:
                embed.add_field(name=x[0], value=x[1], inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(FunCommands(bot))
