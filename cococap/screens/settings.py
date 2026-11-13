import discord

from cococap.ui import Page, Screen
from cococap.ui.components import button, section, text

# key -> (name, what it does)
SETTINGS = {
    "auto_deposit": ("Auto deposit", "Your work wage goes straight into the bank."),
}


class SettingsScreen(Screen):
    id = "settings"
    label = "Settings"
    emoji = "⚙️"
    description = "Change how the bot treats you"

    async def build(self) -> Page:
        body = [*self.note_block(), text("Changes save instantly.")]
        for key, (name, blurb) in SETTINGS.items():
            on = getattr(self.user.settings, key)
            body.append(
                section(
                    f"### {name}",
                    blurb,
                    accessory=button(
                        "ON" if on else "OFF",
                        style=discord.ButtonStyle.success if on else discord.ButtonStyle.secondary,
                        on_click=self._toggler(key),
                    ),
                )
            )
        return Page("Settings", body, accent=0x4CAF50)

    def _toggler(self, key: str):
        async def toggle(interaction: discord.Interaction) -> None:
            new = not getattr(self.user.settings, key)
            await self.user.set_setting(key, new)
            await self.refresh(interaction, f"{SETTINGS[key][0]} is now {'ON' if new else 'OFF'}.")

        return toggle
