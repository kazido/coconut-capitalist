import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import combat
from cococap.services.combat import Battle, Unit
from cococap.ui import Page, Result, Screen
from cococap.ui.components import bar, button, row, section, sep, text
from cococap.user import User


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

    @property
    def locked(self) -> bool:
        return self.battle is not None and self.battle.outcome is None

    # --- lobby -----------------------------------------------------------------------------------
    async def build(self) -> Page:
        if self.battle is not None:
            return self._battle_page(self.battle)
        return Page("Fight", [*self.note_block(), text("Pick a zone on the Combat page to start a fight."),
                              row(button("Combat", emoji=emojis.icon("sword", "⚔️"), on_click=self._to_combat))], accent=0xC0392B)

    async def _to_combat(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "combat")

    async def _begin(self, encounter_id: str) -> None:
        self.encounter, self.picking = encounter_id, None
        self.battle = await combat.start_fight(self.user, encounter_id)

    # --- the fight ---------------------------------------------------------------------------------
    def _battle_page(self, battle: Battle) -> Page:
        me = battle.unit("p1")
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
        order = f" {emojis.icon('next', '→')} ".join(u.emoji for u in battle.turn_order(7)) if battle.outcome is None else ""
        if order:
            body.append(text(f"**Turn order:** {order}"))
        body.append(sep())
        body.append(text("\n".join(battle.log[-9:])))
        body.append(sep())
        body.extend(self._controls(battle, me))
        if self.picking:
            body.insert(0, text(f"{emojis.icon('target', '🎯')} **{battle.skill(self.picking).name}**: pick a target."))
        return Page("Fight", body, accent=0xC0392B)

    def _controls(self, battle: Battle, me: Unit) -> list:
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
        return [row(*buttons), row(button("Flee", emoji=emojis.icon("people", "🏃"), on_click=self._flee))]

    def _skill(self, skill_id: str):
        async def use(interaction: discord.Interaction) -> None:
            battle = self.battle
            skill = battle.skill(skill_id)
            pool = battle.targets_for(battle.unit("p1"), skill)
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
        self.battle.play(skill_id, target_id)
        if self.battle.outcome:
            await self._finish(interaction)
        else:
            await self.refresh(interaction)

    async def _flee(self, interaction: discord.Interaction) -> None:
        self.battle, self.picking = None, None
        await self.refresh(interaction, "You ran away. Nothing gained, nothing lost.")

    async def _finish(self, interaction: discord.Interaction) -> None:
        battle, self.battle, self.picking = self.battle, None, None
        paid = await combat.settle(self.user, battle)
        recap = "\n".join(battle.log[-6:])
        if battle.outcome == "win":
            reg = get_registry()
            loot = [f"{reg.item(i).display} ×{q:,}" for i, q in paid.items.items()] + ([f"**{emojis.bits(paid.bits)}**"] if paid.bits else [])
            lines = [recap, f"**+{paid.xp:,}** combat xp  ·  {paid.kills} slain", f"{emojis.icon('gift', '🎁')} " + (", ".join(loot) if loot else "Nothing dropped this time.")]
            self.result = Result("Victory!", lines, emoji=emojis.icon("record", "🏆"), accent=0x2ECC71, again=self._again, again_label="Fight again")
        else:
            lines = [recap, "You wake up back at the camp, a little bruised. Nothing was lost but the time."]
            self.result = Result("Defeated", lines, emoji=emojis.icon("skull", "💀"), accent=0xE74C3C, again=self._again, again_label="Try again")
        await self.refresh(interaction)

    async def _again(self, interaction: discord.Interaction) -> None:
        if self.zone and not self.encounter:
            self.battle, self.picking = await combat.explore(self.user, self.zone), None
        else:
            await self._begin(self.encounter)
        await self.refresh(interaction)
