import datetime
import random
import time

import discord

from cococap.constants import Rarities
from cococap.registry import get_registry
from cococap.screens.sellall import start_sell_all
from cococap.services import fishing, fishing_community, party_boss, pets, pots
from cococap.services.equipment import equipped_stats
from cococap.services.party import xp_bonus
from cococap.ui import Page, PromptModal, Result, Screen
from cococap.ui.components import bar, bits, button, needs_text, row, select, sep, text, xp_bar
from cococap.user import User

ROD = "🎣"
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
    more, done = len(cast.pattern) - end, "✅" * cast.progress
    if not steps:
        return done
    if "reverse" in cast.modifiers:
        return " ".join(filter(None, [f"… +{more}" if more else "", *reversed(steps[1:]), f"**{steps[0]}**", done]))
    return " ".join(filter(None, [done, f"**{steps[0]}**", *steps[1:], f"… +{more}" if more else ""]))


def reel_buttons(cast: fishing.Cast, rng, handler, style) -> list[discord.ui.Button]:
    """Left, Right and Reel (and Let it go). A "shuffle" boss moves them around every step."""
    buttons = [button("Left", emoji="◀️", style=style, on_click=handler(fishing.LEFT)),
               button("Right", emoji="▶️", style=style, on_click=handler(fishing.RIGHT)),
               button("Reel", emoji=fishing.REEL, style=discord.ButtonStyle.success, on_click=handler(fishing.REEL))]
    if "shuffle" in cast.modifiers:
        rng.shuffle(buttons)
    return buttons


def quest_line(q: fishing.Quest) -> str:
    mark = "✅" if q.done else "⬜"
    progress = "done" if q.done else f"{q.progress}/{q.count}"
    return f"{mark} {q.text}  ·  {progress}  ·  +{bits(q.bits)} bits, +{q.xp} xp"


class FishScreen(Screen):
    id = "fish"
    label = "Fishing"
    emoji = ROD
    description = "Cast a line and reel in fish"
    links = ("fishquests", "fishbook", "fishcommunity", "fishrecords", "fishnotes", "fishpots", "mastery", "sellall")

    def __init__(self, nav):
        super().__init__(nav)
        self.cast: fishing.Cast | None = None
        self.flash: tuple[str, float] | None = None  # (the hallucination's numbers, when they fade)
        self.water: str | None = None  # where you are fishing (None = the best water you have opened)
        self.missed: fishing.Cast | None = None  # a fish written off as too slow, which a late-arriving click can still save
        self.watching = False  # your party has a boss fight open: the page redraws by itself so it shows up and ends
        self.rng = new_rng()

    @property
    def refresh_every(self) -> float | None:  # redraw by itself while a line is in the water or numbers are flashing, or a party fight is open
        return REFRESH if self.cast is not None or self.flash is not None or self.watching else None

    async def build(self) -> Page:
        reg = get_registry()
        cast = self.cast
        if cast is not None and cast.status(now()) == "escaped":
            if cast.timed_out:
                self.missed = cast  # kept for a moment: a click made in time may still be on its way
            self.cast, cast = None, None  # nobody picked up the line in time
            await fishing.lose_streak(self.user)
            self.result = self._lost("🌊 Too slow!", ["It bit, but nobody pulled up the line in time. The fish got away."])
        if self.flash is not None and now() >= self.flash[1]:
            self.flash = None  # the numbers have faded
            extra = "🌫️ The numbers slip away… hold on to what you remember."
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
            body.append(text("### 🌀 The waves of the ocean… the heat of the sun… sirens in the distance, singing…\n"
                             f"# {digits}\n-# Remember them! They fade in a few seconds."))

        if cast is None:
            skill = await self.user.skill("fishing")
            overflow, needed = User.xp_for_next_level(skill.xp)
            header = f"**Level {User.xp_to_level(skill.xp)}**  {xp_bar(overflow / needed if needed else 0)}  {overflow:,}/{needed:,} xp"
            if bonus := await xp_bonus(self.user.id):
                header += f"\n👥 Party bonus: **+{bonus:.0%}** xp"
            body.append(text(header))
            if fight is not None and fight.is_open:
                if fight.you is None:
                    body += [text(f"### 💀 **{fight.boss}** is on your party's line!\n**{fight.reeling}** reeling · closes <t:{int(fight.closes_at)}:R>\n"
                                  "-# Join with your own set of arrows. Everyone who lands theirs is paid, and more for every teammate who does too."),
                             row(button("Join the fight", emoji="💀", style=discord.ButtonStyle.danger, disabled=stats is None, on_click=self._join_boss))]
                elif fight.you == "done":
                    body.append(text(f"### ✅ You landed your part of the fight with **{fight.boss}**\n**{fight.reeling}** still reeling · closes <t:{int(fight.closes_at)}:R>"))
            if stats is None:
                body.append(text("🎣 You need a rod. Buy a **Starter Rod** in the shop and it equips itself."))
            else:
                slips = fishing.slips_allowed(stats.power, reg.fishing, stats.stats.get("slips", 0))
                wait = fishing.typical_wait(stats.power, reg.fishing, stats.stats.get("bite_speed", 0.0))
                body.append(text(f"{ROD} Rod **{stats.power}**"
                                 + (f"  ·  bites in ~**{wait:.0f}s**" if self.user.settings.fishing_estimate else "")
                                 + (f"  ·  forgives **{slips}** slip(s)" if slips else "")))
            level = User.xp_to_level(skill.xp)
            open_waters = fishing.unlocked_waters(level, reg.fishing)
            if self.water not in {w.id for w in open_waters}:
                self.water = open_waters[-1].id  # a newly opened water is where you head next
            here = fishing.water_by_id(reg, self.water)
            body.append(text(f"{here.emoji} **{here.name}**" + (f"  ·  {here.description}" if len(open_waters) == 1 else "")))  # (with a menu, it says what each water is like)
            if len(open_waters) > 1:
                body.append(row(select("Where to fish...", [
                    discord.SelectOption(label=w.name, value=w.id, emoji=w.emoji, default=w.id == self.water,
                                         description=w.description[:100]) for w in open_waters], self._pick_water)))
            if len(open_waters) < len(reg.fishing.waters):
                nxt = reg.fishing.waters[len(open_waters)]
                body.append(text(f"-# {nxt.emoji} {nxt.name} opens at fishing level {nxt.min_level}."))
            if await fishing.chests_possible(self.user, now()):
                body.append(text("-# 🌀 The hallucination lingers… something shiny may be down there."))
            haul = await fishing.stock(self.user)
            level = User.xp_to_level(skill.xp)
            quests = await fishing.quests(self.user, now())
            body.append(sep())
            if quests:
                daily = [q for q in quests if q.kind == "daily"]
                body.append(text(f"📜 Quests: **{sum(q.done for q in daily)}/{len(daily)}** daily  ·  "
                                 f"**{sum(q.done for q in quests if q.kind == 'weekly')}/1** weekly"))
            else:
                body.append(text(f"-# 📜 Quests unlock at fishing level {reg.fishing.quests.min_level}."))
            body.append(text(f"🧺 **{haul.count:,}** fish  ·  worth **{bits(haul.worth)}** bits" if haul.count else "🧺 No fish yet."))
            body.append(row(
                button("Cast", emoji=ROD, style=discord.ButtonStyle.primary, disabled=stats is None, on_click=self._cast),
                button("Sell fish", emoji="💰", disabled=not haul.count, on_click=self._sell),
                button("Quests", emoji="📜", disabled=not fishing.quests_unlocked(level, reg.fishing), on_click=self._quests),
                button("Book", emoji="📖", disabled=not fishing.book_unlocked(level, reg.fishing), on_click=self._book),
                button("Community", emoji="🌍", disabled=not fishing.quests_unlocked(level, reg.fishing), on_click=self._community),
            ))
            body.append(row(button("Records", emoji="📏", on_click=self._records),
                            button("Field notes", emoji="🔍", on_click=self._notes),
                            button("Crab pots", emoji="🦀", disabled=level < reg.fishing.pots.min_level, on_click=self._pots),
                            button("Mastery", emoji="🌟", on_click=self._mastery),
                            button("Sell all", emoji="💰", on_click=self._sell_all)))
            return Page("Fishing", body, accent=ACCENT)

        status = cast.status(now())
        if status == "waiting":
            body += [text("### 🌊 The line is in the water…\n" + await self._wait_estimate()),
                     row(button("Cancel cast", on_click=self._cancel))]
            return Page("Fishing", body, accent=ACCENT)

        if status == "bite":
            body += [text(f"### ❗ A bite!\nPull up the line, quick! It gets away <t:{int(cast.expires_at) + 1}:R>"),
                     row(button("Pull up the line", emoji=ROD, style=discord.ButtonStyle.danger, on_click=self._hook))]
            return Page("Fishing", body, accent=0xE74C3C)

        if status == "chest":
            t = reg.fishing.treasure
            body += [text(f"### 🧰 A treasure chest!\nIt is locked with **{t.code_length}** numbers. Do you remember them?\n"
                          f"Tries left: **{cast.attempts_left}**"),
                     row(button("Enter the numbers", emoji="🔑", style=discord.ButtonStyle.success, on_click=self._enter_code),
                         button("Leave it", on_click=self._cancel))]
            return Page("Fishing", body, accent=0xF1C40F)

        rules = reg.fishing
        slack = (f"\n🧵 Slack left: **{cast.slips_left}**  ·  each one unused pays a bonus" if cast.slips_left else "")
        arrows = sum(t != fishing.REEL for t in cast.pattern)
        if cast.boss:
            twists = "\n".join(rules.boss.modifier_text[m] for m in cast.modifiers)
            body += [
                text(f"### 💀 **{cast.boss}** is on the line!\nA boss! No fish this time, but a mountain of loot if you land it.\n{twists}"
                     + ("\n👥 **Party fight:** you reel your own set of arrows, and everyone who lands theirs is paid." if cast.party_fight is not None else "") + "\n"
                     f"{pattern_line(cast, rules)}{slack}\n-# {arrows} arrows, and some of them turn into **Reel** when you get there. Don't slip!"),
                row(*reel_buttons(cast, self.rng, self._press, discord.ButtonStyle.danger), button("Let it go", on_click=self._cancel)),
            ]
            return Page("Fishing", body, accent=0x7B241C)

        # reeling it in: you can see what kind of fish it is now, so you can use what you have learned about it
        colour = Rarities.from_value(cast.fish.rarity)
        body += [
            text(f"### 🎣 A {cast.fish.display} is on the line!  ·  **{colour.rarity_name}**\n{pattern_line(cast, rules)}{slack}\n"
                 f"-# ◄ ► are the arrows. A step can turn into 🌀 as you reach it: press **Reel**"
                 + (", and ❓ is hidden: it follows this fish's own pattern. Check your field notes!"
                    if fishing.MYSTERY in cast.pattern else ".")),
            row(*reel_buttons(cast, self.rng, self._press, discord.ButtonStyle.primary), button("Let it go", on_click=self._cancel)),
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
        starter = fishing.typical_wait(reg.item("starter_rod").tool.power, rules) * scale
        line = f"⏱️ A bite in about **{mine:.0f}s**"
        return line + (f"  ·  a starter rod: {starter:.0f}s" if round(starter) != round(mine) else "")

    # ---- what happened ---------------------------------------------------------------------------
    def _lost(self, title: str, lines: list[str]) -> Result:
        return Result(title, lines + ["Nothing was lost but the fish. Try again!"], emoji="🌊", accent=0x5D6D7E,
                      again=self._cast, again_label="Cast again")

    @staticmethod
    def _tell_lines(reveals) -> list[str]:
        """What each ❓ turned out to be: written in your field notes, and shown here so you can start working it out."""
        return [f"🔍 The ❓ was **{truth}** (after {before}). Added to your field notes." for before, truth in reveals]

    def _catch_result(self, catch: fishing.Catch) -> Result:
        reg = get_registry()
        rarity = Rarities.from_value(catch.fish.rarity)
        lines = [f"**{rarity.rarity_name}**  ·  📏 **{catch.size:g} cm**  ·  worth **{bits(catch.fish.sell_price)}** bits  ·  **+{catch.xp:,}** xp"]
        if catch.slack_bits:
            lines.append(f"🧵 **Clean reel!** {catch.slack_left} slack unused: **+{bits(catch.slack_bits)}** bits")
        if catch.streak_bits:
            lines.append(f"🔥 **Hot streak!** **+{bits(catch.streak_bits)}** bits for your clean reels in a row")
        if catch.server_record:
            lines.append(f"🏆 **NEW SERVER RECORD!** +{bits(catch.record_bits)} bits"
                         + (f" (you beat {catch.record_holder})" if catch.record_holder else ""))
        elif catch.personal_best:
            lines.append("🏅 New personal best!")
        lines += self._tell_lines(catch.reveals)
        if catch.bycatch:
            lines.append(f"🪝 **Bycatch!** Your rod also hauled up a **{catch.bycatch.display}**.")
        if catch.extra_fish:
            lines.append(f"🎣 Your rod hauled in **{catch.extra_fish}** more: **{catch.extra_fish + 1}** {catch.fish.display} in all!")
        if catch.extras:
            lines.append("🪸 Also washed up: " + ", ".join(f"{q:,} {reg.item(i).display}" for i, q in catch.extras.items()))
        for q in catch.finished:
            lines.append(f"📜 **Quest complete:** {q.text}  ·  +{bits(q.bits)} bits, +{q.xp} xp")
        if catch.hallucination:
            faded = []

            def live() -> tuple[list[str], bool]:
                if self.flash is not None and now() < self.flash[1]:
                    digits = "   ".join(self.flash[0])
                    return ["### 🌀 The waves of the ocean… the heat of the sun… sirens in the distance, singing…\n"
                            f"# {digits}\n-# Remember them! They fade in a few seconds."], True
                if self.flash is not None:
                    self.flash = None
                    faded.append(True)
                return (["🌫️ The numbers slip away… hold on to what you remember."], False) if faded else ([], False)
        else:
            live = None
        return Result(f"You caught a {catch.fish.display}!", lines, emoji="🎣", accent=int(rarity.color, 16),
                      again=self._cast, again_label="Cast again", live=live)

    # ---- handlers --------------------------------------------------------------------------------
    async def _cast(self, interaction: discord.Interaction) -> None:
        stats = await fishing.rod_stats(self.user)
        armed = await fishing.chests_possible(self.user, now())
        level = User.xp_to_level((await self.user.skill("fishing")).xp)
        water = fishing.require_water(level, self.water or fishing.unlocked_waters(level, get_registry().fishing)[-1].id,
                                      get_registry().fishing)
        self.missed = None
        self.cast = fishing.cast_line(stats, self.rng, now(), armed=armed, water=water, pet=await pets.bonuses(self.user))
        await self.refresh(interaction)

    async def _pick_water(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.water = values[0]
        await self.refresh(interaction)

    async def _collect_party_boss(self) -> bool:
        """Pay out any finished party boss fight and show it on a page of its own (True if there was one)."""
        if self.result is not None:
            return False  # (a page is already waiting to be shown: the payout is collected on the next look)
        paid = await party_boss.claim(self.user, now())
        if not paid:
            return False
        reg = get_registry()
        lines = []
        for p in paid:
            loot = ", ".join(f"{q:,} {reg.item(i).display}" for i, q in p.items.items()) or "nothing"
            team = f"  ·  👥 team bonus **+{p.bonus:.0%}** ({p.teammates} teammate(s) landed theirs)" if p.teammates else ""
            lines += [f"💀 **{p.boss}** is beaten!  **+{bits(p.bits)}** bits  ·  **+{p.xp:,}** xp{team}", f"🎁 Loot: {loot}"]
            if p.slack_bits:
                lines.append(f"🧵 Clean reel bonus included: **+{bits(p.slack_bits)}** bits")
        self.result = Result("The party beat the boss!", lines, emoji="💀", accent=0x7B241C, again=self._cast, again_label="Cast again")
        return True

    async def _join_boss(self, interaction: discord.Interaction) -> None:
        stats = await fishing.rod_stats(self.user)
        try:
            fight = await party_boss.join(self.user, now())
        except party_boss.PartyBossError as error:
            return await self.refresh(interaction, str(error))
        cast = fishing.join_boss_cast(stats, self.rng, now(), fight.boss, get_registry(), await pets.bonuses(self.user))
        cast.party_fight = fight.number
        self.cast, self.missed = cast, None
        await self.refresh(interaction, f"💀 You join the fight with **{fight.boss}**! Reel your own set of arrows.")

    async def _cancel(self, interaction: discord.Interaction) -> None:
        if self.cast is not None and self.cast.party_fight is not None:
            await party_boss.report(self.user, "failed", 0, now())  # you let it go: your part of the fight is over
        self.cast = None
        await self.refresh(interaction, "🎣 You reel the line back in.")

    async def _hook(self, interaction: discord.Interaction) -> None:
        cast, clicked = self.cast, clicked_at(interaction)
        if cast is None:  # a click that was already on its way... or one that was made in time but reached us late
            if self.missed is not None and self.missed.salvage(clicked):
                self.cast, self.missed = self.missed, None
                self.nav.screen = self  # the "too slow" page was wrong: this click was in time, so carry on playing
                return await self.refresh(interaction, "🎣 Got it, just in time!")
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
                note = "👥 **Your party can join this fight!** They will see it on their Fishing page."
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
                self.result = Result("You landed your part!", [f"💀 **{cast.boss}** is hooked! Your reel is done."
                                                                 + (f"\n🧵 Clean reel: **{cast.slips_left}** slack unused." if cast.slips_left else "")
                                                                 + "\nYour reward comes when your party's reels are all in (or the fight ends): it is on your Fishing page."],
                                     emoji="💀", accent=0x7B241C, back_label="Back to fishing")
                return await self.refresh(interaction)
            if result == "landed" and cast.boss:
                self.cast = None
                won = await fishing.defeat_boss(self.user, cast, self.rng)
                reg = get_registry()
                loot = ", ".join(f"{q:,} {reg.item(i).display}" for i, q in won.items.items()) or "nothing"
                slack = f"\n🧵 Clean reel: **{won.slack_left}** slack unused  ·  **+{bits(won.slack_bits)}** bits" if won.slack_bits else ""
                self.result = Result(f"You beat {won.name}!", [f"**+{bits(won.bits)}** bits  ·  **+{won.xp:,}** xp{slack}", f"🎁 Loot: {loot}"],
                                     emoji="💀", accent=0x7B241C, again=self._cast, again_label="Cast again")
                return await self.refresh(interaction)
            if result == "landed":
                self.cast = None
                catch = await fishing.land(self.user, cast, now=now(), rng=self.rng)
                if catch.hallucination:
                    self.flash = (catch.hallucination, now() + get_registry().fishing.treasure.flash_seconds)
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
                self.result = self._lost("🌊 It got away!", lines)
                return await self.refresh(interaction)
            await self.refresh(interaction, "🧵 Wrong way! The line goes slack, but you hold on." if result == "slip" else None)  # (an "echo" is ignored)

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
                loot = ", ".join(f"{q:,} {reg.item(i).display}" for i, q in result.items.items())
                self.result = Result("The lock clicks open!", [f"**+{bits(result.bits)}** bits  ·  **+{result.xp}** xp", f"🎁 Inside: {loot}"],
                                     emoji="🧰", accent=0xF1C40F, again=self._cast, again_label="Cast again")
                return await self.refresh(modal_interaction)
            if result.sunk:
                self.cast = None
                self.result = self._lost("🌊 The chest sinks", ["Wrong numbers, and no tries left. The chest sinks back into the deep…"])
                return await self.refresh(modal_interaction)
            await self.refresh(modal_interaction, f"🔒 Wrong numbers. The lock holds. **{result.attempts_left}** tries left.")

        await interaction.response.send_modal(PromptModal("Unlock the chest", f"The {length} numbers", submitted,
                                                          placeholder="e.g. 4815", max_length=length + 4))

    async def _quests(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fishquests")

    async def _book(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fishbook")

    async def _community(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fishcommunity")

    async def _records(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fishrecords")

    async def _notes(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fishnotes")

    async def _pots(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fishpots")

    async def _mastery(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "mastery", skill="fishing")

    async def _sell_all(self, interaction: discord.Interaction) -> None:
        await start_sell_all(self, interaction, "fishing")

    async def _sell(self, interaction: discord.Interaction) -> None:
        total = await fishing.sell_all(self.user)
        await self.refresh(interaction, f"💰 You sold your fish for **{bits(total)}** bits.")


class FishQuestsScreen(Screen):
    id = "fishquests"
    label = "Fishing Quests"
    emoji = "📜"
    description = "Daily and weekly fishing quests"
    links = ("fish",)

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
    return f"❓ **{len(rarities)}** {what}: " + " · ".join(f"{Rarities.from_value(r).rarity_name} {n}" for r, n in sorted(counts.items()))


class FishBookScreen(Screen):
    id = "fishbook"
    label = "Collection Book"
    emoji = "📖"
    description = "Turn in fish for rewards and level the book up"
    links = ("fish", "fishrecords")

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
            mark = "✅" if e.done else "⬜"
            have = f"  ·  you have {owned[e.fish.id]:,}" if not e.done and owned.get(e.fish.id) else ""
            lines.append(f"{mark} {e.fish.display}  ·  **{e.given}/{e.need}**{have}")
        wanted = [e for e in view.entries if not e.done and owned.get(e.fish.id)]
        body = [
            *self.note_block(),
            text(f"### 📖 Book level {view.level}\n+**{rules.bits_per_sell:.0%}** value and xp on fish you turn in  ·  "
                 f"finishing pays **{bits(rules.completion_bits * view.level)}** bits"),
            text("\n".join("  ·  ".join(lines[i:i + 2]) for i in range(0, len(lines), 2))),
        ]
        if wanted:
            body.append(row(select("Turn in a fish...", [
                discord.SelectOption(label=e.fish.name, value=e.fish.id, emoji=e.fish.emoji or None,
                                     description=f"You have {owned[e.fish.id]:,}, the book needs {e.need - e.given:,} more")
                for e in wanted[:25]], self._turn_in)))
        body.append(row(
            button("Finish the book", emoji="🏆", style=discord.ButtonStyle.success, disabled=not view.complete or view.level >= rules.max_level,
                   on_click=self._finish),
            button("Records", emoji="📏", on_click=self._records),
            button("Back to fishing", emoji=ROD, on_click=self._back),
        ))
        return Page("Collection Book", body, accent=0x8E44AD)

    async def _turn_in(self, interaction: discord.Interaction, values: list[str]) -> None:
        done = await fishing.turn_in(self.user, values[0])
        await self.refresh(interaction, f"📖 You added {done.quantity:,} {done.fish.display} to the book  ·  +{bits(done.bits)} bits, +{done.xp} xp")

    async def _records(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fishrecords")

    async def _finish(self, interaction: discord.Interaction) -> None:
        done = await fishing.complete_book(self.user)
        await self.refresh(interaction, f"🏆 **Book complete!** It is now level {done.new_level}  ·  +{bits(done.bits)} bits, +{done.xp} xp")

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fish")


class FishCommunityScreen(Screen):
    """The server's collection book and this month's goals. Redraws itself so you see everyone's progress."""

    id = "fishcommunity"
    label = "Fishing Community"
    emoji = "🌍"
    description = "The community book and this month's goals"
    links = ("fish", "fishrecords")
    refresh_every = 10.0

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
            notes.append(f"🌍 **The community finished its book** (level {', '.join(map(str, paid.levels))})  ·  "
                         f"+{bits(paid.bits)} bits, +{paid.xp:,} xp for you")
        if paid := await fishing_community.claim_monthly(self.user, now()):
            notes.append("🗓️ **Community goal reached:** " + ", ".join(g.text for g in paid.goals)
                         + f"  ·  +{bits(paid.bits)} bits, +{paid.xp:,} xp")
        if notes:
            self.note = "\n".join(filter(None, [self.note, *notes]))
        body = [*self.note_block()]

        view = await fishing_community.book(self.user)
        owned = await self.user.items()
        body.append(text(f"### 📖 Community Book · level {view.level}\n"
                         + "\n".join(f"{'✅' if p.done else '⬜'} {p.fish.display}  ·  **{p.given}/{p.need}**"
                                      + (f"  ·  you have {owned[p.fish.id]:,}" if not p.done and owned.get(p.fish.id) else "")
                                      for p in view.pages)
                         + f"\n-# You have donated **{view.donated_by_you}** this level. Finishing it pays everyone "
                           f"{bits(rules.community.book.completion_bits * view.level)} bits."))
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
            mark = "✅" if g.done else "⬜"
            pay = "" if g.done else f"  ·  +{bits(g.goal.slot.bits)} bits"
            lines.append(f"{mark} {g.goal.text}\n{bar(min(1.0, g.progress / share), 8)}  **{min(g.progress, share):,}/{share:,}**"
                         f"  ·  you: {g.yours:,}{pay}")
        ends = fishing_community.month_ends_at(fishing_community.month_of(now()))
        body += [sep(), text("### 🗓️ This month's goals\n" + "\n".join(lines)
                             + f"\n-# Everyone fishing adds up. Do at least {rules.community.min_share:.0%} of a goal to be paid when "
                               f"it is reached. New goals <t:{int(ends)}:R>."),
                 row(button("Records", emoji="📏", on_click=self._records),
                     button("Back to fishing", emoji=ROD, on_click=self._back))]
        return Page("Fishing Community", body, accent=0x16A085)

    async def _records(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fishrecords")

    async def _donate(self, interaction: discord.Interaction, values: list[str]) -> None:
        done = await fishing_community.donate(self.user, values[0])
        note = f"📖 You gave {done.quantity:,} {done.fish.display} to the community book  ·  +{bits(done.bits)} bits, +{done.xp:,} xp"
        if done.finished_level:
            note += f"\n🎉 **That finished the book!** It is now level {done.finished_level + 1} and everyone will be paid."
        await self.refresh(interaction, note)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fish")


class FishRecordsScreen(Screen):
    """The biggest of every fish: yours, and the biggest ever caught on the server."""

    id = "fishrecords"
    label = "Fish Records"
    emoji = "📏"
    description = "Your biggest catches and the server records"
    links = ("fish",)

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
            record = f"  ·  🏆 {held['size']:g} cm ({held['name']})" if held else ""
            crown = " 👑" if held and best is not None and held["uid"] == self.user.id and held["size"] == best else ""
            lines.append(f"{fish.display}  ·  {yours}{crown}{record}")
        if unknown:
            lines.append(unknown_summary(unknown, "fish nobody has caught yet"))
        return Page("Fish Records", [*self.note_block(), text("### 📏 Biggest catches\n" + "\n".join(lines)
                    + "\n-# 🏆 server record  ·  👑 that's you  ·  beat a record to be paid."),
                    row(button("Back to fishing", emoji=ROD, on_click=self._back),
                        button("Field notes", emoji="🔍", on_click=self._notes))], accent=0x2980B9)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fish")

    async def _notes(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fishnotes")


class FishNotesScreen(Screen):
    """What each ❓ turned out to be, fish by fish, and what it adds up to."""

    id = "fishnotes"
    label = "Field notes"
    emoji = "🔍"
    description = "What the hidden arrows (❓) turned out to be"
    links = ("fish",)

    async def build(self) -> Page:
        reg = get_registry()
        skill = await self.user.skill("fishing")
        lines, unknown = [], []
        for fish in sorted((i for i in fishing.fish_pool(reg) if i.rarity >= reg.fishing.reel.mystery_from_rarity),
                           key=lambda i: (i.rarity, i.name)):
            entries = skill.notes.get(fish.id, [])
            if entries:
                verdict = fishing.notes_verdict(entries)
                lines.append(f"{fish.display}: {fishing.read_notes(entries)}" + (f"\n-# → {verdict}" if verdict else
                             f"\n-# → {fishing.MIN_NOTES_FOR_VERDICT - len(entries)} more ❓ and I can say what it follows"))
            elif fish.id in skill.records:
                lines.append(f"{fish.display}: no ❓ revealed yet. Press the ❓ (or lose at one) to find out what it was.")
            else:
                unknown.append(fish.rarity)
        if unknown:
            lines.append(unknown_summary(unknown, "not caught yet"))
        intro = ("Rare fish hide arrows behind a ❓. Each fish has its own rule for it: always ◄, always ►, the same as the arrow "
                 "before it, or the opposite (a few are pure luck). Every ❓ you see is written here.")
        return Page("Field notes", [*self.note_block(), text("### 🔍 Field notes\n-# " + intro + "\n" + "\n".join(lines)),
                    row(button("Back to fishing", emoji=ROD, on_click=self._back))], accent=0x2980B9)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fish")


class FishPotsScreen(Screen):
    """Crab pots: craft them, load bait, collect what they caught while you were away."""

    id = "fishpots"
    label = "Crab Pots"
    emoji = "🦀"
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
            lines.append(f"{'➤ ' if i == self.index else ''}🦀 **Pot {i + 1}**  ·  Lv {pot.level}  ·  {water.emoji} {water.name}  ·  {bait}  ·  {status}")
        owned_now = await self.user.items()
        body.append(text(f"### 🦀 Crab pots ({len(skill.pots)}/{slots})\n" + ("\n".join(lines) if lines else "You have no pots yet.")
                    + f"\n-# Pots only catch {Rarities.from_value(rules.pots.min_rarity).rarity_name} fish and better, one at a time, while you are away."))
        if len(skill.pots) < slots:
            body.append(text("**🔨 Craft a pot**\n" + needs_text(rules.pots.craft_bits, self.user.purse, rules.pots.craft_items, owned_now, reg)))
        elif len(skill.pots) < len(rules.pots.slot_levels):
            body.append(text(f"-# Another pot opens at fishing level {rules.pots.slot_levels[len(skill.pots)]}."))
        if len(skill.pots) > 1:
            body.append(row(select("Pick a pot...", [
                discord.SelectOption(label=f"Pot {i + 1} · Lv {p.level}", value=str(i), default=i == self.index,
                                     description=fishing.water_by_id(reg, p.water).name) for i, p in enumerate(skill.pots)], self._pick)))
        buttons = [button("Collect all", emoji="🧺", style=discord.ButtonStyle.success,
                          disabled=not any(pots.ready(p, here, reg, pet) for p in skill.pots), on_click=self._collect)]
        if skill.pots:
            pot = skill.pots[self.index]
            if pot.level < len(rules.pots.levels):
                cost = rules.pots.levels[pot.level]
                buttons.append(button(f"Upgrade pot {self.index + 1}", emoji="⬆️", on_click=self._upgrade))
                body.append(text(f"**⬆️ Upgrade pot {self.index + 1} to level {pot.level + 1}**\n"
                                 + needs_text(cost.upgrade_bits, self.user.purse, cost.upgrade_items, owned_now, reg)))
            worth = pots.hourly_value(pot, reg, pet)
            body.append(text(f"-# Pot {self.index + 1} catches about one fish every **{pots.interval_seconds(pot, reg, pet) / 60:.0f}** minutes "
                             f"(holds {pots.level_rules(pot, rules).capacity}), worth about **{bits(round(worth))}** bits an hour. "
                             f"Fishing yourself earns far more."))
        buttons.append(button("Craft a pot", emoji="🔨", disabled=len(skill.pots) >= slots, on_click=self._craft))
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
                for w in fishing.unlocked_waters(level, rules)], self._water)))
        return Page("Crab Pots", body, accent=0xD35400)

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.index = int(values[0])
        await self.refresh(interaction)

    async def _craft(self, interaction: discord.Interaction) -> None:
        await pots.craft(self.user, now())
        self.index = len((await self.user.skill("fishing")).pots) - 1
        await self.refresh(interaction, "🦀 You crafted a crab pot! Load some bait to get it fishing.")

    async def _upgrade(self, interaction: discord.Interaction) -> None:
        pot = await pots.upgrade(self.user, self.index)
        await self.refresh(interaction, f"⬆️ Pot {self.index + 1} is now level {pot.level}.")

    async def _bait(self, interaction: discord.Interaction, values: list[str]) -> None:
        bait_id, index = values[0], self.index
        reg = get_registry()
        have = await self.user.item_quantity(bait_id)

        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            quantity = have if raw.strip().lower() in ("all", "") else int(raw.replace(",", "") or 0)
            loaded, returned = await pots.load_bait(self.user, index, bait_id, quantity, now())
            note = f"🪱 Loaded {loaded:,} {reg.item(bait_id).display} into pot {index + 1}."
            if returned:
                note += f" The {returned:,} left of the old bait came back to you."
            await self.refresh(modal_interaction, note)

        await interaction.response.send_modal(PromptModal(f"Load {reg.item(bait_id).name}", f"How many? (you have {have:,})", submitted,
                                                          default=str(have), max_length=9))

    async def _water(self, interaction: discord.Interaction, values: list[str]) -> None:
        await pots.set_water(self.user, self.index, values[0], now())
        await self.refresh(interaction, f"🦀 Pot {self.index + 1} moved to {fishing.water_by_id(get_registry(), values[0]).name}.")

    async def _collect(self, interaction: discord.Interaction) -> None:
        reg = get_registry()
        haul = await pots.collect_all(self.user, now())
        if not haul.catches:
            return await self.refresh(interaction, "🦀 Nothing has been caught yet.")
        fish = ", ".join(f"{q:,} {reg.item(i).display}" for i, q in sorted(haul.fish.items(), key=lambda kv: -reg.item(kv[0]).rarity))
        worth = sum(reg.item(i).sell_price * q for i, q in haul.fish.items())
        self.result = Result("The pots are emptied!", [f"🧺 {fish}", f"Worth about **{bits(worth)}** bits  ·  **+{haul.xp:,}** xp"],
                             emoji="🦀", accent=0xD35400, back_label="Back to the pots")
        await self.refresh(interaction)
