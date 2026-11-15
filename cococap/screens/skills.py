import discord

from cococap.services.stats import SKILL_ICONS
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, section, xp_bar
from cococap.user import User

# skill -> the screen that plays it
SKILL_SCREENS = {"mining": "mining", "farming": "farm", "foraging": "forage", "fishing": "fish", "combat": "fight"}


class SkillsScreen(Screen):
    id = "skills"
    label = "Skills"
    emoji = "📈"
    description = "Mining, farming, foraging, fishing and combat"
    links = ("mining", "farm", "forage", "fish", "fight", "shipments")

    async def build(self) -> Page:
        body = [*self.note_block()]
        for name, screen_id in SKILL_SCREENS.items():
            icon = SKILL_ICONS[name]
            xp = (await self.user.skill(name)).xp
            overflow, needed = User.xp_for_next_level(xp)
            line = f"### {icon} {name.title()}  ·  Lv {User.xp_to_level(xp)}\n{xp_bar(overflow / needed if needed else 0, 8)}"
            accessory = (
                button("Open", style=discord.ButtonStyle.primary, on_click=self._opener(screen_id))
                if screen_id
                else button("Soon", disabled=True)
            )
            body.append(section(line, accessory=accessory))
        body.append(row(button("Shipments", emoji="📦", on_click=self._opener("shipments"))))
        return Page("Skills", body, accent=0x9E492F)

    def _opener(self, screen_id: str):
        async def go(interaction: discord.Interaction) -> None:
            await self.go(interaction, screen_id)

        return go
