import discord

from cococap.errors import CustomError
from cococap import emojis
from cococap.registry import get_registry
from cococap.ui import Page, Screen
from cococap.ui.components import bits, button, section, sep, text


class RankScreen(Screen):
    id = "rank"
    label = "Ranks"
    emoji = "🏅"
    description = "Spend tokens on a higher wage"

    async def build(self) -> Page:
        reg = get_registry()
        rank = reg.rank(self.user.rank)
        nxt = reg.next_rank(rank.rank_id)
        body = [
            *self.note_block(),
            text(f"### {rank.emoji} {rank.display_name}\n{rank.description}\n**Wage:** {emojis.bits(rank.wage)}  ·  **XP:** +{rank.xp_bonus:.0%} to every skill"),
            sep(),
        ]
        if nxt is None:
            body.append(text("🏆 **You've reached the max rank!** Nice job!"))
        else:
            affordable = self.user.tokens >= nxt.token_price
            body.append(
                section(
                    f"### Next: {nxt.emoji} {nxt.display_name}",
                    f"Wage **{emojis.bits(nxt.wage)}**  ·  XP +{nxt.xp_bonus:.0%}  ·  costs **{bits(nxt.token_price)}** {emojis.currency('tokens')} (you have {bits(self.user.tokens)})",
                    accessory=button(
                        "Rank up",
                        emoji=emojis.currency("tokens"),
                        style=discord.ButtonStyle.success if affordable else discord.ButtonStyle.secondary,
                        disabled=not affordable,
                        on_click=self._rank_up,
                    ),
                )
            )
        return Page("Ranks", body, accent=int(rank.color, 16))

    async def _rank_up(self, interaction: discord.Interaction) -> None:
        reg = get_registry()
        nxt = reg.next_rank(self.user.rank)
        if nxt is None or not await self.user.rank_up(nxt.rank_id, nxt.token_price):
            raise CustomError("You can't rank up right now. You need enough tokens and this must be your next rank.")
        await self.refresh(interaction, f"You are now rank **{nxt.display_name}** {nxt.emoji}!")
