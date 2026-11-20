"""The dungeon map: a window onto the hidden grid, four arrows, and the party's status. Fights open on the fight screen."""

import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import dungeon
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text

VIEW = 7  # the map shows up to this many tiles each way, centred on you
TILES = {"empty": "⬜", "reward": "🎁", "buff": "✨", "enemy": "👹", "boss": "💀"}
ARROWS = (("left", "⬅️"), ("up", "⬆️"), ("down", "⬇️"), ("right", "➡️"))


class DungeonScreen(Screen):
    id = "dungeon"
    label = "Dungeon"
    emoji = emojis.Lazy("ui_skull", "💀")
    description = "Walk the grid, fight what you meet, beat the boss"
    links = ("combat", "fight")
    refresh_every = 3  # fallback: the others' moves also poke this page

    @property
    def locked(self) -> bool:
        run = dungeon.run_of(self.user.id)
        return run is not None and not run.member(self.user.id).out

    @property
    def hides_nav(self) -> bool:
        return self.locked

    async def build(self) -> Page:
        body = [*self.note_block()]
        run = dungeon.run_of(self.user.id)
        if run is None:
            body += [text("The dungeon run is over."), row(button("Combat", on_click=self._to_combat))]
            return Page("Dungeon", body, accent=0x6C3483)
        me = run.member(self.user.id)
        body += [text(f"### T{run.tier.tier} Dungeon\n" + self._map(run, me)), sep()]
        body.append(text("\n".join(self._member_line(run, m) for m in run.members)))
        boss_live = run.boss_battle is not None and run.boss_battle.outcome is None and not me.out
        arrows = [button(emoji=e, on_click=self._move(d), disabled=me.out or me.busy or boss_live) for d, e in ARROWS]
        body.append(row(*arrows, button("Leave", on_click=self._leave, disabled=me.busy or boss_live)))
        if boss_live:
            body.append(row(button("Boss fight", style=discord.ButtonStyle.danger, on_click=self._to_boss)))
        elif me.busy:
            body.append(row(button("Back to the fight", style=discord.ButtonStyle.danger, on_click=self._to_fight)))
        return Page("Dungeon", body, accent=0x6C3483)

    def _map(self, run: dungeon.Run, me: dungeon.Member) -> str:
        view = min(VIEW, run.size)
        x0 = min(max(me.pos[0] - view // 2, 0), run.size - view)
        y0 = min(max(me.pos[1] - view // 2, 0), run.size - view)
        others = {m.pos: ("🧊" if m.busy else "🔵") for m in run.active() if m is not me}
        lines = []
        for y in range(y0, y0 + view):
            cells = []
            for x in range(x0, x0 + view):
                pos = (x, y)
                if pos == me.pos:
                    cells.append("🧑")
                elif pos in others:
                    cells.append(others[pos])
                else:
                    cells.append(TILES[run.tile(pos)] if pos in run.revealed else "⬛")
            lines.append("".join(cells))
        return "\n".join(lines)

    def _member_line(self, run: dungeon.Run, m: dungeon.Member) -> str:
        state = " · out" if m.out else " · fighting" if m.busy else ""
        return f"{'🧑' if m.user_id == self.user.id else '🔵'} **{m.name}**" + (f"  ❤️ {m.hp}" if m.hp else "") + state

    def _move(self, direction: str):
        async def step(interaction: discord.Interaction) -> None:
            run = dungeon.run_of(self.user.id)
            m = run.member(self.user.id)
            before_items, before_bits = dict(m.items), m.bits
            what = await dungeon.move(run, self.user, direction)
            if what == "fight":
                await self.go(interaction, "fight", battle=m.battle, run=run)
            elif what == "boss":
                await self.go(interaction, "fight", battle=run.boss_battle, run=run)
            elif what == "reward":
                reg = get_registry()
                found = [f"{reg.item(i).display} ×{q - before_items.get(i, 0):,}" for i, q in m.items.items() if q > before_items.get(i, 0)]
                if m.bits > before_bits:
                    found.append(emojis.bits(m.bits - before_bits))
                await self.refresh(interaction, "You found loot! " + ", ".join(found))
            elif what == "buff":
                await self.refresh(interaction, "You feel stronger.")
            else:
                await self.refresh(interaction)

        return step

    async def _leave(self, interaction: discord.Interaction) -> None:
        await dungeon.leave(dungeon.run_of(self.user.id), self.user)
        await self.go(interaction, "combat", tab="dungeons")

    async def _to_boss(self, interaction: discord.Interaction) -> None:
        run = dungeon.run_of(self.user.id)
        await self.go(interaction, "fight", battle=run.boss_battle, run=run)

    async def _to_fight(self, interaction: discord.Interaction) -> None:
        run = dungeon.run_of(self.user.id)
        await self.go(interaction, "fight", battle=run.member(self.user.id).battle, run=run)

    async def _to_combat(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "combat", tab="dungeons")
