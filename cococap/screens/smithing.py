"""Smithing panes: build a tool from three parts (Smithing tab) and manage your parts and salvage (Parts tab).

Both are tabs of the Tools page (screens/tools.py), not registered screens. Rules live in services/smithing.py.
"""

import random

import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import equipment, smithing
from cococap.services.equipment import TOOL_FOR_SKILL
from cococap.services.inventory import instance_label
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, select, sep, text


def _slot_of(inst) -> str:
    return inst.template_id.removeprefix("part_")


def _tier(inst) -> int:
    return int(inst.rolled.get("tier", 1))


def _part_emoji(slot: str, inst) -> str | None:
    """The part's own emoji (per tier, else the generic part one) for dropdown options."""
    return emojis.for_id("item", f"part_{slot}_t{_tier(inst)}", get_registry().item(inst.template_id).emoji) or None


def _trait_names(inst, rules) -> str:
    """Trait glyphs for select text (custom emoji do not render there); message text uses smithing.trait_icons."""
    return smithing.trait_icons(inst.traits, rules, plain=True)


class SmithingPane(Screen):
    """Pick a tool kind, then a base, trim and accent part (one trait each), then Smith.

    Steps: 0 = kind, 1..3 = base, trim, accent (one part + trait dropdown each), 4 = preview.
    One step at a time keeps at most two dropdowns on the page.
    """

    label = "Smithing"
    emoji = emojis.Lazy("ui_anvil", "🔨")

    def __init__(self, nav):
        super().__init__(nav)
        self.step: int = 0
        self.kind: str | None = None
        self.chosen: dict[str, int | None] = {slot: None for slot in smithing.PART_TYPES}
        self.sub = "browse"  # "browse" parts of the slot, then "trait" to pick one of the picked part's traits
        self.idx: dict[str, int] = {slot: 0 for slot in smithing.PART_TYPES}
        self.picks: dict[int, str | None] = {}  # part id -> trait taken from it (None = no trait)

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.smithing
        level = await smithing.smithing_level(self.user)
        mine = await self.user.instances()
        parts = {slot: [] for slot in smithing.PART_TYPES}
        for inst in mine:
            if _slot_of(inst) in parts:
                parts[_slot_of(inst)].append(inst)

        body = [*self.note_block()]
        body.append(text(f"Smithing level **{level}**"))
        if not any(parts.values()):
            body.append(text("You have no parts yet. Parts drop from skill actions: mining, fishing, foraging and farming."))
            return Page("Smithing", body, accent=0xB8860B)

        # Forget picks whose part was used up.
        for slot in smithing.PART_TYPES:
            if self.chosen[slot] not in {i.id for i in parts[slot]}:
                self.chosen[slot] = None
        self.picks = {pid: self.picks.get(pid) for pid in self.chosen.values() if pid is not None}
        # A preview needs all three parts; fall back to the first missing slot.
        if self.step == 4 and not all(self.chosen.values()):
            self.step = 1 + next(n for n, s in enumerate(smithing.PART_TYPES) if self.chosen[s] is None)

        if self.step == 0:
            body.append(text("**Kind**"))
            body.append(row(select("Pick a tool kind...", [
                discord.SelectOption(label=k.title(), value=k, default=k == self.kind,
                                     emoji=emojis.skill(equipment.skill_for_tool(k) or "", "🔨") or None)
                for k in smithing.KINDS
            ], self._pick_kind)))
            return Page("Smithing", body, accent=0xB8860B)

        if self.step == 4:
            return self._preview(body, parts, rules)

        slot = smithing.PART_TYPES[self.step - 1]
        summary = " · ".join(f"{s.title()}: {self._summary_of(s, parts, rules)}" for s in smithing.PART_TYPES)
        body.append(text(f"-# {summary}"))
        body.append(text(f"**Step {self.step}/3 · {slot.title()}**"))
        mine_slot = parts[slot]
        if not mine_slot:
            body.append(text(f"-# No {slot} parts at your tier."))
            body.append(row(button("Back", on_click=self._back)))
            return Page("Smithing", body, accent=0xB8860B)
        fitting = {t.id for t in rules.traits_for(self.kind)} if self.kind else set()
        idx = self.idx[slot] = min(self.idx[slot], len(mine_slot) - 1)
        part = mine_slot[idx]

        if self.sub == "trait":
            body.append(text(f"{smithing.part_label(slot, _tier(part), smithing.is_restricted(part))}\n"
                             "Choose the trait this part gives the tool:"))
            trait_options = [discord.SelectOption(label="No trait", value="none", emoji=emojis.icon("cross", "🚫"), default=self.picks.get(part.id) is None)]
            for t in part.traits:
                if t in fitting:
                    tr = rules.trait(t)
                    glyph = smithing.TRAIT_GLYPHS.get(tr.stat, "✨")
                    body.append(text(f"· {smithing.trait_icons([t], rules)} **{tr.name}**"))
                    trait_options.append(discord.SelectOption(
                        label=tr.name[:100], value=t, default=self.picks.get(part.id) == t,
                        emoji=emojis.ui(f"trait_{tr.stat}", glyph)))
            body.append(row(select(f"{slot.title()} trait...", trait_options, self._trait_handler(part.id))))
            body.append(row(button("Back", on_click=self._back)))
            return Page("Smithing", body, accent=0xB8860B)

        # Browse: the dropdown and the arrows move through the same list of parts.
        body.append(text(f"{smithing.part_label(slot, _tier(part), smithing.is_restricted(part))} "
                         f"({idx + 1}/{len(mine_slot)})\n{self._trait_lines(part, rules, fitting)}"))
        start = idx // 25 * 25
        body.append(row(select(f"{slot.title()} part...", [
            discord.SelectOption(label=f"{smithing.part_label(slot, _tier(i))} {_trait_names(i, rules)}"[:100],
                                 value=str(n), default=n == idx, emoji=_part_emoji(slot, i))
            for n, i in enumerate(mine_slot) if start <= n < start + 25
        ], self._browse_to)))
        body.append(row(button("◀", on_click=self._step_part(-1)),
                        button("Pick", style=discord.ButtonStyle.primary, on_click=self._pick_part),
                        button("▶", on_click=self._step_part(1)),
                        button("Back", on_click=self._back)))
        return Page("Smithing", body, accent=0xB8860B)

    @staticmethod
    def _trait_lines(part, rules, fitting: set) -> str:
        lines = [f"· {smithing.trait_icons([t], rules)} {rules.trait(t).name}" + ("" if t in fitting else " *(not for this tool)*")
                 for t in part.traits]
        return "\n".join(lines) or "· no traits"

    def _summary_of(self, slot: str, parts: dict, rules) -> str:
        inst = next((i for i in parts[slot] if i.id == self.chosen[slot]), None)
        if inst is None:
            return "-"
        trait = self.picks.get(inst.id)
        return f"T{_tier(inst)}" + (f" {smithing.trait_icons([trait], rules)}" if trait else "")

    def _preview(self, body: list, parts: dict, rules) -> Page:
        picked = {slot: next(i for i in parts[slot] if i.id == self.chosen[slot]) for slot in smithing.PART_TYPES}
        power = smithing.tool_power({s: {"tier": _tier(i)} for s, i in picked.items()}, rules.grades[0].name, rules)
        body.append(text("**Preview**"))
        for slot in smithing.PART_TYPES:
            inst = picked[slot]
            trait = self.picks.get(inst.id)
            icon = smithing.trait_icons([trait] if trait else [], rules)
            body.append(text(f"· {smithing.part_label(slot, _tier(inst), smithing.is_restricted(inst))} · {icon}"))
        kind = self.kind.title() if self.kind else "-"
        body.append(text(f"Kind **{kind}** · power **{power:g}** before quality"))
        body.append(text("-# Quality is rolled on smithing."))
        body.append(row(button("Back", on_click=self._back),
                        button("Smith", emoji=emojis.icon("craft", "🔨"),
                               style=discord.ButtonStyle.success, on_click=self._smith)))
        return Page("Smithing", body, accent=0xB8860B)

    async def _back(self, interaction: discord.Interaction) -> None:
        if self.sub == "trait":
            self.sub = "browse"
        else:
            self.step = max(0, self.step - 1)
        await self.refresh(interaction)

    async def _browse_to(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.idx[smithing.PART_TYPES[self.step - 1]] = int(values[0])
        await self.refresh(interaction)

    def _step_part(self, delta: int):
        async def handler(interaction: discord.Interaction) -> None:
            slot = smithing.PART_TYPES[self.step - 1]
            count = len([i for i in await self.user.instances() if _slot_of(i) == slot])
            self.idx[slot] = (self.idx[slot] + delta) % max(count, 1)
            await self.refresh(interaction)
        return handler

    async def _pick_part(self, interaction: discord.Interaction) -> None:
        slot = smithing.PART_TYPES[self.step - 1]
        part = [i for i in await self.user.instances() if _slot_of(i) == slot][self.idx[slot]]
        old = self.chosen[slot]
        if old is not None and old != part.id:
            self.picks.pop(old, None)  # a new part starts with no trait
        self.chosen[slot] = part.id
        fitting = {t.id for t in get_registry().smithing.traits_for(self.kind)} if self.kind else set()
        if any(t in fitting for t in part.traits):
            self.sub = "trait"
        else:  # nothing to choose: straight to the next step
            self.step += 1
        await self.refresh(interaction)

    def _trait_handler(self, part_id: int):
        async def handler(interaction: discord.Interaction, values: list[str]) -> None:
            self.picks[part_id] = None if values[0] == "none" else values[0]
            self.sub = "browse"
            self.step += 1
            await self.refresh(interaction)
        return handler

    async def _pick_kind(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.kind = values[0]
        self.picks = {}
        self.chosen = {slot: None for slot in smithing.PART_TYPES}
        self.step, self.sub = 1, "browse"
        await self.refresh(interaction)

    async def _smith(self, interaction: discord.Interaction) -> None:
        reg = get_registry()
        if self.kind is None or not all(self.chosen.values()):
            await self.refresh(interaction, "Pick a tool kind and three parts first.")
            return
        base, trim, accent = (self.chosen[s] for s in smithing.PART_TYPES)
        picks = {pid: self.picks.get(pid) for pid in (base, trim, accent)}
        tool = await smithing.smith(self.user, self.kind, base, trim, accent, picks, random.Random())
        self.chosen = {slot: None for slot in smithing.PART_TYPES}
        self.picks = {}
        self.step, self.sub = 0, "browse"
        power = smithing.tool_power(tool.parts, tool.quality, reg.smithing)
        await self.refresh(interaction, f"{emojis.icon('craft', '🔨')} Smithed a **{reg.item(tool.template_id).name}**: "
                                        f"{tool.quality} quality, power **{power:g}**.")


class PartsPane(Screen):
    """Your smithing parts by type, and salvage for tools smithed by someone else."""

    label = "Parts"
    emoji = emojis.Lazy("ui_bag", "🧩")

    def __init__(self, nav):
        super().__init__(nav)
        self.salvage_id: int | None = None

    async def build(self) -> Page:
        rules = get_registry().smithing
        mine = await self.user.instances()
        body = [*self.note_block()]
        for slot in smithing.PART_TYPES:
            ps = [i for i in mine if _slot_of(i) == slot]
            lines = [f"· {smithing.part_label(slot, _tier(i), smithing.is_restricted(i))} · {smithing.trait_icons(i.traits, rules)}" for i in ps] or ["· none"]
            body.append(text("\n".join([f"**{slot.title()}** ({len(ps)})", *lines])))

        body += [sep(), text("**Salvage**")]
        equipped = {e.id for skill in TOOL_FOR_SKILL if (e := await self.user.equipped_instance(skill))}
        salvageable = [i for i in mine if i.parts and i.smith_id is not None and i.smith_id != self.user.id
                       and i.id not in equipped]
        if not salvageable:
            body.append(text("-# Only tools smithed by someone else can be salvaged."))
        else:
            if self.salvage_id not in {i.id for i in salvageable}:
                self.salvage_id = None
            body.append(row(select("Pick a tool to salvage...", [
                discord.SelectOption(label=instance_label(i)[:100], value=str(i.id), default=i.id == self.salvage_id,
                                     emoji=get_registry().item(i.template_id).emoji or None)
                for i in salvageable
            ], self._pick_salvage)))
            body.append(row(button("Salvage", style=discord.ButtonStyle.danger, on_click=self._salvage)))
        return Page("Parts", body, accent=0xB8860B)

    async def _pick_salvage(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.salvage_id = int(values[0])
        await self.refresh(interaction)

    async def _salvage(self, interaction: discord.Interaction) -> None:
        if self.salvage_id is None:
            await self.refresh(interaction, "Pick a tool to salvage first.")
            return
        tool = await self.user.instance(self.salvage_id)
        name = instance_label(tool) if tool else "tool"
        parts = await smithing.salvage(self.user, self.salvage_id)
        self.salvage_id = None
        await self.refresh(interaction, f"Salvaged **{name}**: got {len(parts)} parts back.")
