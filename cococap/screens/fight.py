import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import combat
from cococap.services.combat import Battle, Unit
from cococap.ui import Page, Result, Screen
from cococap.ui.components import bar, button, row, section, sep, text
from cococap.user import User


def hp_line(unit: Unit) -> str:
    shield = f"  🔰 {unit.shield}" if unit.shield else ""
    return f"{bar(unit.hp / unit.max_hp, 8)} **{unit.hp}**/{unit.max_hp}{shield}"


def effect_line(unit: Unit) -> str:
    return "  ".join(f"{combat.EFFECT_LABELS[e.kind]} {e.turns}" for e in unit.effects)


class FightScreen(Screen):
    id = "fight"
    label = "Fight"
    emoji = "⚔️"
    description = "Turn-based fights: speed, cooldowns and timing"
    links = ("bestiary",)

    def __init__(self, nav):
        super().__init__(nav)
        self.battle: Battle | None = None
        self.encounter: str | None = None  # the fight being played (so "Fight again" knows what to start)
        self.picking: str | None = None  # a skill waiting for the player to choose its target

    @property
    def locked(self) -> bool:
        return self.battle is not None and self.battle.outcome is None

    # --- lobby -----------------------------------------------------------------------------------
    async def build(self) -> Page:
        if self.battle is not None:
            return self._battle_page(self.battle)
        reg = get_registry()
        level = User.xp_to_level((await self.user.skill("combat")).xp)
        me = await combat.build_player(self.user)
        body = [
            *self.note_block(),
            text(f"### ⚔️ Combat  ·  Lv {level}\n❤️ **{me.max_hp}**  ⚔️ **{me.attack}**  🛡️ **{me.defense}**  ⚡ **{me.speed}**"),
            text("\n".join(f"**{reg.combat.skills[s].name}** — {reg.combat.skills[s].description}"
                           + (f" *(recharge {reg.combat.skills[s].cooldown})*" if reg.combat.skills[s].cooldown else "")
                           for s in me.skills)),
            sep(),
        ]
        owned = await self.user.items()
        for enc in reg.combat.encounters:
            foes = ", ".join(reg.enemies[e].emoji + " " + reg.enemies[e].name for e in enc.enemies)
            has_key = not enc.key or owned.get(enc.key, 0) > 0
            open_ = level >= enc.min_level and has_key
            line = f"**{enc.name}**\n{foes}"
            if level < enc.min_level:
                line += f"\n🔒 Combat level {enc.min_level}"
            if enc.key:
                key = reg.item(enc.key)
                line += f"\n{key.display} ×{owned.get(enc.key, 0)}" + ("" if has_key else " · needs a key (monsters drop them)")
            body.append(section(line, accessory=button("Fight", style=discord.ButtonStyle.danger, disabled=not open_,
                                                       on_click=self._starter(enc.id))))
        body.append(sep())
        body.append(row(button("Bestiary", emoji="📖", on_click=self._to_bestiary)))
        return Page("Fight", body, accent=0xC0392B)

    async def _to_bestiary(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "bestiary")

    def _starter(self, encounter_id: str):
        async def start(interaction: discord.Interaction) -> None:
            await self._begin(encounter_id)
            await self.refresh(interaction)

        return start

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
            line = f"### {foe.emoji} {foe.name}" if foe.alive else f"### 💀 ~~{foe.name}~~"
            if foe.alive:
                line += f"\n{hp_line(foe)}"
                if effect_line(foe):
                    line += f"\n{effect_line(foe)}"
                if (reveal or foe.telegraph) and foe.next_skill:
                    line += f"\n👁️ Next: **{battle.skill(foe.next_skill).name}**"
            body.append(text(line))
        body.append(sep())
        body.append(text(f"### {me.emoji} {me.name}\n{hp_line(me)}" + (f"\n{effect_line(me)}" if effect_line(me) else "")))
        order = " → ".join(u.emoji for u in battle.turn_order(7)) if battle.outcome is None else ""
        if order:
            body.append(text(f"**Turn order:** {order}"))
        body.append(sep())
        body.append(text("\n".join(battle.log[-9:])))
        body.append(sep())
        body.extend(self._controls(battle, me))
        if self.picking:
            body.insert(0, text(f"🎯 **{battle.skill(self.picking).name}**: pick a target."))
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
            label = skill.name + (f" ({cd})" if cd else "")
            style = discord.ButtonStyle.primary if i == 0 else discord.ButtonStyle.secondary
            buttons.append(button(label, style=style, disabled=cd > 0, on_click=self._skill(skill_id)))
        return [row(*buttons), row(button("Flee", emoji="🏃", on_click=self._flee))]

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
            lines = [recap, f"**+{paid.xp:,}** combat xp  ·  {paid.kills} slain", "🎁 " + (", ".join(loot) if loot else "Nothing dropped this time.")]
            self.result = Result("Victory!", lines, emoji="🏆", accent=0x2ECC71, again=self._again, again_label="Fight again")
        else:
            lines = [recap, "You wake up back at the camp, a little bruised. Nothing was lost but the time."]
            self.result = Result("Defeated", lines, emoji="💀", accent=0xE74C3C, again=self._again, again_label="Try again")
        await self.refresh(interaction)

    async def _again(self, interaction: discord.Interaction) -> None:
        await self._begin(self.encounter)
        await self.refresh(interaction)
