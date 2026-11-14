import datetime
import random
import time

import discord

from cococap.constants import Rarities
from cococap.registry import get_registry
from cococap.services import fishing, fishing_community
from cococap.services.equipment import equipped_stats
from cococap.services.party import xp_bonus
from cococap.ui import Page, PromptModal, Result, Screen
from cococap.ui.components import bar, bits, button, row, select, sep, text, xp_bar
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


def pattern_line(cast: fishing.Cast) -> str:
    """Arrows already pressed turn into ticks; the next one is bold."""
    left = cast.pattern[cast.progress:]
    done = "✅" * cast.progress
    todo = f"**{left[0]}**" + (" " + " ".join(left[1:]) if len(left) > 1 else "") if left else ""
    return f"{done} {todo}".strip()


def quest_line(q: fishing.Quest) -> str:
    mark = "✅" if q.done else "⬜"
    progress = "done" if q.done else f"{q.progress}/{q.count}"
    return f"{mark} {q.text}  ·  {progress}  ·  +{bits(q.bits)} bits, +{q.xp} xp"


class FishScreen(Screen):
    id = "fish"
    label = "Fishing"
    emoji = ROD
    description = "Cast a line and reel in fish"
    links = ("fishquests", "fishbook", "fishcommunity", "fishrecords")

    def __init__(self, nav):
        super().__init__(nav)
        self.cast: fishing.Cast | None = None
        self.flash: tuple[str, float] | None = None  # (the hallucination's numbers, when they fade)
        self.water: str | None = None  # where you are fishing (None = the best water you have opened)
        self.missed: fishing.Cast | None = None  # a fish written off as too slow, which a late-arriving click can still save
        self.rng = new_rng()

    @property
    def refresh_every(self) -> float | None:  # redraw by itself while a line is in the water or numbers are flashing
        return REFRESH if self.cast is not None or self.flash is not None else None

    async def build(self) -> Page:
        reg = get_registry()
        cast = self.cast
        if cast is not None and cast.status(now()) == "escaped":
            if cast.timed_out:
                self.missed = cast  # kept for a moment: a click made in time may still be on its way
            self.cast, cast = None, None  # nobody picked up the line in time
            self.result = self._lost("🌊 Too slow!", ["It bit, but nobody pulled up the line in time. The fish got away."])
        if self.flash is not None and now() >= self.flash[1]:
            self.flash = None  # the numbers have faded
            extra = "🌫️ The numbers slip away… hold on to what you remember."
            self.note = f"{self.note}\n{extra}" if self.note else extra
        stats = await equipped_stats(self.user, "fishing")
        body = [*self.note_block()]
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
            if stats is None:
                body.append(text("🎣 You need a rod. Buy a **Starter Rod** in the shop and it equips itself."))
            else:
                slips = fishing.slips_allowed(stats.power, reg.fishing, stats.stats.get("slips", 0))
                body.append(text(f"{ROD} Rod power **{stats.power}**" + (f"  ·  forgives **{slips}** wrong arrow(s)" if slips else "")))
            level = User.xp_to_level(skill.xp)
            open_waters = fishing.unlocked_waters(level, reg.fishing)
            if self.water not in {w.id for w in open_waters}:
                self.water = open_waters[-1].id  # a newly opened water is where you head next
            here = fishing.water_by_id(reg, self.water)
            body.append(text(f"{here.emoji} **{here.name}**  ·  {here.description}"))
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
            body.append(row(button("Records", emoji="📏", on_click=self._records)))
            return Page("Fishing", body, accent=ACCENT)

        status = cast.status(now())
        if status == "waiting":
            body += [text("### 🌊 The line is in the water…\nWait for a bite. A stronger rod bites sooner."),
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

        if cast.boss:
            slack = f"\n🧵 Slack left: **{cast.slips_left}**" if cast.slips_left else ""
            body += [
                text(f"### 💀 **{cast.boss}** is on the line!\nA boss! No fish this time, but a mountain of loot if you land it.\n"
                     f"{pattern_line(cast)}{slack}\n-# {len(cast.pattern)} arrows. Don't slip!"),
                row(button("Left", emoji="◀️", style=discord.ButtonStyle.danger, on_click=self._press(fishing.LEFT)),
                    button("Right", emoji="▶️", style=discord.ButtonStyle.danger, on_click=self._press(fishing.RIGHT)),
                    button("Let it go", on_click=self._cancel)),
            ]
            return Page("Fishing", body, accent=0x7B241C)

        # reeling it in
        colour = Rarities.from_value(cast.fish.rarity)
        slack = f"\n🧵 Slack left: **{cast.slips_left}**" if cast.slips_left else ""
        body += [
            text(f"### 🎣 A **{colour.rarity_name}** fish is on the line!\n{pattern_line(cast)}{slack}\n"
                 f"-# Press the arrows in this order."),
            row(button("Left", emoji="◀️", style=discord.ButtonStyle.primary, on_click=self._press(fishing.LEFT)),
                button("Right", emoji="▶️", style=discord.ButtonStyle.primary, on_click=self._press(fishing.RIGHT)),
                button("Let it go", on_click=self._cancel)),
        ]
        return Page("Fishing", body, accent=int(colour.color, 16))

    # ---- what happened ---------------------------------------------------------------------------
    def _lost(self, title: str, lines: list[str]) -> Result:
        return Result(title, lines + ["Nothing was lost but the fish. Try again!"], emoji="🌊", accent=0x5D6D7E,
                      again=self._cast, again_label="Cast again")

    def _catch_result(self, catch: fishing.Catch) -> Result:
        reg = get_registry()
        rarity = Rarities.from_value(catch.fish.rarity)
        lines = [f"**{rarity.rarity_name}**  ·  📏 **{catch.size:g} cm**  ·  worth **{bits(catch.fish.sell_price)}** bits  ·  **+{catch.xp:,}** xp"]
        if catch.server_record:
            lines.append(f"🏆 **NEW SERVER RECORD!** +{bits(catch.record_bits)} bits"
                         + (f" (you beat {catch.record_holder})" if catch.record_holder else ""))
        elif catch.personal_best:
            lines.append("🏅 New personal best!")
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
        self.cast = fishing.cast_line(stats, self.rng, now(), armed=armed, water=water)
        await self.refresh(interaction)

    async def _pick_water(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.water = values[0]
        await self.refresh(interaction)

    async def _cancel(self, interaction: discord.Interaction) -> None:
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
            return await self.refresh(interaction, str(error))
        await self.refresh(interaction)

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
            if result == "landed" and cast.boss:
                self.cast = None
                won = await fishing.defeat_boss(self.user, cast, self.rng)
                reg = get_registry()
                loot = ", ".join(f"{q:,} {reg.item(i).display}" for i, q in won.items.items()) or "nothing"
                self.result = Result(f"You beat {won.name}!", [f"**+{bits(won.bits)}** bits  ·  **+{won.xp:,}** xp", f"🎁 Loot: {loot}"],
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
                what = cast.boss or f"The {cast.fish.display}"
                self.result = self._lost("🌊 It got away!", [f"Wrong way! {what} slipped off the hook."])
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
            text(f"### 📖 Book level {view.level}\nTurn fish in for **+{rules.bits_per_sell:.0%}** of their value and xp. "
                 f"Fill every page to finish the book: it pays **{bits(rules.completion_bits * view.level)}** bits and the next level "
                 f"needs more fish, a lot more of the common ones."),
            text("\n".join(lines)),
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
        lines = []
        for fish in sorted(fishing.fish_pool(reg), key=lambda i: (i.rarity, i.name)):
            best, held = mine.get(fish.id), server.get(fish.id)
            if best is None and held is None:
                lines.append(f"▫️ ???  ·  {Rarities.from_value(fish.rarity).rarity_name}  ·  nobody has caught one yet")
                continue
            yours = f"you **{best:g} cm**" if best is not None else "you: not caught yet"
            record = f"  ·  🏆 {held['size']:g} cm ({held['name']})" if held else ""
            crown = " 👑" if held and best is not None and held["uid"] == self.user.id and held["size"] == best else ""
            lines.append(f"{fish.display}  ·  {yours}{crown}{record}")
        return Page("Fish Records", [*self.note_block(), text("### 📏 Biggest catches\n" + "\n".join(lines)
                    + "\n-# 🏆 is the biggest ever caught on the server, 👑 means that's you. Beat a record to be paid."),
                    row(button("Back to fishing", emoji=ROD, on_click=self._back))], accent=0x2980B9)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fish")
