import random
import time

import discord

from cococap.constants import Rarities
from cococap.registry import get_registry
from cococap.services import fishing
from cococap.services.equipment import equipped_stats
from cococap.services.party import xp_multiplier
from cococap.ui import Page, Screen
from cococap.ui.components import bits, button, row, select, sep, text, xp_bar
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


def pattern_line(cast: fishing.Cast) -> str:
    """Arrows already pressed turn into ticks; the next one is bold."""
    left = cast.pattern[cast.progress:]
    done = "✅" * cast.progress
    todo = f"**{left[0]}**" + (" " + " ".join(left[1:]) if len(left) > 1 else "") if left else ""
    return f"{done} {todo}".strip()


def quest_line(q: fishing.Quest) -> str:
    mark = "✅" if q.done else "⬜"
    progress = "done" if q.done else f"{q.progress}/{q.template.count}"
    return f"{mark} {q.text}  ·  {progress}  ·  +{bits(q.template.bits)} bits, +{q.template.xp} xp"


class FishScreen(Screen):
    id = "fish"
    label = "Fishing"
    emoji = ROD
    description = "Cast a line and reel in fish"
    links = ("fishquests", "fishbook")

    def __init__(self, nav):
        super().__init__(nav)
        self.cast: fishing.Cast | None = None
        self.rng = new_rng()

    @property
    def refresh_every(self) -> float | None:  # redraw by itself only while a line is in the water
        return REFRESH if self.cast is not None else None

    async def build(self) -> Page:
        reg = get_registry()
        cast = self.cast
        if cast is not None and cast.status(now()) == "escaped":
            self.cast, cast = None, None  # nobody picked up the line in time
            extra = "🌊 The fish got away. You were too slow!"
            self.note = f"{self.note}\n{extra}" if self.note else extra
        stats = await equipped_stats(self.user, "fishing")
        body = [*self.note_block()]

        if cast is None:
            skill = await self.user.skill("fishing")
            overflow, needed = User.xp_for_next_level(skill.xp)
            header = f"**Level {User.xp_to_level(skill.xp)}**  {xp_bar(overflow / needed if needed else 0)}  {overflow:,}/{needed:,} xp"
            if await xp_multiplier(self.user.id) > 1:
                header += f"\n👥 Party bonus: **+{reg.economy.party_xp_bonus:.0%}** xp"
            body.append(text(header))
            if stats is None:
                body.append(text("🎣 You need a rod. Buy a **Starter Rod** in the shop and it equips itself."))
            else:
                slips = fishing.slips_allowed(stats.power, reg.fishing)
                body.append(text(f"{ROD} Rod power **{stats.power}**" + (f"  ·  forgives **{slips}** wrong arrow(s)" if slips else "")))
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
            ))
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

    # ---- handlers --------------------------------------------------------------------------------
    async def _cast(self, interaction: discord.Interaction) -> None:
        stats = await fishing.rod_stats(self.user)
        self.cast = fishing.cast_line(stats, self.rng, now())
        await self.refresh(interaction)

    async def _cancel(self, interaction: discord.Interaction) -> None:
        self.cast = None
        await self.refresh(interaction, "🎣 You reel the line back in.")

    async def _hook(self, interaction: discord.Interaction) -> None:
        cast = self.cast
        if cast is None:  # a click that was already on its way
            return await self.refresh(interaction)
        try:
            cast.hook(now())
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
                result = cast.press(arrow, now())
            except fishing.FishingError as error:
                if cast.escaped or cast.progress >= len(cast.pattern):
                    self.cast = None
                return await self.refresh(interaction, str(error))
            if result == "landed":
                self.cast = None
                catch = await fishing.land(self.user, cast, now=now())
                note = f"🎣 **You caught a {catch.fish.display}!**  ·  +{catch.xp:,} xp  ·  worth {bits(catch.fish.sell_price)} bits"
                if catch.extras:
                    note += "\n🪸 Also washed up: " + ", ".join(f"{q:,} {get_registry().item(i).display}" for i, q in catch.extras.items())
                for q in catch.finished:
                    note += f"\n📜 **Quest complete:** {q.text}  ·  +{bits(q.template.bits)} bits, +{q.template.xp} xp"
                return await self.refresh(interaction, note)
            if result == "escaped":
                self.cast = None
                return await self.refresh(interaction, f"🌊 Wrong way! The {cast.fish.display} slipped off the hook.")
            await self.refresh(interaction, "🧵 Wrong way! The line goes slack, but you hold on." if result == "slip" else None)

        return press

    async def _quests(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fishquests")

    async def _book(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fishbook")

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
    links = ("fish",)

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
                 f"needs more of each fish."),
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
            button("Back to fishing", emoji=ROD, on_click=self._back),
        ))
        return Page("Collection Book", body, accent=0x8E44AD)

    async def _turn_in(self, interaction: discord.Interaction, values: list[str]) -> None:
        done = await fishing.turn_in(self.user, values[0])
        await self.refresh(interaction, f"📖 You added {done.quantity:,} {done.fish.display} to the book  ·  +{bits(done.bits)} bits, +{done.xp} xp")

    async def _finish(self, interaction: discord.Interaction) -> None:
        done = await fishing.complete_book(self.user)
        await self.refresh(interaction, f"🏆 **Book complete!** It is now level {done.new_level}  ·  +{bits(done.bits)} bits, +{done.xp} xp")

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fish")
