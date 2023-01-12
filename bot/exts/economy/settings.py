import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import discord.ui
from classLibrary import RequestUser, ranks
from exts.error import registered
import utils.models as mm
import playhouse.shortcuts as phs


class Settings(commands.Cog):
    """Change your settings."""

    def __init__(self, bot):
        self.bot = bot

    # This is the main view that will handle the settings embed and buttons/ui
    class SettingsView(discord.ui.View):
        def __init__(self, embed, interaction, user):
            # Establishes a connection between the settings embed and the view,
            # so that the embed can be updated using the View's children
            self.embed: discord.Embed = embed
            # Fetches the user's settings from the database, or creates them if they don't exist
            self.user_settings, created = mm.Settings.get_or_create(
                id=user.instance.id, defaults={'id': user.instance.id})
            self.user_settings_dict = phs.model_to_dict(self.user_settings)

            self.settings_dict = {
                "auto deposit": {
                    "database_name": "autodeposit",
                    "index": 0,
                    "values": [0, 1],
                    "description": "Automatically deposit your bits after working"
                },
                "withdraw warning": {
                    "database_name": "withdrawwarning",
                    "index": 1,
                    "values": [0, 1],
                    "description": "Enables the warning when withdrawing bits from the bank"
                }
            }

            self.current_setting_dict = self.settings_dict["auto deposit"]
            super().__init__()

    # Select menu that will allow the user to switch between settings
    class SettingsSelect(discord.ui.Select):
        def __init__(self, default_settings_dict):
            placeholder = "Pick a setting to change"
            super().__init__(row=0, placeholder=placeholder)
            self.view: Settings.SettingsView  # Type hinting
            # Adds a select option for each setting in the settings dictionary
            for index, setting in enumerate(default_settings_dict.keys()):
                self.add_option(label=setting, value=index)

        async def callback(self, interaction: discord.Interaction):
            # When an option is selected, update the embed to have the changed description
            for index, field in enumerate(self.view.embed.fields):
                self.view.embed.set_field_at(index=index, name=field.name.removesuffix(' <---'), value=field.value)
            self.view.embed.set_field_at(index=int(self.values[0]),
                                               name=self.view.embed.fields[int(self.values[0])].name + " <---",
                                               value=self.view.embed.fields[int(self.values[0])].value)
            self.view.current_setting_dict = list(
                self.view.settings_dict.values())[int(self.values[0])]
            await interaction.response.edit_message(embed=self.view.embed)

    # Button that will toggle between the respective values for each setting
    class ToggleButton(discord.ui.Button):
        def __init__(self, user_settings):
            self.view: Settings.SettingsView
            if user_settings['autodeposit'] == 0:
                style = discord.ButtonStyle.red
                label = "Turn On?"
            else:
                style = discord.ButtonStyle.green
                label = "Turn Off?"
            super().__init__(row=1, label=label, style=style)

        async def callback(self, interaction: discord.Interaction):
            self.view.embed.set_field_at(index=self.view.current_setting_dict['index'],
                                               name=self.view.embed.fields[self.view.current_setting_dict['index']],
                                               value="Off" if self.view.user_settings_dict[self.view.current_setting_dict['database_name']] == 0 else "On")
            await interaction.response.edit_message(embed=self.view.embed)

    # Button that will save the user's choices and update the database
    class SaveButton(discord.ui.Button):
        def __init__(self):
            self.view: Settings.SettingsView
            super().__init__(row=1, label="Save", style=discord.ButtonStyle.green)

        async def callback(self, interaction: discord.Interaction):
            print(self.view.user_settings_dict)
            await interaction.response.send_message("Settings saved.", ephemeral=True)

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="settings", description="Change your account settings.")
    async def settings(self, interaction: discord.Interaction, help: bool = False):
        # Creates a user object for the command to use
        user = RequestUser(user_id=interaction.user.id,
                           interaction=interaction)
        # Creates the embed that will display the user's settings
        settings_embed = discord.Embed(
            title=f"{user.instance.name}'s Settings",
            description="Change your settings. Don't forget to save your changes.",
            color=discord.Color.dark_theme()
        )
        # Creates the view and adds the select menu, toggle, and save button
        view = Settings.SettingsView(
            embed=settings_embed, interaction=interaction, user=user)
        for setting, setting_value in view.user_settings_dict.items():
            if setting == 'id':
                continue
            for formatted_setting in view.settings_dict.keys():
                if setting == formatted_setting.replace(' ', ''):
                    setting = formatted_setting
            if help:
                view.embed.add_field(
                    name=setting, value=f"{view.settings_dict[setting]['description']}\n" +
                    "Off" if setting_value == 0 else "On"
                )
            else:
                view.embed.add_field(
                    name=setting, value="Off" if setting_value == 0 else "On"
                )
        view.add_item(Settings.SettingsSelect(
            default_settings_dict=view.settings_dict))
        view.add_item(Settings.ToggleButton(
            user_settings=view.user_settings_dict))
        view.add_item(Settings.SaveButton())
        await interaction.response.send_message(embed=settings_embed, view=view)


async def setup(bot):
    await bot.add_cog(Settings(bot))
