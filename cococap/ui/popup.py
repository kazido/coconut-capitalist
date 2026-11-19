"""Popups: a small ephemeral embed (only the player sees it) with Share and Close buttons.

Rare drops and level-ups use it, so the loot screen stays the last screen of an action. ``send`` never raises: a missing popup is better than a
broken click. Share asks for a text channel (a ChannelSelect) and posts the same embed publicly with the player's name on it.
"""

import logging

import discord

from cococap import emojis
from cococap.constants import Rarities
from cococap.registry import Item
from cococap.services.odds import Odds
from cococap.ui import flair

log = logging.getLogger(__name__)

TIMEOUT = 600  # seconds the buttons keep working


def rarity_colour(rarity: int) -> discord.Colour:
    return discord.Colour(int(Rarities.from_value(rarity).color, 16))


def rare_embed(finds: list[tuple[int, Item, int, Odds | None]]) -> discord.Embed:
    """One embed for the rare drops of one action: item, quantity, rarity and drop odds for each. `finds` is (flair level, item, quantity, odds)."""
    best = max(finds, key=lambda f: (f[0], f[1].rarity))
    super_rare = best[0] == 2
    embed = discord.Embed(title=("A super rare find!" if super_rare else "A rare find!"), colour=rarity_colour(best[1].rarity))
    for lvl, item, quantity, odds in finds:
        rate = f"{emojis.icon('dice', '🎲')} {odds.text()}" if odds else f"{emojis.icon('dice', '🎲')} {Rarities.from_value(item.rarity).rarity_name}"
        name = f"{item.emoji or ''} {quantity:,} × {item.name}".strip()
        embed.add_field(name=name, value=f"{Rarities.from_value(item.rarity).rarity_name}  ·  {rate}" + (f"\n*{item.description}*" if lvl == 2 and item.description else ""),
                        inline=False)
    return embed


def sorted_finds(items: dict[str, int], lookup) -> list[tuple[int, Item, int, Odds | None]]:
    """The rare finds in `items` with their odds from `lookup` (item id -> Odds or None), best first."""
    return [(lvl, item, q, lookup(item.id) if lookup else None) for lvl, item, q in flair.finds(items)]


class PopupView(discord.ui.View):
    def __init__(self, embed: discord.Embed, owner: discord.abc.User):
        super().__init__(timeout=TIMEOUT)
        self.embed, self.owner = embed, owner

    @discord.ui.button(label="Share", style=discord.ButtonStyle.primary)
    async def share(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(view=ShareView(self))

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()


class ShareView(discord.ui.View):
    """Pick the channel to post the popup in."""

    def __init__(self, popup: PopupView):
        super().__init__(timeout=TIMEOUT)
        self.popup = popup
        picker = discord.ui.ChannelSelect(placeholder="Share in which channel?", channel_types=[discord.ChannelType.text], min_values=1, max_values=1)
        picker.callback = self.picked
        self.add_item(picker)

    async def picked(self, interaction: discord.Interaction) -> None:
        channel = self.children[0].values[0]
        note = await self.post(interaction, channel)
        await interaction.response.edit_message(content=note, view=self.popup)

    async def post(self, interaction: discord.Interaction, channel) -> str:
        """Post the embed publicly with the player's name on it; the answer for the player."""
        embed = self.popup.embed.copy()
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
        try:
            target = channel.resolve() if hasattr(channel, "resolve") else channel
            target = target or await interaction.client.fetch_channel(channel.id)
            await target.send(embed=embed)
        except (discord.Forbidden, discord.NotFound):
            return "I can't post in that channel. Try another one, or ask a mod to let me send messages there."
        except discord.HTTPException:
            log.exception("sharing a popup failed")
            return "That didn't work. Try another channel."
        return f"Shared in {getattr(target, 'mention', 'the channel')}."


async def send(interaction: discord.Interaction, embed: discord.Embed, owner: discord.abc.User | None = None, ephemeral: bool = True) -> None:
    """Send the popup as a follow-up (ephemeral by default: only the player sees it). Errors are logged and swallowed."""
    try:
        await interaction.followup.send(embed=embed, view=PopupView(embed, owner or interaction.user), ephemeral=ephemeral)
    except Exception:
        log.exception("popup failed")
