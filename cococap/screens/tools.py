from datetime import timezone

import discord

from cococap import emojis
from cococap.constants import STARTER_TOOLS
from cococap.errors import GameRuleError
from cococap.registry import get_registry
from cococap.registry.models import ACCESSORY_SKILLS
from cococap.services.equipment import TOOL_FOR_SKILL, effective_stats, skill_for_tool
from cococap.services import accessories, shop, smithing
from cococap.services.inventory import instance_label
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, select, sep, text
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


KIND_LABEL = {"pickaxe": "Mining", "axe": "Foraging", "sword": "Combat", "bow": "Combat", "staff": "Combat", "shield": "Combat", "rod": "Fishing", "can": "Farming"}


def _describe(inst, rules) -> str:
    """"Work Gloves (Vein Sense) · ore yield +0.02": the name, its traits and its stat bonuses."""
    template = rules.template(inst.template_id)
    traits = ", ".join(rules.trait(t).name for t in inst.traits)
    stats = ", ".join(f"{stat.replace('_', ' ')} +{amount:g}" for stat, amount in accessories.stats_of(inst).items())
    return f"**{template.name}**" + (f" ({traits})" if traits else "") + (f" · {stats}" if stats else "")


class ToolsPane(Screen):
    """Your tool for each skill, as a compact list. Enchant, Smithing and Parts are the other tabs."""

    label = "Tools"
    emoji = emojis.Lazy("ui_anvil", "🧰")
    viewing: int | None = None  # instance id of the tool whose detail page is open
    picked: int | None = None  # the accessory chosen in the detail page's dropdown

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
            return await self._detail(viewed, viewed.id in equipped)
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

    async def _detail(self, inst, equipped: bool) -> Page:
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
                lines.append(f"· {smithing.part_label(slot, int(part.get('tier', 1)), smithing.is_restricted(part))}  ·  "
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
        skill = skill_for_tool(tool.kind)
        if inst.enchants and await smithing.smithing_level(self.user) >= reg.smithing.removal.enchant_unlock_level:
            body.append(row(select("Remove an enchant (returns its scroll)...", [
                discord.SelectOption(label=reg.enchant(e).name[:100], value=e) for e in inst.enchants], self._remove_enchant)))
        if skill in ACCESSORY_SKILLS:
            body += await self._accessory_section(skill)
        body += [sep(), row(button("Back to tools", emoji=emojis.icon("prev", "⬅️"), on_click=self._back))]
        return Page("Tools", body, accent=0xB8860B)

    async def _accessory_section(self, skill: str) -> list:
        """The skill's two accessory slots, a dropdown of the ones you own (worn ones marked) and one Equip/Unequip toggle."""
        reg = get_registry()
        rules = reg.accessories
        worn = await accessories.equipped(self.user, skill, reg)
        worn_ids = {i.id for i in worn if i is not None}
        slots = [f"Slot {n}: " + (_describe(inst, rules) if inst is not None else "empty") for n, inst in enumerate(worn, 1)]
        body = [sep(), text("\n".join(["**Accessories**", *slots]))]
        template_ids = {t.id for t in rules.templates if t.skill == skill}
        owned = [i for i in await self.user.instances() if i.template_id in template_ids]
        if not owned:
            return body + [text(f"-# No {skill} accessories. Buy a basic one in the Shop or wait for a drop.")]
        if self.picked not in {i.id for i in owned}:
            self.picked = None
        body.append(row(select("Pick an accessory...", [
            discord.SelectOption(label=(rules.template(i.template_id).name + (" (worn)" if i.id in worn_ids else ""))[:100],
                                 value=str(i.id), default=i.id == self.picked) for i in owned], self._pick_spare)))
        wearing = self.picked in worn_ids
        full = None not in worn
        body.append(row(button("Unequip" if wearing else "Equip",
                               style=discord.ButtonStyle.secondary if wearing else discord.ButtonStyle.primary,
                               on_click=self._toggle, disabled=self.picked is None or (full and not wearing))))
        if full and self.picked is not None and not wearing:
            body.append(text("-# Both slots are full. Unequip one first."))
        return body

    async def _remove_enchant(self, interaction: discord.Interaction, values: list[str]) -> None:
        try:
            await smithing.remove_enchant(self.user, self.viewing, values[0])
        except GameRuleError as err:
            return await self.refresh(interaction, str(err))
        await self.refresh(interaction, f"Removed **{get_registry().enchant(values[0]).name}**. Its scroll is back in your inventory.")

    async def _pick_spare(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.picked = int(values[0])
        await self.refresh(interaction)

    async def _toggle(self, interaction: discord.Interaction) -> None:
        reg = get_registry()
        inst = next((i for i in await self.user.instances() if i.id == self.viewing), None)
        skill = skill_for_tool(reg.item(inst.template_id).tool.kind) if inst else None
        if self.picked is None or skill is None:
            return await self.refresh(interaction, "Pick an accessory first.")
        worn_ids = [i.id if i is not None else None for i in await accessories.equipped(self.user, skill, reg)]
        if self.picked in worn_ids:
            await accessories.unequip(self.user, skill, worn_ids.index(self.picked))
            return await self.refresh(interaction, "Took it off.")
        if None not in worn_ids:
            return await self.refresh(interaction, "Both slots are full. Unequip one first.")
        instance = await accessories.equip(self.user, skill, self.picked, worn_ids.index(None))
        await self.refresh(interaction, f"Wearing **{reg.accessories.template(instance.template_id).name}**.")

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
    panes = {"tools": ToolsPane, "enchant": EnchantPane, "smithing": SmithingPane, "parts": PartsPane}
