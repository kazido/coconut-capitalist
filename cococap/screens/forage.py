import random
import time
from collections import Counter

import discord

from cococap.registry import get_registry
from cococap.services import foraging, party_tree, pets
from cococap.services.equipment import equipped_stats
from cococap.services.party import Party, xp_bonus
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
    where = " (party tree)" if reward.party else " (community tree)" if reward.window is not None else ""
    return f"{what}{where}  **+{bits(reward.bits)}** bits  ·  {items_text(reward.drops)}  ·  +{reward.xp:,} xp"


async def spot_panel(screen, zone: int, power: int) -> str:
    """Where you are chopping: the grain, how worn it is, how far through its pattern you are (only the steps you have done on
    THIS spot show; the rest are ❔, so you have to remember them or look in your grain notes) and your mistakes."""
    reg = get_registry()
    r = reg.foraging
    spot = screen.spot
    cycle = foraging.cycle_length(zone, r)
    pattern = spot.pattern(r)[:cycle]
    steps = []
    for i, letter in enumerate(pattern):
        glyph = foraging.STANCES[letter][1] if i < spot.step else "❔"
        steps.append(f"**{glyph}**" if i == spot.step else glyph)
    quality = f"{spot.quality - 1:+.0%}" if spot.quality != 1 else "±0%"
    strikes = "❌" * spot.strikes + "⬜" * max(0, r.chopping.strikes - spot.strikes)
    return (f"🪵 **{spot.name}** grain ({quality})  ·  {spot.condition(r)} {bar(spot.freshness(r), 6)}\n"
            f"🧭 {' '.join(steps)}" + (f"  ·  combo ×{spot.combo}" if spot.combo else "") + f"  ·  mistakes {strikes}"
            + f"\n-# step {spot.step + 1}/{cycle}  ·  a right move hits for about **{spot.preview(power, r, cycle)}**"
            + "  ·  what you have learned is in your **Grain notes**")


async def notes_result(user) -> Result:
    """Your grain notes on a page of their own (it returns you to the tree you were chopping)."""
    lines = []
    for grain, known in await foraging.grain_notes(user):
        pattern = grain.pattern
        shown = " ".join(foraging.STANCES[c][1] if i < known else "❔" for i, c in enumerate(pattern))
        lines.append(f"**{grain.name}** ({grain.multiplier - 1:+.0%}): {shown}  ·  {known}/{len(pattern)}")
    return Result("Grain notes", ["Every spot has a grain with its own pattern. What you have learned is written here; the spot "
                                  "you are chopping shows ❔ again, so remember it!", "\n".join(lines)],
                  emoji="📖", accent=0x8D6E63, back_label="Back to chopping")


def swing_note(swing: foraging.Swing, stance: str | None = None, applied: int | None = None) -> str:
    dealt = swing.damage if applied is None else applied
    icon = foraging.STANCES[stance][1] if stance in foraging.STANCES else "🪓"
    if swing.correct is None:
        return f"✨ **Good chop!** {dealt}" if swing.good else f"🪓 {dealt}"
    if not swing.correct:
        return f"💢 Glancing blow ({dealt}). That wasn't the right move for this step."
    extra = "  ✨ **Good chop!**" if swing.good else ""
    if swing.finisher:
        return f"🌟 **Perfect!** The pattern is done and the axe bites deep: **{dealt}**{extra}"
    return f"✅ {icon} The grain gives!  combo ×{swing.combo}  ·  {dealt}{extra}"


def stance_buttons(on_click) -> list[discord.ui.Button]:
    """The three stances. Which one is right depends on the grain and your place in its pattern."""
    return [button(name, emoji=glyph, style=discord.ButtonStyle.primary, on_click=on_click(letter))
            for letter, (name, glyph) in foraging.STANCES.items()]


async def swing_at(screen: Screen, zone: int, power: int, stance: str) -> tuple[foraging.Swing, str]:
    """Swing in a stance on this screen's spot. Remembers any new step of the pattern you got right. Returns the swing and
    what to tell the player about it."""
    reg = get_registry()
    rules = reg.foraging
    stats = await foraging.axe_stats(screen.user)
    grain, name = screen.spot.grain, screen.spot.name  # (the spot may change under us when it ends)
    known = await foraging.learned_steps(screen.user, grain)
    swing = screen.spot.swing(power, rules, screen.rng,
                              stats.stats.get("good_chop", 0.0) + (await pets.bonuses(screen.user)).get("good_chop", 0.0),
                              stance, foraging.cycle_length(zone, rules))
    note = swing_note(swing, stance)
    if swing.correct and swing.index + 1 > known and await foraging.learn(screen.user, grain, swing.index + 1):
        note += f"\n📖 You learned step **{swing.index + 1}** of the **{name}** grain!"
    if swing.ended == "failed":
        note += f"\n💥 Too many mistakes: the **{name}** spot gives out. You move to a new one ({screen.spot.name} grain)."
    elif swing.ended == "finished":
        note += f"\n➡️ You move on to a new spot ({screen.spot.name} grain)."
    return swing, note


async def collect_community_rewards(screen: Screen) -> None:
    """Pay out anything this player is owed from finished community trees and tell them."""
    rewards = await foraging.claim_rewards(screen.user) + await party_tree.claim(screen.user)
    if rewards:
        title = "The tree is down!" if any(r.party for r in rewards) and not any(not r.party for r in rewards) else "The community tree is down!"
        screen.result = Result(title, [reward_text(r) for r in rewards], emoji="🌳", accent=0x2E7D32, back_label="Continue")


class ForageScreen(Screen):
    id = "forage"
    label = "Foraging"
    emoji = TREE
    description = "Chop trees alone or join the community tree"
    links = ("tree", "grove", "partygrove")

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

        # a tree for your party
        body += await self._party_section(stats)

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
                               on_click=self._chop),
                        button("Grain notes", emoji="📖", on_click=self._notes)))
        return Page("Foraging", body, accent=0x4C8C4A)

    async def _party_section(self, stats) -> list:
        party = await Party.for_user(self.user.id)
        if party is None or party.member_count() < 2:
            return [text("-# 👥 Chop with friends: join a party and you can start a **party tree** that pays a little better.")]
        pt = await party_tree.view(self.user)
        bonus = get_registry().foraging.party_tree
        if pt is not None and pt.standing:
            line = (f"### 👥 Party tree (zone {pt.zone})\n{bar(pt.fraction_left)}  **{pt.hp:,}**/{pt.max_hp:,} hp  ·  "
                    f"**{len(pt.chops)}** chopping  ·  falls over <t:{int(pt.closes_at)}:R>")
            return [text(line), row(button("Join the party tree", emoji="👥", style=discord.ButtonStyle.success,
                                          disabled=stats is None, on_click=self._join_party))]
        best = await party_tree.unlocked_zone(party)
        zone = min(self.zone or 1, best)
        return [text(f"### 👥 Party tree\nNo tree is up. Start one for your party of **{party.member_count()}**: **zone {zone}**, "
                     f"up to **+{bonus.max_group_bonus:.0%}** reward for working together.\n-# The whole party needs an axe and the zone unlocked."),
                row(button("Start a party tree", emoji="👥", style=discord.ButtonStyle.primary, disabled=stats is None,
                           on_click=self._start_party))]

    async def _notes(self, interaction: discord.Interaction) -> None:
        self.result = await notes_result(self.user)
        await self.refresh(interaction)

    async def _start_party(self, interaction: discord.Interaction) -> None:
        party = await Party.for_user(self.user.id)
        best = await party_tree.unlocked_zone(party) if party else 1
        await party_tree.start(self.user, min(self.zone or 1, best))
        await self.go(interaction, "partygrove")

    async def _join_party(self, interaction: discord.Interaction) -> None:
        await foraging.axe_stats(self.user)
        await self.go(interaction, "partygrove")

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
                         f"\n{await spot_panel(self, tree.zone, power)}" + (
                             f"\n-# Heavy tree: alone you swing at half your axe's {stats.power}. A Soloist axe fixes that."
                             if power < stats.power else "")))
        body.append(row(*stance_buttons(self._chop)))
        body.append(row(button("Grain notes", emoji="📖", on_click=self._notes), button("Leave", on_click=self._stop)))
        return Page("Tree", body, accent=0x4C8C4A)

    def _chop(self, stance: str):
        async def chop(interaction: discord.Interaction) -> None:
            await self._swing(interaction, stance)

        return chop

    async def _swing(self, interaction: discord.Interaction, stance: str) -> None:
        tree = self.tree
        if tree is None or tree.felled:  # a second click that was already on its way
            return await self.refresh(interaction)
        reg = get_registry()
        stats = await foraging.axe_stats(self.user)
        swing, note = await swing_at(self, tree.zone, foraging.swing_power(stats, tree.zone, reg.foraging), stance)
        applied = tree.chop(swing.damage)
        if tree.felled:
            self.reward = await foraging.fell_private(self.user, tree, self.rng)
            self.result = Result("TIMBER!", [reward_text(self.reward)], emoji="🌳", accent=0x4C8C4A, again=self._again,
                                 again_label="Another tree", back=self._stop, back_label="Back to foraging")
            return await self.refresh(interaction)
        await self.refresh(interaction, note)

    async def _notes(self, interaction: discord.Interaction) -> None:
        self.result = await notes_result(self.user)
        await self.refresh(interaction)

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
                 f"{await spot_panel(self, view.zone, power)}\n-# {status}"),
            row(*stance_buttons(self._chop)),
            row(button("Grain notes", emoji="📖", on_click=self._notes), button("Leave", on_click=self._back)),
        ]
        return Page("Community Tree", body, accent=0x2E7D32)

    def _chop(self, stance: str):
        async def chop(interaction: discord.Interaction) -> None:
            await self._swing(interaction, stance)

        return chop

    async def _swing(self, interaction: discord.Interaction, stance: str) -> None:
        stats = await foraging.axe_stats(self.user)
        rules = get_registry().foraging
        view = await foraging.community_tree(self.user)
        zone = view.zone if view else 1
        swing, note = await swing_at(self, zone, foraging.swing_power(stats, zone, rules, community=True), stance)
        result = await foraging.chop_community(self.user, swing.damage)
        await self.refresh(interaction, "🌳 **You felled it!**" if result.felled_now else note)

    async def _notes(self, interaction: discord.Interaction) -> None:
        self.result = await notes_result(self.user)
        await self.refresh(interaction)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "forage")


class PartyGroveScreen(Screen):
    """Your party's tree: only members can chop it, everyone's chops add up, and it pays a little better for teamwork."""

    id = "partygrove"
    label = "Party Tree"
    emoji = "👥"
    description = "Chop your party's tree together"
    links = ("forage",)

    def __init__(self, nav):
        super().__init__(nav)
        self.refresh_every = get_registry().foraging.party_tree.refresh_seconds
        self.rng = new_rng()
        self.spot = foraging.Spot.pick(get_registry().foraging, self.rng)

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.foraging
        await collect_community_rewards(self)
        view = await party_tree.view(self.user)
        body = [*self.note_block()]
        if view is None or not view.standing:
            ended = {"felled": "🌳 Your party felled it! Well chopped, team.",
                     "expired": "🍂 The tree fell over before it was finished."}.get(view.status if view else "", "Your party has no tree standing.")
            body += [text(ended), row(button("Back to foraging", on_click=self._back))]
            return Page("Party Tree", body, accent=0x1F8A70)
        need = rules.party_tree.min_share
        status = "✅ you qualify for drops" if view.share >= need else f"keep going: **{need:.0%}** of the tree qualifies you for drops"
        stats = await equipped_stats(self.user, "foraging")
        power = foraging.swing_power(stats, view.zone, rules, community=True) if stats else 1
        team = []
        for uid, damage in sorted(view.chops.items(), key=lambda kv: -kv[1]):
            team.append(f"{await self.nav.name_of(uid)}{' (you)' if uid == self.user.id else ''}: **{damage:,}** hp ({damage / view.max_hp:.0%})")
        body += [
            text(f"**Zone {view.zone}**  ·  falls over <t:{int(view.closes_at)}:R>\n"
                 f"{bar(view.fraction_left)}  **{view.hp:,}**/{view.max_hp:,} hp\n" + ("\n".join(team) if team else "Nobody has chopped yet.")),
            text(f"{await spot_panel(self, view.zone, power)}\n-# {status}"),
            row(*stance_buttons(self._chop)),
            row(button("Grain notes", emoji="📖", on_click=self._notes), button("Leave", on_click=self._back)),
        ]
        return Page("Party Tree", body, accent=0x1F8A70)

    def _chop(self, stance: str):
        async def chop(interaction: discord.Interaction) -> None:
            await self._swing(interaction, stance)

        return chop

    async def _swing(self, interaction: discord.Interaction, stance: str) -> None:
        stats = await foraging.axe_stats(self.user)
        rules = get_registry().foraging
        view = await party_tree.view(self.user)
        zone = view.zone if view else 1
        swing, note = await swing_at(self, zone, foraging.swing_power(stats, zone, rules, community=True), stance)
        result = await party_tree.chop(self.user, swing.damage)
        await self.refresh(interaction, "🌳 **You felled it!**" if result.felled_now else note)

    async def _notes(self, interaction: discord.Interaction) -> None:
        self.result = await notes_result(self.user)
        await self.refresh(interaction)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "forage")
