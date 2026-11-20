import re

import discord

from cococap import emojis
from cococap.constants import Rarities
from cococap.registry import get_registry
from cococap.services import smithing
from cococap.services.inventory import inventory_entries
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, section_art, select, sep, text
from utils.items.items import item_attributes

PER_PAGE = 12


_LEAD = re.compile(r"^(<a?:\w+:\d+>|[^\w\s<*#]+)\s*")  # a line's leading emoji (custom or unicode)


class InventoryScreen(Screen):
    id = "inventory"
    label = "Inventory"
    emoji = emojis.Lazy("ui_bag", "🎒")
    description = "Your items"
    links = ("tools", "shop", "trade", "craft")

    def __init__(self, nav):
        super().__init__(nav)
        self.page = 0
        self.picking = False  # the Inspect dropdown is showing
        self.inspecting: str | None = None  # "item:<id>" or "part:<instance id>" while its detail page is open

    async def build(self) -> Page:
        # Stacked items, then smithing parts (unique, so listed one per line). Tools live on the Tools page.
        items = await self.user.items()
        entries = inventory_entries(items, await self.user.instances())
        if self.inspecting:
            if detail := await self._detail(self.inspecting, items):
                return Page("Inventory", [*self.note_block(), *detail, row(button("Back", on_click=self._back))], accent=0x99B0A2)
            self.inspecting = None  # it is gone (sold, smithed away): fall back to the list
        lines = [line for _, line in entries]
        body = [*self.note_block()]
        pages = max(1, -(-len(lines) // PER_PAGE))
        self.page = min(self.page, pages - 1)
        shown = "\n".join(lines[self.page * PER_PAGE : (self.page + 1) * PER_PAGE])
        body.append(text(shown if lines else "You don't have any items yet. Get to it!"))
        if pages > 1:
            body.append(
                row(
                    button(emoji=emojis.icon("prev", "◀️"), on_click=self._turn(-1), disabled=self.page == 0),
                    button(f"{self.page + 1}/{pages}", disabled=True),
                    button(emoji=emojis.icon("next", "▶️"), on_click=self._turn(1), disabled=self.page >= pages - 1),
                )
            )
        if self.picking:
            on_page = entries[self.page * PER_PAGE : (self.page + 1) * PER_PAGE]
            # Custom emoji do not render in select text: the line's leading emoji goes in the option's emoji slot instead.
            options = []
            for key, line in on_page:
                lead = _LEAD.match(line)
                options.append(discord.SelectOption(
                    label=(re.sub(r"<a?:\w+:\d+>\s*", "", line[lead.end():] if lead else line).strip(" ·") or key)[:100],
                    value=key, emoji=lead.group(0).strip() if lead else None))
            body.append(row(select("Pick an item to inspect...", options, self._pick)))
        body += [sep(), row(button("Inspect", emoji=emojis.icon("search", "🔍"), style=discord.ButtonStyle.success, disabled=not lines, on_click=self._inspect),
                            button("Tools", emoji=emojis.icon("anvil", "🧰"), on_click=self._tools),
                            button("Trade", emoji=emojis.icon("trade", "🤝"), on_click=self._trade),
                            button("Workbench", emoji=emojis.icon("craft", "🛠️"), on_click=self._craft))]
        return Page("Inventory", body, accent=0x99B0A2)

    def _turn(self, step: int):
        async def turn(interaction: discord.Interaction) -> None:
            self.page += step
            await self.refresh(interaction)

        return turn

    async def _inspect(self, interaction: discord.Interaction) -> None:
        self.picking = not self.picking
        await self.refresh(interaction)

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.inspecting = values[0]
        await self.refresh(interaction)

    async def _back(self, interaction: discord.Interaction) -> None:
        self.inspecting = None
        await self.refresh(interaction)

    async def _detail(self, key: str, items: dict[str, int]) -> list | None:
        """The detail page for one inventory entry: big picture, details and (for a part) its traits. None if it is gone."""
        reg = get_registry()
        kind, _, ident = key.partition(":")
        if kind == "item":
            item = reg.find_item(ident)
            qty = items.get(ident, 0)
            if item is None or qty <= 0:
                return None
            head = f"### {item.display}\n×{qty:,}  ·  {emojis.bits(item.sell_price)} each\n"
            return [section_art(head + item_attributes(item), emojis.image_url("item", item.id))]
        inst = await self.user.instance(int(ident))
        if inst is None or not inst.template_id.startswith("part_"):
            return None
        rules = reg.smithing
        slot, tier = inst.template_id.removeprefix("part_"), int(inst.rolled.get("tier", 1))
        lines = [f"### {smithing.part_label(slot, tier, smithing.is_restricted(inst))}",
                 f"**Rarity**: *{Rarities.from_value(rules.part_rarity(tier)).rarity_name}*  ·  **Type**: *Tool {slot.title()}*"]
        if smithing.is_restricted(inst):
            lines.append("**Restricted**: a tool may hold only one restricted part; it adds a second enchant slot.")
        if inst.traits:
            lines.append("**Traits** (the amount depends on the tool's quality):")
            for t in inst.traits:
                trait = rules.trait(t)
                lines.append(f"· {smithing.trait_icons([t], rules)} **{trait.name}**: {trait.stat.replace('_', ' ')} "
                             f"+{min(trait.amounts):g} to +{max(trait.amounts):g}")
        else:
            lines.append("**Traits**: none")
        if template := reg.find_item(inst.template_id):
            lines.append(f"-# {template.wiki}")
        return [section_art("\n".join(lines), emojis.image_url("item", f"part_{slot}_t{tier}"))]

    async def _tools(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "tools")

    async def _trade(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "trade")

    async def _craft(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "craft")
