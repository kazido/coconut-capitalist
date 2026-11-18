import discord
from discord import ui

from cococap import emojis
from cococap.registry import get_registry
from cococap.services.stats import SKILL_ICONS
from cococap.ui import Page, Screen
from cococap.ui.components import bar, bits, section, sep, text, xp_bar
from cococap.user import User


class ProfileScreen(Screen):
    id = "profile"
    label = "Profile"
    emoji = "👤"
    description = "Your balances, rank and skill levels"

    async def build(self) -> Page:
        reg = get_registry()
        user = self.user
        rank = reg.rank(user.rank)
        avatar = self.nav.owner.display_avatar
        header = section(
            f"### {self.nav.owner.display_name}",
            f"{rank.emoji} **{rank.display_name}**  ·  wage {bits(rank.wage)} bits",
            accessory=ui.Thumbnail(getattr(avatar, "url", str(avatar))),
        )
        skills = []
        for name, glyph in SKILL_ICONS.items():
            icon = emojis.skill(name, glyph)
            xp = (await user.skill(name)).xp
            overflow, needed = User.xp_for_next_level(xp)
            skills.append(f"{icon} **{name.title()}** Lv {User.xp_to_level(xp)}  {xp_bar(overflow / needed if needed else 0, 8)}")
        body = [
            *self.note_block(),
            header,
            text(f"{emojis.currency('bits')} Purse **{bits(user.purse)}**\n{emojis.currency('tokens')} Tokens **{bits(user.tokens)}**\n{emojis.currency('luckbucks')} Luckbucks **{bits(user.luckbucks)}**"),
            sep(),
            text("\n".join(skills)),
        ]
        return Page("Profile", body, accent=discord.Colour.blue().value)
