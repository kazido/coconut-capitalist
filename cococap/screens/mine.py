import random
import time
from collections import Counter

import discord

from cococap.constants import PROJECT_ROOT
from cococap.registry import get_registry
from cococap.services import mining
from cococap.ui import Page, PromptModal, Screen
from cococap.ui.components import bar, button, row, sep, text

from cococap import emojis

# Map emojis come from the bot's application emojis (by name); the plain emoji is the fallback.
def _cell() -> str: return emojis.get("cell", "⬛")
def _cell_empty() -> str: return emojis.get("cell_empty", "▫️")
def _rich() -> str: return emojis.get("cell_upgraded", "🟦")
def _hole() -> str: return emojis.get("wyrmhole", "🌀")
VENT = "💨"
CACHE = "📦"
BOMB = "💣"
CURSOR = "🔻"
SOFT, FIRM, HARD = "🟫", "🟧", "🟥"  # the rock from above: soft (little pressure, copper), firm (iron), hard (a lot of pressure, the best ore)
NOTCH = "▪️"
MILESTONE = "🏁"  # a landmark row: finish it and the tunnel is shored up
VAULT = "🏆"  # the last row: the vault is worth getting to
MAGNET = "✨"
ACCENT = {"Calm": 0x2ECC71, "Tremors": 0xF1C40F, "Unstable": 0xE67E22, "Critical": 0xE74C3C}
SHOWN_ROWS = 1  # rows you've already passed that stay on screen


def _words() -> list[str]:
    path = PROJECT_ROOT / "resources" / "unscramble_words.txt"
    return [w.strip() for w in path.read_text().splitlines() if len(w.strip()) >= 5]


def item_emoji(item_id: str) -> str:
    return get_registry().item(item_id).emoji or "🟫"


def loot_lines(loot: Counter) -> str:
    reg = get_registry()
    lines = []
    for item_id, quantity in loot.items():
        item = reg.item(item_id)
        lines.append(f"{item_emoji(item_id)} +{quantity:,} " + (f"**{item.name}**" if item.rarity >= 5 else item.name))
    return "\n".join(lines)


def cell_emoji(feel: str) -> str:
    """A cell as it feels from above: soft, firm or hard rock, a highlighted rich lode, or a wyrmhole. You cannot tell ore, nothing, vents and
    caches apart inside the same kind of rock, only how hard it is."""
    return {"rich": _rich(), "hole": _hole(), "soft": SOFT, "firm": FIRM, "hard": HARD}.get(feel) or _cell()


def dug_emoji(sign: str, cell) -> str:
    """A cell you dug, now revealed: its vent, its cache, its ore, or nothing."""
    if sign == "vent":
        return VENT
    if sign == "cache":
        return CACHE
    return item_emoji(cell[0]) if cell else _cell_empty()


def row_mark(run: mining.MineRun, depth: int) -> str:
    """A landmark beside a row you can see ahead: 🏁 on a milestone row, 🏆 on the last one (the vault)."""
    if depth == run.floor - 1:
        return f"  {VAULT} vault"
    if any(m.row == depth + 1 for m in run.rules.descent.milestones):
        return f"  {MILESTONE} checkpoint"
    return ""


def next_landmark(run: mining.MineRun) -> str:
    """"🏁 row 10 (3 to go)" or "🏆 the vault (12 to go)": what you are digging toward."""
    for m in run.rules.descent.milestones:
        if m.row > run.depth:
            return f"{MILESTONE} checkpoint at row {m.row} ({m.row - run.depth} to go)"
    return f"{VAULT} the vault ({run.floor - run.depth} to go)"


def render_shaft(run: mining.MineRun) -> str:
    """The last row you dug, a cursor line, then the rows ahead with everything visible."""
    columns = run.rules.columns
    lines = []
    for dug in run.history[-SHOWN_ROWS:]:
        # What you dug shows what it gave; what you left behind stays as it looked.
        lines.append("".join(
            dug_emoji(dug.kinds[c], dug.cells[c]) if c in dug.dug else cell_emoji(run.feel(dug.depth)[c])
            for c in range(columns)
        ))
    if not run.finished:
        header = [NOTCH] * columns
        for col in run.best_columns():
            header[col] = MAGNET
        for col in run.cursors:
            header[col] = CURSOR
        lines.append("".join(header))
        for ahead in range(run.rules.descent.lookahead):
            depth = run.depth + ahead
            if depth >= run.floor:
                break
            lines.append("".join(cell_emoji(feel) for feel in run.feel(depth)) + row_mark(run, depth))
    return "\n".join(lines)


def risk_text(risk: float) -> str:
    """The collapse chance for the next dig. "0%" only ever means exactly zero."""
    if risk <= 0:
        return "0%"
    return "<1%" if risk < 0.005 else f"{risk:.0%}"


def carrying(haul: Counter) -> str:
    if not haul:
        return "-# Nothing in your pack yet."
    return "🎒 " + "  ".join(f"{item_emoji(i)} {q:,}" for i, q in haul.items())


HELP = (
    f"Read the rock: {SOFT} **soft** (little pressure, mostly copper)  ·  {FIRM} **firm** (iron)  ·  {HARD} **hard** (a lot of pressure, the best ore).\n"
    "Inside it hides ore, nothing, a **vent** that cools the tunnel, or a **cache** with a brace.\n"
    "cell_upgraded: a **rich lode**, a mystery with better loot  ·  wyrmhole: a way out, if you dig it\n"
    f"{BOMB} **bomb**: clears a whole row  ·  {MAGNET} a charged magnet marks the richest cell"
)


class MineScreen(Screen):
    id = "mine"
    label = "The Mines"
    emoji = "⛏️"
    description = "Dig deeper for rarer loot, but watch the danger meter"
    links = ("mining", "wyrmhole")

    def __init__(self, nav):
        super().__init__(nav)
        self.run: mining.MineRun | None = None  # set when the player enters the mines
        self.summary: mining.RunSummary | None = None
        self.challenge: mining.ScarabChallenge | None = None
        self.challenge_deadline = 0.0
        self.scarab_result: str | None = None
        self.show_help = False

    @property
    def locked(self) -> bool:
        return self.run is not None and not self.run.finished

    async def on_abandon(self) -> None:
        if self.run is not None and not self.run.finished:
            await mining.abandon_run(self.user, self.run)

    # ---- rendering ----------------------------------------------------------------------------
    async def build(self) -> Page:
        run = self.run
        if run is None:
            return Page("The Mines", [text("Head into the mines from the Mining page.")])
        if run.finished:
            return await self._finished_page()
        warning = run.warning
        body = [
            *self.note_block(),
            text(f"**Row {run.depth + 1} of {run.floor}**  ·  {next_landmark(run)}     {warning.emoji} **{risk_text(run.risk)}** collapse risk"),
            text(render_shaft(run)),
            text(carrying(run.haul)),
        ]
        if self.show_help:
            body.append(text(HELP.replace("cell_upgraded", _rich()).replace("wyrmhole:", f"{_hole()}:")))
        body.append(row(
            button(emoji="⬅️", on_click=self._move(-1)),
            button("Dig", emoji="⛏️", style=discord.ButtonStyle.primary, on_click=self._dig),
            button(emoji="➡️", on_click=self._move(1)),
        ))
        extra = [button(f"Brace ({run.braces})", emoji="🛡️", disabled=run.braces == 0 or run.danger == 0, on_click=self._brace)]
        if run.bombs or run.bombs_used:
            extra.append(button(f"Bomb ({run.bombs})", emoji=BOMB, disabled=run.bombs == 0, on_click=self._bomb))
        extra.append(button("Leave & bank", emoji="🎒", style=discord.ButtonStyle.success, on_click=self._leave))
        extra.append(button(
            "Hide tips" if self.show_help else "Tips", emoji="❔",
            style=discord.ButtonStyle.primary if self.show_help else discord.ButtonStyle.secondary,
            on_click=self._toggle_help,
        ))
        body.append(row(*extra))
        return Page("The Mines", body, accent=ACCENT.get(warning.name, 0x9E492F))

    async def _finished_page(self) -> Page:
        run, summary = self.run, self.summary
        titles = {"left": ("🎒 You climbed out safely", 0x2ECC71),
                  "collapse": ("💥 The mine collapsed!", 0xE74C3C),
                  "wyrmhole": ("🌀 You broke into a wyrmhole!", 0x9B59B6),
                  "floor": ("🏆 You reached the vault!", 0xF1C40F)}
        title, accent = titles[run.outcome]
        body = [*self.note_block(), text(f"## {title}")]
        if summary is not None:
            body.append(text(f"Row **{summary.depth}** of {run.floor}  ·  **{summary.lodes}** lodes dug  ·  **+{summary.xp}** xp"))
            body.append(text(("**Banked**\n" + loot_lines(summary.haul)) if summary.haul else "Nothing to bank this time."))
        if self.challenge is not None:
            body += [sep(), text(f"🪲 **A subterranean scarab appears!** It holds a scroll: **{self.challenge.scrambled}**\n"
                                 f"Unscramble it before <t:{int(self.challenge_deadline)}:R> and it will reward you!"),
                     row(button("Answer", emoji="📜", style=discord.ButtonStyle.primary, on_click=self._ask_scarab),
                         button("Ignore", on_click=self._skip_scarab))]
        elif self.scarab_result:
            body += [sep(), text(self.scarab_result)]
        actions = [button("Mine again", emoji="🔄", style=discord.ButtonStyle.primary, on_click=self._again)]
        if run.outcome == "wyrmhole":
            actions.insert(0, button("Enter the wyrmhole", emoji="🌀", style=discord.ButtonStyle.success, on_click=self._wyrmhole))
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
        if result.collapsed:
            lost = ", ".join(f"{q:,} {reg.item(i).name}" for i, q in result.lost.items())
            note = "The tunnel gave way!" + (f" You lost {lost}." if lost else "")
        else:
            note = ("💥 BOOM! " if result.bombed else "") + (f"Found {found}." if found else ("" if result.wyrmhole else "Nothing here."))
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
                note += f" {MILESTONE} **Row {m.row}: checkpoint!** What is in your pack is safe from a collapse now.{extra}"
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

    async def _ask_scarab(self, interaction: discord.Interaction) -> None:
        async def submitted(modal_interaction: discord.Interaction, answer: str) -> None:
            challenge, self.challenge = self.challenge, None
            if challenge is None:
                return await self.refresh(modal_interaction)
            if time.time() > self.challenge_deadline:
                self.scarab_result = f"🪲 Too slow! The scarab scuttled away. (It was **{challenge.word}**.)"
            elif challenge.check(answer):
                win = await mining.claim_scarab_reward(self.user, random.Random())
                gifts = [loot_lines(win.items)] if win.items else []
                if win.xp:
                    gifts.append(f"✨ +{win.xp:,} mining xp")
                self.scarab_result = f"🪲 The scarab is pleased! **{win.name}**:\n" + "\n".join(gifts)
            else:
                self.scarab_result = f"🪲 Wrong! The scarab scuttles away. (It was **{challenge.word}**.)"
            await self.refresh(modal_interaction)

        await interaction.response.send_modal(PromptModal("Unscramble the scroll", "Your answer", submitted, max_length=40))

    async def _skip_scarab(self, interaction: discord.Interaction) -> None:
        self.challenge = None
        await self.refresh(interaction)

    async def _again(self, interaction: discord.Interaction) -> None:
        self.run = await mining.start_run(self.user, random.Random())
        self.summary = self.challenge = self.scarab_result = None
        await self.refresh(interaction)

    async def _wyrmhole(self, interaction: discord.Interaction) -> None:
        hole = await mining.enter_wyrmhole(self.user, random.Random())
        await self.go(interaction, "wyrmhole", hole=hole)
