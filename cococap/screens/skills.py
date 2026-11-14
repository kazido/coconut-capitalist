import discord

from cococap.services.stats import SKILL_ICONS
from cococap.ui import Page, Screen
from cococap.ui.components import bar, button, section, text, xp_bar
from cococap.user import User

# skill -> (one-line pitch, screen id when it is playable)
SKILL_INFO = {
    "mining": ("Push your luck: dig deeper for rarer ores and gems.", "mining"),
    "farming": ("Plan your plots and wait for the rain.", "farm"),
    "foraging": ("Fell trees alone or together with the whole server.", "forage"),
    "fishing": ("Cast a line, reel in the big one and sell your catch.", "fish"),
    "combat": ("Turn-based fights: speed, cooldowns, timing.", "fight"),
}


class SkillsScreen(Screen):
    id = "skills"
    label = "Skills"
    emoji = "📈"
    description = "Mining, farming, foraging, fishing and combat"
    links = ("mining", "farm", "forage", "fish", "fight")

    async def build(self) -> Page:
        body = [*self.note_block()]
        for name, (blurb, screen_id) in SKILL_INFO.items():  # playable skills first
            icon = SKILL_ICONS[name]
            xp = (await self.user.skill(name)).xp
            overflow, needed = User.xp_for_next_level(xp)
            line = f"### {icon} {name.title()}  ·  Lv {User.xp_to_level(xp)}\n{xp_bar(overflow / needed if needed else 0, 8)}  {blurb}"
            accessory = (
                button("Open", style=discord.ButtonStyle.primary, on_click=self._opener(screen_id))
                if screen_id
                else button("Soon", disabled=True)
            )
            body.append(section(line, accessory=accessory))
        return Page("Skills", body, accent=0x9E492F)

    def _opener(self, screen_id: str):
        async def go(interaction: discord.Interaction) -> None:
            await self.go(interaction, screen_id)

        return go
