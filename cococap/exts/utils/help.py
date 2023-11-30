import math

import discord
from discord.ext import commands
from discord.errors import Forbidden
from discord import app_commands

"""This custom help command is a perfect replacement for the default one on any Discord Bot written in Discord.py!
However, you must put "bot.remove_command('help')" in your bot, and the command must be in a cog for it to work.
Original concept by Jared Newsom (AKA Jared M.F.)
"""


async def send_embed(interaction, embed):
    """
    Function that handles the sending of embeds
    -> Takes context and embed to send
    - tries to send embed in channel
    - tries to send normal message when that fails
    - tries to send embed private with information abot missing permissions
    If this all fails: https://youtu.be/dQw4w9WgXcQ
    """
    try:
        await interaction.response.send_message(embed=embed)
    except Forbidden:
        try:
            await interaction.response.send_message("Hey, seems like I can't send embeds. Please check my permissions :)")
        except Forbidden:
            await interaction.user.send(
                f"Hey, seems like I can't send any message in {interaction.channel.name} on {interaction.guild.name}\n"
                f"May you inform the server team about this issue? :slight_smile: ", embed=embed)


class Page:
    def __init__(self, number, embed, location="middle"):
        self.number = number
        self.embed = embed
        self.location = location


class Help(commands.Cog, name='Help'):
    """Sends this help message"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name='help')
    async def help(self, interaction: discord.Interaction, module: str = None):
        """Shows all modules of that bot"""
        # checks if cog parameter was given
        # if not: sending all modules and commands not associated with a cog
        if not module:
            # starting to build embed
            emb = discord.Embed(title='Commands and modules', color=discord.Color.blue(),
                                description=f'Use `/help <module>` to gain more information about that module '
                                            f':smiley:\n')

            # iterating trough cogs, gathering descriptions
            cogs_desc = ''
            ignored_cogs = ['CommandErrorHandler', 'DebuggingCommands', 'ClassLibrary', 'Help']
            for cog in self.bot.cogs:
                if cog in ignored_cogs:
                    pass
                else:
                    cogs_desc += f'`{cog}` - {self.bot.cogs[cog].__doc__}\n'

            # adding 'list' of cogs to embed
            emb.add_field(name='Modules', value=cogs_desc, inline=False)

            # integrating trough uncategorized commands
            commands_desc = ''
            for command in self.bot.walk_commands():
                # if cog not in a cog
                # listing command if cog name is None and command isn't hidden
                if not command.cog_name and not command.hidden:
                    commands_desc += f'{command.name} - {command.help}\n'

            # adding those commands to embed
            if commands_desc:
                emb.add_field(name='Not belonging to a module', value=commands_desc, inline=False)

        # block called when one cog-name is given
        # trying to find matching cog and it's commands
        elif module:

            # iterating trough cogs
            for cog in self.bot.cogs:
                # check if cog is the matching one
                if cog.lower() == module.lower():

                    # making title - getting description from doc-string below class

                    # getting commands from cog
                    commands_desc = {}
                    bot_commands = []
                    embeds = {}
                    pages = []
                    for command in self.bot.get_cog(cog).get_app_commands():
                        bot_commands.append(command)
                    if len(bot_commands) > 5:
                        for x in range(0, math.ceil(len(bot_commands) / 5)):
                            commands_desc[f'page{x} commands'] = []
                            i = 0
                            while i < 5:
                                try:
                                    if not bot_commands[0].hidden:
                                        commands_desc[f'page{x} commands'].append(bot_commands[0])
                                    else:
                                        pass
                                except IndexError:
                                    break
                                bot_commands.pop(0)
                                i += 1
                            # if cog is not hidden
                        for index, i in enumerate(commands_desc):
                            embeds[f'page{index + 1}'] = discord.Embed(title=f'{cog} - Commands {index + 1}',
                                                                       description=self.bot.cogs[cog].__doc__,
                                                                       color=discord.Color.green())
                            for dict_command in commands_desc[i]:
                                if dict_command.description:
                                    embeds[f'page{index + 1}'].add_field(name=f"`-{dict_command.name}`",
                                                                         value=dict_command.description, inline=False)
                                else:
                                    embeds[f'page{index + 1}'].add_field(name=f"`/{dict_command.name}`", value=None,
                                                                         inline=False)
                            index = Page(index, embeds[f'page{index + 1}'])
                            pages.append(index)

                        class HelpPaginatorButtons(discord.ui.View):
                            def __init__(self, page, *, timeout=40):
                                super().__init__(timeout=timeout)
                                self.page = page

                            async def on_timeout(self) -> None:
                                await message.edit(view=None)

                            def next_page(self):
                                current_page = pages.index(self.page)
                                try:
                                    self.page = pages[current_page + 1]
                                except IndexError:
                                    return
                                return self.page

                            def back_page(self):
                                current_page = pages.index(self.page)
                                if current_page == 0:
                                    return
                                self.page = pages[current_page - 1]
                                return self.page

                            @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.blurple, disabled=True,
                                               custom_id="1")
                            async def back_page_button(self, back_page_interaction: discord.Interaction,
                                                       button: discord.ui.Button):
                                if back_page_interaction.user != interaction.user:
                                    return
                                if self.page.number == len(pages)-1:
                                    self.children[1].disabled = False
                                self.back_page()
                                if self.page == pages[0]:
                                    button.disabled = True
                                else:
                                    button.disabled = False
                                await interaction.response.edit_message(embed=self.page.embed, view=self)

                            @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.blurple, custom_id="2")
                            async def next_page_button(self, next_page_interaction: discord.Interaction,
                                                       next_button: discord.ui.Button):
                                if next_page_interaction.user != interaction.user:
                                    return
                                if self.page == pages[0]:
                                    self.children[0].disabled = False
                                self.next_page()
                                if self.page.number == len(pages)-1:
                                    next_button.disabled = True
                                else:
                                    next_button.disabled = False
                                await interaction.response.edit_message(embed=self.page.embed, view=self)
                        message = await interaction.response.send_message(embed=pages[0].embed,
                                                                          view=HelpPaginatorButtons(pages[0]))
                        return
                    else:
                        emb = discord.Embed(title=f'{cog} - Commands',
                                            description=self.bot.cogs[cog].__doc__,
                                            color=discord.Color.green())
                        for command in self.bot.get_cog(cog).get_commands():
                            if not command.hidden:
                                if command.description:
                                    emb.add_field(name=f"`-{command.name}`",
                                                  value=command.description, inline=False)
                                else:
                                    emb.add_field(name=f"`-{command.name}`", value=None,
                                                  inline=False)

                    # found cog - breaking loop
                    break

            # if input not found
            # yes, for-loops have an else statement, it's called when no 'break' was issued
            else:
                emb = discord.Embed(title="What's that?!",
                                    description=f"I've never heard from a module called `{module}` before :scream:",
                                    color=discord.Color.orange())

        else:
            emb = discord.Embed(title="It's a magical place.",
                                description="I don't know how you got here. But I didn't see this coming at all.\n"
                                            "Would you please be so kind to report that issue to me on github?\n"
                                            "https://github.com/nonchris/discord-fury/issues\n"
                                            "Thank you! ~Chris",
                                color=discord.Color.red())

        # sending reply embed using our own function defined above
        await send_embed(interaction, emb)


async def setup(bot):
    await bot.add_cog(Help(bot))
