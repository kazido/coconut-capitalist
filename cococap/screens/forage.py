import random
import time
from collections import Counter

import discord

from cococap.registry import get_registry
from cococap.screens.sellall import start_sell_all
from cococap.services import foraging, party_tree, pets, releaf
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
    line = f"{what}{where}  **+{bits(reward.bits)}** bits  ·  {items_text(reward.drops)}  ·  +{reward.xp:,} xp"
    if reward.jackpot:
        kind, amount = reward.jackpot
        line += ("\n🌲🌲 **DOUBLE TREE!** A **Spirit of the Forest** drops: your pet will love it." if kind == "spirit"
                 else f"\n🌲🌲 **DOUBLE TREE!** A jackpot of **+{amount:,}** foraging xp!")
    return line


async def releaf_actions(screen: Screen, drops: Counter, **after) -> list:
    """The "donate the drops to Re-leaf" button for a result page, if you may (level 10, a donation left today, something to give)."""
    status = await releaf.status(screen.user)
    if not (status.unlocked and status.left_today > 0 and any(q > 0 for q in drops.values())):
        return []
    gain = releaf.meter_gain(drops, get_registry())

    async def donate(interaction: discord.Interaction) -> None:
        done = await releaf.donate(screen.user, drops)
        lines = [f"You gave {items_text(drops)} to the Re-leaf foundation.",
                 f"🌱 Meter **{done.meter}/{done.goal}**  (+{done.gained})  ·  **{done.left_today}** donation(s) left today"]
        if done.became_ready:
            lines.append("🌲🌲 **Your next tree will be a double tree!**")
        screen.result = Result("The trees thank you!", lines, emoji="🌱", accent=0x2E7D32, **after)
        await screen.refresh(interaction)

    return [(f"Donate the drops (+{gain})", "🌱", donate)]


async def releaf_line(user) -> str | None:
    """Where your Re-leaf meter stands (nothing before foraging level 10)."""
    s = await releaf.status(user)
    if not s.unlocked:
        return None
    line = f"🌱 **Re-leaf**  {bar(s.meter / s.goal, 8)}  {s.meter}/{s.goal}  ·  {s.left_today} donation(s) left today"
    return line + ("\n🌲🌲 **Your next tree is a double tree!**" if s.double_ready else "")


async def spot_panel(screen, power: int) -> str:
    """Where you are chopping: the grain, how worn the spot is and what a chop in the right style does right now. The style the grain
    likes is NOT shown: it is in your Grain notes, so you have to remember it."""
    reg = get_registry()
    spot = screen.spot
    quality = f" ({spot.quality - 1:+.0%})" if spot.quality != 1 else ""
    left = max(0.0, 1 - spot.wear)
    wedges = sum(q for _, q in await foraging.wedges(screen.user))
    return (f"🪵 **{spot.title(reg.foraging)}** grain{quality}   🪚 spot {bar(left, 6)} {left:.0%}   🪓 **{spot.preview(power, reg.foraging)}** a chop"
            + (f"   ·   🔩 {wedges} wedge(s)" if wedges else ""))


async def notes_result(user) -> Result:
    """Your grain notes on a page of their own (it returns you to the tree you were chopping)."""
    lines = []
    for note in await foraging.grain_notes(user):
        g = note.grain
        if note.known:
            what = f"{foraging.STANCES[note.known][1]} {foraging.STANCES[note.known][0]}"
        elif note.ruled_out:
            what = "❔ " + " ".join(f"✖️{foraging.STANCES[c][1]}" for c in note.ruled_out)
        else:
            what = "❔"
        lines.append(f"**{g.name}** ({g.multiplier - 1:+.0%}, wears {'slowly' if g.wear < 0.95 else 'quickly' if g.wear > 1.05 else 'normally'}): {what}")
    return Result("Grain notes", ["Every grain likes one chop style. Chop in any other and the swing glances off at half strength. ✖️ marks "
                                  "styles you have seen fail, so two crossed off give away the third. The spot you are chopping never "
                                  "tells you its style: remember it!", "\n".join(lines)],
                  emoji="📖", accent=0x8D6E63, back_label="Back to chopping")


def swing_note(swing: foraging.Swing, stance: str | None = None, applied: int | None = None) -> str:
    dealt = swing.damage if applied is None else applied
    icon = foraging.STANCES[stance][1] if stance in foraging.STANCES else "🪓"
    good = "  ✨ **Good chop!**" if swing.good else ""
    extra = "  🪓🪓 **Double chop!**" if swing.doubled else ""
    extra += {"damage": "  💎 **Heartwood: a huge hit!**", "xp": "  ✨ **Golden Knot: double xp!**",
              "mark": f"  🏷️ **Marked: +{swing.mark:.0%} rewards**"}.get(swing.special, "")
    if swing.correct is None:
        return (f"✨ **Good chop!** {dealt}" if swing.good else f"🪓 {dealt}") + extra
    return f"{'✅' if swing.correct else '❌ glanced off'} {icon}  ·  {dealt}{good}{extra}"


def stance_buttons(on_click) -> list[discord.ui.Button]:
    """The three styles. Which one is right depends on the grain you are on."""
    return [button(name, emoji=glyph, style=discord.ButtonStyle.primary, on_click=on_click(letter))
            for letter, (name, glyph) in foraging.STANCES.items()]


async def wedge_row(screen: Screen):
    """One button per kind of wedge you hold (moving off a bad spot), or nothing when you hold none."""
    held = await foraging.wedges(screen.user)
    if not held:
        return None
    reg = get_registry()

    def use(item_id: str):
        async def go(interaction: discord.Interaction) -> None:
            await foraging.spend_wedge(screen.user, screen.spot, item_id, screen.rng)
            await screen.refresh(interaction, f"🪚 You drive a wedge in: new spot, **{screen.spot.title(reg.foraging)}** grain.")

        return go

    return row(*(button(f"{reg.item(w.item).name} ×{q}", emoji="🔩", on_click=use(w.item)) for w, q in held))


async def swing_at(screen: Screen, power: int, stance: str) -> tuple[foraging.Swing, str]:
    """Swing in a style on this screen's spot. Writes down what you found out about the grain (the right style is remembered, a wrong
    one is crossed off) and wears the spot. Returns the swing and what to tell the player about it."""
    reg = get_registry()
    rules = reg.foraging
    stats = await foraging.axe_stats(screen.user)
    grain, name = screen.spot.grain, screen.spot.name
    pet = await pets.bonuses(screen.user)
    swing = screen.spot.swing(power, rules, screen.rng, stats.stats.get("good_chop", 0.0) + pet.get("good_chop", 0.0), stance,
                              stats.stats.get("wear_slow", 0.0), stats.stats.get("double_chop", 0.0), stats.stats.get("clean_cut", 0.0))
    note = swing_note(swing, stance)
    if swing.correct is not None and await foraging.note_style(screen.user, grain, stance, swing.correct):
        note += (f"  📖 Learned: the **{name}** grain likes **{foraging.STANCES[stance][0]}**!" if swing.correct
                 else f"  ✖️ {foraging.STANCES[stance][0]} crossed off the **{name}** grain in your notes")
    shaken = await foraging.shake(screen.user, stats.stats.get("shake", 0.0), screen.rng) + await foraging.windfall(screen.user, int(stats.stats.get("windfall", 0)), screen.rng)
    if shaken:
        note += "  🍃 Shook loose " + ", ".join(f"{q:,} {reg.item(i).name}" for i, q in shaken.items()) + "!"
    if swing.ended:
        note += f"\n🪵 The spot wore out. New spot: **{screen.spot.title(rules)}** grain"
    return swing, note


async def collect_community_rewards(screen: Screen) -> None:
    """Pay out anything this player is owed from finished community trees and tell them."""
    rewards = await foraging.claim_rewards(screen.user) + await party_tree.claim(screen.user)
    if rewards:
        title = "The tree is down!" if any(r.party for r in rewards) and not any(not r.party for r in rewards) else "The community tree is down!"
        drops = sum((r.drops for r in rewards), Counter())
        screen.result = Result(title, [reward_text(r) for r in rewards], emoji="🌳", accent=0x2E7D32, back_label="Continue",
                               actions=await releaf_actions(screen, drops, back_label="Continue"))


class ForageScreen(Screen):
    id = "forage"
    label = "Foraging"
    emoji = TREE
    description = "Chop trees alone or join the community tree"
    links = ("tree", "grove", "partygrove", "sellall", "mastery")

    def __init__(self, nav):
        super().__init__(nav)
        self.zone: int | None = None
        self.watching_party = False  # in a party: redraw by itself so a tree a teammate starts shows up

    @property
    def refresh_every(self) -> float | None:  # type: ignore[override]
        return get_registry().foraging.party_tree.refresh_seconds if self.watching_party else None

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
        if line := await releaf_line(self.user):
            body.append(text(line))
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
                        button("Grain notes", emoji="📖", on_click=self._notes),
                        button("Mastery", emoji="🌟", on_click=self._mastery),
                        button("Sell all", emoji="💰", on_click=self._sell_all)))
        return Page("Foraging", body, accent=0x4C8C4A)

    async def _party_section(self, stats) -> list:
        party = await Party.for_user(self.user.id)
        self.watching_party = party is not None and party.member_count() >= 2
        if party is None or party.member_count() < 2:
            return [text("-# 👥 In a party you can start a **party tree** (pays better).")]
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

    async def _sell_all(self, interaction: discord.Interaction) -> None:
        await start_sell_all(self, interaction, "foraging")

    async def _mastery(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "mastery", skill="foraging")

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
        tree = await releaf.new_tree(self.user, self.zone, random.Random())
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
        body.append(text(f"{'🌲🌲 **Double tree!**  ' if tree.double else ''}**Zone {tree.zone}**\n{bar(tree.hp / tree.max_hp)}  **{tree.hp:,}**/{tree.max_hp:,} hp"
                         f"\n{await spot_panel(self, power)}" + (f"\n🏷️ Marked: **+{tree.bonus:.0%}** bits and drops when it falls" if tree.bonus else "") + (
                             f"\n-# Heavy tree: alone you swing at half your axe's {stats.power}. A Soloist axe fixes that."
                             if power < stats.power else "")))
        body.append(row(*stance_buttons(self._chop)))
        body.append(row(button("Grain notes", emoji="📖", on_click=self._notes), button("Leave", on_click=self._stop)))
        if wedges := await wedge_row(self):
            body.append(wedges)
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
        swing, note = await swing_at(self, foraging.swing_power(stats, tree.zone, reg.foraging), stance)
        applied = tree.chop(swing.damage, swing.effort)
        if swing.mark:
            tree.bonus = min(reg.foraging.chopping.mark_cap, tree.bonus + swing.mark)
        if tree.felled:
            self.reward = await foraging.fell_private(self.user, tree, self.rng)
            self.result = Result("TIMBER!", [reward_text(self.reward)], emoji="🌳", accent=0x4C8C4A, again=self._again,
                                 again_label="Another tree", back=self._stop, back_label="Back to foraging",
                                 actions=await releaf_actions(self, self.reward.drops, again=self._again, again_label="Another tree",
                                                              back=self._stop, back_label="Back to foraging"))
            return await self.refresh(interaction)
        await self.refresh(interaction, note)

    async def _notes(self, interaction: discord.Interaction) -> None:
        self.result = await notes_result(self.user)
        await self.refresh(interaction)

    async def _again(self, interaction: discord.Interaction) -> None:
        self.tree = await releaf.new_tree(self.user, self.tree.zone, self.rng)
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
        self.spot = foraging.Spot.pick(get_registry().foraging, self.rng, private=False)

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
                 f"{await spot_panel(self, power)}\n-# {status}"),
            row(*stance_buttons(self._chop)),
            row(button("Grain notes", emoji="📖", on_click=self._notes), button("Leave", on_click=self._back)),
        ]
        if wedges := await wedge_row(self):
            body.append(wedges)
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
        swing, note = await swing_at(self, foraging.swing_power(stats, zone, rules, community=True), stance)
        try:
            result = await foraging.chop_community(self.user, swing.damage, effort=swing.effort)
        except foraging.ForagingError:  # the tree is already down (or fell over): redraw, which collects what you are owed and shows it
            return await self.refresh(interaction)
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
        self.spot = foraging.Spot.pick(get_registry().foraging, self.rng, private=False)

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
            text(f"{await spot_panel(self, power)}\n-# {status}"),
            row(*stance_buttons(self._chop)),
            row(button("Grain notes", emoji="📖", on_click=self._notes), button("Leave", on_click=self._back)),
        ]
        if wedges := await wedge_row(self):
            body.append(wedges)
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
        swing, note = await swing_at(self, foraging.swing_power(stats, zone, rules, community=True), stance)
        try:
            result = await party_tree.chop(self.user, swing.damage, effort=swing.effort)
        except party_tree.PartyTreeError:  # a teammate felled it (or it fell over) while your panel was old: redraw, which collects and shows your rewards
            return await self.refresh(interaction)
        await self.refresh(interaction, "🌳 **You felled it!**" if result.felled_now else note)

    async def _notes(self, interaction: discord.Interaction) -> None:
        self.result = await notes_result(self.user)
        await self.refresh(interaction)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "forage")
