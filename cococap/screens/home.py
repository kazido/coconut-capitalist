import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services.party import Party
from cococap.services import economy, party_invites, trade
from cococap.ui import Page, Screen
from cococap.ui.components import bits, button, row, section, sep, text
from cococap.user import Cooldowns

# The main things to do, each its own section with an Open button; one row of smaller things at the bottom (then More, which also
# holds Trade and the Minigames).
FEATURED = ["skills", "shipments", "shop", "inventory", "pets", "checkin"]
SECOND_ROW = ["ship", "player", "rank", "party"]
MORE_LINKS = ["trade", "games", "bestiary", "wiki", "settings"]
PARTY_NAMES_SHOWN = 4


def balance_line(user) -> str:
    return (
        f"{emojis.currency('bits')} **{bits(user.purse)}**  ·  "
        f"{emojis.currency('tokens')} **{bits(user.tokens)}**  ·  {emojis.currency('luckbucks')} **{bits(user.luckbucks)}**"
    )


def anything_ready(user) -> bool:
    """Is any check-in (work, daily or weekly) ready to claim? The timers live on the Check-in page."""
    return any(economy.cooldown_state(user, c).ready for c in (Cooldowns.WORK, Cooldowns.DAILY, Cooldowns.WEEKLY))


def check_in_line(user) -> str:
    return f"{emojis.icon('check', '✅')} Check-in ready" if anything_ready(user) else f"{emojis.icon('timer', '⏳')} Check-in not ready yet"


def _opener(screen: Screen, screen_id: str):
    async def go(interaction: discord.Interaction) -> None:
        await screen.go(interaction, screen_id)

    return go


class HomeScreen(Screen):
    id = "home"
    label = "Home"
    emoji = emojis.icon('coconut', '🥥')
    description = "Where everything starts"
    links = (*FEATURED, *SECOND_ROW, "more")

    async def party_summary(self) -> str | None:
        """The party line, only for a player who is in a party."""
        party = await Party.for_user(self.user.id)
        if party is None:
            return None
        shown = [
            f"{await self.nav.name_of(member_id)}{(' ' + emojis.icon('crown', '👑')) if party.is_owner(member_id) else ''}"
            for member_id in party.members[:PARTY_NAMES_SHOWN]
        ]
        extra = party.member_count() - len(shown)
        return f"{emojis.icon('group', '👥')} **Party:** {', '.join(shown)}" + (f" +{extra} more" if extra > 0 else "")

    async def invite_sections(self) -> list:
        """A line and a button for a waiting party invite and for a waiting trade invite."""
        out = []
        if (invite := party_invites.pending_for(self.user.id)) is not None:
            out.append(section(
                f"### {emojis.icon('group', '👥')} Party invite\n{await self.nav.name_of(invite.inviter_id)} invited you to their party.",
                accessory=button("Accept", style=discord.ButtonStyle.success, on_click=_opener(self, "party")),
            ))
        if (offer := trade.invite_for(self.user.id)) is not None:
            out.append(section(
                f"### {emojis.icon('trade', '🤝')} Trade invite\n{await self.nav.name_of(offer.sender_id)} wants to trade with you.",
                accessory=button("Open", style=discord.ButtonStyle.success, on_click=_opener(self, "trade")),
            ))
        return out

    async def build(self) -> Page:
        rank = get_registry().rank(self.user.rank)
        ready = anything_ready(self.user)
        lines = [f"**{self.nav.owner.display_name}**  ·  {rank.emoji} {rank.display_name}", balance_line(self.user), check_in_line(self.user)]
        if (party_line := await self.party_summary()) is not None:
            lines.append(party_line)
        body = [*self.note_block(), text("\n".join(lines)), sep()]
        body += await self.invite_sections()
        for screen_id in FEATURED:
            target = self.nav.screens[screen_id]
            lit = screen_id == "checkin" and ready
            body.append(section(
                f"### {target.emoji} {target.label}",
                accessory=button("Open", style=discord.ButtonStyle.success if lit else discord.ButtonStyle.primary, on_click=_opener(self, screen_id)),
            ))
        second = [button(self.nav.screens[i].label, emoji=self.nav.screens[i].emoji, on_click=_opener(self, i)) for i in SECOND_ROW]
        second.append(button("More", emoji=emojis.icon('next', '➡️'), on_click=_opener(self, "more")))
        body.append(row(*second))
        return Page("Coconut Capitalist", body, accent=0xE6B34A)


class MoreScreen(Screen):
    """The less-used pages, so the home page stays clean."""

    id = "more"
    label = "More"
    emoji = emojis.icon('next', '➡️')
    description = "Trade, games, bestiary, wiki and settings"
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
