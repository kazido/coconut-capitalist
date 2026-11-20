import discord

from cococap import emojis

from cococap.registry import get_registry
from cococap.services import smithing
from cococap.services.stats import SKILL_ICONS
from cococap.ui import Page, Screen
from cococap.ui.components import bar, button, row, section, sep, text, xp_bar
from cococap.ui.tabs import TabsScreen
from cococap.user import User

# skill -> the screen that plays it
SKILL_SCREENS: dict[str, str | None] = {"mining": "mining", "farming": "farm", "foraging": "forage", "fishing": "fish", "combat": None}  # combat is paused while it is redesigned (the fight screen still exists)


class SkillsPane(Screen):
    """The main skills: one row per skill, each with its level and a button into its screen."""

    label = "Skills"
    emoji = emojis.Lazy("ui_skills", "📈")
    links = ("mining", "farm", "forage", "fish")

    async def build(self) -> Page:
        body = [*self.note_block()]
        for name, screen_id in SKILL_SCREENS.items():
            icon = emojis.skill(name, SKILL_ICONS[name])
            xp = (await self.user.skill(name)).xp
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


class SmithingLightPane(Screen):
    """Smithing's level, xp to the next one, the max part tier now and the next unlock. Tools are smithed on Tools -> Smithing."""

    label = "Smithing"
    emoji = emojis.Lazy("ui_anvil", "🧰")

    async def build(self) -> Page:
        rules = get_registry().smithing
        xp = await smithing.smithing_xp(self.user)
        level = User.xp_to_level(xp)
        overflow, needed = User.xp_for_next_level(xp)
        swap = rules.levels.swap_unlock_level
        if swap > level:
            next_line = f"Next unlock: Lv {swap}, swapping one part of a tool"
        else:
            next_line = "Everything unlocked."
        # One compact block per lesser skill: name + level, a bar, then one quiet line of facts.
        body = [
            text(f"### {self.emoji} Smithing  ·  Lv {level}\n{bar(overflow / needed if needed else 0, 10)}\n"
                 f"{next_line}\n-# Smith tools on Tools -> Smithing."),
        ]
        return Page("Lesser skills", body, accent=0x9E492F)


# The lesser skills (small skills that sit beside the main four). Later ones are added here and show up as rows on the Lesser tab.
LIGHT_SKILLS: list[type[Screen]] = [SmithingLightPane]


class LightSkillsPane(Screen):
    label = "Lesser skills"
    emoji = emojis.Lazy("ui_skills", "📈")

    async def build(self) -> Page:
        body: list = [*self.note_block()]
        for pane_cls in LIGHT_SKILLS:
            body.extend((await pane_cls(self.nav).build()).body)
            body.append(sep())
        return Page("Lesser skills", body[:-1] if LIGHT_SKILLS else [text("No lesser skills yet.")], accent=0x9E492F)


class SkillsScreen(TabsScreen):
    """The Skills page: the main skills, and a Lesser tab for the small skills (smithing)."""

    id = "skills"
    label = "Skills"
    emoji = emojis.Lazy("ui_skills", "📈")
    description = "Mining, farming, foraging, fishing and combat; lesser skills like smithing"
    links = ("mining", "farm", "forage", "fish")
    panes = {"skills": SkillsPane, "light": LightSkillsPane}
