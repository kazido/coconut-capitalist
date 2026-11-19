import asyncio
import random
import time
from collections import Counter

import discord

from cococap.constants import PROJECT_ROOT
from cococap.registry import get_registry
from cococap.services import mining
from cococap.services import odds
from cococap.ui import flair
from cococap.ui.rewards import rewards_result
from cococap.ui import Page, PromptModal, ResultScreen, Screen
from cococap.ui.components import bar, button, row, sep, text

from cococap import emojis

# Map emojis come from the bot's application emojis (by name); the plain emoji is the fallback.
def _cell() -> str: return emojis.get("cell", "⬛")
def _cell_empty() -> str: return emojis.get("cell_empty", "▫️")
def _rich() -> str: return emojis.icon("rock_rich", "🟦")
def _hole() -> str: return emojis.icon("wyrmhole", "🌀")
def _wyrm_rock() -> str: return emojis.icon("rock_wyrm", "🟪")  # a hidden cell inside a wyrmhole
def _vent() -> str: return emojis.icon("vent", "💨")
def _cache() -> str: return emojis.icon("cache", "📦")
def _bomb() -> str: return emojis.icon("bomb", "💣")
def _cursor() -> str: return emojis.icon("cursor", "🔻")
def _soft() -> str: return emojis.icon("rock_soft", "🟫")
def _firm() -> str: return emojis.icon("rock_firm", "🟧")
def _hard() -> str: return emojis.icon("rock_hard", "🟥")  # the rock from above: soft (little pressure, copper), firm (iron), hard (a lot of pressure, the top ore)
NOTCH = "▪️"  # plain fallback kept for importers; mine.py itself draws _notch()


def _notch() -> str:
    return emojis.icon("pip", "▪️")
def _milestone() -> str: return emojis.icon("milestone", "🏁")  # a landmark row: finish it and the tunnel is shored up
def _vault() -> str: return emojis.icon("vault", "🏆")  # the last row: the vault is worth getting to
def _magnet() -> str: return emojis.icon("magnet", "✨")
ACCENT = {"Calm": 0x2ECC71, "Tremors": 0xF1C40F, "Unstable": 0xE67E22, "Critical": 0xE74C3C}
SHOWN_ROWS = 1  # rows you've already passed that stay on screen


def _words() -> list[str]:
    path = PROJECT_ROOT / "resources" / "unscramble_words.txt"
    return [w.strip() for w in path.read_text().splitlines() if len(w.strip()) >= 5]


def item_emoji(item_id: str) -> str:
    return get_registry().item(item_id).emoji or emojis.icon('sq_brown', '🟫')


def loot_lines(loot: Counter) -> str:
    reg = get_registry()
    lines = []
    for item_id, quantity in loot.items():
        item = reg.item(item_id)
        lines.append(f"{item_emoji(item_id)} +{quantity:,} " + (f"**{item.name}**" if item.rarity >= 5 else item.name))
    if fanfare := flair.banner(loot):
        lines.append(fanfare)
    return "\n".join(lines)


def cell_emoji(feel: str) -> str:
    """A cell as it feels from above: soft, firm or hard rock, a highlighted rich lode, or a wyrmhole. You cannot tell ore, nothing, vents and
    caches apart inside the same kind of rock, only how hard it is."""
    return {"rich": _rich(), "hole": _hole(), "soft": _soft(), "firm": _firm(), "hard": _hard()}.get(feel) or _cell()


def dug_emoji(sign: str, cell) -> str:
    """A cell you dug, now revealed: its vent, its cache, its ore, or nothing."""
    if sign == "vent":
        return _vent()
    if sign == "cache":
        return _cache()
    return item_emoji(cell[0]) if cell else _cell_empty()


def row_mark(run: mining.MineRun, depth: int) -> str:
    """A landmark beside a row you can see ahead: 🏁 on a milestone row, 🏆 on the last one (the vault)."""
    if depth == run.floor - 1:
        return f"  {_vault()} vault"
    if any(m.row == depth + 1 for m in run.rules.descent.milestones):
        return f"  {_milestone()} checkpoint"
    return ""


def next_landmark(run: mining.MineRun) -> str:
    """"🏁 row 10 (3 to go)" or "🏆 the vault (12 to go)": what you are digging toward."""
    for m in run.rules.descent.milestones:
        if m.row > run.depth:
            return f"{_milestone()} checkpoint at row {m.row} ({m.row - run.depth} to go)"
    return f"{_vault()} the vault ({run.floor - run.depth} to go)"


def render_shaft(run: mining.MineRun) -> str:
    """A cursor line, then the rows ahead with everything visible (the row you just dug is not shown)."""
    columns = run.rules.columns
    lines = []
    for dug in (run.history[-SHOWN_ROWS:] if run.finished else []):  # (a live mine shows only the rows AHEAD, so the view does not jump after every dig)
        # What you dug shows what it gave; what you left behind stays as it looked.
        lines.append("".join(
            dug_emoji(dug.kinds[c], dug.cells[c]) if c in dug.dug else cell_emoji(run.feel(dug.depth)[c])
            for c in range(columns)
        ))
    if not run.finished:
        header = [_notch()] * columns
        for col in run.vent_columns():
            header[col] = _vent()  # the magnet shows where the vents are (it never aims at them)
        for col in run.best_columns():
            header[col] = _magnet()
        for col in run.cursors:
            header[col] = _cursor()
        lines.append("".join(header))
        for ahead in range(run.rules.descent.lookahead):
            depth = run.depth + ahead
            if depth >= run.floor:
                break
            lines.append("".join(cell_emoji(feel) for feel in run.feel(depth)) + row_mark(run, depth))
    return "\n".join(lines)


def type_line(run: mining.MineRun) -> str:
    """The kind of mine this is: just its name for a Standard mine, the name and what it does for any other."""
    t = run.mine_type
    place = next((loc for loc in run.registry.locations.get("mining", []) if loc.id == run.site.id), None)
    return (f"{place.emoji} **{place.name}**  ·  " if place else "") + f"{t.emoji} **{t.name}**" + ("" if t.id == "standard" else f"  ·  {t.description}")


def risk_text(risk: float) -> str:
    """The collapse chance for the next dig. "0%" only ever means exactly zero."""
    if risk <= 0:
        return "0%"
    return "<1%" if risk < 0.005 else f"{risk:.0%}"


def carrying(haul: Counter) -> str:
    if not haul:
        return "-# Nothing in your pack yet."
    return f"{emojis.icon('haul', '🎒')} " + "  ".join(f"{item_emoji(i)} {q:,}" for i, q in haul.items())


HELP = (
    f"Read the rock: {_soft()} **soft** (little pressure, mostly copper)  ·  {_firm()} **firm** (iron)  ·  {_hard()} **hard** (a lot of pressure, the top ore).\n"
    "Inside it hides ore, nothing, a **vent** that cools the tunnel, or a **cache** with a brace.\n"
    "cell_upgraded: a **rich lode**, a mystery with better loot  ·  wyrmhole: dig it to drop into a hole of treasure (what you carry is banked)\n"
    f"{_bomb()} **bomb**: clears a whole row  ·  {_magnet()} the magnet aims at the richest column and marks vents while it has fuel"
)


class MineScreen(Screen):
    id = "mine"
    label = "The Mines"
    emoji = emojis.Lazy("ui_skill_mining", "⛏️")
    description = "Dig deeper for rarer loot, but watch the danger meter"
    links = ("mining", "reactor")

    def __init__(self, nav):
        super().__init__(nav)
        self.run: mining.MineRun | None = None  # set when the player enters the mines
        self.summary: mining.RunSummary | None = None
        self.challenge: mining.ScarabChallenge | None = None
        self.challenge_deadline = 0.0
        self.scarab_result: str | None = None
        self.show_help = False
        self.hole: mining.WyrmholeSession | None = None  # the wyrmhole mini mine you are digging, if any

    @property
    def locked(self) -> bool:
        return (self.run is not None and not self.run.finished) or (self.hole is not None and not self.hole.finished)

    @property
    def hides_nav(self) -> bool:
        return self.locked  # "Leave & bank" is the way out while a run is live

    async def on_abandon(self) -> None:
        if self.hole is not None and not self.hole.finished:
            await mining.finish_wyrmhole(self.user, self.hole)  # walking away still takes your pick
        if self.run is not None and not self.run.finished:
            await mining.abandon_run(self.user, self.run)

    # ---- rendering ----------------------------------------------------------------------------
    async def build(self) -> Page:
        run = self.run
        if self.hole is not None:
            return self._hole_page(self.hole)
        if run is None:
            return Page("The Mines", [text("Head into the mines from the Mining page.")])
        if run.finished:
            return await self._finished_page()
        warning = run.warning
        body = [
            *self.note_block(),
            text(type_line(run)),
            text(f"**Row {run.depth + 1} of {run.floor}**  ·  {next_landmark(run)}     {warning.emoji} **{risk_text(run.risk)}** collapse risk"
                 + (f"\n{emojis.icon('bomb', '💣')} Auto-Bomb: **{'this dig!' if run.auto_bomb_in == 1 else f'in {run.auto_bomb_in} rows'}**" if run.auto_bomb_every else "")
                 + (f"\n{_magnet()} Magnet: **{run.magnet_rows_left}** rows of fuel" if run.magnet_rows_left is not None else "")
                 + ((f"\n{emojis.icon('lifeline', '🛟')} Lifeline: **used**" if run.lifeline_fired else f"\n{emojis.icon('lifeline', '🛟')} Lifeline: **ready**" if run.lifeline_ready else f"\n{emojis.icon('lifeline', '🛟')} Lifeline: recharging (not this mine)") if run.lifeline else "")),
            text(render_shaft(run)),
            text(carrying(run.haul)),
        ]
        if self.show_help:
            body.append(text(HELP.replace("cell_upgraded", _rich()).replace("wyrmhole:", f"{_hole()}:")))
        body.append(row(
            button(emoji=emojis.icon('prev', '⬅️'), on_click=self._move(-1)),
            button("Dig", emoji=emojis.icon("dig", "⛏️"), style=discord.ButtonStyle.primary, on_click=self._dig),
            button(emoji=emojis.icon('next', '➡️'), on_click=self._move(1)),
        ))
        extra = [button(f"Brace ({run.braces})", emoji=emojis.icon("brace", "🛡️"), disabled=run.braces == 0 or run.danger == 0, on_click=self._brace)]
        if run.bombs or run.bombs_used:
            extra.append(button(f"Bomb ({run.bombs})", emoji=_bomb(), disabled=run.bombs == 0, on_click=self._bomb))
        extra.append(button("Leave & bank", emoji=emojis.icon("haul", "🎒"), style=discord.ButtonStyle.success, on_click=self._leave))
        extra.append(button(
            "Hide tips" if self.show_help else "Tips", emoji=emojis.icon("tips", "❔"),
            style=discord.ButtonStyle.primary if self.show_help else discord.ButtonStyle.secondary,
            on_click=self._toggle_help,
        ))
        body.append(row(*extra))
        return Page("The Mines", body, accent=ACCENT.get(warning.name, 0x9E492F))

    async def _finished_page(self) -> Page:
        run, summary = self.run, self.summary
        titles = {"left": (f"{emojis.icon('haul', '🎒')} You climbed out safely", 0x2ECC71),
                  "collapse": (f"{emojis.icon('boom', '💥')} The mine collapsed!", 0xE74C3C),
                  "wyrmhole": (f"{emojis.icon('wyrmhole', '🌀')} You broke into a wyrmhole!", 0x9B59B6),
                  "floor": (f"{_vault()} You reached the vault!", 0xF1C40F)}
        title, accent = titles[run.outcome]
        body = [*self.note_block(), text(f"## {title}")]
        if summary is not None:
            body.append(text(f"Row **{summary.depth}** of {run.floor}  ·  **{summary.lodes}** lodes dug"))
            if not summary.haul:
                body.append(text("Nothing to bank this time."))
        if self.challenge is not None:
            body += [sep(), text(f"{emojis.icon('scarab', '🪲')} **A subterranean scarab appears!** It holds a scroll: **{self.challenge.scrambled}**\n"
                                 f"Unscramble it before <t:{int(self.challenge_deadline)}:R> and it will reward you!"),
                     row(button("Answer", emoji=emojis.icon("scroll", "📜"), style=discord.ButtonStyle.primary, on_click=self._ask_scarab),
                         button("Ignore", on_click=self._skip_scarab))]
        elif self.scarab_result:
            body += [sep(), text(self.scarab_result)]
        actions = [button("Mine again", emoji=emojis.icon("again", "🔄"), style=discord.ButtonStyle.primary, on_click=self._again)]
        if run.outcome == "wyrmhole":
            actions.insert(0, button("Enter the wyrmhole", emoji=emojis.icon("wyrmhole", "🌀"), style=discord.ButtonStyle.success, on_click=self._wyrmhole))
        body.append(row(*actions))
        return Page("The Mines", body, accent=accent)

    # ---- actions: each calls the service, then redraws ----------------------------------------------------
    def _move(self, step: int):
        async def move(interaction: discord.Interaction) -> None:
            if not self.run.finished:
                self.run.move(step)
            await self.refresh(interaction)

        return move

    async def _dig(self, interaction: discord.Interaction) -> None:
        if self.run.finished:  # a second click that was already on its way when the mine ended
            return await self.refresh(interaction)
        await self._after(interaction, self.run.dig())

    async def _bomb(self, interaction: discord.Interaction) -> None:
        if self.run.finished:
            return await self.refresh(interaction)
        result = await mining.use_bomb(self.user, self.run)
        await self._after(interaction, result)

    async def _after(self, interaction: discord.Interaction, result: mining.DigResult) -> None:
        reg = get_registry()
        found = ", ".join(f"{q:,} {reg.item(i).name}" for i, q in result.found.items())
        auto = f"{emojis.icon('bomb', '💣')} **Auto-Bomb!** " if result.auto_bombed else ""
        multi = f"{emojis.icon('pickaxe', '⛏️')}{emojis.icon('pickaxe', '⛏️')} **Multi-Mine!** (+{len(result.multi)} column) " if result.multi else ""
        if result.collapsed:
            lost = ", ".join(f"{q:,} {reg.item(i).name}" for i, q in result.lost.items())
            note = "The tunnel gave way!" + (f" You lost {lost}." if lost else "")
        else:
            note = auto + multi + (f"{emojis.icon('boom', '💥')} BOOM! " if result.bombed and not result.auto_bombed else "") + (f"Found {found}." if found else ("" if result.wyrmhole else "Nothing here."))
            if result.lifeline:
                lost_text = ", ".join(f"{q:,} {reg.item(i).name}" for i, q in result.lifeline_lost.items())
                note = f"{emojis.icon('lifeline', '🛟')} **Lifeline!** The reactor held the tunnel when it would have collapsed" + (f" (it cost you {lost_text})" if lost_text else "") + ". " + note
            if not self.run.finished and (fanfare := flair.banner(result.found)):  # (a mine that just ended shows its finds on the reward screen)
                note += "\n" + fanfare + "\n"
            if result.vented:
                note += " The vent hisses; the tunnel cools."
            if result.caches:
                note += f" Supplies! +{result.caches} brace."
            if result.milestone:
                m = result.milestone
                extra = ""
                if m.relief:
                    extra += f" Pressure -{m.relief:g}."
                if m.braces:
                    extra += f" +{m.braces} brace."
                if result.milestone_haul:
                    extra += " A taste of the vault: " + ", ".join(f"{q:,} {reg.item(i).name}" for i, q in result.milestone_haul.items()) + "."
                note += f" {_milestone()} **Row {m.row}: checkpoint!** What is in your pack is safe from a collapse now.{extra}"
            if result.vault:
                note += " The vault opens: " + ", ".join(f"{q:,} {reg.item(i).name}" for i, q in result.vault.items()) + "."
        if self.run.finished:
            await self._end(note)
        await self.refresh(interaction, note)

    async def _toggle_help(self, interaction: discord.Interaction) -> None:
        self.show_help = not self.show_help
        await self.refresh(interaction)

    async def _brace(self, interaction: discord.Interaction) -> None:
        if self.run.finished:
            return await self.refresh(interaction)
        self.run.brace()
        await self.refresh(interaction, "You brace the tunnel. The risk falls.")

    async def _leave(self, interaction: discord.Interaction) -> None:
        if self.run.finished:
            return await self.refresh(interaction)
        self.run.leave()
        await self._end(None)
        await self.refresh(interaction)

    async def _end(self, note: str | None) -> None:
        """The run is over: bank it, and maybe a scarab shows up (after any mine, however it ended)."""
        self.summary = await mining.settle_run(self.user, self.run)
        rules = get_registry().mining
        if mining.scarab_appears(rules, random.Random()):
            self.challenge = mining.make_scarab(_words(), rules, random.Random())
            self.challenge_deadline = time.time() + self.challenge.seconds
            self._arm_scarab_timer()
        self._show_loot(note)

    def _arm_scarab_timer(self) -> None:
        """When the scroll's time runs out, the scarab leaves by itself: the page shows the word and Mine again unlocks.
        (Without this the page just sat there, its Discord timestamp counting up "x seconds ago".)"""
        challenge = self.challenge

        async def expire() -> None:
            await asyncio.sleep(max(0.0, self.challenge_deadline - time.time()))
            await self.nav.redraw_by_itself(lambda: self._expire_scarab(challenge))

        self._scarab_timer = asyncio.get_running_loop().create_task(expire())  # (kept so the task is not garbage-collected)

    def _expire_scarab(self, challenge: mining.ScarabChallenge) -> Screen | None:
        """The scroll's time is up: the scarab scuttles off. Returns the screen to redraw, or None if nothing to do."""
        if self.challenge is not challenge:
            return None  # already answered or ignored (or a new mine started)
        self.challenge = None
        self.scarab_result = f"{emojis.icon('scarab', '🪲')} Too slow! The scarab scuttled away. (It was **{challenge.word}**.)"
        shown = self.nav.screen
        if not (isinstance(shown, ResultScreen) and shown.origin is self):
            return None  # the player left the loot page: the mine page shows the result on its next draw
        self._show_loot()
        return self

    def _show_loot(self, note: str | None = None) -> None:
        """Build the reward screen of the finished mine (separate from `_end` so a scarab turning up later can be added to it)."""
        summary = self.summary
        titles = {"left": "You climbed out safely", "collapse": "The mine collapsed!", "wyrmhole": "You broke into a wyrmhole!", "floor": "You reached the vault!"}
        # The reward screen is the LAST screen of a mine: the next action starts from it (on the last rare-drop page when there are rare drops).
        choices: list[tuple[str, str, object]] = []
        if self.run.outcome == "wyrmhole":
            choices.append(("Enter the wyrmhole", emojis.icon("wyrmhole", "🌀"), self._wyrmhole))
        notes = []
        if self.challenge is not None:
            notes.append(f"{emojis.icon('scarab', '🪲')} **A subterranean scarab appears!** It holds a scroll: **{self.challenge.scrambled}**\n"
                         f"Unscramble it before <t:{int(self.challenge_deadline)}:R> and it will reward you!")
            choices += [("Answer", emojis.icon("scroll", "📜"), self._ask_scarab), ("Ignore", emojis.icon("cross", "✖️"), self._skip_scarab)]
        elif self.scarab_result:
            notes.append(self.scarab_result)  # (the scarab left: time ran out)
        self.result = rewards_result(
            titles[self.run.outcome], items=summary.haul, xp=summary.xp, notes=notes,
            headline=[f"Row **{summary.depth}** of {self.run.floor}  ·  **{summary.lodes}** lodes dug", *filter(None, [note])],
            odds=odds.mining(depth=summary.depth), emoji=emojis.icon("dig", "⛏️"), accent=0x2ECC71 if self.run.outcome != "collapse" else 0xE74C3C,
            again=self._again, again_label="Mine again", back=self._to_menu, back_label="Mining page", actions=choices,
            again_locked=self.challenge is not None)  # (a scarab waits: answer or ignore it first)

    async def _ask_scarab(self, interaction: discord.Interaction) -> None:
        async def submitted(modal_interaction: discord.Interaction, answer: str) -> None:
            challenge, self.challenge = self.challenge, None
            if challenge is None:
                return await self.refresh(modal_interaction)
            if time.time() > self.challenge_deadline:
                self.scarab_result = f"{emojis.icon('scarab', '🪲')} Too slow! The scarab scuttled away. (It was **{challenge.word}**.)"
            elif challenge.check(answer):
                win = await mining.claim_scarab_reward(self.user, random.Random())
                gifts = [loot_lines(win.items)] if win.items else []
                if win.xp:
                    gifts.append(f"{emojis.icon('star', '✨')} +{win.xp:,} mining xp")
                self.scarab_result = f"{emojis.icon('scarab', '🪲')} The scarab is pleased! **{win.name}**:\n" + "\n".join(gifts)
            else:
                self.scarab_result = f"{emojis.icon('scarab', '🪲')} Wrong! The scarab scuttles away. (It was **{challenge.word}**.)"
            self.result = rewards_result("The scarab", headline=[self.scarab_result], emoji=emojis.icon("scarab", "🪲"), again=self._again, again_label="Mine again",
                                         back=self._to_menu, back_label="Mining page")
            await self.refresh(modal_interaction)

        await interaction.response.send_modal(PromptModal("Unscramble the scroll", "Your answer", submitted, max_length=40))

    async def _skip_scarab(self, interaction: discord.Interaction) -> None:
        self.challenge = None
        self._show_loot()  # the same loot screen, now without the scarab (Mine again is free again)
        await self.refresh(interaction)

    async def _again(self, interaction: discord.Interaction) -> None:
        self.run = await mining.start_run(self.user, random.Random(), location=self.run.site.id)  # (the same mine again)
        self.summary = self.challenge = self.scarab_result = self.hole = None
        await self.refresh(interaction)

    async def _to_menu(self, interaction: discord.Interaction) -> None:
        """Leave the finished mine for the Mining page (the reward screen was the end of the run)."""
        await self.go(interaction, "mining")

    # ---- the wyrmhole: a small mine of its own (no hazards, nothing empty), drawn on this same screen ----------------
    async def _wyrmhole(self, interaction: discord.Interaction) -> None:
        self.hole = await mining.enter_wyrmhole(self.user, random.Random())
        await self.refresh(interaction)

    def _hole_page(self, hole: mining.WyrmholeSession) -> Page:
        """Rows you dug show your pick, the row you are on shows the cursor, the rest are still rock. The last row of a big wyrmhole is the one with gems."""
        reg = get_registry()
        lines = []
        for r, nodes in enumerate(hole.rows):
            if r < len(hole.picks):
                item, quantity = hole.picks[r]
                lines.append("".join(item_emoji(i) if c == hole.columns_picked[r] else _wyrm_rock() for c, (i, _) in enumerate(nodes)) + f"  {emojis.icon('check', '✅')} {quantity:,} {reg.item(item).name}")
            else:
                lines.append(_wyrm_rock() * len(nodes))
        header = [_notch()] * hole.width
        header[hole.cursor] = _cursor()
        shaft = "\n".join(lines[:hole.row]) + ("\n" if hole.row else "") + "".join(header) + "\n" + "\n".join(lines[hole.row:])
        name = "small wyrmhole" if hole.small else "wyrmhole"
        last = "" if hole.small else (" **The last row hides a gem!**" if hole.row == len(hole.rows) - 1 else " The last row hides a gem.")
        body = [*self.note_block(),
                text(f"## {emojis.icon('small_wyrmhole' if hole.small else 'wyrmhole', '🕳️')} A {name}\nNo danger in here and nothing is empty: dig **one** node on each of the **{len(hole.rows)}** rows."
                     f" Row **{hole.row + 1}** of {len(hole.rows)}: the deeper, the better.{last}"),
                sep(), text(shaft)]
        if hole.finished:
            body += [sep(), text("## Your picks\n" + loot_lines(hole.loot())),
                     row(button("Back to the mines", emoji=emojis.icon("dig", "⛏️"), on_click=self._hole_back))]
        else:
            body.append(row(
                button(emoji=emojis.icon("prev", "⬅️"), on_click=self._hole_move(-1)),
                button("Dig", emoji=emojis.icon("dig", "⛏️"), style=discord.ButtonStyle.primary, on_click=self._hole_dig),
                button(emoji=emojis.icon("next", "➡️"), on_click=self._hole_move(1)),
            ))
        return Page("The Mines", body, accent=0x9B59B6)

    def _hole_move(self, step: int):
        async def move(interaction: discord.Interaction) -> None:
            self.hole.move(step)
            await self.refresh(interaction)

        return move

    async def _hole_dig(self, interaction: discord.Interaction) -> None:
        hole = self.hole
        if hole.finished:  # a second click that was already on its way
            return await self.refresh(interaction)
        hole.dig()
        if not hole.finished:  # on to the next row
            return await self.refresh(interaction)
        await mining.finish_wyrmhole(self.user, hole)
        headline = [f"{emojis.icon('small_wyrmhole' if hole.small else 'wyrmhole', '🕳️')} You dug the whole " + ("small " if hole.small else "") + "wyrmhole."]
        self.result = rewards_result("Your picks", items=hole.loot(), xp=hole.xp_awarded, headline=headline, emoji=emojis.icon("wyrmhole", "🌀"), accent=0x9B59B6,
                                     back=self._hole_back, back_label="Back to the mines", odds=odds.mini_wyrmhole() if hole.small else None)
        await self.refresh(interaction)

    async def _hole_back(self, interaction: discord.Interaction) -> None:
        self.hole = None
        await self.go(interaction, "mining")
