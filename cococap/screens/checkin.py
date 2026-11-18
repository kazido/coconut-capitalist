import discord
import randfacts

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import economy
from cococap.ui import Page, Screen
from cococap.ui.components import bits, button, duration, section, sep, text
from cococap.user import Cooldowns


class CheckInScreen(Screen):
    id = "checkin"
    label = "Check-in"
    emoji = "📅"
    description = "Claim your work, daily and weekly rewards"

    def _claim_button(self, cooldown: Cooldowns, handler):
        state = economy.cooldown_state(self.user, cooldown)
        if state.ready:
            return button("Claim", emoji="✅", style=discord.ButtonStyle.success, on_click=handler)
        return button(duration(state.seconds_left), emoji="⏳", disabled=True)

    async def build(self) -> Page:
        wage = get_registry().rank(self.user.rank).wage
        body = [
            *self.note_block(),
            section("### 💼 Work", f"Your wage: **{emojis.bits(wage)}**  ·  every {Cooldowns.WORK.value}h",
                    accessory=self._claim_button(Cooldowns.WORK, self._work)),
            section("### 🌅 Daily", f"Interest on your bits + **{economy.DAILY_TOKENS}** token  ·  every {Cooldowns.DAILY.value}h",
                    accessory=self._claim_button(Cooldowns.DAILY, self._daily)),
            section("### 🗓️ Weekly", f"**{get_registry().economy.weekly_luckbucks}** luckbucks  ·  every {Cooldowns.WEEKLY.value}h",
                    accessory=self._claim_button(Cooldowns.WEEKLY, self._weekly)),
        ]
        return Page("Check-in", body, accent=discord.Colour.dark_blue().value)

    async def _work(self, interaction: discord.Interaction) -> None:
        reward = await economy.claim_work(self.user)
        await self.refresh(interaction, f"{emojis.currency('bits')} Work: +{emojis.bits(reward.wage)}.")

    async def _daily(self, interaction: discord.Interaction) -> None:
        reward = await economy.claim_daily(self.user)
        await self.refresh(
            interaction,
            f"🌅 Daily: +{emojis.bits(reward.interest)} interest, +{reward.tokens} token.\n> 💡 {randfacts.get_fact()}",
        )

    async def _weekly(self, interaction: discord.Interaction) -> None:
        luck = await economy.claim_weekly(self.user)
        await self.refresh(interaction, f"🍀 Weekly: +{luck} luckbucks.")
