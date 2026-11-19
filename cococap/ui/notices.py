"""The notice popup: every notice a player has not seen yet, sent only to them (ephemeral) when they open the hub, one notice per page with
◀ ▶ to turn and Close. `open_screen` calls `check` after the menu is sent, so no screen has to know about it. A failure here must never break
opening the menu: a missing popup is better than no menu (the notices stay unseen and pop up next time)."""

import logging

import discord

from cococap import emojis
from cococap.registry.models import Notice
from cococap.services import news
from cococap.user import User

log = logging.getLogger(__name__)

TIMEOUT = 600  # seconds the buttons keep working
COLOUR = discord.Colour(0xE6B34A)  # the More page's accent


def embed(notices: list[Notice], page: int) -> discord.Embed:
    notice = notices[page]
    out = discord.Embed(title=notice.title, description=notice.body.strip(), colour=COLOUR)
    more = f"  ·  {page + 1}/{len(notices)}" if len(notices) > 1 else ""
    out.set_footer(text=f"{news.day(notice.date)}{more}  ·  All messages: More → News")
    return out


class NoticeView(discord.ui.View):
    def __init__(self, notices: list[Notice]):
        super().__init__(timeout=TIMEOUT)
        self.notices, self.page = notices, 0
        if len(notices) > 1:
            self.prev = discord.ui.Button(emoji=emojis.icon("prev", "◀️"), style=discord.ButtonStyle.secondary, disabled=True)
            self.next = discord.ui.Button(emoji=emojis.icon("next", "▶️"), style=discord.ButtonStyle.secondary)
            self.prev.callback, self.next.callback = self._turn(-1), self._turn(1)
            self.add_item(self.prev)
            self.add_item(self.next)
        close = discord.ui.Button(label="Close", style=discord.ButtonStyle.secondary)
        close.callback = self.close
        self.add_item(close)

    def _turn(self, step: int):
        async def turn(interaction: discord.Interaction) -> None:
            self.page = max(0, min(len(self.notices) - 1, self.page + step))
            self.prev.disabled, self.next.disabled = self.page == 0, self.page == len(self.notices) - 1
            await interaction.response.edit_message(embed=embed(self.notices, self.page), view=self)

        return turn

    async def close(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()


async def check(interaction: discord.Interaction, user: User) -> None:
    """Pop up the player's unseen notices (if any) and mark them seen once the popup has gone out."""
    try:
        fresh = news.unseen(user)
        if not fresh:
            return
        await interaction.followup.send(embed=embed(fresh, 0), view=NoticeView(fresh), ephemeral=True)
        await news.mark_seen(user, fresh)
    except Exception:
        log.exception("notice popup failed")
