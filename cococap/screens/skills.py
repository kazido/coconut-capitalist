import discord

from cococap import emojis

from cococap.services import smithing
from cococap.services.stats import SKILL_PAGE_ICONS
from cococap.ui import Page, Screen
from cococap.ui.components import button, section, xp_bar
from cococap.user import User

# skill -> the screen that plays it
SKILL_SCREENS: dict[str, str | None] = {"mining": "mining", "farming": "farm", "foraging": "forage", "fishing": "fish", "combat": "combat", "smithing": "smithing"}


class SkillsScreen(Screen):
    """The main skills: one row per skill, each with its level and a button into its screen."""

    id = "skills"
    label = "Skills"
    emoji = emojis.Lazy("ui_skills", "📈")
    description = "Mining, farming, foraging, fishing, combat and smithing"
    links = ("mining", "farm", "forage", "fish", "combat", "smithing")

    async def build(self) -> Page:
        body = [*self.note_block()]
        for name, screen_id in SKILL_SCREENS.items():
            icon = emojis.skill(name, SKILL_PAGE_ICONS[name])
            xp = await smithing.smithing_xp(self.user) if name == "smithing" else (await self.user.skill(name)).xp
            overflow, needed = User.xp_for_next_level(xp)
            line = f"### {icon} {name.title()}  ·  Lv {User.xp_to_level(xp)}\n{xp_bar(overflow / needed if needed else 0, 8)}"
            accessory = (
                button("Open", style=discord.ButtonStyle.primary, on_click=self._opener(screen_id))
                if screen_id
                else button("Paused", disabled=True)
            )
            body.append(section(line, accessory=accessory))
        return Page("Skills", body, accent=0x9E492F)

    def _opener(self, screen_id: str):
        async def go(interaction: discord.Interaction) -> None:
            await self.go(interaction, screen_id)

        return go
