"""The /mine command. Discord only: every rule lives in cococap.services.mining."""

import random
from collections import Counter
from logging import getLogger

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from cococap.constants import IMAGES_REPO, PROJECT_ROOT, Categories
from cococap.registry import get_registry
from cococap.services import mining
from cococap.ui import OwnedView
from cococap.user import User
from utils.custom_embeds import CustomEmbed
from utils.utils import timestamp_to_english

log = getLogger(__name__)

CELL = "<:cell:1280658009306959893>"
CELL_EMPTY = "<:cell_empty:1280658029703860244>"
WYRMHOLE = "<a:wyrmhole:1280656910290260038>"
NOTCH = ":black_small_square:"
CURSOR = ":small_red_triangle_down:"
MAGNET = ":sparkles:"


def _words() -> list[str]:
    """Words for scarab scrolls (read on use so a missing file only breaks the scarab)."""
    path = PROJECT_ROOT / "resources" / "unscramble_words.txt"
    return [w.strip() for w in path.read_text().splitlines() if len(w.strip()) >= 5]


def item_emoji(item_id: str) -> str:
    return get_registry().item(item_id).emoji or "🟫"


def loot_lines(loot: Counter) -> str:
    reg = get_registry()
    lines = []
    for item_id, quantity in loot.items():
        item = reg.item(item_id)
        name = f"**{item.name}**" if item.rarity >= 5 else item.name
        lines.append(f"{item_emoji(item_id)} +{quantity:,} {name}")
    return "\n".join(lines) or "Nothing yet"


# ---- rendering: state in, embed out (no game logic) ----------------------------------------------
def render_grid(session: mining.MineSession) -> str:
    header = [NOTCH] * session.columns
    for col in session.magnet_columns:
        header[col] = MAGNET
    for col in session.cursors:
        header[col] = CURSOR
    rows = []
    for r, cells in enumerate(session.nodes):
        line = []
        for c in range(session.columns):
            if (r, c) in session.revealed:
                cell = session.revealed[(r, c)]
                line.append(item_emoji(cell[0]) if cell else CELL_EMPTY)
            elif (r, c) in session.wyrmholes:
                line.append(WYRMHOLE)
            else:
                line.append(CELL)
        rows.append("".join(line))
    return "".join(header) + "\n" + "\n".join(rows)


def xp_field(xp: int) -> tuple[str, str]:
    overflow, needed = User.xp_for_next_level(xp)
    return f"Level {User.xp_to_level(xp)} - {overflow:,}/{needed:,} xp", User.create_xp_bar(xp)


def mine_embed(interaction: Interaction, session: mining.MineSession, xp: int, footer: str) -> discord.Embed:
    embed = CustomEmbed(
        title=":pick: Welcome back to the mines.",
        desc="Pick a column to dig out for ores and gems!\nUpgrade your reactor to dig more columns.",
        color=discord.Color.blue(),
        interaction=interaction,
        activity="mining",
    )
    embed.add_field(name="Mineshaft :ladder:", value=render_grid(session))
    embed.add_field(name="Loot :moneybag:", value=loot_lines(session.loot))
    name, bar = xp_field(xp)
    embed.add_field(name=name, value=bar, inline=False)
    embed.set_footer(text=footer)
    return embed


# ---- views: a button calls one service method, then redraws ---------------------------------------
class MineView(OwnedView):
    def __init__(self, interaction: Interaction, user: User, session: mining.MineSession, xp: int):
        super().__init__(interaction.user, timeout=180)
        self.interaction, self.user, self.session, self.xp = interaction, user, session, xp
        self.started = discord.utils.utcnow()

    def embed(self, footer: str = "Mine all the way down to receive xp!") -> discord.Embed:
        return mine_embed(self.interaction, self.session, self.xp, footer)

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.grey)
    async def left(self, interaction: Interaction, button: discord.ui.Button):
        self.session.move(-1)
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(emoji="⛏️", style=discord.ButtonStyle.blurple)
    async def dig(self, interaction: Interaction, button: discord.ui.Button):
        result = await mining.dig_row(self.user, self.session)
        if result.wyrmhole:
            self.stop()
            hole = await mining.enter_wyrmhole(self.user, random.Random())
            await mining.finish_mine(self.user, self.session)
            view = WyrmholeView(interaction, self.user, hole, self.xp)
            return await interaction.response.edit_message(embed=view.embed(), view=view)
        if not result.finished:
            return await interaction.response.edit_message(embed=self.embed(), view=self)

        self.stop()
        gained = await mining.finish_mine(self.user, self.session)
        self.xp += gained
        footer = f"+{gained} xp. What's one more? Might find a wyrmhole!"
        rng = random.Random()
        rules = get_registry().mining
        if mining.scarab_appears(rules, rng):
            challenge = mining.make_scarab(_words(), rules, rng)
            view = ScarabView(interaction, self.user, challenge, self)
            embed = self.embed(footer)
            embed.add_field(
                name="🪲 A subterranean scarab appears!",
                value=f"It holds a scroll: **{challenge.scrambled}**\nUnscramble it within {challenge.seconds}s!",
                inline=False,
            )
            return await interaction.response.edit_message(embed=embed, view=view)
        view = FinishedView(self)
        await interaction.response.edit_message(embed=self.embed(footer), view=view)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.grey)
    async def right(self, interaction: Interaction, button: discord.ui.Button):
        self.session.move(1)
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def on_timeout(self) -> None:
        if not self.session.finished:  # wandered off mid-mine: keep the lodes, no completion xp
            await mining.finish_mine(self.user, self.session)
        await super().on_timeout()


class FinishedView(OwnedView):
    def __init__(self, parent: MineView):
        super().__init__(parent.owner, timeout=120)
        self.parent = parent

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.gray)
    async def leave(self, interaction: Interaction, button: discord.ui.Button):
        p = self.parent
        embed = p.embed(footer=f"You spent {timestamp_to_english((discord.utils.utcnow() - p.started).total_seconds()) or 'no time'} mining {p.session.lodes} lodes.")
        embed.title = ":pick: Mine Left"
        embed.description = "Here's what you got in your mini-mining-session."
        embed.color = discord.Color.dark_gray()
        embed.remove_field(0)
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(emoji="🔄", style=discord.ButtonStyle.blurple, label="Mine again")
    async def again(self, interaction: Interaction, button: discord.ui.Button):
        self.stop()
        view = await new_mine_view(interaction, self.parent.user)
        await interaction.response.edit_message(embed=view.embed(), view=view)


class WyrmholeView(OwnedView):
    def __init__(self, interaction: Interaction, user: User, hole: mining.WyrmholeSession, xp: int):
        super().__init__(interaction.user, timeout=600)
        self.interaction, self.user, self.hole, self.xp = interaction, user, hole, xp

    def embed(self, footer: str = "Don't tilt too hard if you don't get it, okay?") -> discord.Embed:
        embed = CustomEmbed(
            title=f"You found a Wyrmhole! {WYRMHOLE}",
            desc="You can only choose one node! Good luck!",
            color=discord.Color.purple(),
            interaction=self.interaction,
            activity="mining",
        )
        header = [NOTCH] * len(self.hole.nodes)
        header[self.hole.cursor] = CURSOR
        body = "".join(item_emoji(i) if self.hole.revealed else CELL for i, _ in self.hole.nodes)
        embed.add_field(name="Mineshaft :ladder:", value="".join(header) + "\n" + body)
        embed.set_footer(text=footer)
        return embed

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.grey)
    async def left(self, interaction: Interaction, button: discord.ui.Button):
        self.hole.move(-1)
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(emoji="⛏️", style=discord.ButtonStyle.blurple)
    async def dig(self, interaction: Interaction, button: discord.ui.Button):
        item_id, quantity = await mining.finish_wyrmhole(self.user, self.hole)
        embed = self.embed("The wyrmhole collapses behind you.")
        embed.add_field(name="Loot :moneybag:", value=loot_lines(Counter({item_id: quantity})))
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.grey)
    async def right(self, interaction: Interaction, button: discord.ui.Button):
        self.hole.move(1)
        await interaction.response.edit_message(embed=self.embed(), view=self)


class ScarabAnswer(discord.ui.Modal, title="Unscramble the scroll"):
    answer = discord.ui.TextInput(label="Your answer", max_length=40)

    def __init__(self, view: "ScarabView"):
        super().__init__()
        self.scarab_view = view

    async def on_submit(self, interaction: Interaction) -> None:
        await self.scarab_view.resolve(interaction, self.answer.value)


class ScarabView(OwnedView):
    def __init__(self, interaction: Interaction, user: User, challenge: mining.ScarabChallenge, parent: MineView):
        super().__init__(interaction.user, timeout=challenge.seconds)
        self.user, self.challenge, self.parent = user, challenge, parent
        self.done = False

    @discord.ui.button(label="Answer", style=discord.ButtonStyle.blurple, emoji="📜")
    async def answer(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ScarabAnswer(self))

    async def resolve(self, interaction: Interaction, text: str) -> None:
        if self.done:
            return await interaction.response.defer()
        self.done = True
        self.stop()
        embed = self.parent.embed()
        if self.challenge.check(text):
            reward = await mining.claim_scarab_reward(self.user, random.Random())
            embed.add_field(name="🪲 The scarab is pleased!", value="It takes you to level 6:\n" + loot_lines(reward), inline=False)
        else:
            embed.add_field(name="🪲 The scarab scuttles away.", value=f"The word was **{self.challenge.word}**.", inline=False)
        await interaction.response.edit_message(embed=embed, view=FinishedView(self.parent))

    async def on_timeout(self) -> None:
        if not self.done:
            self.done = True
            if self.message is not None:
                try:
                    await self.message.edit(view=FinishedView(self.parent))
                except discord.HTTPException:
                    pass


async def new_mine_view(interaction: Interaction, user: User) -> MineView:
    session = await mining.start_mine(user, random.Random())
    return MineView(interaction, user, session, (await user.skill("mining")).xp)


class ReactorView(OwnedView):
    def __init__(self, interaction: Interaction, user: User, status: dict):
        super().__init__(interaction.user, timeout=180)
        self.interaction, self.user, self.status = interaction, user, status

    @staticmethod
    async def build(interaction: Interaction, user: User) -> "ReactorView":
        return ReactorView(interaction, user, await mining.reactor_status(user))

    def embed(self, note: str | None = None) -> discord.Embed:
        mining_skill, rules = self.status["mining"], get_registry().mining
        reactor = mining_skill.reactor
        embed = CustomEmbed(
            title=f"Reactor Level: 🌟 {reactor.level:,}",
            desc="Level up your reactor for passive mining and to mine more columns!",
            color=discord.Color.from_str("0x0408dd"),
            interaction=self.interaction,
            activity="reactor",
        )
        cores = [reactor.core_1, reactor.core_2, reactor.core_3, reactor.core_4]
        embed.add_field(
            name="Cores",
            value=" ".join(item_emoji(c.gem_id) if c.gem_id else CELL_EMPTY for c in cores)
            + ("" if self.status["gem_slots_open"] else f"\n*Gem slots unlock at mining level {rules.reactor.gem_slot_level}*"),
        )
        embed.add_field(
            name="Auto-Miner™",
            value=f"**{self.status['pending_lodes']:,}** lodes ready to claim\n"
            f"{reactor.level} lode(s) every {rules.reactor.automine_seconds // 60} minutes",
            inline=False,
        )
        embed.add_field(name="Digging", value=f"{self.status['columns_dug']} column(s) per swing")
        if self.status["level"] >= rules.magnet.level:
            embed.add_field(name="Magnet", value=f"{mining_skill.magnet_meter:,}/{rules.magnet.capacity:,}")
        if note:
            embed.set_footer(text=note)
        return embed

    async def _refresh(self, interaction: Interaction, note: str) -> None:
        self.status = await mining.reactor_status(self.user)
        await interaction.response.edit_message(embed=self.embed(note), view=self)

    @discord.ui.button(label="Claim lodes", style=discord.ButtonStyle.green)
    async def claim(self, interaction: Interaction, button: discord.ui.Button):
        lodes, loot = await mining.claim_lodes(self.user, random.Random())
        await self._refresh(interaction, f"Claimed {lodes:,} lodes: " + (", ".join(f"{q:,} {get_registry().item(i).name}" for i, q in loot.items()) or "nothing"))

    @discord.ui.button(label="Insert gems", style=discord.ButtonStyle.gray)
    async def insert(self, interaction: Interaction, button: discord.ui.Button):
        placed, problem = [], None
        inventory = await self.user.items()
        for gem in get_registry().mining.reactor.core_gems:
            if inventory.get(gem):
                try:
                    placed.append(get_registry().item(gem).name)
                    await mining.place_gem(self.user, gem)
                except mining.MiningError as e:
                    placed.pop()
                    problem = str(e)
        await self._refresh(interaction, ("Inserted: " + ", ".join(placed)) if placed else (problem or "You have no reactor gems to insert."))

    @discord.ui.button(label="Prestige", style=discord.ButtonStyle.blurple)
    async def prestige(self, interaction: Interaction, button: discord.ui.Button):
        try:
            level = await mining.prestige(self.user)
            note = f"Your reactor is now level {level}!"
        except mining.MiningError as e:
            note = str(e)
        await self._refresh(interaction, note)

    @discord.ui.button(label="Feed magnet", style=discord.ButtonStyle.gray)
    async def feed(self, interaction: Interaction, button: discord.ui.Button):
        note = "Fed the magnet."
        owned = await self.user.items()
        try:
            for ore in get_registry().mining.magnet.values:  # cheapest first
                if owned.get(ore):
                    await mining.deposit_ore(self.user, ore, owned[ore])
        except mining.MiningError as e:
            note = str(e)
        await self._refresh(interaction, note)


class MineMenu(OwnedView):
    """The /mine home screen."""

    def __init__(self, interaction: Interaction, user: User, xp: int):
        super().__init__(interaction.user, timeout=120)
        self.interaction, self.user, self.xp = interaction, user, xp

    def embed(self) -> discord.Embed:
        embed = CustomEmbed(
            title=f"Level: 🌟 {User.xp_to_level(self.xp):,}",
            color=discord.Color.from_str(Categories.MINING.color),
            interaction=self.interaction,
            activity="mining",
        )
        embed.set_thumbnail(url=f"{IMAGES_REPO}/skills/mining.png")
        return embed

    @discord.ui.button(label="Mine", style=discord.ButtonStyle.blurple, emoji="⛏️")
    async def mine(self, interaction: Interaction, button: discord.ui.Button):
        self.stop()
        view = await new_mine_view(interaction, self.user)
        await interaction.response.edit_message(embed=view.embed(), view=view)

    @discord.ui.button(label="Reactor", style=discord.ButtonStyle.gray, emoji="☢️")
    async def reactor(self, interaction: Interaction, button: discord.ui.Button):
        self.stop()
        view = await ReactorView.build(interaction, self.user)
        await interaction.response.edit_message(embed=view.embed(), view=view)


class MiningCog(commands.Cog, name="Mining"):
    """Mine nodes to receive ores, gems, and bits! Upgrade your reactor for more mining power."""

    @app_commands.command(name="mine", description="Head down into the mines.")
    async def mine(self, interaction: Interaction):
        user = await User.get(interaction.user.id)
        skill = await user.skill("mining")
        menu = MineMenu(interaction, user, skill.xp)
        embed = menu.embed()
        ores = Counter({i: q for i, q in (await user.items()).items() if i in get_registry().mining.magnet.values})
        embed.add_field(name="Ores", value=loot_lines(ores) if ores else "None yet")
        embed.add_field(name="Lodes Mined", value=f":pick: **{skill.stats.lodes_mined:,}** lodes", inline=False)
        await interaction.response.send_message(embed=embed, view=menu)
        await menu.attach(interaction)


async def setup(bot):
    await bot.add_cog(MiningCog())
