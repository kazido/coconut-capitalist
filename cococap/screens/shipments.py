import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import shipments
from cococap.ui import Page, Result, Screen
from cococap.ui.components import bar, bits, button, row, select, sep, text


class ShipmentsScreen(Screen):
    """Fill crates with materials from the skills and ship them for xp and bits; and a weekly one the whole server fills together."""

    id = "shipments"
    label = "Shipments"
    emoji = emojis.Lazy("ui_crate", "📦")
    description = "Fill crates with materials from your skills and ship them for xp and bits"
    links = ()

    def __init__(self, nav):
        super().__init__(nav)
        self.page = ""  # which shipment is showing (its id, like "mining:basic", or "community")

    async def build(self) -> Page:
        reg = get_registry()
        community_on = reg.shipments.community.enabled
        if community_on and (paid := await shipments.claim_community(self.user)):
            self.result = Result("The community shipment is out!", [f"{emojis.icon('crate', '📦')} **+{bits(p.bits)}** bits  ·  **+{p.xp:,}** {p.skill} xp for your part" for p in paid],
                                 emoji=emojis.icon('crate', '📦'), accent=0xB8860B, back_label="Continue")
        owned = await self.user.items()
        body = [*self.note_block()]
        crates = await shipments.mine(self.user, reg)
        locked = await shipments.locked(self.user, reg)
        if not crates and not community_on:
            first = min(shipments.unlock_level(t, reg) for _, t in shipments.slot_ids(reg))
            body.append(text(f"### {emojis.icon('crate', '📦')} Shipments\nEach skill unlocks its first shipment at level **{first}**. Keep gathering!"))
            return Page("Shipments", body, accent=0xB8860B)
        view = await shipments.community_now(self.user) if community_on else None
        names = {c.id: (self._name(c), emojis.skill(c.theme, emojis.icon('crate', '📦'))) for c in crates}
        ids = [c.id for c in crates] + (["community"] if community_on else [])
        if self.page not in ids:
            self.page = ids[0]
        options = [discord.SelectOption(label=names[c.id][0], value=c.id, emoji=names[c.id][1], default=c.id == self.page, description="Ready to ship" if c.done() else None) for c in crates]
        if community_on:
            options.append(discord.SelectOption(label="Community shipment", value="community", emoji=emojis.icon('world', '🌍'), default=self.page == "community", description="Full" if view.done else None))
        body.append(row(select("Pick a shipment...", options, self._pick)))
        if self.page != "community":
            ship = next(c for c in crates if c.id == self.page)
            reward_bits, reward_xp = shipments.reward(ship, reg)
            xp_text = ", ".join(f"{emojis.skill(s)} {x:,}" for s, x in sorted(reward_xp.items(), key=lambda kv: -kv[1]) if x)
            lines = []
            for item_id, need in ship.need.items():
                have = ship.have.get(item_id, 0)
                item = reg.item(item_id)
                lines.append(f"{emojis.icon('check', '✅') if have >= need else emojis.icon('pip', '▫️')} {item.display}  **{have:,}/{need:,}**" + (f"  ·  you have {owned.get(item_id, 0):,}" if have < need and owned.get(item_id, 0) else ""))
            name, emoji = names[ship.id]
            body.append(text(f"### {emoji} {name}\n" + "\n".join(lines) + f"\n-# Ships for **{emojis.bits(reward_bits)}** and {xp_text} xp"))
            usable = any(owned.get(i, 0) and ship.have.get(i, 0) < q for i, q in ship.need.items())
            body.append(row(button("Fill", emoji=emojis.icon('box', '📥'), style=discord.ButtonStyle.primary, disabled=ship.done() or not usable, on_click=self._fill(ship.id)),
                            button("Ship", emoji=emojis.icon('send', '🚚'), style=discord.ButtonStyle.success, disabled=not ship.done(), on_click=self._ship(ship.id))))
        else:
            c = reg.shipments.community
            lines = []
            for item_id, need in view.need.items():
                have = min(view.have.get(item_id, 0), need)
                lines.append(f"{emojis.icon('check', '✅') if have >= need else emojis.icon('pip', '▫️')} {reg.item(item_id).display}  **{have:,}/{need:,}**")
            body.append(text(f"### {emojis.icon('world', '🌍')} Community shipment\n{bar(view.fraction, 12, 'progress')}  **{view.fraction:.0%}**" + (f" {emojis.icon('check', '✅')} full!" if view.done else f"  ·  new one <t:{int(view.closes_at)}:R>")
                             + "\n" + "\n".join(lines)
                             + f"\n-# Sized for **{view.players}** active player(s): **{emojis.bits(view.value)}**' worth in all. You have given **{emojis.bits(view.yours)}**' worth. Finishing pays everyone who gave at least {c.min_share:.0%} {c.bits_factor:.1f}x what they gave, and {c.xp:,} xp."))
            body.append(row(button("Give what it needs", emoji=emojis.icon('gift', '🎁'), style=discord.ButtonStyle.primary, disabled=view.done, on_click=self._donate)))
        if locked:
            soonest = sorted(locked, key=lambda e: e[2])[:3]
            body.append(text("-# Locked: " + ", ".join(f"{s.title()} {t} (level {n})" for s, t, n in soonest) + (" …" if len(locked) > 3 else "")))
        return Page("Shipments", body, accent=0xB8860B)

    @staticmethod
    def _name(ship: shipments.Shipment) -> str:
        return f"{ship.theme.title()} shipment" + (" (hard)" if ship.tier != "basic" else "")

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.page = values[0]
        await self.refresh(interaction)

    def _fill(self, slot_id: str):
        async def go(interaction: discord.Interaction) -> None:
            try:
                moved = await shipments.fill(self.user, slot_id)
            except shipments.ShipmentError as error:
                return await self.refresh(interaction, str(error))
            reg = get_registry()
            await self.refresh(interaction, f"{emojis.icon('box', '📥')} Added " + ", ".join(f"{q:,} {reg.item(i).name}" for i, q in moved.items()) + ".")

        return go

    def _ship(self, slot_id: str):
        async def go(interaction: discord.Interaction) -> None:
            try:
                sent = await shipments.ship(self.user, slot_id)
            except shipments.ShipmentError as error:
                return await self.refresh(interaction, str(error))
            xp = ", ".join(f"{emojis.skill(s)} {x:,} {s} xp" for s, x in sent.xp.items() if x)
            self.result = Result("Shipped!", [f"{emojis.icon('box', '🚚')} **+{bits(sent.bits)}** bits  ·  {xp}", "A new crate is waiting in its place."], emoji=emojis.icon('crate', '📦'), accent=0xB8860B)
            await self.refresh(interaction)

        return go

    async def _donate(self, interaction: discord.Interaction) -> None:
        try:
            gave = await shipments.donate(self.user)
        except shipments.ShipmentError as error:
            return await self.refresh(interaction, str(error))
        reg = get_registry()
        await self.refresh(interaction, f"{emojis.icon('gift', '🎁')} You gave " + ", ".join(f"{q:,} {reg.item(i).name}" for i, q in gave.items()) + ".")
