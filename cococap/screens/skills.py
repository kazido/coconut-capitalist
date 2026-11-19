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
        cap = smithing.max_part_tier(level, rules)
        # The next unlock is whichever comes first: a higher part tier, or the part-swap level.
        unlocks = [(lvl, f"parts up to tier {tier}") for lvl, tier in rules.levels.max_tier_by_level if lvl > level]
        swap = rules.levels.swap_unlock_level
        if swap > level:
            unlocks.append((swap, "swapping one part of a tool"))
        if unlocks:
            lvl, what = min(unlocks)
            next_line = f"Next unlock: Lv {lvl}, {what}"
        else:
            next_line = "Everything unlocked."
        body = [
            text(f"### Smithing  ·  Lv {level}\n{bar(overflow / needed if needed else 0, 10)}"),
            text(f"Max part tier: **{cap}**\n{next_line}"),
            sep(),
            text("Smith tools on Tools -> Smithing."),
        ]
        return Page("Light skills", body, accent=0x9E492F)


# The light skills (small skills that sit beside the main four). Later ones are added here and show up as rows on the Light tab.
LIGHT_SKILLS: list[type[Screen]] = [SmithingLightPane]


class LightSkillsPane(Screen):
    label = "Light skills"
    emoji = emojis.Lazy("ui_skills", "📈")

    async def build(self) -> Page:
        body: list = [*self.note_block()]
        for pane_cls in LIGHT_SKILLS:
            body.extend((await pane_cls(self.nav).build()).body)
            body.append(sep(large=True))
        return Page("Light skills", body[:-1] if LIGHT_SKILLS else [text("No light skills yet.")], accent=0x9E492F)


class SkillsScreen(TabsScreen):
    """The Skills page: the main skills, and a Light tab for the small skills (smithing)."""

    id = "skills"
    label = "Skills"
    emoji = emojis.Lazy("ui_skills", "📈")
    description = "Mining, farming, foraging, fishing and combat; light skills like smithing"
    links = ("mining", "farm", "forage", "fish")
    panes = {"skills": SkillsPane, "light": LightSkillsPane}
