import random
import time
from collections import Counter

import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.screens.sellall import start_sell_all
from cococap.services import areas, foraging, party_tree, pets, releaf
from cococap.services.equipment import equipped_stats
from cococap.services.party import Party, xp_bonus
from cococap.services import odds
from cococap.ui.rewards import rewards_result
from cococap.ui.tabs import TabsScreen
from cococap.ui import Page, Result, Screen
from cococap.ui.components import bar, bits, button, row, sep, select, text, xp_bar
from cococap.user import User

def new_rng() -> random.Random:
    """Each chopping screen's dice (tests replace this to make good chops predictable)."""
    return random.Random()


def reward_headline(reward: foraging.Reward) -> str:
    what = f"{emojis.icon('tree', '🌳')} **TIMBER!**" if reward.felled else f"{emojis.icon('leaf', '🍂')} The tree fell over before it was finished."
    where = " (party tree)" if reward.party else " (community tree)" if reward.window is not None else ""
    return what + where


def rewards_page(rewards: list[foraging.Reward], title: str, **after) -> Result:
    """The shared reward screen for one or several trees: what you got in all, rare drops on pages of their own (their odds from the forest's tables)."""
    return rewards_result(
        title, items=sum((r.drops for r in rewards), Counter()), bits=sum(r.bits for r in rewards), xp=sum(r.xp for r in rewards),
        headline=[reward_headline(r) for r in rewards],
        odds=odds.foraging(), emoji=emojis.icon("tree", "🌳"), accent=0x2E7D32, **after)


async def spot_panel(screen, power: int) -> str:
    """Where you are chopping: the grain (its pull on your damage, less what the wear has taken, so it matches the swing number), how much of the spot is left and
    about how many chops that is, and what a chop in the right style does right now. The style the grain likes is NOT shown: it is in your Grain notes."""
    reg = get_registry()
    spot = screen.spot
    strength = spot.strength(reg.foraging) - 1
    quality = f" ({strength:+.0%})" if round(strength, 2) else ""
    left = max(0.0, 1 - spot.wear)
    stats = await equipped_stats(screen.user, "foraging")  # (no axe yet: the page still draws)
    chops = spot.chops_left(reg.foraging, stats.stats.get("wear_slow", 0.0) if stats else 0.0)
    wedges = sum(q for _, q in await foraging.wedges(screen.user))
    rules = reg.foraging.chopping
    streak = ""
    if rules.streak_max and spot.streak:  # (one short bit on the swing line: no warnings, no sentences)
        streak = f"  {emojis.icon('flame', '🔥')} **+{rules.streak_bonus * min(spot.streak, rules.streak_max):.0%}**" + (" max" if spot.streak >= rules.streak_max else "")
    return (f"{emojis.icon('wood', '🪵')} **{spot.title(reg.foraging)}** grain{quality}  \n{bar(left, 6, 'wear')} **{left:.0%}** left (about {chops} chops)   {emojis.icon('axe', '🪓')} **{spot.preview(power, reg.foraging)}** per swing{streak}"
            + (f"   ·   {emojis.icon('wedge', '🔩')} {wedges} wedge(s)" if wedges else "")
            + (f"\n{emojis.icon('wedge_gold', '🪚')} Wedge bonus: **{spot.boost:+.0%}** for **{spot.boost_chops}** more chops" if spot.boost_chops else ""))


async def notes_result(user) -> Result:
    """Your grain notes on a page of their own (it returns you to the tree you were chopping)."""
    lines = []
    for note in await foraging.grain_notes(user):
        g = note.grain
        if note.known:
            what = f"{foraging.STANCES[note.known][1]} {foraging.STANCES[note.known][0]}"
        elif note.ruled_out:
            what = f"{emojis.icon('unknown', '❔')} " + " ".join(f"{emojis.icon('cross', '✖️')}{foraging.STANCES[c][1]}" for c in note.ruled_out)
        else:
            what = emojis.icon("unknown", "❔")
        lines.append(f"**{g.name}** ({g.multiplier - 1:+.0%}, wears {'slowly' if g.wear < 0.95 else 'quickly' if g.wear > 1.05 else 'normally'}): {what}")
    return Result("Grain notes", [f"Every grain likes one chop style. Chop in any other and the swing glances off at half strength. {emojis.icon('cross', '✖️')} marks "
                                  "styles you have seen fail, so two crossed off give away the third. The spot you are chopping never "
                                  "tells you its style: remember it!", "\n".join(lines)],
                  emoji=emojis.icon("book", "📖"), accent=0x8D6E63, back_label="Back to chopping")


def swing_note(swing: foraging.Swing, stance: str | None = None, applied: int | None = None) -> str:
    dealt = swing.damage if applied is None else applied
    icon = foraging.STANCES[stance][1] if stance in foraging.STANCES else f"{emojis.icon('axe', '🪓')}"
    good = f"  {emojis.icon('star', '✨')} **Good chop!**" if swing.good else ""
    extra = f"  {emojis.icon('axe', '🪓')}{emojis.icon('axe', '🪓')} **Double chop!**" if swing.doubled else ""
    extra += {"damage": f"  {emojis.icon('gem', '💎')} **Heartwood: a huge hit!**", "xp": f"  {emojis.icon('star', '✨')} **Golden Knot: double xp!**",
              "mark": f"  {emojis.icon('page', '🏷️')} **Marked: +{swing.mark:.0%} rewards**"}.get(swing.special, "")
    if swing.correct is None:
        return (f"{emojis.icon('star', '✨')} **Good chop!** {dealt}" if swing.good else f"{emojis.icon('axe', '🪓')} {dealt}") + extra
    verdict = emojis.icon('check', '✅') if swing.correct else f"{emojis.icon('cross', '❌')} glanced off"
    return f"{verdict} {icon}  ·  {dealt}{good}{extra}"


def species_label(species_id: str) -> str:
    """"🌳 Oak" for a species id, or "" (no species)."""
    sp = get_registry().foraging.species_of(species_id)
    return f"{sp.emoji} {sp.name}" if sp else ""


def tree_title(base: str, species_id: str) -> str:
    """The page title of a tree: "🌿 Birch Tree", "🌳 Oak Community Tree"..."""
    label = species_label(species_id)
    return f"{label} {base}" if label else base


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
            note = f" Your next **{screen.spot.boost_chops}** chops hit **{screen.spot.boost:+.0%}** harder." if screen.spot.boost_chops else ""
            await screen.refresh(interaction, f"{emojis.icon('wedge_gold', '🪚')} You drive a wedge in: new spot, **{screen.spot.title(reg.foraging)}** grain.{note}")

        return go

    return row(*(button(f"{reg.item(w.item).name} ×{q}", emoji=emojis.icon("wedge", "🔩"), on_click=use(w.item)) for w, q in held))


async def swing_at(screen: Screen, power: int, stance: str, tree_key: object, species: str = "") -> tuple[foraging.Swing, str]:
    """Swing in a style on this screen's spot. Writes down what you found out about the grain (the right style is remembered, a wrong
    one is crossed off) and wears the spot. Returns the swing and what to tell the player about it."""
    reg = get_registry()
    rules = reg.foraging
    stats = await foraging.axe_stats(screen.user)
    grain, name = screen.spot.grain, screen.spot.name
    screen.spot.on_tree(tree_key)  # (a new tree starts the right-style streak over)
    pet = await pets.bonuses(screen.user)
    swing = screen.spot.swing(power, rules, screen.rng, stats.stats.get("good_chop", 0.0) + pet.get("good_chop", 0.0), stance,
                              stats.stats.get("wear_slow", 0.0), stats.stats.get("double_chop", 0.0), stats.stats.get("clean_cut", 0.0))
    note = swing_note(swing, stance)
    if swing.correct is not None and await foraging.note_style(screen.user, grain, stance, swing.correct):
        note += (f"  {emojis.icon('book', '📖')} Learned: the **{name}** grain likes **{foraging.STANCES[stance][0]}**!" if swing.correct
                 else f"  {emojis.icon('cross', '✖️')} {foraging.STANCES[stance][0]} crossed off the **{name}** grain in your notes")
    shaken = await foraging.shake(screen.user, stats.stats.get("shake", 0.0), screen.rng) + await foraging.windfall(screen.user, int(stats.stats.get("windfall", 0)), screen.rng, grain_done=swing.clean_grain, species=species)
    if shaken:
        note += f"  {emojis.icon('leaf', '🍃')} Shook loose " + ", ".join(f"{q:,} {reg.item(i).name}" for i, q in shaken.items()) + "!"
    if swing.ended:
        note += f"\n{emojis.icon('wood', '🪵')} The spot wore out. New spot: **{screen.spot.title(rules)}** grain"
    return swing, note


async def collect_community_rewards(screen: Screen) -> None:
    """Pay out anything this player is owed from finished community trees and tell them."""
    rewards = await foraging.claim_rewards(screen.user) + await party_tree.claim(screen.user)
    if rewards:
        title = "The tree is down!" if any(r.party for r in rewards) and not any(not r.party for r in rewards) else "The community tree is down!"
        screen.result = rewards_page(rewards, title, back_label="Continue")


class ForageScreen(Screen):
    id = "forage"
    label = "Foraging"
    emoji = emojis.Lazy("ui_tree", "🌳")
    description = "Chop trees alone or join the community tree"
    links = ("trees", "mastery", "releaf")

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
        # the forests you can chop: unlocked by level AND by area (a forest's number is its zone)
        forests = await areas.open_location_list(self.user, "foraging", reg)
        zones = [loc.n for loc in forests]
        if self.zone not in zones:
            self.zone = zones[-1]  # an unknown or closed forest falls back to the highest open one
        here_forest = forests[zones.index(self.zone)]
        stats = await equipped_stats(self.user, "foraging")
        overflow, needed = User.xp_for_next_level(skill.xp)

        header = f"**Level {level}**  {xp_bar(overflow / needed if needed else 0)}  {overflow:,}/{needed:,} xp"
        if bonus := await xp_bonus(self.user.id):
            header += f"\n{emojis.icon('people', '👥')} Party bonus: **+{bonus:.0%}** xp"
        body = [*self.note_block(), text(header)]

        if stats is None:
            body.append(text(f"{emojis.icon('axe', '🪓')} You need an axe. Claim your free **Starter Axe** on the Tools page."))
        else:
            body.append(text(f"{emojis.icon('axe', '🪓')} Axe power **{stats.power}**" + (f"  ·  {emojis.icon('star', '✨')} Soloist" if stats.has("soloist") else "")))
        if (found := await releaf.foundation()).bloom_active:
            body.append(text(f"{emojis.icon('flower', '🌸')} **Bloom** is up for everyone: **+{get_registry().foraging.releaf.bloom_xp:.0%}** foraging xp and **+{get_registry().foraging.releaf.bloom_drops:.0%}** drop chances, "
                             f"ends <t:{int(found.bloom_until)}:R>"))
        body.append(sep())

        # the community tree
        view = await foraging.community_tree(self.user)
        now = time.time()
        if view is not None and view.standing:
            line = (f"### {emojis.icon('tree', '🌲')} Community tree: {species_label(view.species) or 'forest ' + str(view.zone)}  ·  forest {view.zone}\n{bar(view.fraction_left, 10, 'hp')}  **{view.hp:,}**/{view.max_hp:,} hp  ·  "
                    f"**{view.choppers}** chopping  ·  falls over <t:{int(view.closes_at)}:R>")
            if view.yours:
                line += f"\nYou have chopped **{view.share:.0%}** of it."
            body.append(text(line))
            body.append(row(button("Join the community tree", emoji=emojis.icon("tree", "🌳"), style=discord.ButtonStyle.success,
                                   disabled=stats is None, on_click=self._join)))
        else:
            ended = ("It was felled!" if view is not None and view.status == "felled" else "No tree is standing.")
            body.append(text(f"### {emojis.icon('tree', '🌲')} Community tree\n{ended} The next one grows <t:{int(foraging.next_tree_at(now))}:R>."))

        # a tree for your party
        body += await self._party_section(stats)

        # a private tree
        body.append(sep())
        heavy = foraging.is_heavy(self.zone, rules) and not (stats and stats.has("soloist"))
        here = ", ".join(f"{sp.emoji} {sp.name}" for sp in rules.species_in(self.zone))
        private = f"### {emojis.icon('wood', '🪵')} A tree of your own\n{here_forest.emoji} **{here_forest.name}**  ·  forest {self.zone}" + (f"  ·  {here}" if here else "") + (
            "  ·  heavy: you swing at half power alone" if heavy else "")
        if (hint := await areas.next_location_hint(self.user, "foraging", reg)) is not None:
            private += f"\n-# Next forest: {hint}."
        body.append(text(private))
        if len(forests) > 1:
            body.append(row(select(
                "Where to chop...",
                [discord.SelectOption(label=loc.name, value=str(loc.n), emoji=loc.emoji, default=loc.n == self.zone,
                                      description=f"Forest {loc.n}" + (" · heavy trees" if foraging.is_heavy(loc.n, rules) else ""))
                 for loc in forests],
                self._pick_zone,
            )))
        body.append(row(button("Chop a tree", emoji=emojis.icon("axe", "🪓"), style=discord.ButtonStyle.primary, disabled=stats is None,
                               on_click=self._chop),
                        button("Grain notes", emoji=emojis.icon("book", "📖"), on_click=self._notes),
                        button("Mastery", emoji=emojis.icon("star", "🌟"), on_click=self._mastery),
                        button("Sell all", emoji=emojis.icon("sell", "💰"), on_click=self._sell_all),
                        *([button("Releaf Foundation", emoji=emojis.icon("sprout", "🌱"), on_click=self._releaf)] if level >= rules.releaf.min_level else [])))
        return Page("Foraging", body, accent=0x4C8C4A)

    async def _party_section(self, stats) -> list:
        party = await Party.for_user(self.user.id)
        self.watching_party = party is not None and party.member_count() >= 2
        if party is None or party.member_count() < 2:
            return [text(f"-# {emojis.icon('people', '👥')} In a party you can start a **party tree** (pays better).")]
        pt = await party_tree.view(self.user)
        bonus = get_registry().foraging.party_tree
        if pt is not None and pt.standing:
            line = (f"### {emojis.icon('people', '👥')} Party tree: {species_label(pt.species) or 'forest ' + str(pt.zone)}  ·  forest {pt.zone}\n{bar(pt.fraction_left, 10, 'hp')}  **{pt.hp:,}**/{pt.max_hp:,} hp  ·  "
                    f"**{len(pt.chops)}** chopping  ·  falls over <t:{int(pt.closes_at)}:R>")
            return [text(line), row(button("Join the party tree", emoji=emojis.icon("people", "👥"), style=discord.ButtonStyle.success,
                                          disabled=stats is None, on_click=self._join_party))]
        best = await party_tree.unlocked_zone(party)
        zone = min(self.zone or 1, best)
        return [text(f"### {emojis.icon('people', '👥')} Party tree\nNo tree is up. Start one for your party of **{party.member_count()}**: **forest {zone}**, "
                     f"up to **+{bonus.max_group_bonus:.0%}** reward for working together.\n-# The whole party needs an axe and the forest unlocked."),
                row(button("Start a party tree", emoji=emojis.icon("people", "👥"), style=discord.ButtonStyle.primary, disabled=stats is None,
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
        await self.go(interaction, "trees", tab="party")

    async def _releaf(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "releaf")

    async def _join_party(self, interaction: discord.Interaction) -> None:
        await foraging.axe_stats(self.user)
        await self.go(interaction, "trees", tab="party")

    async def _pick_zone(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.zone = int(values[0])
        await self.refresh(interaction)

    async def _chop(self, interaction: discord.Interaction) -> None:
        await foraging.axe_stats(self.user)
        tree = foraging.roll_tree(self.zone, random.Random(), get_registry().foraging)
        await self.go(interaction, "trees", tab="own", tree=tree)

    async def _join(self, interaction: discord.Interaction) -> None:
        await foraging.axe_stats(self.user)
        await self.go(interaction, "trees", tab="grove")


class TreeScreen(Screen):
    """A private tree: chop it down on your own."""

    label = "Tree"
    emoji = f"{emojis.icon('tree', '🌳')}"
    description = "Your own tree"

    def __init__(self, nav):
        super().__init__(nav)
        self.tree: foraging.Tree | None = None
        self.reward: foraging.Reward | None = None
        self.rng = new_rng()
        self.spot = foraging.Spot.pick(get_registry().foraging, self.rng)

    @property
    def locked(self) -> bool:
        return True  # the page has its own Leave button (nothing is half-done: chops are paid as they land)

    @property
    def hides_nav(self) -> bool:
        return True

    async def build(self) -> Page:
        rules = get_registry().foraging
        tree = self.tree
        if tree is None:
            return Page("Tree", [text("Pick a forest on the Foraging page and chop a tree.")], accent=0x4C8C4A)
        stats = await foraging.axe_stats(self.user)
        power = foraging.swing_power(stats, tree.zone, rules)
        self.spot.on_tree(id(tree))  # (a new tree starts the right-style streak over before the panel draws it)
        body = [*self.note_block()]
        body.append(text(f"**Forest {tree.zone}**{self._species_line(tree.species)}\n{bar(tree.hp / tree.max_hp, 10, 'hp')}  **{tree.hp:,}**/{tree.max_hp:,} hp"
                         f"\n{await spot_panel(self, power)}" + (f"\n{emojis.icon('page', '🏷️')} Marked: **+{tree.bonus:.0%}** drops when it falls" if tree.bonus else "") + (
                             f"\n-# Heavy tree: alone you swing at half your axe's {stats.power}. A Soloist axe fixes that."
                             if power < stats.power else "")))
        body.append(row(*stance_buttons(self._chop)))
        body.append(row(button("Grain notes", emoji=emojis.icon("book", "📖"), on_click=self._notes), button("Leave", on_click=self._stop)))
        if wedges := await wedge_row(self):
            body.append(wedges)
        return Page(tree_title("Tree", tree.species), body, accent=0x4C8C4A)

    @staticmethod
    def _species_line(species_id: str) -> str:
        return f"  ·  {species_label(species_id)}" if species_label(species_id) else ""

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
        swing, note = await swing_at(self, foraging.swing_power(stats, tree.zone, reg.foraging), stance, id(tree), tree.species)
        applied = tree.chop(swing.damage, swing.effort)
        if swing.mark:
            tree.bonus = min(reg.foraging.chopping.mark_cap, tree.bonus + swing.mark)
        if tree.felled:
            self.reward = await foraging.fell_private(self.user, tree, self.rng)
            self.result = rewards_page([self.reward], "TIMBER!", again=self._again, again_label="Another tree", back=self._stop, back_label="Back to foraging")
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

    label = "Community Tree"
    emoji = f"{emojis.icon('tree', '🌲')}"
    description = "Chop the hourly tree together"

    def __init__(self, nav):
        super().__init__(nav)
        self.refresh_every = get_registry().foraging.community.refresh_seconds
        self.rng = new_rng()
        self.spot = foraging.Spot.pick(get_registry().foraging, self.rng, private=False)

    @property
    def locked(self) -> bool:
        return True  # the page has its own Leave button (nothing is half-done: chops are paid as they land)

    @property
    def hides_nav(self) -> bool:
        return True

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.foraging
        await collect_community_rewards(self)
        view = await foraging.community_tree(self.user)
        body = [*self.note_block()]
        if view is None or not view.standing:
            ended = {"felled": f"{emojis.icon('tree', '🌳')} The tree has been felled! Thank you, everyone.",
                     "expired": f"{emojis.icon('leaf', '🍂')} The tree fell over before it was finished."}.get(view.status if view else "", "No tree is standing.")
            body += [text(f"{ended}\nThe next one grows <t:{int(foraging.next_tree_at(time.time()))}:R>."),
                     row(button("Back to foraging", on_click=self._back))]
            return Page("Community Tree", body, accent=0x2E7D32)

        need = rules.community.min_share
        status = f"{emojis.icon('check', '✅')} you qualify for drops" if view.share >= need else f"keep going: **{need:.0%}** of the tree qualifies you for drops"
        if view.share >= rules.community.max_share:
            status = f"{emojis.icon('check', '✅')} max: you are paid for {rules.community.max_share:.0%} of the tree"
        stats = await equipped_stats(self.user, "foraging")
        power = foraging.swing_power(stats, view.zone, rules, community=True) if stats else 1
        self.spot.on_tree(("shared", view.closes_at))
        medals = (emojis.icon("medal_gold", "🥇"), emojis.icon("medal_silver", "🥈"), emojis.icon("medal_bronze", "🥉"))
        top = [f"{medals[i]} {await self.nav.name_of(uid)}{' (you)' if uid == self.user.id else ''}: **{damage:,}** hp ({damage / view.max_hp:.0%})"
               for i, (uid, damage) in enumerate(view.top)]
        body += [
            text(f"**Forest {view.zone}**{TreeScreen._species_line(view.species)}  ·  falls over <t:{int(view.closes_at)}:R>\n"
                 f"{bar(view.fraction_left, 10, 'hp')}  **{view.hp:,}**/{view.max_hp:,} hp\n"
                 f"**{view.choppers}** chopper(s)" + ("\n" + "\n".join(top) if top else "")),
            text(f"You: **{view.yours:,}** hp  ·  **{view.share:.1%}** of the tree\n"
                 f"{await spot_panel(self, power)}\n-# {status}"),
            row(*stance_buttons(self._chop)),
            row(button("Grain notes", emoji=emojis.icon("book", "📖"), on_click=self._notes), button("Leave", on_click=self._back)),
        ]
        if wedges := await wedge_row(self):
            body.append(wedges)
        return Page(tree_title("Community Tree", view.species), body, accent=0x2E7D32)

    def _chop(self, stance: str):
        async def chop(interaction: discord.Interaction) -> None:
            await self._swing(interaction, stance)

        return chop

    async def _swing(self, interaction: discord.Interaction, stance: str) -> None:
        stats = await foraging.axe_stats(self.user)
        rules = get_registry().foraging
        view = await foraging.community_tree(self.user)
        zone = view.zone if view else 1
        swing, note = await swing_at(self, foraging.swing_power(stats, zone, rules, community=True), stance, ("shared", view.closes_at if view else 0), view.species if view else "")
        try:
            result = await foraging.chop_community(self.user, swing.damage, effort=swing.effort)
        except foraging.ForagingError:  # the tree is already down (or fell over): redraw, which collects what you are owed and shows it
            return await self.refresh(interaction)
        await self.refresh(interaction, f"{emojis.icon('tree', '🌳')} **You felled it!**" if result.felled_now else note)

    async def _notes(self, interaction: discord.Interaction) -> None:
        self.result = await notes_result(self.user)
        await self.refresh(interaction)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "forage")


class PartyGroveScreen(Screen):
    """Your party's tree: only members can chop it, everyone's chops add up, and it pays a little better for teamwork."""

    label = "Party Tree"
    emoji = f"{emojis.icon('people', '👥')}"
    description = "Chop your party's tree together"

    def __init__(self, nav):
        super().__init__(nav)
        self.refresh_every = get_registry().foraging.party_tree.refresh_seconds
        self.rng = new_rng()
        self.spot = foraging.Spot.pick(get_registry().foraging, self.rng, private=False)

    @property
    def locked(self) -> bool:
        return True  # the page has its own Leave button (nothing is half-done: chops are paid as they land)

    @property
    def hides_nav(self) -> bool:
        return True

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.foraging
        await collect_community_rewards(self)
        view = await party_tree.view(self.user)
        body = [*self.note_block()]
        if view is None or not view.standing:
            ended = {"felled": f"{emojis.icon('tree', '🌳')} Your party felled it! Well chopped, team.",
                     "expired": f"{emojis.icon('leaf', '🍂')} The tree fell over before it was finished."}.get(view.status if view else "", "Your party has no tree standing.")
            body += [text(ended), row(button("Back to foraging", on_click=self._back))]
            return Page("Party Tree", body, accent=0x1F8A70)
        need = rules.party_tree.min_share
        status = f"{emojis.icon('check', '✅')} you qualify for drops" if view.share >= need else f"keep going: **{need:.0%}** of the tree qualifies you for drops"
        stats = await equipped_stats(self.user, "foraging")
        power = foraging.swing_power(stats, view.zone, rules, community=True) if stats else 1
        self.spot.on_tree(("shared", view.closes_at))
        team = []
        for uid, damage in sorted(view.chops.items(), key=lambda kv: -kv[1]):
            team.append(f"{await self.nav.name_of(uid)}{' (you)' if uid == self.user.id else ''}: **{damage:,}** hp ({damage / view.max_hp:.0%})")
        body += [
            text(f"**Forest {view.zone}**{TreeScreen._species_line(view.species)}  ·  falls over <t:{int(view.closes_at)}:R>\n"
                 f"{bar(view.fraction_left, 10, 'hp')}  **{view.hp:,}**/{view.max_hp:,} hp\n" + ("\n".join(team) if team else "Nobody has chopped yet.")),
            text(f"{await spot_panel(self, power)}\n-# {status}"),
            row(*stance_buttons(self._chop)),
            row(button("Grain notes", emoji=emojis.icon("book", "📖"), on_click=self._notes), button("Leave", on_click=self._back)),
        ]
        if wedges := await wedge_row(self):
            body.append(wedges)
        return Page(tree_title("Party Tree", view.species), body, accent=0x1F8A70)

    def _chop(self, stance: str):
        async def chop(interaction: discord.Interaction) -> None:
            await self._swing(interaction, stance)

        return chop

    async def _swing(self, interaction: discord.Interaction, stance: str) -> None:
        stats = await foraging.axe_stats(self.user)
        rules = get_registry().foraging
        view = await party_tree.view(self.user)
        zone = view.zone if view else 1
        swing, note = await swing_at(self, foraging.swing_power(stats, zone, rules, community=True), stance, ("shared", view.closes_at if view else 0), view.species if view else "")
        try:
            result = await party_tree.chop(self.user, swing.damage, effort=swing.effort)
        except party_tree.PartyTreeError:  # a teammate felled it (or it fell over) while your panel was old: redraw, which collects and shows your rewards
            return await self.refresh(interaction)
        await self.refresh(interaction, f"{emojis.icon('tree', '🌳')} **You felled it!**" if result.felled_now else note)

    async def _notes(self, interaction: discord.Interaction) -> None:
        self.result = await notes_result(self.user)
        await self.refresh(interaction)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "forage")


class TreesScreen(TabsScreen):
    """Trees: your own tree, the community tree and your party's tree, as tabs of one page."""

    id = "trees"
    label = "Trees"
    emoji = emojis.Lazy("ui_tree", "🌳")
    description = "Chop your own tree, the community tree or your party's tree"
    links = ("forage",)
    panes = {"own": TreeScreen, "grove": GroveScreen, "party": PartyGroveScreen}
