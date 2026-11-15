import discord

from cococap.ui import Page, Screen
from cococap.ui.components import button, section, text

# key -> (name, what it does)
SETTINGS: dict[str, tuple[str, str]] = {
    "confirm_sell_all": ("Confirm Sell all", "Ask before a skill's Sell all button sells everything it has gathered (turn off to sell with one press)."),
    "keep_upgrade_materials": ("Keep upgrade materials", "Sell all holds back the materials the next upgrade of any tool you own needs (the most one upgrade asks for, both roads at a fork), so you never sell something you were saving."),
    "confirm_upgrades": ("Confirm tool upgrades", "Upgrading a tool takes a second press, so a costly or one-way (fork) upgrade is never an accident."),
    "fishing_estimate": ("Fishing wait estimate", "Show how long your rod usually takes to get a bite on the Fishing page."),
}


class SettingsScreen(Screen):
    id = "settings"
    label = "Settings"
    emoji = "⚙️"
    description = "Change how the bot treats you"

    async def build(self) -> Page:
        body = [*self.note_block(), text("Changes save instantly." if SETTINGS else "There is nothing to change yet.")]
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
