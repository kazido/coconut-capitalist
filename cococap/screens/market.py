import random
import time

import discord

from cococap.registry import get_registry
from cococap.services import farming
from cococap.ui import Page, Screen
from cococap.ui.components import bits, button, row, sep, text


class MarketScreen(Screen):
    id = "market"
    label = "Farmer's Market"
    emoji = "🧺"
    description = "Fridays and Saturdays: better crop prices, and blessings for land deeds"
    links = ("farm",)

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.farming
        skill = await self.user.skill("farming")
        level, now = farming.level_of(skill), time.time()
        is_open, changes = farming.market_window(now, reg)
        if level < rules.market.min_level:
            return Page("Farmer's Market", [
                *self.note_block(),
                text(f"🔒 The market opens to farmers of **level {rules.market.min_level}** (you are level {level})."),
            ], accent=0xE6B34A)

        crops = {i: q for i, q in (await self.user.items()).items() if (it := reg.find_item(i)) and it.category == "crop" and it.sellable}
        total = sum(farming.market_price(i, q, reg) for i, q in crops.items())
        status = (f"🟢 **Open** until <t:{changes}:R>" if is_open else f"🔴 **Closed.** Opens <t:{changes}:R>")
        lines = [f"{reg.item(i).display} x{q:,}  →  **{bits(farming.market_price(i, q, reg))}** bits" for i, q in crops.items()]
        body = [
            *self.note_block(),
            text(f"{status}\nCrops sell for **+{rules.market.price_bonus:.0%}** while the market is open."),
            sep(),
            text("**Your crops**\n" + ("\n".join(lines) if lines else "None to sell.")),
            text(f"💧 **{skill.rain_god_blessings}** rain god's blessing(s)  ·  each has a **{rules.market.deed_chance:.0%}** chance to become a "
                 f"{reg.item(rules.deed_item).display}"),
            row(
                button(f"Sell all ({bits(total)})" if total else "Sell all", emoji="💰", style=discord.ButtonStyle.success,
                       disabled=not (is_open and crops), on_click=self._sell),
                button("Deposit blessings", emoji="💧", disabled=not (is_open and skill.rain_god_blessings), on_click=self._deposit),
            ),
        ]
        return Page("Farmer's Market", body, accent=0xE6B34A)

    async def _sell(self, interaction: discord.Interaction) -> None:
        earned, sold = await farming.sell_crops(self.user)
        await self.refresh(interaction, f"Sold {sum(sold.values()):,} crop(s) for **{bits(earned)}** bits.")

    async def _deposit(self, interaction: discord.Interaction) -> None:
        used, deeds = await farming.deposit_blessings(self.user, random.Random())
        deed = get_registry().item(get_registry().farming.deed_item).name
        await self.refresh(interaction, f"Deposited {used} blessing(s): " + (f"you received {deeds} {deed}!" if deeds else "no deed this time. Better luck next rain!"))
