"""Smithing panes: build a tool from three parts (Smithing tab) and manage your parts and salvage (Parts tab).

Both are tabs of the Tools page (screens/tools.py), not registered screens. Rules live in services/smithing.py.
"""

import random

import discord

from cococap import emojis
from cococap.constants import Rarities
from cococap.registry import get_registry
from cococap.services import smithing
from cococap.services.equipment import TOOL_FOR_SKILL
from cococap.services.inventory import instance_label
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, select, sep, text


def _slot_of(inst) -> str:
    return inst.template_id.removeprefix("part_")


def _tier(inst) -> int:
    return int(inst.rolled.get("tier", 1))


def _rarity(inst) -> str:
    """A part's rarity name: its tier is its rarity."""
    return Rarities.from_value(_tier(inst)).rarity_name


def _trait_names(inst, rules) -> str:
    names = [rules.trait(t).name for t in inst.traits]
    return ", ".join(names) if names else "no trait"


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
        self.picks: dict[int, str | None] = {}  # part id -> trait taken from it (None = no trait)

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.smithing
        level = await smithing.smithing_level(self.user)
        cap = smithing.max_part_tier(level, rules)
        mine = await self.user.instances()
        parts = {slot: [] for slot in smithing.PART_TYPES}
        for inst in mine:
            if _slot_of(inst) in parts and _tier(inst) <= cap:
                parts[_slot_of(inst)].append(inst)

        body = [*self.note_block()]
        body.append(text(f"Smithing level **{level}** · parts up to tier **{cap}**"))
        if not any(parts.values()):
            body.append(text("You have no parts yet. Parts drop from skill actions: mining, fishing, foraging and farming."))
            return Page("Smithing", body, accent=0xB8860B)

        # Forget picks whose part was used up or is now above the cap.
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
                discord.SelectOption(label=k.title(), value=k, default=k == self.kind) for k in smithing.KINDS
            ], self._pick_kind)))
            return Page("Smithing", body, accent=0xB8860B)

        if self.step == 4:
            return self._preview(body, parts, rules)

        slot = smithing.PART_TYPES[self.step - 1]
        summary = " · ".join(f"{s.title()}: {self._summary_of(s, parts, rules)}" for s in smithing.PART_TYPES)
        body.append(text(f"-# {summary}"))
        body.append(text(f"**Step {self.step}/3 · {slot.title()}**"))
        options = [
            discord.SelectOption(label=f"Tier {_tier(i)} {_rarity(i)} · {_trait_names(i, rules)}"[:100], value=str(i.id),
                                 default=i.id == self.chosen[slot])
            for i in parts[slot]
        ]
        if not options:
            body.append(text(f"-# No {slot} parts at your tier."))
        else:
            body.append(row(select(f"{slot.title()} part...", options, self._part_handler(slot))))
        picked = next((i for i in parts[slot] if i.id == self.chosen[slot]), None)
        if picked is not None:
            fitting = {t.id for t in rules.traits_for(self.kind)} if self.kind else set()
            trait_options = [discord.SelectOption(label="No trait", value="none",
                                                  default=self.picks.get(picked.id) is None)]
            trait_options += [
                discord.SelectOption(label=rules.trait(t).name[:100], value=t, default=self.picks.get(picked.id) == t)
                for t in picked.traits if t in fitting
            ]
            body.append(row(select(f"{slot.title()} trait...", trait_options, self._trait_handler(picked.id))))
        body.append(row(button("Back", on_click=self._back),
                        button("Next", style=discord.ButtonStyle.primary, on_click=self._next,
                               disabled=self.chosen[slot] is None)))
        return Page("Smithing", body, accent=0xB8860B)

    def _summary_of(self, slot: str, parts: dict, rules) -> str:
        inst = next((i for i in parts[slot] if i.id == self.chosen[slot]), None)
        if inst is None:
            return "-"
        trait = self.picks.get(inst.id)
        return f"T{_tier(inst)}" + (f" {rules.trait(trait).name}" if trait else "")

    def _preview(self, body: list, parts: dict, rules) -> Page:
        picked = {slot: next(i for i in parts[slot] if i.id == self.chosen[slot]) for slot in smithing.PART_TYPES}
        power = smithing.tool_power({s: {"tier": _tier(i)} for s, i in picked.items()}, rules.grades[0].name, rules)
        body.append(text("**Preview**"))
        for slot in smithing.PART_TYPES:
            inst = picked[slot]
            trait = self.picks.get(inst.id)
            name = rules.trait(trait).name if trait else "no trait"
            body.append(text(f"· {smithing.part_label(slot, _tier(inst), smithing.is_restricted(inst))} · {name}"))
        kind = self.kind.title() if self.kind else "-"
        body.append(text(f"Kind **{kind}** · power **{power:g}** before quality"))
        body.append(text("-# Quality is rolled on smithing."))
        body.append(row(button("Back", on_click=self._back),
                        button("Smith", emoji=emojis.icon("craft", "🔨"),
                               style=discord.ButtonStyle.success, on_click=self._smith)))
        return Page("Smithing", body, accent=0xB8860B)

    async def _back(self, interaction: discord.Interaction) -> None:
        self.step = max(0, self.step - 1)
        await self.refresh(interaction)

    async def _next(self, interaction: discord.Interaction) -> None:
        if 1 <= self.step <= 3 and self.chosen[smithing.PART_TYPES[self.step - 1]] is None:
            await self.refresh(interaction, "Pick a part first.")
            return
        self.step = min(4, self.step + 1)
        await self.refresh(interaction)

    def _part_handler(self, slot: str):
        async def handler(interaction: discord.Interaction, values: list[str]) -> None:
            old = self.chosen[slot]
            if old is not None:
                self.picks.pop(old, None)  # a new part starts with no trait
            self.chosen[slot] = int(values[0])
            await self.refresh(interaction)
        return handler

    def _trait_handler(self, part_id: int):
        async def handler(interaction: discord.Interaction, values: list[str]) -> None:
            self.picks[part_id] = None if values[0] == "none" else values[0]
            await self.refresh(interaction)
        return handler

    async def _pick_kind(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.kind = values[0]
        self.picks = {}
        self.chosen = {slot: None for slot in smithing.PART_TYPES}
        self.step = 1
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
        self.step = 0
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
            lines = [f"· {smithing.part_label(slot, _tier(i), smithing.is_restricted(i))} · {_trait_names(i, rules)}" for i in ps] or ["· none"]
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
                discord.SelectOption(label=instance_label(i)[:100], value=str(i.id), default=i.id == self.salvage_id)
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
