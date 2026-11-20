from datetime import timezone

import discord

from cococap import emojis
from cococap.constants import STARTER_TOOLS
from cococap.errors import GameRuleError
from cococap.registry import get_registry
from cococap.registry.models import ACCESSORY_SKILLS
from cococap.services.equipment import TOOL_FOR_SKILL, effective_stats, skill_for_tool
from cococap.services import accessories, equipment, shop, smithing, tool_effects
from cococap.services.inventory import instance_label
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, select, sep, text
from cococap.screens.enchant import EnchantPane
from cococap.ui.tabs import TabsScreen

# what a tool's extra stats say in words: stat -> (label, how to show the amount)
STAT_WORDS = {
    "danger_reduction": ("less creaking", "pct"), "ore_yield": ("more ore", "pct"), "bite_speed": ("faster bites", "pct"),
    "rare_luck": ("rare drop luck", "pct"), "treasure_luck": ("better treasure odds", "pct"), "slips": ("extra forgiven arrow(s)", "int"),
    "boss_luck": ("more bosses", "pct"), "braces": ("extra brace(s)", "int"),
    "power": ("tool power", "int"), "scholar": ("skill xp", "pct"), "appraise": ("sell price", "pct"), "drop_amount": ("bigger drops", "pct"),
    "rich_chance": ("richer lodes", "pct"),
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
    """One tool at a time: a dropdown switches skill, the arrows flip between your tools for it, and Equip makes one the tool you use.
    Enchant and Parts are buttons at the bottom (smithing itself lives on the Smithing skill page)."""

    label = "Tools"
    emoji = emojis.Lazy("ui_anvil", "🧰")
    skill: str | None = None  # the skill whose tools are showing
    idx: int = 0  # which of that skill's tools (the arrows move this)
    viewing: int | None = None  # instance id of the tool on screen (the handlers below act on it)
    picked: int | None = None  # the accessory chosen in the detail page's dropdown

    async def _equipped_ids(self) -> set[int]:
        ids = set()
        for skill in TOOL_FOR_SKILL:
            equipped = (await self.user.skill(skill)).equipped_instance_id
            if equipped is not None:
                ids.add(equipped)
        return ids

    async def _mine(self, skill: str) -> list:
        reg = get_registry()
        # skill_for_tool, not one kind per skill: bows, staffs and shields share the combat slot with swords
        return [i for i in await self.user.instances()
                if reg.item(i.template_id).tool and skill_for_tool(reg.item(i.template_id).tool.kind) == skill]

    async def _home(self, skill: str) -> int:
        """Index of the tool you use for `skill` (the one to show first)."""
        mine = await self._mine(skill)
        worn = (await self.user.skill(skill)).equipped_instance_id
        return next((n for n, i in enumerate(mine) if i.id == worn), 0)

    async def build(self) -> Page:
        equipped = await self._equipped_ids()
        by_skill = {skill: await self._mine(skill) for skill in TOOL_FOR_SKILL}
        have = [skill for skill, tools in by_skill.items() if tools]
        body = [*self.note_block()]
        if not have:
            body.append(text("You have no tools yet. Claim your free starter tools below."))
        else:
            if self.skill not in have:
                self.skill = have[0]
                self.idx = await self._home(self.skill)
            tools = by_skill[self.skill]
            self.idx = min(self.idx, len(tools) - 1)
            inst = tools[self.idx]
            self.viewing = inst.id
            body.append(row(select("Switch skill...", [
                discord.SelectOption(label=skill.title(), value=skill, default=skill == self.skill, emoji=emojis.skill(skill) or None)
                for skill in have], self._pick_skill)))
            body += await self._detail(inst, inst.id in equipped, self.idx + 1, len(tools))
            controls = []
            if len(tools) > 1:
                controls.append(button(emoji=emojis.icon("prev", "◀️"), on_click=self._flip(-1)))
            controls.append(button("Equipped" if inst.id in equipped else "Equip", style=discord.ButtonStyle.primary,
                                   disabled=inst.id in equipped, on_click=self._equip))
            if len(tools) > 1:
                controls.append(button(emoji=emojis.icon("next", "▶️"), on_click=self._flip(1)))
            body.append(row(*controls))
            body += [sep(), row(button("Enchant", emoji=emojis.icon("scroll", "📜"), on_click=self._enchant),
                                button("Parts", emoji=emojis.icon("anvil", "🧩"), on_click=self._parts))]
        if await self._unclaimed():
            body += [sep(), row(button("Claim free starter tools", emoji=emojis.icon("gift", "🎁"), style=discord.ButtonStyle.success, on_click=self._claim))]
        body += [sep(), row(button("Inventory", emoji=emojis.icon("bag", "🎒"), on_click=self._inventory))]
        return Page("Tools", body, accent=0xB8860B)

    async def _detail(self, inst, equipped: bool, n: int, total: int) -> list:
        """Everything about one tool: its numbers, when and by whom it was smithed, each part with its tier and the trait picked from it,
        its enchants and (for skills that have them) accessories. The big Pillow picture comes with the cosmetics step."""
        reg = get_registry()
        item = reg.item(inst.template_id)
        tool = item.tool
        count = f"  ({n}/{total})" if total > 1 else ""
        head = [f"{tool_emoji(inst, item)} **{instance_label(inst)}**" + (f"  {emojis.icon('check', '✅')}" if equipped else "") + count,
                f"{KIND_LABEL.get(tool.kind, tool.kind.title())}  ·  power **{effective_stats(inst, reg).power}**"
                + (f"  ·  {inst.quality}" if inst.quality else "")]
        date = f"<t:{int(inst.created_at.replace(tzinfo=timezone.utc).timestamp())}:D>" if inst.created_at else None
        if inst.smith_id is not None:
            head.append(f"Smithed {date or 'on an unknown date'} by <@{inst.smith_id}>")
        elif date:
            head.append(f"Made by the game · {date}")
        body = [text("\n".join(head))]
        if inst.parts:
            lines = ["**Parts**"]
            for slot in smithing.PART_TYPES:
                part = inst.parts.get(slot, {})
                trait = part.get("trait")
                lines.append(f"{smithing.part_label(slot, int(part.get('tier', 1)), smithing.is_restricted(part))} "
                             + smithing.trait_names([trait] if trait else [], reg.smithing))
            body.append(text("\n".join(lines)))
        extra = []
        if tool.ability_name:
            extra.append(f"{emojis.icon('sparkle', '✨')} {tool.ability_name}")
        if inst.enchants:
            extra.append("Enchants: " + ", ".join(reg.enchant(e).name + (f" {lvl}" if lvl > 1 else "") for e, lvl in inst.enchants.items()))
        if extra:
            body.append(text("\n".join(extra)))
        body.append(text(self._bonuses(inst, reg)))
        skill = skill_for_tool(tool.kind)
        if inst.enchants and await smithing.smithing_level(self.user) >= reg.smithing.removal.enchant_unlock_level:
            body.append(row(select("Remove an enchant (returns its scroll)...", [
                discord.SelectOption(label=reg.enchant(e).name[:100], value=e, emoji=reg.enchant(e).emoji or None) for e in inst.enchants], self._remove_enchant)))
        if skill in ACCESSORY_SKILLS:
            body += await self._accessory_section(skill)
        return body

    @staticmethod
    def _bonuses(inst, reg) -> str:
        """Where the tool's bonuses come from: its quality, each part's trait, its own power, and the tool's built-in stats."""
        tool = reg.item(inst.template_id).tool
        rules = reg.smithing
        lines = ["**Bonuses**"]
        if inst.parts and inst.quality:
            grade = rules.quality(inst.quality)
            lines.append(f"{inst.quality} quality: x{grade.mult:g} on its power and on every trait's amount")
            idx = [q.name for q in rules.grades].index(inst.quality)
            for slot in smithing.PART_TYPES:
                trait_id = (inst.parts.get(slot) or {}).get("trait")
                if trait_id:
                    trait = rules.trait(trait_id)
                    lines.append(f"{smithing.trait_icons([trait_id], rules)} {trait.name}: "
                                 + describe_stats({trait.stat: trait.amounts[idx] * grade.mult}))
        if tool.stats:
            lines.append("This tool: " + describe_stats(tool.stats))
        from_power = {k: v for k, v in tool_effects.power_stats(tool.kind, effective_stats(inst, reg).power, reg, tool.path).items() if v}
        if from_power:
            lines.append(f"{emojis.icon('power', '💪')} Power {effective_stats(inst, reg).power}: " + describe_stats(from_power))
        if len(lines) == 1:
            lines.append("none yet")
        return "\n".join(lines)

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
                                 value=str(i.id), default=i.id == self.picked,
                                 emoji=emojis.skill(skill) or None) for i in owned], self._pick_spare)))
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

    async def _pick_skill(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.skill = values[0]
        self.idx = await self._home(self.skill)
        self.picked = None
        await self.refresh(interaction)

    def _flip(self, step: int):
        async def flip(interaction: discord.Interaction) -> None:
            total = len(await self._mine(self.skill))
            self.idx = (self.idx + step) % max(total, 1)
            self.picked = None
            await self.refresh(interaction)

        return flip

    async def _equip(self, interaction: discord.Interaction) -> None:
        try:
            inst = await equipment.equip(self.user, self.skill, self.viewing)
        except GameRuleError as err:
            return await self.refresh(interaction, str(err))
        await self.refresh(interaction, f"Now using **{instance_label(inst)}** for {self.skill}.")

    async def _enchant(self, interaction: discord.Interaction) -> None:
        self.nav.screen.tab = "enchant"
        await self.refresh(interaction)

    async def _parts(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "smithing", tab="parts")

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
    """The Tools page: your tools one at a time. Enchant opens in place (Back returns); smithing, parts and the workbench are on the Smithing page."""

    id = "tools"
    label = "Tools"
    emoji = emojis.Lazy("ui_anvil", "🧰")
    description = "Your tools: equip, inspect and enchant them"
    links = ("inventory", "smithing")
    tab_menu = False
    panes = {"tools": ToolsPane, "enchant": EnchantPane}

    async def build(self) -> Page:
        page = await super().build()
        if self.tab != "tools":
            page.body.append(row(button("Back to the tool", emoji=emojis.icon("prev", "⬅️"), on_click=self._to_tool)))
        return page

    async def _to_tool(self, interaction: discord.Interaction) -> None:
        self.tab = "tools"
        await self.nav.refresh(interaction)
