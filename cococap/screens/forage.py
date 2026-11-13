import random
import time
from collections import Counter

import discord

from cococap.registry import get_registry
from cococap.services import foraging
from cococap.services.equipment import equipped_stats
from cococap.services.party import xp_multiplier
from cococap.ui import Page, Screen
from cococap.ui.components import bar, bits, button, row, sep, select, text, xp_bar
from cococap.user import User

TREE = "🌳"


def new_rng() -> random.Random:
    """Each chopping screen's dice (tests replace this to make good chops predictable)."""
    return random.Random()


def items_text(drops: Counter | dict) -> str:
    reg = get_registry()
    return ", ".join(f"{q:,} {reg.item(i).display}" for i, q in drops.items()) or "no drops"


def reward_text(reward: foraging.Reward) -> str:
    what = "🌳 **TIMBER!**" if reward.felled else "🍂 The tree fell over before it was finished."
    where = " (community tree)" if reward.window is not None else ""
    return f"{what}{where}  **+{bits(reward.bits)}** bits  ·  {items_text(reward.drops)}  ·  +{reward.xp:,} xp"


def spot_line(spot: foraging.Spot, power: int, rules) -> str:
    """The chopping spot's condition and what the next ordinary chop would do."""
    fresh = spot.freshness(rules.foraging)
    return f"🪵 Spot: **{spot.condition(rules.foraging)}** {bar(fresh, 6)}  ·  next chop **{spot.preview(power, rules.foraging)}**"


def swing_note(swing: foraging.Swing, applied: int | None = None) -> str:
    dealt = swing.damage if applied is None else applied
    return f"✨ **Good chop!** {dealt}" if swing.good else f"🪓 {dealt}"


def rotate_button(spot: foraging.Spot, rules, on_click) -> discord.ui.Button:
    """Lit up when the spot is worn enough that moving is worth the click."""
    worn = spot.freshness(rules.foraging) < 0.7
    return button("Rotate", emoji="🔄", style=discord.ButtonStyle.primary if worn else discord.ButtonStyle.secondary,
                  on_click=on_click)


async def collect_community_rewards(screen: Screen) -> None:
    """Pay out anything this player is owed from finished community trees and tell them."""
    rewards = await foraging.claim_rewards(screen.user)
    if rewards:
        lines = "\n".join(reward_text(r) for r in rewards)
        screen.note = f"{screen.note}\n{lines}" if screen.note else lines


class ForageScreen(Screen):
    id = "forage"
    label = "Foraging"
    emoji = TREE
    description = "Chop trees alone or join the community tree"
    links = ("tree", "grove")

    def __init__(self, nav):
        super().__init__(nav)
        self.zone: int | None = None

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.foraging
        await collect_community_rewards(self)
        skill = await self.user.skill("foraging")
        level = User.xp_to_level(skill.xp)
        zones = foraging.unlocked_zones(level, rules)
        if self.zone not in zones:
            self.zone = zones[-1]
        stats = await equipped_stats(self.user, "foraging")
        overflow, needed = User.xp_for_next_level(skill.xp)

        header = f"**Level {level}**  {xp_bar(overflow / needed if needed else 0)}  {overflow:,}/{needed:,} xp"
        if await xp_multiplier(self.user.id) > 1:
            header += f"\n👥 Party bonus: **+{reg.economy.party_xp_bonus:.0%}** xp"
        body = [*self.note_block(), text(header)]

        if stats is None:
            body.append(text("🪓 You need an axe. Buy a **Starter Axe** in the shop, then equip it from your inventory."))
        else:
            body.append(text(f"🪓 Axe power **{stats.power}**" + ("  ·  ✨ Soloist" if stats.has("soloist") else "")))
        body.append(sep())

        # the community tree
        view = await foraging.community_tree(self.user)
        now = time.time()
        if view is not None and view.standing:
            line = (f"### 🌲 Community tree (zone {view.zone})\n{bar(view.fraction_left)}  **{view.hp:,}**/{view.max_hp:,} hp  ·  "
                    f"**{view.choppers}** chopping  ·  falls over <t:{int(view.closes_at)}:R>")
            if view.yours:
                line += f"\nYou have chopped **{view.share:.0%}** of it."
            body.append(text(line))
            body.append(row(button("Join the community tree", emoji=TREE, style=discord.ButtonStyle.success,
                                   disabled=stats is None, on_click=self._join)))
        else:
            ended = ("It was felled!" if view is not None and view.status == "felled" else "No tree is standing.")
            body.append(text(f"### 🌲 Community tree\n{ended} The next one grows <t:{int(foraging.next_tree_at(now))}:R>."))

        # a private tree
        body.append(sep())
        heavy = foraging.is_heavy(self.zone, rules) and not (stats and stats.has("soloist"))
        private = f"### 🪵 A tree of your own\nZone **{self.zone}**" + (
            "  ·  heavy: you swing at half power alone" if heavy else "")
        if len(zones) < rules.zones:
            private += f"\n-# Zone {zones[-1] + 1} needs level {foraging.zone_level(zones[-1] + 1, rules)}."
        body.append(text(private))
        if len(zones) > 1:
            body.append(row(select(
                "Zone",
                [discord.SelectOption(label=f"Zone {z}", value=str(z), default=z == self.zone,
                                      description="Heavy trees" if foraging.is_heavy(z, rules) else None) for z in zones],
                self._pick_zone,
            )))
        body.append(row(button("Chop a tree", emoji="🪓", style=discord.ButtonStyle.primary, disabled=stats is None,
                               on_click=self._chop)))
        return Page("Foraging", body, accent=0x4C8C4A)

    async def _pick_zone(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.zone = int(values[0])
        await self.refresh(interaction)

    async def _chop(self, interaction: discord.Interaction) -> None:
        await foraging.axe_stats(self.user)
        tree = foraging.roll_tree(self.zone, random.Random(), get_registry().foraging)
        await self.go(interaction, "tree", tree=tree)

    async def _join(self, interaction: discord.Interaction) -> None:
        await foraging.axe_stats(self.user)
        await self.go(interaction, "grove")


class TreeScreen(Screen):
    """A private tree: chop it down on your own."""

    id = "tree"
    label = "Tree"
    emoji = TREE
    description = "Your own tree"
    links = ("forage",)

    def __init__(self, nav):
        super().__init__(nav)
        self.tree: foraging.Tree | None = None
        self.reward: foraging.Reward | None = None
        self.spot = foraging.Spot()
        self.rng = new_rng()

    async def build(self) -> Page:
        rules = get_registry().foraging
        tree = self.tree
        if tree is None:
            return Page("Tree", [text("Pick a zone on the Foraging page and chop a tree.")], accent=0x4C8C4A)
        stats = await foraging.axe_stats(self.user)
        power = foraging.swing_power(stats, tree.zone, rules)
        body = [*self.note_block()]
        if self.reward is not None:
            body += [text("## 🌳 TIMBER!\n" + reward_text(self.reward)),
                     row(button("Another tree", emoji=TREE, style=discord.ButtonStyle.primary, on_click=self._again),
                         button("Stop", on_click=self._stop))]
            return Page("Tree", body, accent=0x4C8C4A)
        body.append(text(f"**Zone {tree.zone}**\n{bar(tree.hp / tree.max_hp)}  **{tree.hp:,}**/{tree.max_hp:,} hp"
                         f"\n{spot_line(self.spot, power, get_registry())}" + (
                             f"\n-# Heavy tree: alone you swing at half your axe's {stats.power}. A Soloist axe fixes that."
                             if power < stats.power else "")))
        body.append(row(button("Chop", emoji="🪓", style=discord.ButtonStyle.primary, on_click=self._chop),
                        rotate_button(self.spot, get_registry(), self._rotate),
                        button("Leave", on_click=self._stop)))
        return Page("Tree", body, accent=0x4C8C4A)

    async def _chop(self, interaction: discord.Interaction) -> None:
        tree = self.tree
        if tree is None or tree.felled:  # a second click that was already on its way
            return await self.refresh(interaction)
        reg = get_registry()
        stats = await foraging.axe_stats(self.user)
        swing = self.spot.swing(foraging.swing_power(stats, tree.zone, reg.foraging), reg.foraging, self.rng)
        applied = tree.chop(swing.damage)
        if tree.felled:
            self.reward = await foraging.fell_private(self.user, tree, self.rng)
        await self.refresh(interaction, swing_note(swing, applied))

    async def _rotate(self, interaction: discord.Interaction) -> None:
        self.spot.rotate()
        await self.refresh(interaction, "🔄 You move around the trunk to a fresh spot.")

    async def _again(self, interaction: discord.Interaction) -> None:
        self.tree = foraging.roll_tree(self.tree.zone, self.rng, get_registry().foraging)
        self.reward = None
        self.spot.rotate()
        await self.refresh(interaction)

    async def _stop(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "forage")


class GroveScreen(Screen):
    """The community tree: everyone's chops add up, and the panel refreshes itself so you see it fall."""

    id = "grove"
    label = "Community Tree"
    emoji = "🌲"
    description = "Chop the hourly tree together"
    links = ("forage",)

    def __init__(self, nav):
        super().__init__(nav)
        self.refresh_every = get_registry().foraging.community.refresh_seconds
        self.spot = foraging.Spot()
        self.rng = new_rng()

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.foraging
        await collect_community_rewards(self)
        view = await foraging.community_tree(self.user)
        body = [*self.note_block()]
        if view is None or not view.standing:
            ended = {"felled": "🌳 The tree has been felled! Thank you, everyone.",
                     "expired": "🍂 The tree fell over before it was finished."}.get(view.status if view else "", "No tree is standing.")
            body += [text(f"{ended}\nThe next one grows <t:{int(foraging.next_tree_at(time.time()))}:R>."),
                     row(button("Back to foraging", on_click=self._back))]
            return Page("Community Tree", body, accent=0x2E7D32)

        need = rules.community.min_share
        status = "✅ you qualify for drops" if view.share >= need else f"keep going: **{need:.0%}** of the tree qualifies you for drops"
        stats = await equipped_stats(self.user, "foraging")
        power = foraging.swing_power(stats, view.zone, rules, community=True) if stats else 1
        body += [
            text(f"**Zone {view.zone}**  ·  falls over <t:{int(view.closes_at)}:R>\n"
                 f"{bar(view.fraction_left)}  **{view.hp:,}**/{view.max_hp:,} hp\n"
                 f"**{view.choppers}** chopper(s)"),
            text(f"You: **{view.yours:,}** hp  ·  **{view.share:.1%}** of the tree\n"
                 f"{spot_line(self.spot, power, reg)}\n-# {status}"),
            row(button("Chop", emoji="🪓", style=discord.ButtonStyle.primary, on_click=self._chop),
                rotate_button(self.spot, reg, self._rotate),
                button("Leave", on_click=self._back)),
        ]
        return Page("Community Tree", body, accent=0x2E7D32)

    async def _chop(self, interaction: discord.Interaction) -> None:
        stats = await foraging.axe_stats(self.user)
        rules = get_registry().foraging
        view = await foraging.community_tree(self.user)
        power = foraging.swing_power(stats, view.zone if view else 1, rules, community=True)
        swing = self.spot.swing(power, rules, self.rng)
        result = await foraging.chop_community(self.user, swing.damage)
        note = "🌳 **You felled it!**" if result.felled_now else swing_note(swing, result.applied)
        await self.refresh(interaction, note)

    async def _rotate(self, interaction: discord.Interaction) -> None:
        self.spot.rotate()
        await self.refresh(interaction, "🔄 You move around the trunk to a fresh spot.")

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "forage")
