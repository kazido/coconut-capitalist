import discord

from cococap.registry import get_registry
from cococap.services.party import Party
from cococap.services import economy
from cococap.ui import Page, Screen
from cococap.ui.components import bits, button, row, section, sep, text
from cococap.user import Cooldowns

# The two big things to do, as full sections; the everyday shortcuts sit in one row; the rest is on "More".
FEATURED = ["skills", "minigames"]
SHORTCUTS = ["checkin", "inventory", "shop", "pets"]
MORE_LINKS = ["wiki", "profile", "rank", "top", "stats", "settings"]
PARTY_NAMES_SHOWN = 4


def balance_line(user) -> str:
    return (
        f"💸 **{bits(user.purse)}**  ·  "
        f"🪙 **{bits(user.tokens)}**  ·  🍀 **{bits(user.luckbucks)}**"
    )


def anything_ready(user) -> bool:
    """Is any check-in (work, daily or weekly) ready to claim? The timers live on the Check-in page."""
    return any(economy.cooldown_state(user, c).ready for c in (Cooldowns.WORK, Cooldowns.DAILY, Cooldowns.WEEKLY))


def check_in_line(user) -> str:
    return "✅ Check-in ready" if anything_ready(user) else "⏳ Check-in not ready yet"


def _opener(screen: Screen, screen_id: str):
    async def go(interaction: discord.Interaction) -> None:
        await screen.go(interaction, screen_id)

    return go


class HomeScreen(Screen):
    id = "home"
    label = "Home"
    emoji = "🥥"
    description = "Where everything starts"
    links = (*FEATURED, *SHORTCUTS, "party", "more")

    async def party_summary(self) -> str:
        party = await Party.for_user(self.user.id)
        if party is None:
            return "### 👥 Party\nNot in a party yet."
        shown = [
            f"{await self.nav.name_of(member_id)}{' 👑' if party.is_owner(member_id) else ''}"
            for member_id in party.members[:PARTY_NAMES_SHOWN]
        ]
        extra = party.member_count() - len(shown)
        return f"### 👥 Party\n{', '.join(shown)}" + (f" +{extra} more" if extra > 0 else "")

    async def build(self) -> Page:
        rank = get_registry().rank(self.user.rank)
        ready = anything_ready(self.user)
        body = [
            *self.note_block(),
            text(f"**{self.nav.owner.display_name}**  ·  {rank.emoji} {rank.display_name}\n"
                 f"{balance_line(self.user)}\n{check_in_line(self.user)}"),
            sep(),
            section(await self.party_summary(), accessory=button("Open", on_click=_opener(self, "party"))),
        ]
        for screen_id in FEATURED:
            target = self.nav.screens[screen_id]
            body.append(section(
                f"### {target.emoji} {target.label}\n{target.description}",
                accessory=button("Open", style=discord.ButtonStyle.primary, on_click=_opener(self, screen_id)),
            ))
        shortcuts = []
        for screen_id in SHORTCUTS:
            target = self.nav.screens[screen_id]
            lit = screen_id == "checkin" and ready
            shortcuts.append(button(target.label, emoji=target.emoji,
                                    style=discord.ButtonStyle.success if lit else discord.ButtonStyle.secondary,
                                    on_click=_opener(self, screen_id)))
        shortcuts.append(button("More", emoji="➡️", on_click=_opener(self, "more")))
        body.append(row(*shortcuts))
        return Page("Coconut Capitalist", body, accent=0xE6B34A)


class MoreScreen(Screen):
    """The less-used pages, so the home page stays clean."""

    id = "more"
    label = "More"
    emoji = "➡️"
    description = "Profile, rank, leaderboard, stats and settings"
    links = tuple(MORE_LINKS)

    async def build(self) -> Page:
        body = [*self.note_block()]
        for screen_id in MORE_LINKS:
            target = self.nav.screens[screen_id]
            body.append(section(
                f"### {target.emoji} {target.label}\n{target.description}",
                accessory=button("Open", on_click=_opener(self, screen_id)),
            ))
        return Page("More", body, accent=0xE6B34A)
