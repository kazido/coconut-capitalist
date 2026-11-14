import discord

from cococap.registry import get_registry
from cococap.services import upgrades
from cococap.services.equipment import effective_stats
from cococap.services.inventory import instance_label
from cococap.ui import Page, Screen
from cococap.ui.components import button, needs_text, row, section, sep, text

MAX_SHOWN = 6

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


class UpgradeScreen(Screen):
    id = "upgrade"
    label = "Upgrade Tools"
    emoji = "🔨"
    description = "Turn a tool into the next one up"
    links = ("inventory",)

    async def build(self) -> Page:
        reg = get_registry()
        offers = await upgrades.offers(self.user)
        body = [*self.note_block()]
        if not offers:
            body.append(text("Nothing to upgrade. Buy a starter tool in the shop first; "
                             "tools that are already the best of their kind don't show up here."))
        owned = await self.user.items()
        for offer in offers[:MAX_SHOWN]:
            cost = offer.cost
            now = effective_stats(offer.instance).power
            after = offer.target.tool.power
            target = offer.target.tool
            road = f"  ·  **{target.path} path**" if target.path and offer.current.tool.fork else ""
            lines = (f"### {offer.current.emoji or '🔨'} {instance_label(offer.instance)}  →  {offer.target.name}{road}\n"
                     f"Power **{now}** → **{after}**" + (f"  ·  {describe_stats(target.stats)}" if target.stats else "") + "\n"
                     + needs_text(cost.bits, self.user.purse, cost.items, owned, reg)
                     + ("\n-# ⚠️ A fork in the road: the road you take is the one your tool climbs from now on." if offer.current.tool.fork else ""))
            if offer.level_needed:
                lines += f"\n-# {offer.target.name} needs level {offer.level_needed} in its skill."
            body.append(section(lines, accessory=button(
                "Upgrade", style=discord.ButtonStyle.success, disabled=not offer.affordable,
                on_click=self._upgrade(offer.instance.id, offer.path))))
        if len(offers) > MAX_SHOWN:
            body.append(text(f"-# …and {len(offers) - MAX_SHOWN} more tools."))
        body += [sep(), row(button("Back to inventory", emoji="🎒", on_click=self._back))]
        return Page("Upgrade Tools", body, accent=0xB8860B)

    def _upgrade(self, instance_id: int, path: str = "up"):
        async def go(interaction: discord.Interaction) -> None:
            done = await upgrades.upgrade(self.user, instance_id, path=path)
            await self.refresh(interaction, f"🔨 Your {done.current.name} became a **{done.target.name}**!")

        return go

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "inventory")
