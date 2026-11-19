import datetime
import math
import random
import time
from collections import Counter

import discord

from cococap import emojis
from cococap.constants import Rarities
from cococap.registry import get_registry
from cococap.services import areas, fishing, fishing_community, party_boss, pets, pots, smithing
from cococap.services.equipment import equipped_stats
from cococap.services.party import xp_bonus
from cococap.services import odds
from cococap.ui.rewards import rewards_result
from cococap.ui import Page, PromptModal, Result, Screen
from cococap.ui.tabs import TabsScreen
from cococap.ui.components import bar, bits, button, needs_text, row, select, sep, text, xp_bar
from cococap.user import User

ROD = emojis.icon('rod', '🎣')
ACCENT = 0x2E86C1
REFRESH = 1.5  # seconds between redraws while a line is in the water (a bite only lasts a few seconds)


def new_rng() -> random.Random:
    """Each fishing screen's dice (tests replace this to make the catch predictable)."""
    return random.Random()


def now() -> float:
    """The clock (tests replace this to skip the waiting)."""
    return time.time()


def clicked_at(interaction: discord.Interaction) -> float:
    """When the player actually clicked (Discord stamps every interaction), unless that is later than our own clock.
    If the bot or the connection lagged, the click still counts as made on time."""
    stamp = getattr(interaction, "created_at", None)
    if isinstance(stamp, datetime.datetime):
        return min(now(), stamp.timestamp())
    return now()


def pattern_line(cast: fishing.Cast, rules=None) -> str:
    """The next few steps (a Reel step looks like an ordinary arrow until you reach it, then it turns into 🌀). What is done
    is a tick count; the next step is bold. A "reverse" boss is read from the right."""
    reel = (rules or get_registry().fishing).reel
    window = reel.fog_window if "fog" in cast.modifiers else reel.window
    end = min(len(cast.pattern), cast.progress + window)
    steps = [cast.display(i) for i in range(cast.progress, end)]
    more, done = len(cast.pattern) - end, emojis.icon('check', '✅') * cast.progress
    if not steps:
        return done
    if "reverse" in cast.modifiers:
        return " ".join(filter(None, [f"… +{more}" if more else "", *reversed(steps[1:]), f"**{steps[0]}**", done]))
    return " ".join(filter(None, [done, f"**{steps[0]}**", *steps[1:], f"… +{more}" if more else ""]))


def reel_buttons(cast: fishing.Cast, rng, handler, style) -> list[discord.ui.Button]:
    """Left, Right and Reel (and Let it go). A "shuffle" boss moves them around every step."""
    buttons = [button("Left", emoji=emojis.icon('prev', '◀️'), style=style, on_click=handler(fishing.LEFT)),
               button("Right", emoji=emojis.icon('next', '▶️'), style=style, on_click=handler(fishing.RIGHT)),
               button("Reel", emoji=fishing.REEL, style=discord.ButtonStyle.success, on_click=handler(fishing.REEL))]
    if "shuffle" in cast.modifiers:
        rng.shuffle(buttons)
    return buttons


def quest_line(q: fishing.Quest) -> str:
    mark = emojis.icon('check', '✅') if q.done else emojis.icon('sq_white', '⬜')
    progress = "done" if q.done else f"{q.progress}/{q.count}"
    return f"{mark} {q.text}  ·  {progress}  ·  +{emojis.bits(q.bits)}, +{q.xp} xp"


class FishScreen(Screen):
    id = "fish"
    label = "Fishing"
    emoji = ROD
    description = "Cast a line and reel in fish"
    links = ("fishlog", "fishpots", "mastery", "radar")

    def __init__(self, nav):
        super().__init__(nav)
        self.cast: fishing.Cast | None = None
        self.flash: tuple[str, float] | None = None  # (the hallucination's numbers, when they fade)
        self.water: str | None = None  # where you are fishing (None = the best water you have opened)
        self.offer: tuple[float, object] | None = None  # a Double Hook's Quick cast on the result page: (when the offer ends, the water)
        self.missed: fishing.Cast | None = None  # a fish written off as too slow, which a late-arriving click can still save
        self.watching = False  # your party has a boss fight open: the page redraws by itself so it shows up and ends
        self.rng = new_rng()

    @property
    def locked(self) -> bool:
        return self.cast is not None  # a line in the water has its own Cancel / Let it go

    @property
    def hides_nav(self) -> bool:
        return self.cast is not None

    async def on_abandon(self) -> None:
        """The hub timed out with a line in the water: cancel it the way "Let it go" does (a party boss cast reports failed)."""
        cast, self.cast = self.cast, None
        if cast is not None and cast.party_fight is not None:
            await party_boss.report(self.user, "failed", 0, now())

    @property
    def refresh_every(self) -> float | None:  # redraw by itself while a line is in the water or numbers are flashing, or a party fight is open
        if self.cast is not None and self.flash is None and self.cast.status(now()) in ("chest", "reeling"):
            return None  # nothing on these pages changes by itself: redrawing would only swap the buttons' ids under a player who is thinking
        return REFRESH if self.cast is not None or self.flash is not None or self.watching else None

    async def build(self) -> Page:
        reg = get_registry()
        cast = self.cast
        if cast is not None and cast.status(now()) == "escaped":
            if cast.timed_out:
                self.missed = cast  # kept for a moment: a click made in time may still be on its way
            self.cast, cast = None, None  # nobody picked up the line in time
            await fishing.lose_streak(self.user)
            self.result = self._lost(f"{emojis.icon('wave', '🌊')} Too slow!", ["It bit, but nobody pulled up the line in time. The fish got away."])
        if self.flash is not None and now() >= self.flash[1]:
            self.flash = None  # the numbers have faded
            extra = f"{emojis.icon('mist', '🌫️')} The numbers slip away… hold on to what you remember."
            self.note = f"{self.note}\n{extra}" if self.note else extra
        stats = await equipped_stats(self.user, "fishing")
        body = [*self.note_block()]
        fight = None
        if cast is None:
            await self._collect_party_boss()  # a finished fight pays you, and the page says so
            fight = await party_boss.view(self.user, now())
        self.watching = fight is not None and fight.is_open
        if self.flash is not None:
            digits = "   ".join(self.flash[0])
            body.append(text(f"### {emojis.icon('swirl', '🌀')} The waves of the ocean… the heat of the sun… sirens in the distance, singing…\n"
                             f"# {digits}\n-# Remember them! They fade in a few seconds."))

        if cast is None:
            skill = await self.user.skill("fishing")
            overflow, needed = User.xp_for_next_level(skill.xp)
            header = f"**Level {User.xp_to_level(skill.xp)}**  {xp_bar(overflow / needed if needed else 0)}  {overflow:,}/{needed:,} xp"
            if bonus := await xp_bonus(self.user.id):
                header += f"\n{emojis.icon('group', '👥')} Party bonus: **+{bonus:.0%}** xp"
            body.append(text(header))
            if fight is not None and fight.is_open:
                if fight.you is None:
                    whose = "your party's" if fight.own else "a player's"
                    body += [text(f"### {emojis.icon('boss', '💀')} **{fight.boss}** is on {whose} line!\n**{fight.reeling}** reeling · closes <t:{int(fight.closes_at)}:R>\n"
                                  "-# Join with your own set of arrows. Everyone who lands theirs is paid, and more for every teammate who does too."),
                             row(button("Join the fight", emoji=emojis.icon("boss", "💀"), style=discord.ButtonStyle.danger, disabled=stats is None, on_click=self._join_boss(fight.host if not fight.own else None)))]
                elif fight.you == "done":
                    body.append(text(f"### {emojis.icon('check', '✅')} You landed your part of the fight with **{fight.boss}**\n**{fight.reeling}** still reeling · closes <t:{int(fight.closes_at)}:R>"))
            if stats is None:
                body.append(text(f"{emojis.icon('rod', '🎣')} You need a rod. Claim your free **Starter Rod** on the Tools page."))
            else:
                slips = fishing.slips_allowed(stats.power, reg.fishing, stats.stats.get("slips", 0))
                wait = fishing.typical_wait(stats.power, reg.fishing, stats.stats.get("bite_speed", 0.0))
                body.append(text(f"{ROD} Rod **{stats.power}**"
                                 + (f"  ·  bites in ~**{wait:.0f}s**" if self.user.settings.fishing_estimate else "")
                                 + (f"  ·  forgives **{slips}** slip(s)" if slips else "")))
            level = User.xp_to_level(skill.xp)
            open_waters = await fishing.open_waters(self.user, reg)
            if self.water is None:
                self.water = self.user.settings.zones.get("fishing")  # where you last set it
            if self.water not in {w.id for w in open_waters}:
                self.water = open_waters[-1].id  # a closed or unknown water falls back to the newest one you can fish
            here = fishing.water_by_id(reg, self.water)
            body.append(text(f"{here.emoji} **{here.name}**" + (f"  ·  {here.description}" if len(open_waters) == 1 else "")))  # (with a menu, it says what each water is like)
            if len(open_waters) > 1:
                body.append(row(select("Where to fish...", [
                    discord.SelectOption(label=w.name, value=w.id, emoji=w.emoji, default=w.id == self.water,
                                         description=w.description[:100]) for w in open_waters], self._pick_water)))
            if (hint := await areas.next_location_hint(self.user, "fishing", reg)) is not None:
                body.append(text(f"-# Next water: {hint}."))
            if await fishing.chests_possible(self.user, now()):
                body.append(text(f"-# {emojis.icon('swirl', '🌀')} The hallucination lingers… something shiny may be down there."))
            haul = await fishing.stock(self.user)
            level = User.xp_to_level(skill.xp)
            quests = await fishing.quests(self.user, now())
            body.append(sep())
            if quests:
                daily = [q for q in quests if q.kind == "daily"]
                body.append(text(f"{emojis.icon('quest', '📜')} Quests: **{sum(q.done for q in daily)}/{len(daily)}** daily  ·  "
                                 f"**{sum(q.done for q in quests if q.kind == 'weekly')}/1** weekly"))
            else:
                body.append(text(f"-# {emojis.icon('quest', '📜')} Quests unlock at fishing level {reg.fishing.quests.min_level}."))
            body.append(text(f"{emojis.icon('basket', '🧺')} **{haul.count:,}** fish  ·  worth **{emojis.bits(haul.worth)}**" if haul.count else f"{emojis.icon('haul', '🧺')} No fish yet."))
            body.append(row(
                button("Cast", emoji=emojis.icon("cast", "🎣"), style=discord.ButtonStyle.primary, disabled=stats is None, on_click=self._cast),
                button("Collection", emoji=emojis.icon('book', '📖'), disabled=not (fishing.quests_unlocked(level, reg.fishing) or fishing.book_unlocked(level, reg.fishing)),
                       on_click=self._collection),
            ))
            body.append(row(button("Crab pots", emoji=emojis.icon("crab", "🦀"), disabled=level < reg.fishing.pots.min_level, on_click=self._pots),
                            button("Mastery", emoji=emojis.icon("star", "🌟"), on_click=self._mastery)))
            body.append(row(button("Radar", emoji=emojis.icon('radar', '📡'), disabled=level < reg.fishing.radar.unlock_level, on_click=self._radar)))
            if stats is not None and stats.stats.get("net_cast", 0.0) > 0:  # the Net Cast enchant shows its button
                left = await fishing.net_ready_in(self.user)
                label = "Net" if left <= 0 else f"Net ready in {math.ceil(left / 60)}m"
                body.append(row(button(label, emoji=emojis.icon("net", "🥅"), disabled=left > 0, on_click=self._net)))
            return Page("Fishing", body, accent=ACCENT)

        status = cast.status(now())
        if status == "waiting":
            body += [text(f"### {emojis.icon('bobber', '🎣')} The line is in the water…\n" + await self._wait_estimate()),
                     row(button("Cancel cast", on_click=self._cancel))]
            return Page("Fishing", body, accent=ACCENT)

        if status == "bite":
            body += [text(f"### {emojis.icon('warn', '❗')} A bite!\nPull up the line, quick! It gets away <t:{int(cast.expires_at) + 1}:R>"),
                     row(button("Pull up the line", emoji=ROD, style=discord.ButtonStyle.danger, on_click=self._hook))]
            return Page("Fishing", body, accent=0xE74C3C)

        if status == "chest":
            t = reg.fishing.treasure
            body += [text(f"### {emojis.ui('chest', '🧰')} A treasure chest!\nIt is locked with **{t.code_length}** numbers. Do you remember them?\n"
                          f"Tries left: **{cast.attempts_left}**"),
                     row(button("Enter the numbers", emoji=emojis.icon("key", "🔑"), style=discord.ButtonStyle.success, on_click=self._enter_code),
                         button("Leave it", on_click=self._cancel))]
            return Page("Fishing", body, accent=0xF1C40F)

        rules = reg.fishing
        slack = (f"\n{emojis.ui('hook', '🪝')} Slack left: **{cast.slips_left}**  ·  each one unused pays a bonus" if cast.slips_left else "")
        arrows = sum(t != fishing.REEL for t in cast.pattern)
        if cast.boss:
            twists = "\n".join(rules.boss.modifier_text[m] for m in cast.modifiers)
            body += [
                text(f"### {emojis.icon('boss', '💀')} **{cast.boss}** is on the line!\nA boss! No fish this time, but a mountain of loot if you land it.\n{twists}"
                     + (f"\n{emojis.icon('group', '👥')} **Party fight:** you reel your own set of arrows, and everyone who lands theirs is paid." if cast.party_fight is not None else "") + "\n"
                     f"{pattern_line(cast, rules)}{slack}\n-# {arrows} arrows, and some of them turn into **Reel** when you get there. Don't slip!"),
                row(*reel_buttons(cast, self.rng, self._press, discord.ButtonStyle.danger), button("Let it go", on_click=self._cancel)),
            ]
            if cast.hooked and not cast.public:
                body.append(row(button("Open to others", emoji=emojis.icon("group", "👥"), on_click=self._open_boss)))
            return Page("Fishing", body, accent=0x7B241C)

        # reeling it in: you can see what kind of fish it is now, so you can use what you have learned about it
        colour = Rarities.from_value(cast.fish.rarity)
        body += [
            text(f"### {emojis.icon('rod', '🎣')} A {cast.fish.display} is on the line!  ·  **{colour.rarity_name}**\n{pattern_line(cast, rules)}{slack}\n"
                 f"-# {emojis.icon('prev', '◄')} {emojis.icon('next', '►')} are the arrows. A step can turn into {emojis.icon('swirl', '🌀')} as you reach it: press **Reel**"
                 + (f", and {emojis.icon('unknown', '❓')} is hidden: it follows this fish's own pattern. Check your field notes!"
                    if fishing.MYSTERY in cast.pattern else ".")),
            row(*reel_buttons(cast, self.rng, self._press, discord.ButtonStyle.primary), button("Let it go", on_click=self._cancel)),
            row(button("Field notes", emoji=emojis.icon('search', '🔍'), on_click=self._reel_notes)),
        ]
        return Page("Fishing", body, accent=int(colour.color, 16))

    async def _wait_estimate(self) -> str:
        """About how long a bite takes with YOUR rod here, next to a starter rod's, so an upgrade is something you can feel."""
        reg = get_registry()
        rules = reg.fishing
        stats = await fishing.rod_stats(self.user)
        water = fishing.water_by_id(reg, self.water) if self.water else None
        scale = water.wait_multiplier if water else 1.0
        bite = stats.stats.get("bite_speed", 0.0) + (await pets.bonuses(self.user)).get("bite_speed", 0.0)
        mine = fishing.typical_wait(stats.power, rules, bite) * scale
        starter = fishing.typical_wait(reg.item("tool_rod_starter").tool.power, rules) * scale
        line = f"{emojis.icon('timer', '⏱️')} A bite in about **{mine:.0f}s**"
        return line + (f"  ·  a starter rod: {starter:.0f}s" if round(starter) != round(mine) else "")

    # ---- what happened ---------------------------------------------------------------------------
    def _lost(self, title: str, lines: list[str]) -> Result:
        return Result(title, lines + ["Nothing was lost but the fish. Try again!"], emoji=emojis.icon('wave', '🌊'), accent=0x5D6D7E,
                      again=self._cast, again_label="Cast again")

    @staticmethod
    def _tell_lines(reveals) -> list[str]:
        """What each ❓ turned out to be: written in your field notes, and shown here so you can start working it out."""
        return [f"{emojis.icon('search', '🔍')} The {emojis.icon('unknown', '❓')} was **{truth}** (the arrow before it was {before}; {emojis.icon('swirl', '🌀')} steps do not count). Added to your field notes." for before, truth, _first in reveals]

    def _catch_result(self, catch: fishing.Catch) -> Result:
        reg = get_registry()
        rarity = Rarities.from_value(catch.fish.rarity)
        lines = [f"**{rarity.rarity_name}**  ·  {emojis.icon('ruler', '📏')} **{catch.size:g} cm**  ·  worth **{emojis.bits(catch.fish.sell_price)}**"]
        if catch.slack_bits:
            lines.append(f"{emojis.ui('hook', '🪝')} **Clean reel!** {catch.slack_left} slack unused: **+{bits(catch.slack_bits)}** bits")
        if catch.streak_bits:
            lines.append(f"{emojis.icon('flame', '🔥')} **Hot streak!** **+{bits(catch.streak_bits)}** bits for your clean reels in a row")
        if catch.server_record:
            lines.append(f"{emojis.icon('record', '🏆')} **NEW SERVER RECORD!** +{emojis.bits(catch.record_bits)}"
                         + (f" (you beat {catch.record_holder})" if catch.record_holder else ""))
        elif catch.personal_best:
            lines.append(f"{emojis.icon('medal', '🏅')} New personal best!")
        lines += self._tell_lines(catch.reveals)
        if catch.bycatch:
            lines.append(f"{emojis.icon('hook', '🪝')} **Bycatch!** Your rod also hauled up a **{catch.bycatch.display}**.")
        if catch.extra_fish:
            lines.append(f"{emojis.icon('rod', '🎣')} Your rod hauled in **{catch.extra_fish}** more: **{catch.extra_fish + 1}** {catch.fish.display} in all!")
        for q in catch.finished:
            lines.append(f"{emojis.icon('scroll', '📜')} **Quest complete:** {q.text}  ·  +{emojis.bits(q.bits)}, +{q.xp} xp")
        faded = []

        def flash_live() -> tuple[list[str], bool]:
            if self.flash is not None and now() < self.flash[1]:
                digits = "   ".join(self.flash[0])
                return [f"### {emojis.icon('swirl', '🌀')} The waves of the ocean… the heat of the sun… sirens in the distance, singing…\n"
                        f"# {digits}\n-# Remember them! They fade in a few seconds."], True
            if self.flash is not None:
                self.flash = None
                faded.append(True)
            return ([f"{emojis.icon('mist', '🌫️')} The numbers slip away… hold on to what you remember."], False) if faded else ([], False)

        def offer_live() -> tuple[list[str], bool]:
            if self.offer is not None and now() < self.offer[0]:
                return [f"### {emojis.icon('bolt', '⚡')} Quick cast! A second line is already biting.\n-# {max(1, round(self.offer[0] - now()))}s left to take it. Ignoring it costs nothing."], True
            return [], False

        actions = [("Quick cast!", f"{emojis.icon('bolt', '⚡')}", self._quick_cast)] if self.offer is not None else []
        if catch.hallucination and self.offer is not None:
            def live() -> tuple[list[str], bool]:
                (a, ticking_a), (b, ticking_b) = flash_live(), offer_live()
                return a + b, ticking_a or ticking_b
        elif catch.hallucination:
            live = flash_live
        else:
            live = offer_live if self.offer is not None else None
        part_notes = [smithing.part_line(catch.part)] if catch.part is not None else []
        return rewards_result(f"You caught a {catch.fish.display}!", items=Counter({catch.fish.id: 1 + catch.extra_fish}) + Counter(catch.extras), xp=catch.xp,
                              notes=lines[1:] + part_notes, headline=lines[:1], odds=odds.fishing_catch(), emoji=emojis.skill("fishing", "🎣"), accent=int(rarity.color, 16),
                              again=self._cast, again_label="Cast again", live=live, actions=actions)

    # ---- handlers --------------------------------------------------------------------------------
    async def _cast(self, interaction: discord.Interaction) -> None:
        stats = await fishing.rod_stats(self.user)
        armed = await fishing.chests_possible(self.user, now())
        open_waters = await fishing.open_waters(self.user)
        water = next((w for w in open_waters if w.id == self.water), open_waters[-1])  # closed or unknown: the newest open one
        self.missed, self.offer = None, None
        self.cast = fishing.cast_line(stats, self.rng, now(), armed=armed, water=water, pet=await pets.bonuses(self.user), chase=await fishing.use_radar(self.user, water))
        await self.refresh(interaction)

    async def _quick_cast(self, interaction: discord.Interaction) -> None:
        """Take a Double Hook's offer: a free second line in the same water, already biting. Too late (or none) costs nothing."""
        offer, self.offer = self.offer, None
        rules = get_registry().fishing
        if offer is None or clicked_at(interaction) > offer[0] + rules.bite.grace:
            return await self.refresh(interaction, f"{emojis.icon('bolt', '⚡')} The quick cast has passed.")
        stats = await fishing.rod_stats(self.user)
        self.missed = None
        self.cast = fishing.quick_cast(stats, self.rng, now(), offer[1], get_registry(), await pets.bonuses(self.user))
        await self.refresh(interaction, f"{emojis.icon('bolt', '⚡')} A second line is biting! Pull it up.")

    async def _net(self, interaction: discord.Interaction) -> None:
        """Net Cast: a net hauls a few of the water's commonest fish at once, then it cools down."""
        open_waters = await fishing.open_waters(self.user)
        water = next((w for w in open_waters if w.id == self.water), open_waters[-1])  # closed or unknown: the newest open one
        _, count, _ = await fishing.net_cast(self.user, water)
        await self.refresh(interaction, f"{emojis.icon('net', '🥅')} **Net Cast!** You hauled in {count} fish.")

    async def _pick_water(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.water = values[0]
        await self.user.set_zone("fishing", self.water)
        await self.refresh(interaction)

    async def _collect_party_boss(self) -> bool:
        """Pay out any finished party boss fight and show it on a page of its own (True if there was one)."""
        if self.result is not None:
            return False  # (a page is already waiting to be shown: the payout is collected on the next look)
        paid = await party_boss.claim(self.user, now())
        if not paid:
            return False
        reg = get_registry()
        headline, notes = [], []
        for p in paid:
            team = f"  ·  {emojis.icon('group', '👥')} team bonus **+{p.bonus:.0%}** ({p.teammates} teammate(s) landed theirs)" if p.teammates else ""
            headline.append(f"{emojis.icon('boss', '💀')} **{p.boss}** is beaten!{team}")
            if p.slack_bits:
                notes.append(f"{emojis.ui('hook', '🪝')} Clean reel bonus included: **+{bits(p.slack_bits)}** bits")
        self.result = rewards_result("The party beat the boss!", items=sum((p.items for p in paid), Counter()), bits=sum(p.bits for p in paid), xp=sum(p.xp for p in paid),
                                     headline=headline, notes=notes, odds=odds.fishing_boss(), emoji=emojis.icon("boss", "💀"), accent=0x7B241C, again=self._cast, again_label="Cast again")
        return True

    def _join_boss(self, host: str | None = None):
        """The Join button's handler: your party's fight, or (with `host`) one that was opened to everyone."""
        async def join(interaction: discord.Interaction) -> None:
            stats = await fishing.rod_stats(self.user)
            try:
                fight = await party_boss.join(self.user, now(), host=host)
            except party_boss.PartyBossError as error:
                return await self.refresh(interaction, str(error))
            cast = fishing.join_boss_cast(stats, self.rng, now(), fight.boss, get_registry(), await pets.bonuses(self.user))
            cast.party_fight, cast.public = fight.number, True  # (only the one who hooked it can open it up)
            self.cast, self.missed = cast, None
            await self.refresh(interaction, f"{emojis.icon('boss', '💀')} You join the fight with **{fight.boss}**! Reel your own set of arrows.")

        return join

    async def _open_boss(self, interaction: discord.Interaction) -> None:
        cast = self.cast
        if cast is None or not cast.boss or cast.public:
            return await self.refresh(interaction)
        try:
            fight = await party_boss.open_to_all(self.user, cast.boss, cast.modifiers, now())
        except party_boss.PartyBossError as error:
            return await self.refresh(interaction, str(error))
        cast.party_fight, cast.public = fight.number, True
        await self.refresh(interaction, f"{emojis.icon('group', '👥')} **Open to everyone!** Any player will see this fight on their Fishing page.")

    async def _cancel(self, interaction: discord.Interaction) -> None:
        if self.cast is not None and self.cast.party_fight is not None:
            await party_boss.report(self.user, "failed", 0, now())  # you let it go: your part of the fight is over
        self.cast = None
        await self.refresh(interaction, f"{emojis.icon('rod', '🎣')} You reel the line back in.")

    async def _hook(self, interaction: discord.Interaction) -> None:
        cast, clicked = self.cast, clicked_at(interaction)
        if cast is None:  # a click that was already on its way... or one that was made in time but reached us late
            if self.missed is not None and self.missed.salvage(clicked):
                self.cast, self.missed = self.missed, None
                self.nav.screen = self  # the "too slow" page was wrong: this click was in time, so carry on playing
                return await self.refresh(interaction, f"{emojis.icon('rod', '🎣')} Got it, just in time!")
            return await self.refresh(interaction)
        try:
            cast.hook(clicked)
        except fishing.FishingError as error:
            if cast.escaped:
                self.cast = None
                await fishing.lose_streak(self.user)
            return await self.refresh(interaction, str(error))
        note = None
        if cast.boss and cast.hooked and cast.party_fight is None:  # a boss on the line: if you are in a party, the rest of it can join the fight
            fight = await party_boss.open_fight(self.user, cast.boss, cast.modifiers, now())
            if fight is not None:
                cast.party_fight = fight.number
                note = f"{emojis.icon('group', '👥')} **Your party can join this fight!** They will see it on their Fishing page."
        await self.refresh(interaction, note)

    def _press(self, arrow: str):
        async def press(interaction: discord.Interaction) -> None:
            cast = self.cast
            if cast is None:  # a click that was already on its way
                return await self.refresh(interaction)
            try:
                result = cast.press(arrow, clicked_at(interaction))
            except fishing.FishingError as error:
                if cast.escaped or cast.progress >= len(cast.pattern):
                    self.cast = None
                return await self.refresh(interaction, str(error))
            if result == "landed" and cast.boss and cast.party_fight is not None:
                self.cast = None
                await party_boss.report(self.user, "done", cast.slips_left, now())
                if await self._collect_party_boss():  # you were the last one: the fight is over and you are paid right now
                    return await self.refresh(interaction)
                self.result = Result("You landed your part!", [f"{emojis.icon('boss', '💀')} **{cast.boss}** is hooked! Your reel is done."
                                                                 + (f"\n{emojis.ui('hook', '🪝')} Clean reel: **{cast.slips_left}** slack unused." if cast.slips_left else "")
                                                                 + "\nYour reward comes when your party's reels are all in (or the fight ends): it is on your Fishing page."],
                                     emoji=emojis.icon("boss", "💀"), accent=0x7B241C, back_label="Back to fishing")
                return await self.refresh(interaction)
            if result == "landed" and cast.boss:
                self.cast = None
                won = await fishing.defeat_boss(self.user, cast, self.rng)
                slack = [f"{emojis.ui('hook', '🪝')} Clean reel: **{won.slack_left}** slack unused  ·  **+{bits(won.slack_bits)}** bits"] if won.slack_bits else []
                self.result = rewards_result(f"You beat {won.name}!", items=won.items, bits=won.bits, xp=won.xp, notes=slack, odds=odds.fishing_boss(),
                                             emoji=emojis.icon("boss", "💀"), accent=0x7B241C, again=self._cast, again_label="Cast again")
                return await self.refresh(interaction)
            if result == "landed":
                self.cast = None
                catch = await fishing.land(self.user, cast, now=now(), rng=self.rng)
                if catch.hallucination:
                    self.flash = (catch.hallucination, now() + get_registry().fishing.treasure.flash_seconds)
                self.offer = None
                if not cast.quick and (window := fishing.roll_double_hook(await fishing.rod_stats(self.user), self.rng, get_registry().fishing)):
                    self.offer = (now() + window, cast.water)  # Double Hook: a free Quick cast, only after a plain landing and never after another Quick cast
                self.result = self._catch_result(catch)
                return await self.refresh(interaction)
            if result == "escaped":
                self.cast = None
                await fishing.lose_streak(self.user)
                if cast.party_fight is not None:
                    await party_boss.report(self.user, "failed", 0, now())
                what = cast.boss or f"The {cast.fish.display}"
                lines = [f"Wrong way! {what} slipped off the hook."] + self._tell_lines(cast.reveals)
                await fishing.note_tells(self.user, cast)
                self.result = self._lost(f"{emojis.icon('wave', '🌊')} It got away!", lines)
                return await self.refresh(interaction)
            await self.refresh(interaction, f"{emojis.ui('hook', '🪝')} Wrong way! The line goes slack, but you hold on." if result == "slip" else None)  # (an "echo" is ignored)

        return press

    async def _enter_code(self, interaction: discord.Interaction) -> None:
        cast = self.cast
        if cast is None or not cast.chest:
            return await self.refresh(interaction)
        length = get_registry().fishing.treasure.code_length

        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            if self.cast is not cast:  # the chest is gone
                return await self.refresh(modal_interaction)
            try:
                result = await fishing.open_chest(self.user, cast, raw, self.rng, now())
            except fishing.FishingError as error:
                self.cast = None
                return await self.refresh(modal_interaction, str(error))
            reg = get_registry()
            if result.opened:
                self.cast = None
                self.result = rewards_result("The lock clicks open!", items=result.items, bits=result.bits, xp=result.xp, odds=odds.fishing_chest(),
                                             emoji=emojis.icon('anvil', '🧰'), accent=0xF1C40F, again=self._cast, again_label="Cast again")
                return await self.refresh(modal_interaction)
            if result.sunk:
                self.cast = None
                self.result = self._lost(f"{emojis.icon('wave', '🌊')} The chest sinks", ["Wrong numbers, and no tries left. The chest sinks back into the deep…"])
                return await self.refresh(modal_interaction)
            await self.refresh(modal_interaction, f"{emojis.icon('lock', '🔒')} Wrong numbers. The lock holds. **{result.attempts_left}** tries left.")

        await interaction.response.send_modal(PromptModal("Unlock the chest", f"The {length} numbers", submitted,
                                                          placeholder="e.g. 4815", max_length=length + 4))

    async def _reel_notes(self, interaction: discord.Interaction) -> None:
        """Field notes on a page of their own while you reel (like the foraging Grain notes). The cast stays as it is: nothing in a
        reel is timed once the line is up, so Back to reeling carries on at the same step."""
        intro, lines = await notes_content(self.user)
        self.result = Result("Field notes", [intro, lines], emoji=emojis.icon('search', '🔍'), accent=0x2980B9, back_label="Back to reeling")
        await self.refresh(interaction)

    async def _collection(self, interaction: discord.Interaction) -> None:
        # open on Quests when they are unlocked, else on the Book (the dropdown switches tabs either way)
        level = User.xp_to_level((await self.user.skill("fishing")).xp)
        tab = "quests" if fishing.quests_unlocked(level, get_registry().fishing) else "book"
        await self.go(interaction, "fishlog", tab=tab)

    async def _pots(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fishpots")

    async def _radar(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "radar")

    async def _mastery(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "mastery", skill="fishing")

class FishQuestsScreen(Screen):
    """A pane of the Collection (fishlog): daily and weekly quests."""

    label = "Quests"
    emoji = f"{emojis.icon('quest', '📜')}"
    description = "Daily and weekly fishing quests"

    async def build(self) -> Page:
        quests = await fishing.quests(self.user, now())
        if not quests:
            return Page("Fishing Quests", [*self.note_block(), text(
                f"Quests unlock at fishing level {get_registry().fishing.quests.min_level}.")], accent=ACCENT)
        daily, weekly = [q for q in quests if q.kind == "daily"], [q for q in quests if q.kind == "weekly"]
        today, week = fishing.day_of(now()), fishing.week_of(now())
        return Page("Fishing Quests", [
            *self.note_block(),
            text("### Daily\n" + "\n".join(quest_line(q) for q in daily) + f"\n-# New ones <t:{(today + 1) * fishing.DAY}:R>"),
            sep(),
            text("### Weekly\n" + "\n".join(quest_line(q) for q in weekly) + f"\n-# New one <t:{(week * 7 - 3 + 7) * fishing.DAY}:R>"),
            row(button("Back to fishing", emoji=ROD, on_click=self._back)),
        ], accent=ACCENT)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fish")


def unknown_summary(rarities: list[int], what: str) -> str:
    """One line for every fish you have not met yet, instead of one "???" line each: "❓ 21 unknown: Common 3 · Rare 3 ..."."""
    counts: dict[int, int] = {}
    for rarity in rarities:
        counts[rarity] = counts.get(rarity, 0) + 1
    return f"{emojis.icon('unknown', '❓')} **{len(rarities)}** {what}: " + " · ".join(f"{Rarities.from_value(r).rarity_name} {n}" for r, n in sorted(counts.items()))


class FishBookScreen(Screen):
    """A pane of the Collection (fishlog): turn in fish and level the book up."""

    label = "Book"
    emoji = f"{emojis.icon('book', '📖')}"
    description = "Turn in fish for rewards and level the book up"

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.fishing.book
        level = User.xp_to_level((await self.user.skill("fishing")).xp)
        if not fishing.book_unlocked(level, reg.fishing):
            return Page("Collection Book", [*self.note_block(), text(f"The book opens at fishing level {rules.min_level}.")], accent=ACCENT)
        view = await fishing.book(self.user)
        owned = await self.user.items()
        lines = []
        for e in view.entries:
            mark = emojis.icon('check', '✅') if e.done else emojis.icon('sq_white', '⬜')
            have = f"  ·  you have {owned[e.fish.id]:,}" if not e.done and owned.get(e.fish.id) else ""
            lines.append(f"{mark} {e.fish.display}  ·  **{e.given}/{e.need}**{have}")
        wanted = [e for e in view.entries if not e.done and owned.get(e.fish.id)]
        body = [
            *self.note_block(),
            text(f"### {emojis.icon('book', '📖')} Book level {view.level}\n+**{rules.bits_per_sell:.0%}** value and xp on fish you turn in  ·  "
                 f"finishing pays **{emojis.bits(rules.completion_bits * view.level)}**"),
            text("\n".join("  ·  ".join(lines[i:i + 2]) for i in range(0, len(lines), 2))),
        ]
        if wanted:
            body.append(row(select("Turn in a fish...", [
                discord.SelectOption(label=e.fish.name, value=e.fish.id, emoji=e.fish.emoji or None,
                                     description=f"You have {owned[e.fish.id]:,}, the book needs {e.need - e.given:,} more")
                for e in wanted[:25]], self._turn_in)))
        body.append(row(
            button("Finish the book", emoji=emojis.icon("record", "🏆"), style=discord.ButtonStyle.success, disabled=not view.complete or view.level >= rules.max_level,
                   on_click=self._finish),
            button("Records", emoji=emojis.icon("record", "📏"), on_click=self._records),
            button("Back to fishing", emoji=ROD, on_click=self._back),
        ))
        return Page("Collection Book", body, accent=0x8E44AD)

    async def _turn_in(self, interaction: discord.Interaction, values: list[str]) -> None:
        done = await fishing.turn_in(self.user, values[0])
        await self.refresh(interaction, f"{emojis.icon('book', '📖')} You added {done.quantity:,} {done.fish.display} to the book  ·  +{emojis.bits(done.bits)}, +{done.xp} xp")

    async def _records(self, interaction: discord.Interaction) -> None:
        self.nav.screen.tab = "records"  # a tab of the same page, not a new page
        await self.nav.refresh(interaction)

    async def _finish(self, interaction: discord.Interaction) -> None:
        done = await fishing.complete_book(self.user)
        await self.refresh(interaction, f"{emojis.icon('record', '🏆')} **Book complete!** It is now level {done.new_level}  ·  +{emojis.bits(done.bits)}, +{done.xp} xp")

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fish")


class FishCommunityScreen(Screen):
    """The server's collection book and this month's goals. Redraws itself so you see everyone's progress."""

    label = "Community"
    emoji = emojis.icon('world', '🌍')
    description = "The community book and this month's goals"
    refresh_every = 10.0  # the host (TabsScreen) passes this on to the page while this tab is open

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.fishing
        level = User.xp_to_level((await self.user.skill("fishing")).xp)
        if not fishing.quests_unlocked(level, rules):
            return Page("Fishing Community", [*self.note_block(), text(
                f"The community opens at fishing level {rules.quests.min_level}.")], accent=ACCENT)

        # whatever you are owed from finished goals and finished books is paid when you look
        notes = []
        if paid := await fishing_community.claim_book_rewards(self.user):
            notes.append(f"{emojis.icon('world', '🌍')} **The community finished its book** (level {', '.join(map(str, paid.levels))})  ·  "
                         f"+{emojis.bits(paid.bits)}, +{paid.xp:,} xp for you")
        if paid := await fishing_community.claim_monthly(self.user, now()):
            notes.append(f"{emojis.icon('page', '🗓️')} **Community goal reached:** " + ", ".join(g.text for g in paid.goals)
                         + f"  ·  +{emojis.bits(paid.bits)}, +{paid.xp:,} xp")
        if notes:
            self.note = "\n".join(filter(None, [self.note, *notes]))
        body = [*self.note_block()]

        view = await fishing_community.book(self.user)
        owned = await self.user.items()
        body.append(text(f"### {emojis.icon('book', '📖')} Community Book · level {view.level}\n"
                         + "\n".join(f"{emojis.icon('check', '✅') if p.done else emojis.icon('sq_white', '⬜')} {p.fish.display}  ·  **{p.given}/{p.need}**"
                                      + (f"  ·  you have {owned[p.fish.id]:,}" if not p.done and owned.get(p.fish.id) else "")
                                      for p in view.pages)
                         + f"\n-# You have donated **{view.donated_by_you}** this level. Finishing it pays everyone "
                           f"{emojis.bits(rules.community.book.completion_bits * view.level)}."))
        wanted = [p for p in view.pages if not p.done and owned.get(p.fish.id)]
        if not fishing.book_unlocked(level, rules):
            body.append(text(f"-# Donating opens at fishing level {rules.book.min_level}."))
        elif wanted:
            body.append(row(select("Donate a fish...", [
                discord.SelectOption(label=p.fish.name, value=p.fish.id, emoji=p.fish.emoji or None,
                                     description=f"You have {owned[p.fish.id]:,}, the book needs {p.need - p.given:,} more")
                for p in wanted], self._donate)))

        goals = await fishing_community.monthly(self.user, now())
        lines = []
        for g in goals:
            share = g.goal.slot.count
            mark = emojis.icon('check', '✅') if g.done else emojis.icon('sq_white', '⬜')
            pay = "" if g.done else f"  ·  +{emojis.bits(g.goal.slot.bits)}"
            lines.append(f"{mark} {g.goal.text}\n{bar(min(1.0, g.progress / share), 8, 'progress')}  **{min(g.progress, share):,}/{share:,}**"
                         f"  ·  you: {g.yours:,}{pay}")
        ends = fishing_community.month_ends_at(fishing_community.month_of(now()))
        body += [sep(), text(f"### {emojis.icon('page', '🗓️')} This month's goals\n" + "\n".join(lines)
                             + f"\n-# Everyone fishing adds up. Do at least {rules.community.min_share:.0%} of a goal to be paid when "
                               f"it is reached. New goals <t:{int(ends)}:R>."),
                 row(button("Records", emoji=emojis.icon("record", "📏"), on_click=self._records),
                     button("Back to fishing", emoji=ROD, on_click=self._back))]
        return Page("Fishing Community", body, accent=0x16A085)

    async def _records(self, interaction: discord.Interaction) -> None:
        self.nav.screen.tab = "records"  # a tab of the same page, not a new page
        await self.nav.refresh(interaction)

    async def _donate(self, interaction: discord.Interaction, values: list[str]) -> None:
        done = await fishing_community.donate(self.user, values[0])
        note = f"{emojis.icon('book', '📖')} You gave {done.quantity:,} {done.fish.display} to the community book  ·  +{emojis.bits(done.bits)}, +{done.xp:,} xp"
        if done.finished_level:
            note += f"\n{emojis.icon('party', '🎉')} **That finished the book!** It is now level {done.finished_level + 1} and everyone will be paid."
        await self.refresh(interaction, note)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fish")


class FishRecordsScreen(Screen):
    """The biggest of every fish: yours, and the biggest ever caught on the server."""

    label = "Records"
    emoji = f"{emojis.icon('record', '📏')}"
    description = "Your biggest catches and the server records"

    async def build(self) -> Page:
        reg = get_registry()
        mine = (await self.user.skill("fishing")).records
        server = await fishing.server_records()
        lines, unknown = [], []
        for fish in sorted(fishing.fish_pool(reg), key=lambda i: (i.rarity, i.name)):
            best, held = mine.get(fish.id), server.get(fish.id)
            if best is None and held is None:
                unknown.append(fish.rarity)
                continue
            yours = f"you **{best:g} cm**" if best is not None else "you: not caught yet"
            record = f"  ·  {emojis.icon('record', '🏆')} {held['size']:g} cm ({held['name']})" if held else ""
            crown = f" {emojis.icon('crown', '👑')}" if held and best is not None and held["uid"] == self.user.id and held["size"] == best else ""
            lines.append(f"{fish.display}  ·  {yours}{crown}{record}")
        if unknown:
            lines.append(unknown_summary(unknown, "fish nobody has caught yet"))
        return Page("Fish Records", [*self.note_block(), text(f"### {emojis.icon('record', '📏')} Biggest catches\n" + "\n".join(lines)
                    + f"\n-# {emojis.icon('record', '🏆')} server record  ·  {emojis.icon('crown', '👑')} that's you  ·  beat a record to be paid."),
                    row(button("Back to fishing", emoji=ROD, on_click=self._back),
                        button("Field notes", emoji=emojis.icon('search', '🔍'), on_click=self._notes))], accent=0x2980B9)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fish")

    async def _notes(self, interaction: discord.Interaction) -> None:
        self.nav.screen.tab = "notes"
        await self.nav.refresh(interaction)


async def notes_content(user) -> tuple[str, str]:
    """(the intro, the lines) of the field notes, for the page and for the pop-up while reeling. A pattern shows only when it is confirmed."""
    reg = get_registry()
    skill = await user.skill("fishing")
    lines, unknown = [], []
    for fish in sorted((i for i in fishing.fish_pool(reg) if i.rarity >= reg.fishing.reel.mystery_from_rarity),
                       key=lambda i: (i.rarity, i.name)):
        entries = skill.notes.get(fish.id, [])
        if entries:
            verdict = fishing.notes_verdict(entries)
            qmark = emojis.icon('unknown', '❓')
            lines.append(f"{fish.display}: {verdict or f'**{len(entries)}** {qmark} seen, no pattern confirmed yet'}")
        elif fish.id in skill.records:
            lines.append(f"{fish.display}: no {emojis.icon('unknown', '❓')} revealed yet. Press the {emojis.icon('unknown', '❓')} (or lose at one) to find out what it was.")
        else:
            unknown.append(fish.rarity)
    if unknown:
        lines.append(unknown_summary(unknown, "not caught yet"))
    intro = (f"Rare fish hide arrows behind a {emojis.icon('unknown', '❓')}. Each fish has its own rule for it: always {emojis.icon('prev', '◄')}, always {emojis.icon('next', '►')}, the opposite of the last arrow before it, "
             f"the same as the last arrow before it, or the same as the FIRST arrow of the reel. {emojis.icon('swirl', '🌀')} Reel steps are skipped when looking back, and a Reel step's "
             f"disguise arrow does not count. Every {emojis.icon('unknown', '❓')} you see is counted here, and a rule is only written down once "
             f"**{fishing.MIN_NOTES_FOR_VERDICT}** of them agree on it.")
    return intro, "\n".join(lines)


class FishNotesScreen(Screen):
    """What each ❓ turned out to be, fish by fish: only the patterns that are confirmed."""

    label = "Notes"
    emoji = emojis.icon('search', '🔍')
    description = f"What the hidden arrows ({emojis.icon('unknown', '❓')}) turned out to be"

    async def build(self) -> Page:
        intro, lines = await notes_content(self.user)
        return Page("Field notes", [*self.note_block(), text(f"### {emojis.icon('search', '🔍')} Field notes\n-# " + intro + "\n" + lines),
                    row(button("Back to fishing", emoji=ROD, on_click=self._back))], accent=0x2980B9)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fish")


class FishLogScreen(TabsScreen):
    """The fishing Collection: quests, the book, the community book, records and field notes, as tabs of one page."""

    id = "fishlog"
    label = "Collection"
    emoji = emojis.icon('book', '📖')
    description = "Fishing quests, the collection book, community, records and field notes"
    links = ("fish",)
    panes = {"quests": FishQuestsScreen, "book": FishBookScreen, "community": FishCommunityScreen,
             "records": FishRecordsScreen, "notes": FishNotesScreen}


class FishPotsScreen(Screen):
    """Crab pots: craft them, load bait, collect what they caught while you were away."""

    id = "fishpots"
    label = "Crab Pots"
    emoji = f"{emojis.icon('crab', '🦀')}"
    description = "Pots that catch rare fish while you are away"
    links = ("fish",)

    def __init__(self, nav):
        super().__init__(nav)
        self.index = 0

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.fishing
        skill = await self.user.skill("fishing")
        level = User.xp_to_level(skill.xp)
        if level < rules.pots.min_level:
            return Page("Crab Pots", [*self.note_block(), text(f"Crab pots open at fishing level {rules.pots.min_level}.")], accent=0xD35400)
        pet = await pets.bonuses(self.user)
        slots, here = pots.slots_for(level, rules), now()
        self.index = min(self.index, max(0, len(skill.pots) - 1))
        body = [*self.note_block()]
        lines = []
        for i, pot in enumerate(skill.pots):
            water = fishing.water_by_id(reg, pot.water)
            lvl = pots.level_rules(pot, rules)
            bait = f"{reg.item(pot.bait).display} ×{pot.bait_left}" if pot.bait and pot.bait_left else "no bait"
            waiting = pots.ready(pot, here, reg, pet)
            eta = pots.time_to_next(pot, here, reg, pet)
            status = (f"**{waiting}/{lvl.capacity}** caught" if pot.bait_left or waiting else "idle")
            if eta is not None:
                status += f"  ·  next <t:{int(here + eta)}:R>"
            elif pot.bait_left and waiting:
                status += "  ·  full" if waiting >= lvl.capacity else "  ·  out of bait soon"
            lines.append(f"{(emojis.icon('next', '➤') + ' ') if i == self.index else ''}{emojis.icon('crab', '🦀')} **Pot {i + 1}**  ·  Lv {pot.level}  ·  {water.emoji} {water.name}  ·  {bait}  ·  {status}")
        owned_now = await self.user.items()
        body.append(text(f"### {emojis.icon('crab', '🦀')} Crab pots ({len(skill.pots)}/{slots})\n" + ("\n".join(lines) if lines else "You have no pots yet.")
                    + f"\n-# Pots only catch {Rarities.from_value(rules.pots.min_rarity).rarity_name} fish and better, one at a time, while you are away."))
        if len(skill.pots) < slots:
            body.append(text(f"**{emojis.icon('craft', '🔨')} Craft a pot**\n" + needs_text(rules.pots.craft_bits, self.user.purse, rules.pots.craft_items, owned_now, reg)))
        elif len(skill.pots) < len(rules.pots.slot_levels):
            body.append(text(f"-# Another pot opens at fishing level {rules.pots.slot_levels[len(skill.pots)]}."))
        if len(skill.pots) > 1:
            body.append(row(select("Pick a pot...", [
                discord.SelectOption(label=f"Pot {i + 1} · Lv {p.level}", value=str(i), default=i == self.index,
                                     description=fishing.water_by_id(reg, p.water).name) for i, p in enumerate(skill.pots)], self._pick)))
        buttons = [button("Collect all", emoji=emojis.icon("haul", "🧺"), style=discord.ButtonStyle.success,
                          disabled=not any(pots.ready(p, here, reg, pet) for p in skill.pots), on_click=self._collect)]
        if skill.pots:
            pot = skill.pots[self.index]
            if pot.level < len(rules.pots.levels):
                cost = rules.pots.levels[pot.level]
                buttons.append(button(f"Upgrade pot {self.index + 1}", emoji=emojis.icon("upgrade", "⬆️"), on_click=self._upgrade))
                body.append(text(f"**{emojis.icon('upgrade', '⬆️')} Upgrade pot {self.index + 1} to level {pot.level + 1}**\n"
                                 + needs_text(cost.upgrade_bits, self.user.purse, cost.upgrade_items, owned_now, reg)))
            worth = pots.hourly_value(pot, reg, pet)
            body.append(text(f"-# Pot {self.index + 1} catches about one fish every **{pots.interval_seconds(pot, reg, pet) / 60:.0f}** minutes "
                             f"(holds {pots.level_rules(pot, rules).capacity}), worth about **{emojis.bits(round(worth))}** an hour. "
                             f"Fishing yourself earns far more."))
        buttons.append(button("Craft a pot", emoji=emojis.icon("craft", "🔨"), disabled=len(skill.pots) >= slots, on_click=self._craft))
        body.append(row(*buttons))
        if skill.pots:
            owned = await self.user.items()
            baits = [(reg.item(i), q) for i, q in owned.items() if q > 0 and (it := reg.find_item(i)) and it.bait]
            if baits:
                body.append(row(select("Load bait...", [
                    discord.SelectOption(label=f"{b.name} ×{q:,}", value=b.id, emoji=b.emoji,
                                         description=f"{b.bait.luck:g}x rare fish, {b.bait.speed:g}x speed") for b, q in baits][:25], self._bait)))
            else:
                body.append(text("-# You have no bait. Buy some in the shop (fishing)."))
            body.append(row(select("Move pot to...", [
                discord.SelectOption(label=w.name, value=w.id, emoji=w.emoji, default=w.id == skill.pots[self.index].water)
                for w in await fishing.open_waters(self.user, reg)], self._water)))
        return Page("Crab Pots", body, accent=0xD35400)

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.index = int(values[0])
        await self.refresh(interaction)

    async def _craft(self, interaction: discord.Interaction) -> None:
        await pots.craft(self.user, now())
        self.index = len((await self.user.skill("fishing")).pots) - 1
        await self.refresh(interaction, f"{emojis.icon('crab', '🦀')} You crafted a crab pot! Load some bait to get it fishing.")

    async def _upgrade(self, interaction: discord.Interaction) -> None:
        pot = await pots.upgrade(self.user, self.index)
        await self.refresh(interaction, f"{emojis.icon('upgrade', '⬆️')} Pot {self.index + 1} is now level {pot.level}.")

    async def _bait(self, interaction: discord.Interaction, values: list[str]) -> None:
        bait_id, index = values[0], self.index
        reg = get_registry()
        have = await self.user.item_quantity(bait_id)

        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            quantity = have if raw.strip().lower() in ("all", "") else int(raw.replace(",", "") or 0)
            loaded, returned = await pots.load_bait(self.user, index, bait_id, quantity, now())
            note = f"{emojis.icon('worm', '🪱')} Loaded {loaded:,} {reg.item(bait_id).display} into pot {index + 1}."
            if returned:
                note += f" The {returned:,} left of the old bait came back to you."
            await self.refresh(modal_interaction, note)

        await interaction.response.send_modal(PromptModal(f"Load {reg.item(bait_id).name}", f"How many? (you have {have:,})", submitted,
                                                          default=str(have), max_length=9))

    async def _water(self, interaction: discord.Interaction, values: list[str]) -> None:
        await pots.set_water(self.user, self.index, values[0], now())
        await self.refresh(interaction, f"{emojis.icon('crab', '🦀')} Pot {self.index + 1} moved to {fishing.water_by_id(get_registry(), values[0]).name}.")

    async def _collect(self, interaction: discord.Interaction) -> None:
        reg = get_registry()
        haul = await pots.collect_all(self.user, now())
        if not haul.catches:
            return await self.refresh(interaction, f"{emojis.icon('crab', '🦀')} Nothing has been caught yet.")
        worth = sum(reg.item(i).sell_price * q for i, q in haul.fish.items())
        self.result = rewards_result("The pots are emptied!", items=haul.fish, xp=haul.xp, notes=[f"Worth about **{emojis.bits(worth)}**"],
                                     emoji=emojis.icon("crab", "🦀"), accent=0xD35400, back_label="Back to the pots")
        await self.refresh(interaction)
