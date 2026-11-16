import discord

from cococap.registry import get_registry
from cococap.services import tool_effects, upgrades
from cococap.services.equipment import effective_stats
from cococap.services.inventory import instance_label
from cococap.ui import Page, Screen
from cococap.ui.components import button, needs_text, row, section, select, sep, text


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


KIND_ORDER = ("pickaxe", "axe", "sword", "rod", "can")
KIND_SKILL = {"pickaxe": "Mining", "axe": "Foraging", "sword": "Combat", "rod": "Fishing", "can": "Farming"}


class UpgradeScreen(Screen):
    """One tool per page: swipe with Prev / Next between your tools, so each one's costs are easy to read on their own."""

    id = "upgrade"
    label = "Upgrade Tools"
    emoji = "🔨"
    description = "Turn a tool into the next one up"
    links = ("tools",)

    def __init__(self, nav):
        super().__init__(nav)
        self.page = 0  # which tool is showing
        self.sure: tuple[int, str] | None = None  # the upgrade waiting for its second press (when confirming is on)
        self.road: dict[int, str] = {}  # tool id -> the path showing, for a tool at a fork

    async def build(self) -> Page:
        reg = get_registry()
        offers = await upgrades.offers(self.user)
        body = [*self.note_block()]
        if not offers:
            body.append(text("Nothing to upgrade. Claim your free starter tools on the Tools page first; "
                             "tools that are already maxed don't show up here."))
            return Page("Upgrade Tools", [*body, sep(), row(button("Back to tools", emoji="🧰", on_click=self._back))], accent=0xB8860B)
        groups: dict[int, list] = {}
        for offer in sorted(offers, key=lambda o: KIND_ORDER.index(o.current.tool.kind)):
            groups.setdefault(offer.instance.id, []).append(offer)
        tools = list(groups.values())
        self.page = max(0, min(self.page, len(tools) - 1))
        mine = tools[self.page]
        first = mine[0]
        owned = await self.user.items()
        body.append(text(f"### {first.current.emoji or '🔨'} {instance_label(first.instance)}  ·  {KIND_SKILL[first.current.tool.kind]}\n"
                         f"Power **{effective_stats(first.instance).power}**"
                         + (f"  ·  {describe_stats(first.current.tool.stats)}" if first.current.tool.stats else "")
                         + (f"  ·  {first.current.tool.path} path" if first.current.tool.path else "")
                         + f"\n-# {tool_effects.HOW[first.current.tool.kind]}"
                         + (f"\n-# ✨ {first.current.tool.ability_name}: {first.current.tool.ability_description}" if first.current.tool.ability_name else "")))
        shown = mine
        if len(mine) > 1:  # a fork in the road: one page per path, swapped with a dropdown
            chosen = self.road.get(first.instance.id, mine[0].path)
            shown = [o for o in mine if o.path == chosen] or mine[:1]
            body.append(row(select("Pick a path...", [
                discord.SelectOption(label=f"{(o.target.tool.path or o.path).title()} path", description=o.target.name, value=o.path, default=o is shown[0])
                for o in mine], self._road(first.instance.id))))
        for offer in shown:
            cost, target = offer.cost, offer.target.tool
            road = f"  ·  **{target.path} path**" if target.path and offer.current.tool.fork else ""
            now = effective_stats(offer.instance).power
            after = target.power + (now - offer.current.tool.power)  # (enchant and rolled bonuses carry over)
            lines = (f"**→ {offer.target.name}**{road}\n"
                     f"Power **{now}** → **{after}**" + (f"  ·  {describe_stats(target.stats)}" if target.stats else "")
                     + "\n" + "\n".join(tool_effects.compare(target.kind, now, after, reg, offer.current.tool.path, target.path, offer.current.tool.stats, target.stats))
                     + (f"\n✨ New ability: **{target.ability_name}**: {target.ability_description}" if target.ability_name and target.ability != offer.current.tool.ability else "")
                     + "\n" + needs_text(cost.bits, self.user.purse, cost.items, owned, reg))
            if offer.level_needed:
                lines += f"\n-# {offer.target.name} needs level {offer.level_needed} in its skill."
            body.append(section(lines, accessory=button(
                "Sure?" if self.sure == (offer.instance.id, offer.path) else "Upgrade",
                style=discord.ButtonStyle.danger if self.sure == (offer.instance.id, offer.path) else discord.ButtonStyle.success, disabled=not offer.affordable,
                on_click=self._upgrade(offer.instance.id, offer.path))))
        if first.current.tool.fork:
            body.append(text("-# ⚠️ A fork in the road: the path you take is the one your tool climbs from now on."))
        body.append(sep())
        if len(tools) > 1:
            body.append(row(button("Prev", emoji="◀️", disabled=self.page == 0, on_click=self._turn(-1)),
                            button(f"{self.page + 1}/{len(tools)}", disabled=True),
                            button("Next", emoji="▶️", disabled=self.page >= len(tools) - 1, on_click=self._turn(1))))
        body.append(row(button("Back to tools", emoji="🧰", on_click=self._back)))
        return Page("Upgrade Tools", body, accent=0xB8860B)

    def _turn(self, step: int):
        async def go(interaction: discord.Interaction) -> None:
            self.page += step
            self.sure = None
            await self.refresh(interaction)

        return go

    def _road(self, instance_id: int):
        async def pick(interaction: discord.Interaction, values: list[str]) -> None:
            self.road[instance_id] = values[0]
            self.sure = None
            await self.refresh(interaction)

        return pick

    def _upgrade(self, instance_id: int, path: str = "up"):
        async def go(interaction: discord.Interaction) -> None:
            if self.user.settings.confirm_upgrades and self.sure != (instance_id, path):
                self.sure = (instance_id, path)
                return await self.refresh(interaction, "Press **Sure?** to upgrade, or look at something else to cancel.")
            self.sure = None
            done = await upgrades.upgrade(self.user, instance_id, path=path)
            await self.refresh(interaction, f"🔨 Your {done.current.name} became a **{done.target.name}**!")

        return go

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "tools")
