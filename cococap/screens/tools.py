from datetime import timezone

import discord

from cococap import emojis
from cococap.constants import STARTER_TOOLS
from cococap.registry import get_registry
from cococap.services.equipment import TOOL_FOR_SKILL, effective_stats
from cococap.services import shop, smithing
from cococap.services.inventory import instance_label
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, select, sep, text
from cococap.screens.accessories import AccessoriesPane
from cococap.screens.enchant import EnchantPane
from cococap.screens.smithing import PartsPane, SmithingPane
from cococap.ui.tabs import TabsScreen

# what a tool's extra stats say in words: stat -> (label, how to show the amount)
STAT_WORDS = {
    "danger_reduction": ("less creaking", "pct"), "ore_yield": ("more ore", "pct"), "bite_speed": ("faster bites", "pct"),
    "rare_luck": ("better odds of rare fish", "pct"), "treasure_luck": ("better treasure odds", "pct"), "slips": ("extra forgiven arrow(s)", "int"),
    "boss_luck": ("more bosses", "pct"), "braces": ("extra brace(s)", "int"),
}


def describe_stats(stats: dict[str, float]) -> str:
    """"+4% more ore, 2% more creaking" for a tool's extra stats (a negative one reads as the opposite)."""
    opposite = {"less creaking": "more creaking", "more ore": "less ore", "faster bites": "slower bites"}
    parts = []
    for stat, amount in stats.items():
        label, how = STAT_WORDS.get(stat, (stat.replace("_", " "), "pct"))
        if amount < 0:
            label, amount = opposite.get(label, f"less {label}"), -amount
        parts.append(f"+{amount:.0%} {label}" if how == "pct" else f"+{amount:g} {label}")
    return ", ".join(parts)

def tool_emoji(inst, item) -> str:
    """A smithed tool shows the one generic pixel emoji of its kind (tool_<kind>); older tools keep their own."""
    fallback = item.emoji or emojis.icon("craft", "🔨")
    return emojis.get(f"tool_{item.tool.kind}", fallback) if inst.parts else fallback


KIND_LABEL = {"pickaxe": "Mining", "axe": "Foraging", "sword": "Combat", "rod": "Fishing", "can": "Farming"}


class ToolsPane(Screen):
    """Your tool for each skill, as a compact list. Enchant, Smithing and Parts are the other tabs."""

    label = "Tools"
    emoji = emojis.Lazy("ui_anvil", "🧰")
    viewing: int | None = None  # instance id of the tool whose detail page is open

    async def _equipped_ids(self) -> set[int]:
        ids = set()
        for skill in TOOL_FOR_SKILL:
            equipped = (await self.user.skill(skill)).equipped_instance_id
            if equipped is not None:
                ids.add(equipped)
        return ids

    async def build(self) -> Page:
        reg = get_registry()
        instances = [i for i in await self.user.instances() if reg.item(i.template_id).tool]
        equipped = await self._equipped_ids()
        viewed = next((i for i in instances if i.id == self.viewing), None)
        if viewed is not None:
            return self._detail(viewed, viewed.id in equipped)
        self.viewing = None
        body = [*self.note_block()]
        shown = []
        if not instances:
            body.append(text("You have no tools yet. Claim your free starter tools below."))
        # one compact line per skill: the equipped tool (you hold one tool per skill, so there is nothing to pick between)
        lines = []
        for kind in KIND_LABEL:
            mine = [i for i in instances if reg.item(i.template_id).tool.kind == kind]
            if not mine:
                continue
            inst = next((i for i in mine if i.id in equipped), mine[0])
            shown.append(inst)
            item = reg.item(inst.template_id)
            tool = item.tool
            extra = [describe_stats(tool.stats)] if tool.stats else []
            if inst.parts:  # smithed: quality grade and the traits picked from its parts
                extra += ([inst.quality] if inst.quality else []) + [reg.smithing.trait(p["trait"]).name for p in inst.parts.values() if p.get("trait")]
            lines.append(f"{tool_emoji(inst, item)} **{instance_label(inst)}**  ·  {KIND_LABEL[kind]}  ·  power **{effective_stats(inst, reg).power}**"
                         + "".join(f"  ·  {e}" for e in extra) + (f"  ·  {emojis.icon('sparkle', '✨')} {tool.ability_name}" if tool.ability_name else ""))
        if lines:
            body.append(text("\n".join(lines)))
            options = [discord.SelectOption(label=f"{instance_label(i)} · {KIND_LABEL[reg.item(i.template_id).tool.kind]}"[:100], value=str(i.id))
                       for i in shown]
            body.append(row(select("See a tool's details...", options, self._view)))
        if await self._unclaimed():
            body += [sep(), row(button("Claim free starter tools", emoji=emojis.icon("gift", "🎁"), style=discord.ButtonStyle.success, on_click=self._claim))]
        body += [sep(), row(button("Inventory", emoji=emojis.icon("bag", "🎒"), on_click=self._inventory))]
        return Page("Tools", body, accent=0xB8860B)

    def _detail(self, inst, equipped: bool) -> Page:
        """Everything about one tool: the big picture (a smithed tool is drawn from its three parts' tiers), its numbers,
        when and by whom it was smithed, and each part with its tier/rarity and the trait picked from it."""
        reg = get_registry()
        item = reg.item(inst.template_id)
        tool = item.tool
        body = [*self.note_block()]  # the big Pillow picture (art_runtime) comes in the cosmetics step
        head = [f"{tool_emoji(inst, item)} **{instance_label(inst)}**" + ("  ·  equipped" if equipped else ""),
                f"{KIND_LABEL.get(tool.kind, tool.kind.title())}  ·  power **{effective_stats(inst, reg).power}**"
                + (f"  ·  {inst.quality}" if inst.quality else "")]
        date = f"<t:{int(inst.created_at.replace(tzinfo=timezone.utc).timestamp())}:D>" if inst.created_at else None
        if inst.smith_id is not None:
            head.append(f"Smithed {date or 'on an unknown date'} by <@{inst.smith_id}>")
        elif date:
            head.append(f"Made by the game · {date}")
        body.append(text("\n".join(head)))
        if inst.parts:
            lines = ["**Parts**"]
            for slot in smithing.PART_TYPES:
                part = inst.parts.get(slot, {})
                trait = part.get("trait")
                lines.append(f"· {smithing.part_label(slot, int(part.get('tier', 1)))}  ·  "
                             + (f"**{reg.smithing.trait(trait).name}**" if trait else "no trait"))
            body.append(text("\n".join(lines)))
        extra = []
        if tool.stats:
            extra.append(describe_stats(tool.stats))
        if tool.ability_name:
            extra.append(f"{emojis.icon('sparkle', '✨')} {tool.ability_name}")
        if inst.enchants:
            extra.append("Enchants: " + ", ".join(reg.enchant(e).name + (f" {lvl}" if lvl > 1 else "") for e, lvl in inst.enchants.items()))
        if extra:
            body.append(text("\n".join(extra)))
        body += [sep(), row(button("Back to tools", emoji=emojis.icon("back", "↩️"), on_click=self._back))]
        return Page("Tools", body, accent=0xB8860B)

    async def _view(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.viewing = int(values[0])
        await self.refresh(interaction)

    async def _back(self, interaction: discord.Interaction) -> None:
        self.viewing = None
        await self.refresh(interaction)

    async def _unclaimed(self) -> bool:
        reg = get_registry()
        have = {t.tool.kind for i in await self.user.instances() if (t := reg.find_item(i.template_id)) and t.tool}
        for item_id in STARTER_TOOLS:
            if reg.item(item_id).tool.kind not in have and not await self.user.get_stat(f"starter_claimed_{item_id}"):
                return True
        return False

    async def _claim(self, interaction: discord.Interaction) -> None:
        got = await shop.claim_starter_tools(self.user)
        names = ", ".join(get_registry().item(i).name for i in got)
        await self.refresh(interaction, f"{emojis.icon('gift', '🎁')} You got: {names}." if got else "You have no starter tools to claim.")

    async def _inventory(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "inventory")


class ToolsScreen(TabsScreen):
    """The Tools page: your tools (the list), then Enchant, Smithing and Parts as tabs."""

    id = "tools"
    label = "Tools"
    emoji = emojis.Lazy("ui_anvil", "🧰")
    description = "Your tools: smith, enchant and salvage them"
    links = ("inventory",)
    panes = {"tools": ToolsPane, "enchant": EnchantPane, "smithing": SmithingPane, "parts": PartsPane, "accessories": AccessoriesPane}
