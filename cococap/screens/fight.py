import asyncio

import discord

from cococap import emojis
from cococap.services import combat, dungeon
from cococap.services.combat import Battle, Unit
from cococap.ui import Page, Result, Screen
from cococap.ui.components import bar, button, row, section, sep, text
from cococap.ui.rewards import rewards_result
from cococap.user import User


PAUSE = 1.2  # seconds between the steps of a round (tests set it to 0)


def hp_line(unit: Unit) -> str:
    shield = f"  {emojis.icon('shield', '🔰')} {unit.shield}" if unit.shield else ""
    res = f"  {bar(unit.resource / unit.resource_max, 8, 'meter')} **{unit.resource}**/{unit.resource_max} {unit.resource_kind}" if unit.resource_kind else ""
    return f"{bar(unit.hp / unit.max_hp, 8, 'hp')} **{unit.hp}**/{unit.max_hp}{shield}{res}"


def effect_line(unit: Unit) -> str:
    return "  ".join(f"{combat.EFFECT_LABELS[e.kind]} {e.turns}" for e in unit.effects)


class FightScreen(Screen):
    id = "fight"
    label = "Fight"
    emoji = emojis.Lazy("ui_sword", "⚔️")
    description = "Turn-based fights: speed, cooldowns and timing"
    links = ("bestiary",)

    def __init__(self, nav):
        super().__init__(nav)
        self.battle: Battle | None = None
        self.encounter: str | None = None  # the key fight being played, or None for a zone fight (so "Fight again" knows what to start)
        self.zone: str | None = None  # the zone being explored
        self.picking: str | None = None  # a skill waiting for the player to choose its target
        self.animating = False  # a round is being played out: no buttons until it ends
        self.shown: list[tuple[str, list[str]]] = []  # the round being played out (empty = show the log tail)
        self.run: dungeon.Run | None = None  # set when this fight is part of a dungeon run (a tile fight or the shared boss fight)

    @property
    def me_id(self) -> str:
        return self.run.member(self.user.id).unit_id if self.run else "p1"

    @property
    def _boss(self) -> bool:
        return self.run is not None and self.battle is not None and self.battle is self.run.boss_battle

    @property
    def refresh_every(self) -> float | None:  # type: ignore[override]
        """The boss fight is shared: redraw every 3 s to see the others' turns."""
        return 3 if self._boss and self.battle.outcome is None else None

    @property
    def locked(self) -> bool:
        return self.battle is not None and self.battle.outcome is None

    # --- lobby -----------------------------------------------------------------------------------
    async def build(self) -> Page:
        if self._boss:
            dungeon.auto_play(self.run)  # an idle member's turn plays itself
            if self.battle.outcome:  # someone else's click ended it: settle (idempotent) and show our result
                await self._settle()
        if self.battle is not None:
            return self._battle_page(self.battle)
        return Page("Fight", [*self.note_block(), text("Pick a zone on the Combat page to start a fight."),
                              row(button("Combat", emoji=emojis.icon("sword", "⚔️"), on_click=self._to_combat))], accent=0xC0392B)

    async def _to_combat(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "combat")

    async def _begin(self, encounter_id: str) -> None:
        self.encounter, self.picking, self.shown = encounter_id, None, []
        self.battle = await combat.start_fight(self.user, encounter_id)

    # --- the fight ---------------------------------------------------------------------------------
    def _battle_page(self, battle: Battle) -> Page:
        me = battle.unit(self.me_id)
        foes = [u for u in battle.units if u.side == "enemy"]
        reveal = me.has("reveal")
        body = [*self.note_block()]
        for foe in foes:
            line = f"### {foe.emoji} {foe.name}" if foe.alive else f"### {emojis.icon('skull', '💀')} ~~{foe.name}~~"
            if foe.alive:
                line += f"\n{hp_line(foe)}"
                if effect_line(foe):
                    line += f"\n{effect_line(foe)}"
                if (reveal or foe.telegraph) and foe.next_skill:
                    line += f"\n{emojis.icon('eye', '👁️')} Next: **{battle.skill(foe.next_skill).name}**"
            body.append(text(line))
        body.append(sep())
        body.append(text(f"### {me.emoji} {me.name}\n{hp_line(me)}" + (f"\n{effect_line(me)}" if effect_line(me) else "")))
        for ally in (u for u in battle.units if u.side == "player" and u.id != me.id):
            body.append(text(f"{ally.emoji} {ally.name}\n{hp_line(ally)}"))
        order = f" {emojis.icon('next', '→')} ".join(u.emoji for u in battle.turn_order(7)) if battle.outcome is None else ""
        if order:
            body.append(text(f"**Turn order:** {order}"))
        body.append(sep())
        if self.shown:
            for side, lines in self.shown:
                body.append(text(f"**{'You' if side == 'you' else 'Enemy'}**\n" + "\n".join(lines)))
        else:
            body.append(text("\n".join(battle.log[-9:])))
        body.append(sep())
        body.extend(self._controls(battle, me))
        if self.picking:
            body.insert(0, text(f"{emojis.icon('target', '🎯')} **{battle.skill(self.picking).name}**: pick a target."))
        return Page("Fight", body, accent=0xC0392B)

    def _controls(self, battle: Battle, me: Unit) -> list:
        if self.animating:
            return [text(f"{emojis.icon('timer', '⌛')} ...")]
        if self._boss and battle.outcome is None and (battle.active is None or battle.active.id != me.id):
            who = battle.active.name if battle.active else "the others"
            waiting = [button(battle.skill(s).name, disabled=True, on_click=self._cancel) for s in me.skills]
            return [text(f"Waiting for {who}..."), row(*waiting)]
        if self.picking:
            targets = battle.targets_for(me, battle.skill(self.picking))
            return [row(
                *(button(f"{u.name} {u.hp}/{u.max_hp}", emoji=u.emoji, style=discord.ButtonStyle.danger, on_click=self._target(u.id))
                  for u in targets),
                button("Cancel", on_click=self._cancel),
            )]
        buttons = []
        for i, skill_id in enumerate(me.skills):
            skill = battle.skill(skill_id)
            cd = me.cooldowns.get(skill_id, 0)
            label = skill.name + (f" ({cd})" if cd else "") + (f" · {skill.cost}" if skill.cost else "")
            style = discord.ButtonStyle.primary if i == 0 else discord.ButtonStyle.secondary
            buttons.append(button(label, style=style, disabled=cd > 0 or me.resource < skill.cost, on_click=self._skill(skill_id)))
        if self.run:  # no running away from a dungeon fight
            return [row(*buttons)]
        return [row(*buttons), row(button("Flee", emoji=emojis.icon("people", "🏃"), on_click=self._flee))]

    def _skill(self, skill_id: str):
        async def use(interaction: discord.Interaction) -> None:
            battle = self.battle
            skill = battle.skill(skill_id)
            pool = battle.targets_for(battle.unit(self.me_id), skill)
            if skill.target in {"enemy", "ally"} and len(pool) > 1:
                self.picking = skill_id
                await self.refresh(interaction)
                return
            await self._act(interaction, skill_id, pool[0].id if pool else None)

        return use

    def _target(self, target_id: str):
        async def pick(interaction: discord.Interaction) -> None:
            skill_id, self.picking = self.picking, None
            await self._act(interaction, skill_id, target_id)

        return pick

    async def _cancel(self, interaction: discord.Interaction) -> None:
        self.picking = None
        await self.refresh(interaction)

    async def _act(self, interaction: discord.Interaction, skill_id: str, target_id: str | None) -> None:
        self.shown = []
        if self._boss:
            dungeon.boss_play(self.run, self.user, skill_id, target_id)
        else:
            self.battle.play(skill_id, target_id, self.me_id)
            steps = self.battle.steps
            if len(steps) > 1:  # your move first, then pause, then the enemy's reply (the bars already show the end state)
                self.shown, self.animating = steps[:1], True
                await self.refresh(interaction)
                try:
                    for i in range(1, len(steps)):
                        await asyncio.sleep(PAUSE)
                        self.shown = steps[: i + 1]
                        await self.nav.update(interaction)
                    await asyncio.sleep(PAUSE)
                finally:
                    self.animating = False
                if self.battle.outcome:
                    await self._settle()
                await self.nav.update(interaction)
                return
            self.shown = steps
        if self.battle.outcome:
            await self._finish(interaction)
        else:
            await self.refresh(interaction)

    async def _flee(self, interaction: discord.Interaction) -> None:
        self.battle, self.picking = None, None
        await self.refresh(interaction, "You ran away. Nothing gained, nothing lost.")

    async def _finish(self, interaction: discord.Interaction) -> None:
        await self._settle()
        await self.refresh(interaction)

    async def _settle(self) -> None:
        """Pay the finished battle and set the Victory/Defeated page (also called from build when another member ended the boss fight)."""
        battle, boss, self.battle, self.picking, self.shown = self.battle, self._boss, None, None, []
        if boss:
            paid = (await dungeon.finish_boss(self.run)).get(self.user.id)
        elif self.run:
            paid = await dungeon.finish_fight(self.run, self.user)
        else:
            paid = await combat.settle(self.user, battle)
        won = battle.outcome == "win"
        # "Continue" goes straight to Combat (the Fight lobby page it used to land on is pointless).
        kw = {"again": self._again, "again_label": "Fight again" if won else "Try again", "back": self._to_combat}
        if boss:
            kw = {"back": self._to_combat, "back_label": "Done"}
        elif self.run:
            kw = {"back": self._to_dungeon, "back_label": "Back to the dungeon"}
        if won:
            paid = paid or combat.Settlement()
            self.result = rewards_result("Victory!", items=paid.items, bits=paid.bits, xp=paid.xp, emoji=emojis.icon("record", "🏆"),
                                         accent=0x2ECC71, notes=[] if paid.items or paid.bits or paid.xp else ["Nothing dropped this time."], **kw)
        else:
            lines = ["The dungeon run is over for you." if self.run else "You wake up back at the camp, a little bruised. Nothing was lost but the time."]
            self.result = Result("Defeated", lines, emoji=emojis.icon("skull", "💀"), accent=0xE74C3C, **kw)

    async def _to_dungeon(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "dungeon")

    async def _again(self, interaction: discord.Interaction) -> None:
        if self.zone and not self.encounter:
            self.battle, self.picking, self.shown = await combat.explore(self.user, self.zone), None, []
        else:
            await self._begin(self.encounter)
        await self.refresh(interaction)
