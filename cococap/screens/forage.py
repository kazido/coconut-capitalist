import random
import time
from collections import Counter

import discord

from cococap.registry import get_registry
from cococap.services import foraging, pets
from cococap.services.equipment import equipped_stats
from cococap.services.party import xp_bonus
from cococap.ui import Page, Result, Screen
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
    """Where you are chopping, how worn it is, and what the next ordinary chop would do."""
    r = rules.foraging
    quality = f"{spot.quality - 1:+.0%}" if spot.quality != 1 else "±0%"
    return (f"🪵 **{spot.name}** spot ({quality})  ·  {spot.condition(r)} {bar(spot.freshness(r), 6)}"
            f"\n-# next: 🪓 **{spot.preview(power, r)}**  ·  💥 heavy **{spot.preview(power, r, 'heavy')}** ({r.chopping.heavy.miss:.0%} to miss)"
            f"  ·  🔪 careful **{spot.preview(power, r, 'careful')}**")


def swing_note(swing: foraging.Swing, applied: int | None = None) -> str:
    if swing.missed:
        return "💨 **You swing wide!** The axe hits nothing."
    dealt = swing.damage if applied is None else applied
    icon = {"heavy": "💥", "careful": "🔪"}.get(swing.style, "🪓")
    return f"✨ **Good chop!** {dealt}" if swing.good else f"{icon} {dealt}"


def chop_buttons(on_click) -> list[discord.ui.Button]:
    """Chop (steady), Heavy swing (hits harder, wears the spot out, can miss) and Careful cut (gentle, never wears it)."""
    return [button("Chop", emoji="🪓", style=discord.ButtonStyle.primary, on_click=on_click("normal")),
            button("Heavy", emoji="💥", style=discord.ButtonStyle.danger, on_click=on_click("heavy")),
            button("Careful", emoji="🔪", style=discord.ButtonStyle.secondary, on_click=on_click("careful"))]


def rotate_button(on_click) -> discord.ui.Button:
    """Rotating picks a random new spot, so when to do it is the player's call (nothing lights up to tell them)."""
    return button("Rotate", emoji="🔄", on_click=on_click)


def rotated_note(spot: foraging.Spot) -> str:
    return f"🔄 You move around the trunk to a **{spot.name}** spot."


async def collect_community_rewards(screen: Screen) -> None:
    """Pay out anything this player is owed from finished community trees and tell them."""
    rewards = await foraging.claim_rewards(screen.user)
    if rewards:
        screen.result = Result("The community tree is down!", [reward_text(r) for r in rewards], emoji="🌳", accent=0x2E7D32,
                               back_label="Continue")


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
        if bonus := await xp_bonus(self.user.id):
            header += f"\n👥 Party bonus: **+{bonus:.0%}** xp"
        body = [*self.note_block(), text(header)]

        if stats is None:
            body.append(text("🪓 You need an axe. Buy a **Starter Axe** in the shop and it equips itself."))
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
        self.rng = new_rng()
        self.spot = foraging.Spot.pick(get_registry().foraging, self.rng)

    async def build(self) -> Page:
        rules = get_registry().foraging
        tree = self.tree
        if tree is None:
            return Page("Tree", [text("Pick a zone on the Foraging page and chop a tree.")], accent=0x4C8C4A)
        stats = await foraging.axe_stats(self.user)
        power = foraging.swing_power(stats, tree.zone, rules)
        body = [*self.note_block()]
        body.append(text(f"**Zone {tree.zone}**\n{bar(tree.hp / tree.max_hp)}  **{tree.hp:,}**/{tree.max_hp:,} hp"
                         f"\n{spot_line(self.spot, power, get_registry())}" + (
                             f"\n-# Heavy tree: alone you swing at half your axe's {stats.power}. A Soloist axe fixes that."
                             if power < stats.power else "")))
        body.append(row(*chop_buttons(self._chop), rotate_button(self._rotate)))
        body.append(row(button("Leave", on_click=self._stop)))
        return Page("Tree", body, accent=0x4C8C4A)

    def _chop(self, style: str):
        async def chop(interaction: discord.Interaction) -> None:
            await self._swing(interaction, style)

        return chop

    async def _swing(self, interaction: discord.Interaction, style: str) -> None:
        tree = self.tree
        if tree is None or tree.felled:  # a second click that was already on its way
            return await self.refresh(interaction)
        reg = get_registry()
        stats = await foraging.axe_stats(self.user)
        swing = self.spot.swing(foraging.swing_power(stats, tree.zone, reg.foraging), reg.foraging, self.rng,
                                stats.stats.get("good_chop", 0.0) + (await pets.bonuses(self.user)).get("good_chop", 0.0), style)
        if swing.missed:
            return await self.refresh(interaction, swing_note(swing))
        applied = tree.chop(swing.damage)
        if tree.felled:
            self.reward = await foraging.fell_private(self.user, tree, self.rng)
            self.result = Result("TIMBER!", [reward_text(self.reward)], emoji="🌳", accent=0x4C8C4A, again=self._again,
                                 again_label="Another tree", back=self._stop, back_label="Back to foraging")
            return await self.refresh(interaction)
        await self.refresh(interaction, swing_note(swing, applied))

    async def _rotate(self, interaction: discord.Interaction) -> None:
        self.spot.rotate(get_registry().foraging, self.rng)
        await self.refresh(interaction, rotated_note(self.spot))

    async def _again(self, interaction: discord.Interaction) -> None:
        self.tree = foraging.roll_tree(self.tree.zone, self.rng, get_registry().foraging)
        self.reward = None
        self.spot.rotate(get_registry().foraging, self.rng)
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
        self.rng = new_rng()
        self.spot = foraging.Spot.pick(get_registry().foraging, self.rng)

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
            row(*chop_buttons(self._chop), rotate_button(self._rotate)),
            row(button("Leave", on_click=self._back)),
        ]
        return Page("Community Tree", body, accent=0x2E7D32)

    def _chop(self, style: str):
        async def chop(interaction: discord.Interaction) -> None:
            await self._swing(interaction, style)

        return chop

    async def _swing(self, interaction: discord.Interaction, style: str) -> None:
        stats = await foraging.axe_stats(self.user)
        rules = get_registry().foraging
        view = await foraging.community_tree(self.user)
        power = foraging.swing_power(stats, view.zone if view else 1, rules, community=True)
        swing = self.spot.swing(power, rules, self.rng,
                                stats.stats.get("good_chop", 0.0) + (await pets.bonuses(self.user)).get("good_chop", 0.0), style)
        if swing.missed:
            return await self.refresh(interaction, swing_note(swing))
        result = await foraging.chop_community(self.user, swing.damage)
        note = "🌳 **You felled it!**" if result.felled_now else swing_note(swing, result.applied)
        await self.refresh(interaction, note)

    async def _rotate(self, interaction: discord.Interaction) -> None:
        self.spot.rotate(get_registry().foraging, self.rng)
        await self.refresh(interaction, rotated_note(self.spot))

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "forage")
