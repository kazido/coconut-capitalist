import discord

from cococap.registry import get_registry
from cococap.services import shipments
from cococap.ui import Page, Result, Screen
from cococap.ui.components import bar, bits, button, row, select, sep, text

EMOJI = {"mining": "⛏️", "farming": "🌽", "foraging": "🌳", "fishing": "🐟", "mixed": "📦"}


class ShipmentsScreen(Screen):
    """Fill crates with materials from the skills and ship them for xp and bits; and a weekly one the whole server fills together."""

    id = "shipments"
    label = "Shipments"
    emoji = "📦"
    description = "Fill crates with materials from your skills and ship them for xp and bits"
    links = ()

    def __init__(self, nav):
        super().__init__(nav)
        self.page = 0  # which shipment is showing: your crates in order, then the community one

    async def build(self) -> Page:
        reg = get_registry()
        if paid := await shipments.claim_community(self.user):
            self.result = Result("The community shipment is out!", [f"📦 **+{bits(p.bits)}** bits  ·  **+{p.xp:,}** {p.skill} xp for your part" for p in paid],
                                 emoji="📦", accent=0xB8860B, back_label="Continue")
        owned = await self.user.items()
        body = [*self.note_block()]
        crates = await shipments.mine(self.user, reg)
        view = await shipments.community_now(self.user)
        names = [("Mixed shipment" if c.theme == "mixed" else f"{c.theme.title()} shipment", EMOJI.get(c.theme, "📦")) for c in crates] + [("Community shipment", "🌍")]
        self.page = max(0, min(self.page, len(names) - 1))
        body.append(row(select("Pick a shipment...", [
            discord.SelectOption(label=name, value=str(i), emoji=emoji, default=i == self.page,
                                 description=("Ready to ship" if i < len(crates) and crates[i].done() else "Full" if i >= len(crates) and view.done else None))
            for i, (name, emoji) in enumerate(names)], self._pick)))
        if self.page < len(crates):
            index, ship = self.page, crates[self.page]
            reward_bits, reward_xp = shipments.reward(ship, reg)
            xp_text = ", ".join(f"{EMOJI.get(s, '')} {x:,}" for s, x in sorted(reward_xp.items(), key=lambda kv: -kv[1]) if x)
            lines = []
            for item_id, need in ship.need.items():
                have = ship.have.get(item_id, 0)
                item = reg.item(item_id)
                lines.append(f"{'✅' if have >= need else '▫️'} {item.display}  **{have:,}/{need:,}**" + (f"  ·  you have {owned.get(item_id, 0):,}" if have < need and owned.get(item_id, 0) else ""))
            name, emoji = names[index]
            body.append(text(f"### {emoji} {name}\n" + "\n".join(lines) + f"\n-# Ships for **{bits(reward_bits)}** bits and {xp_text} xp"))
            usable = any(owned.get(i, 0) and ship.have.get(i, 0) < q for i, q in ship.need.items())
            body.append(row(button("Fill", emoji="📥", style=discord.ButtonStyle.primary, disabled=ship.done() or not usable, on_click=self._fill(index)),
                            button("Ship", emoji="🚚", style=discord.ButtonStyle.success, disabled=not ship.done(), on_click=self._ship(index))))
        else:
            c = reg.shipments.community
            lines = []
            for item_id, need in view.need.items():
                have = min(view.have.get(item_id, 0), need)
                lines.append(f"{'✅' if have >= need else '▫️'} {reg.item(item_id).display}  **{have:,}/{need:,}**")
            body.append(text(f"### 🌍 Community shipment\n{bar(view.fraction, 12)}  **{view.fraction:.0%}**" + (" ✅ full!" if view.done else f"  ·  new one <t:{int(view.closes_at)}:R>")
                             + "\n" + "\n".join(lines)
                             + f"\n-# You have given **{bits(view.yours)}** bits' worth. Finishing pays everyone who gave at least {c.min_share:.0%} {c.bits_factor:.1f}x what they gave, and {c.xp:,} xp."))
            body.append(row(button("Give what it needs", emoji="🎁", style=discord.ButtonStyle.primary, disabled=view.done, on_click=self._donate)))
        return Page("Shipments", body, accent=0xB8860B)

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.page = int(values[0])
        await self.refresh(interaction)

    def _fill(self, index: int):
        async def go(interaction: discord.Interaction) -> None:
            try:
                moved = await shipments.fill(self.user, index)
            except shipments.ShipmentError as error:
                return await self.refresh(interaction, str(error))
            reg = get_registry()
            await self.refresh(interaction, "📥 Added " + ", ".join(f"{q:,} {reg.item(i).name}" for i, q in moved.items()) + ".")

        return go

    def _ship(self, index: int):
        async def go(interaction: discord.Interaction) -> None:
            try:
                sent = await shipments.ship(self.user, index)
            except shipments.ShipmentError as error:
                return await self.refresh(interaction, str(error))
            xp = ", ".join(f"{EMOJI.get(s, '')} {x:,} {s} xp" for s, x in sent.xp.items() if x)
            self.result = Result("Shipped!", [f"🚚 **+{bits(sent.bits)}** bits  ·  {xp}", "A new crate is waiting in its place."], emoji="📦", accent=0xB8860B)
            await self.refresh(interaction)

        return go

    async def _donate(self, interaction: discord.Interaction) -> None:
        try:
            gave = await shipments.donate(self.user)
        except shipments.ShipmentError as error:
            return await self.refresh(interaction, str(error))
        reg = get_registry()
        await self.refresh(interaction, "🎁 You gave " + ", ".join(f"{q:,} {reg.item(i).name}" for i, q in gave.items()) + ".")
