import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import crafting, shop, upgrades
from cococap.ui import Page, Result, Screen
from cococap.ui.components import bits, button, row, text

SHOWN = 8


async def upgrade_needs_by_tool(user) -> dict[str, tuple[int, list[str]]]:
    """What the next upgrade of EVERY tool you own asks for (both roads at a fork), and what every Workbench recipe and a crab pot use:
    item -> (how many, what wants it). The amount is the most any ONE upgrade or craft needs, not the total: you do them one at a time,
    so one pile can serve them all."""
    needs: dict[str, tuple[int, list[str]]] = {}
    for offer in await upgrades.offers(user):
        for item_id, quantity in offer.cost.items.items():
            have, tools = needs.get(item_id, (0, []))
            needs[item_id] = (max(have, quantity), [*tools, offer.target.name])
    for item_id, (quantity, uses) in crafting.needed_items().items():
        have, tools = needs.get(item_id, (0, []))
        needs[item_id] = (max(have, quantity), [*tools, *uses])
    return needs


async def upgrade_needs(user) -> dict[str, int]:
    """Just the amounts (what Sell all holds back)."""
    return {item_id: quantity for item_id, (quantity, _) in (await upgrade_needs_by_tool(user)).items()}


async def start_sell_all(screen: Screen, interaction: discord.Interaction, skill: str) -> None:
    """A skill's Sell all button: straight to selling if you turned confirming off, otherwise to the confirm page."""
    if screen.user.settings.confirm_sell_all:
        return await screen.go(interaction, "sellall", skill=skill)
    keep = await upgrade_needs(screen.user) if screen.user.settings.keep_upgrade_materials else None
    earned, sold = await shop.sell_all_for_skill(screen.user, skill, keep=keep)
    await screen.refresh(interaction, f"💰 Sold {sum(sold.values()):,} items for **{bits(earned)}** bits." if sold else "You have nothing from this skill to sell.")


class SellAllScreen(Screen):
    """"Sell everything this skill gave you?": what it is worth, and a way to keep what your upgrades need."""

    id = "sellall"
    label = "Sell all"
    emoji = "💰"
    description = "Sell everything one skill gave you"
    links = ()

    def __init__(self, nav):
        super().__init__(nav)
        self.skill = "mining"

    async def build(self) -> Page:
        reg = get_registry()
        owned = await self.user.items()
        everything = shop.sellable_for_skill(owned, self.skill, reg)
        if not everything:
            return Page("Sell all", [*self.note_block(), text(f"{emojis.skill(self.skill)} You have nothing from **{self.skill}** to sell."),
                                     row(button("Back", on_click=self._cancel))], accent=0xD4A017)
        needs = await upgrade_needs(self.user)
        kept = shop.sellable_for_skill(owned, self.skill, reg, needs)
        worth = sum(reg.item(i).sell_price * q for i, q in everything.items())
        keep_worth = sum(reg.item(i).sell_price * q for i, q in kept.items())
        top = sorted(everything.items(), key=lambda kv: -reg.item(kv[0]).sell_price * kv[1])[:SHOWN]
        lines = "\n".join(f"{reg.item(i).display} ×{q:,}  ·  {bits(reg.item(i).sell_price * q)}" for i, q in top)
        more = len(everything) - len(top)
        by_tool = await upgrade_needs_by_tool(self.user)
        reserved = {i: min(q, needs[i]) for i, q in everything.items() if i in needs}
        warn = ""
        if reserved:
            parts = [f"{reg.item(i).name}: you have {everything[i]:,}, an upgrade or craft needs {needs[i]:,}" + (f" ({', '.join(dict.fromkeys(by_tool[i][1]))})" if i in by_tool else "")
                     for i in reserved]
            warn = "\n-# 🔨 Upgrade and crafting materials in this pile (any tool you own, either road at a fork, and the Workbench):\n-# " + "\n-# ".join(parts)
        keeping = self.user.settings.keep_upgrade_materials
        if keeping or not reserved:  # (with nothing to hold back there is only one way to sell)
            first = button("Sell everything" if not reserved else f"Sell, keep upgrade materials ({bits(keep_worth)})", emoji="💰", style=discord.ButtonStyle.danger,
                           disabled=bool(reserved) and not kept, on_click=self._sell(keeping))
            second = button(f"Sell everything ({bits(worth)})", emoji="⚠️", on_click=self._sell(False)) if reserved else None
        else:
            first = button(f"Sell everything ({bits(worth)})", emoji="💰", style=discord.ButtonStyle.danger, on_click=self._sell(False))
            second = button(f"Sell, keep upgrade materials ({bits(keep_worth)})", emoji="🔨", disabled=not kept, on_click=self._sell(True))
        body = [*self.note_block(),
                text(f"### {emojis.skill(self.skill, '💰')} Sell everything from {self.skill.title()}?\n{lines}" + (f"\n-# …and {more} more kinds" if more > 0 else "")
                     + f"\n**{sum(everything.values()):,}** items for **{bits(worth)}** bits{warn}"),
                row(*[b for b in (first, second) if b], button("Cancel", on_click=self._cancel))]
        return Page("Sell all", body, accent=0xD4A017)

    def _sell(self, keep_for_upgrades: bool):
        async def go(interaction: discord.Interaction) -> None:
            keep = await upgrade_needs(self.user) if keep_for_upgrades else None
            earned, sold = await shop.sell_all_for_skill(self.user, self.skill, keep=keep)
            self.result = Result("Sold!", [f"💰 You sold **{sum(sold.values()):,}** items for **{bits(earned)}** bits." if sold else "Nothing was left to sell."]
                                 + (["🔨 Your upgrade materials were kept."] if keep_for_upgrades and sold else []),
                                 emoji="💰", accent=0xD4A017, back=self._cancel, back_label="Back")
            await self.refresh(interaction)

        return go

    async def _cancel(self, interaction: discord.Interaction) -> None:
        await self.nav.back(interaction)
