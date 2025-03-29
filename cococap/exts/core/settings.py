import discord

from discord.ext import commands
from discord import app_commands, Interaction
from cococap.user import User
from cococap.utils.messages import Cembed


class Settings(commands.Cog):
    """Change your settings."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="settings")
    async def settings(self, interaction: Interaction):
        """Change your account settings."""
        # Load the user
        user = User(uid=interaction.user.id)
        await user.load()

        settings_dict = {
            "auto_deposit": {
                "name": "Auto Deposit",
                "description": "Automatically deposit your bits after working",
            },
            "withdraw_warning": {
                "name": "Withdraw Warning",
                "description": "Enables the warning when withdrawing bits from the bank",
            },
            "disable_max_bet": {
                "name": "Disable Max Bet",
                "description": "Prevents you from betting all the bits in your purse",
            },
        }

        settings: dict = user.get_field("settings")
        keys = list(settings.keys())

        class SettingsView(discord.ui.View):
            def __init__(self, *, timeout: float | None = 180):
                super().__init__(timeout=timeout)
                self.current = keys[0]
                self.embed = Cembed(
                    title=f"{interaction.user.name}'s Settings",
                    color=discord.Color.green() if settings[self.current] else discord.Color.red(),
                    interaction=interaction,
                    activity="changing settings",
                )
                self.embed.add_field(
                    name=f"{settings_dict[self.current]['name']} - {'ON' if settings[self.current] else 'OFF'}",
                    value=settings_dict[self.current]["description"],
                )

                self.embed.set_footer(text="Don't forget to save your changes!")

            options = []
            for key, value in settings_dict.items():
                options.append(discord.SelectOption(label=value["name"], value=key))

            @discord.ui.select(placeholder="Select a setting to change", options=options)
            async def select_menu(self, interaction: Interaction, select: discord.ui.Select):
                self.current = select.values[0]
                self.embed.set_field_at(
                    0,
                    name=f"{settings_dict[self.current]['name']} - {'ON' if settings[self.current] else 'OFF'}",
                    value=settings_dict[self.current]["description"],
                )
                self.embed.color = (
                    discord.Color.green() if settings[self.current] else discord.Color.red()
                )
                await interaction.response.edit_message(embed=self.embed)

            @discord.ui.button(label="Toggle")
            async def toggle_button(self, interaction: Interaction, button: discord.Button):
                settings[self.current] = not settings[self.current]
                self.embed.set_field_at(
                    0,
                    name=f"{settings_dict[self.current]['name']} - {'ON' if settings[self.current] else 'OFF'}",
                    value=settings_dict[self.current]["description"],
                )
                self.embed.color = (
                    discord.Color.green() if settings[self.current] else discord.Color.red()
                )
                await interaction.response.edit_message(embed=self.embed)

            @discord.ui.button(label="Save")
            async def save_button(self, interaction: Interaction, button: discord.Button):
                await user.save()
                self.embed.set_footer(text="Settings saved!")
                self.clear_items()
                await interaction.response.edit_message(embed=self.embed, view=self)

        view = SettingsView()
        await interaction.response.send_message(embed=view.embed, view=view)


async def setup(bot):
    await bot.add_cog(Settings(bot))
