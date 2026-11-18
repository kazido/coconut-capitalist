"""Turn-based combat in the style of Summoners War. No Discord, no SQL in the engine (only `build_player` and the
reward helpers touch the database).

* Every unit has a SPEED. Its turn meter fills by that much per tick; the first unit to reach `meter_full` acts and its
  meter drops back to 0. Speed, slows and meter pushes are how you win fights, not just damage.
* Skills have COOLDOWNS, never costs: no consumables, no mana. Skill 1 of every kit can always be used.
* Buffs and debuffs (attack, defense, speed, stun, bleed, shields, ...) last a number of the AFFECTED unit's own turns.
* Enemies use the first of their skills that is off cooldown, so their next move is predictable (and a sword may show it).
* Damage is deterministic apart from crits: attack x skill power x scale / (scale + defense).

A `Battle` is driven by `start()` (runs until it is a player's turn) and then `play(skill_id, target_id)` per player turn.
"""

import random
from dataclasses import dataclass, field

from cococap import emojis
from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.registry.models import BUFFS, CombatRules, CombatSkill, Enemy, Phase, SkillEffect
from cococap.services import equipment, loot, tool_effects
from cococap.user import User

TIMED = frozenset({"attack_up", "attack_down", "defense_up", "defense_down", "speed_up", "speed_down", "stun", "bleed", "empower", "reveal"})
STAT_PAIRS = {"attack": ("attack_up", "attack_down"), "defense": ("defense_up", "defense_down"), "speed": ("speed_up", "speed_down")}
_EFFECT_LABEL_PARTS = {  # effect -> (icon name, glyph fallback, label)
    "attack_up": ("up", "⬆️", "Attack"), "attack_down": ("down", "⬇️", "Attack"), "defense_up": ("shield", "🛡️", "Defense"),
    "defense_down": ("heart", "💔", "Defense"), "speed_up": ("bolt", "⚡", "Speed"), "speed_down": ("bug", "🐌", "Slow"),
    "stun": ("sparkle", "💫", "Stun"), "bleed": ("blood", "🩸", "Bleed"), "empower": ("flame", "🔥", "Primed"), "reveal": ("eye", "👁️", "Insight"),
}


class _EffectLabels:
    """EFFECT_LABELS[kind] / .get(kind): "<icon> Label", with the icon looked up when read (custom emoji load after import)."""

    def __getitem__(self, kind: str) -> str:
        name, glyph, label = _EFFECT_LABEL_PARTS[kind]
        return f"{emojis.icon(name, glyph)} {label}"

    def get(self, kind: str, default=None):
        return self[kind] if kind in _EFFECT_LABEL_PARTS else default


EFFECT_LABELS = _EffectLabels()


class CombatError(GameRuleError):
    """The player tried something the rules do not allow; the message is safe to show."""


@dataclass
class ActiveEffect:
    kind: str
    turns: int
    value: float  # a fraction for stat changes, damage per turn for bleed, a multiplier for empower
    fresh: bool = False  # applied by the unit to itself during its own turn: it must not lose a turn right away

    @property
    def is_buff(self) -> bool:
        return self.kind in BUFFS


@dataclass
class Unit:
    id: str
    name: str
    side: str  # "player" or "enemy"
    max_hp: int
    attack: int
    defense: int
    speed: int
    skills: list[str]
    hp: int = 0
    shield: int = 0
    emoji: str = field(default_factory=lambda: emojis.icon("people", "🧑"))
    immune: frozenset[str] = frozenset()
    xp: int = 0
    meter: float = 0.0
    cooldowns: dict[str, int] = field(default_factory=dict)  # skill id -> own turns until it can be used again
    effects: list[ActiveEffect] = field(default_factory=list)
    next_skill: str | None = None  # enemies only: what they will do on their next turn
    enemy_id: str | None = None  # which kind of enemy this is (the Bestiary counts kills by it)
    boss: bool = False
    drops: str | None = None  # enemies: the drop table a kill rolls
    drop_chance: int = 0
    telegraph: bool = False  # bosses: the player can always see next_skill
    phases: list[Phase] = field(default_factory=list)  # bosses: changes of behaviour as hp drops
    phase: int = 0  # how many phases have already started

    def __post_init__(self):
        if not self.hp:
            self.hp = self.max_hp

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def has(self, kind: str) -> bool:
        return any(e.kind == kind for e in self.effects)

    def _stat(self, base: int, stat: str) -> float:
        up, down = STAT_PAIRS[stat]
        change = sum(e.value for e in self.effects if e.kind == up) - sum(e.value for e in self.effects if e.kind == down)
        return base * max(0.1, 1 + change)

    @property
    def eff_attack(self) -> float:
        return self._stat(self.attack, "attack")

    @property
    def eff_defense(self) -> float:
        return self._stat(self.defense, "defense")

    @property
    def eff_speed(self) -> float:
        return self._stat(self.speed, "speed")

    def ready(self, skill_id: str) -> bool:
        return self.cooldowns.get(skill_id, 0) <= 0


def enemy_unit(enemy: Enemy, uid: str) -> Unit:
    return Unit(
        id=uid, name=enemy.name, side="enemy", max_hp=enemy.hp, attack=enemy.attack, defense=enemy.defense,
        speed=enemy.speed, skills=list(enemy.skills), shield=enemy.shield, emoji=enemy.emoji,
        immune=frozenset(enemy.immune), xp=enemy.xp, enemy_id=enemy.id, boss=enemy.boss, drops=enemy.drops, drop_chance=enemy.drop_chance, telegraph=enemy.telegraph, phases=list(enemy.phases),
    )


class Battle:
    """One fight. Player units act when the UI calls `play`; enemies act by themselves."""

    def __init__(self, rules: CombatRules, units: list[Unit], rng: random.Random | None = None):
        self.rules = rules
        self.units = units
        self.rng = rng or random.Random()
        self.log: list[str] = []
        self.turns = 0  # turns taken so far
        self.active: Unit | None = None  # whose turn it is (a player, while the fight waits for input)
        self.outcome: str | None = None  # None while fighting, then "win" or "loss"

    # --- lookups -----------------------------------------------------------------------------
    def unit(self, uid: str) -> Unit:
        for u in self.units:
            if u.id == uid:
                return u
        raise CombatError("No such target.")

    def living(self, side: str | None = None) -> list[Unit]:
        return [u for u in self.units if u.alive and (side is None or u.side == side)]

    def skill(self, skill_id: str) -> CombatSkill:
        return self.rules.skills[skill_id]

    def targets_for(self, actor: Unit, skill: CombatSkill) -> list[Unit]:
        """The units this skill can be aimed at (the ones the player may pick from)."""
        foe = "enemy" if actor.side == "player" else "player"
        if skill.target == "enemy":
            return self.living(foe)
        if skill.target == "all_enemies":
            return self.living(foe)
        if skill.target == "ally":
            return self.living(actor.side)
        return [actor]

    @property
    def xp_earned(self) -> int:
        return sum(u.xp for u in self.units if u.side == "enemy") if self.outcome == "win" else 0

    @property
    def kills(self) -> int:
        return sum(1 for u in self.units if u.side == "enemy" and not u.alive)

    def turn_order(self, count: int = 6) -> list[Unit]:
        """The next `count` units to act, from the current meters and speeds (effects that change speed later are ignored)."""
        sim = {u.id: u.meter for u in self.living()}
        speeds = {u.id: u.eff_speed for u in self.living()}
        order = {u.id: i for i, u in enumerate(self.units)}
        full = self.rules.meter_full
        out: list[Unit] = []
        while len(out) < count and sim:
            need = {uid: max(0.0, (full - m) / speeds[uid]) for uid, m in sim.items()}
            dt = min(need.values())
            for uid in sim:
                sim[uid] += dt * speeds[uid]
            ready = [uid for uid, m in sim.items() if m >= full - 1e-9]
            actor = max(ready, key=lambda uid: (sim[uid], -order[uid]))
            out.append(self.unit(actor))
            sim[actor] = 0.0
        return out

    # --- driving the fight -----------------------------------------------------------------------
    def start(self) -> None:
        """Plan the enemies' first moves and run until it is the first player's turn."""
        for u in self.living("enemy"):
            u.next_skill = self._choose_skill(u)
        self.log.append(f"{emojis.icon('sword', '⚔️')} The fight begins!")
        self._advance()

    def play(self, skill_id: str, target_id: str | None = None) -> None:
        """The active player unit uses a skill, then the fight runs on to the next player turn (or the end)."""
        actor = self.active
        if self.outcome or actor is None or actor.side != "player":
            raise CombatError("It isn't your turn.")
        if skill_id not in actor.skills:
            raise CombatError("You don't know that skill.")
        skill = self.skill(skill_id)
        if not actor.ready(skill_id):
            raise CombatError(f"{skill.name} is recharging ({actor.cooldowns[skill_id]} more turn(s)).")
        pool = self.targets_for(actor, skill)
        if skill.target in {"enemy", "ally"}:
            target = next((u for u in pool if u.id == target_id), None) or (pool[0] if len(pool) == 1 else None)
            if target is None:
                raise CombatError("Pick a target.")
            chosen = [target]
        else:
            chosen = pool
        self._use(actor, skill, chosen)
        self._end_turn(actor)
        self._advance()

    # --- internals -------------------------------------------------------------------------------
    def _advance(self) -> None:
        """Run turns until a player must choose, or the fight is over."""
        while not self.outcome:
            self._check_end()
            if self.outcome:
                break
            if self.turns >= self.rules.max_rounds:
                self.outcome = "loss"
                self.log.append(f"{emojis.icon('timer', '⌛')} The fight dragged on too long. You retreat.")
                break
            actor = self._next_actor()
            self.active = actor
            if not self._start_turn(actor):  # died to bleed or was stunned
                continue
            if actor.side == "player":
                return
            self._enemy_turn(actor)
        self.active = None

    def _next_actor(self) -> Unit:
        full = self.rules.meter_full
        units = self.living()
        ready = [u for u in units if u.meter >= full]
        if not ready:
            dt = min((full - u.meter) / u.eff_speed for u in units)
            for u in units:
                u.meter += dt * u.eff_speed
            ready = [u for u in units if u.meter >= full - 1e-9]
        # most meter first; on a tie the earlier unit in the list (players come first) goes
        return max(ready, key=lambda u: (u.meter, -self.units.index(u)))

    def _start_turn(self, actor: Unit) -> bool:
        """Damage over time and stuns. Returns True if the unit can act."""
        self.turns += 1
        for e in [e for e in actor.effects if e.kind == "bleed"]:
            actor.hp = max(0, actor.hp - round(e.value))
            self.log.append(f"{emojis.icon('blood', '🩸')} {actor.name} bleeds for **{round(e.value)}**.")
            self._check_phase(actor)
        if not actor.alive:
            self.log.append(f"{emojis.icon('skull', '💀')} {actor.name} bled out.")
            actor.meter = 0
            return False
        if actor.has("stun"):
            self.log.append(f"{emojis.icon('sparkle', '💫')} {actor.name} is stunned and loses the turn.")
            self._end_turn(actor)
            return False
        return True

    def _end_turn(self, actor: Unit) -> None:
        actor.meter = 0
        for skill_id in list(actor.cooldowns):
            actor.cooldowns[skill_id] -= 1
            if actor.cooldowns[skill_id] <= 0:
                del actor.cooldowns[skill_id]
        for e in list(actor.effects):
            if e.fresh:
                e.fresh = False
            else:
                e.turns -= 1
                if e.turns <= 0:
                    actor.effects.remove(e)
        if actor.side == "enemy" and actor.alive:
            actor.next_skill = self._choose_skill(actor)
        self._check_end()

    def _choose_skill(self, unit: Unit) -> str:
        return next((s for s in unit.skills if unit.ready(s)), unit.skills[0])

    def _enemy_turn(self, actor: Unit) -> None:
        skill = self.skill(actor.next_skill or self._choose_skill(actor))
        pool = self.targets_for(actor, skill)
        if skill.target == "ally":
            chosen = [min(pool, key=lambda u: u.hp / u.max_hp)]
        elif skill.target == "enemy":
            chosen = [self.rng.choice(pool)]
        else:
            chosen = pool
        self._use(actor, skill, chosen)
        self._end_turn(actor)

    def _check_end(self) -> None:
        if self.outcome:
            return
        if not self.living("enemy"):
            self.outcome = "win"
            self.log.append(f"{emojis.icon('record', '🏆')} Victory!")
        elif not self.living("player"):
            self.outcome = "loss"
            self.log.append(f"{emojis.icon('skull', '💀')} You were defeated.")

    # --- skills ----------------------------------------------------------------------------------
    def _use(self, actor: Unit, skill: CombatSkill, targets: list[Unit]) -> None:
        if skill.cooldown:
            actor.cooldowns[skill.id] = skill.cooldown + 1  # +1: it counts down at the end of this very turn
        names = ", ".join(t.name for t in targets) if targets != [actor] else "itself"
        self.log.append(f"{actor.emoji} **{actor.name}** uses **{skill.name}** on {names}.")
        power = skill.power
        if power:
            empower = next((e for e in actor.effects if e.kind == "empower"), None)
            if empower:
                power *= empower.value
                actor.effects.remove(empower)
                self.log.append(f"{emojis.icon('flame', '🔥')} The primed blade bites twice as deep!")
        for target in targets:
            for _ in range(skill.hits):
                if power and target.alive:
                    self._hit(actor, target, power)
            for effect in skill.effects:
                if effect.on == "target" and target.alive:
                    self._apply(effect, actor, target)
        for effect in skill.effects:
            if effect.on == "self" and actor.alive:
                self._apply(effect, actor, actor)
        self._check_end()

    def _hit(self, actor: Unit, target: Unit, power: float) -> None:
        raw = actor.eff_attack * power * self.rules.defense_scale / (self.rules.defense_scale + target.eff_defense)
        crit = self.rng.random() * 100 < self.rules.crit_chance
        if crit:
            raw *= self.rules.crit_damage
        damage = max(1, round(raw))
        absorbed = min(target.shield, damage)
        target.shield -= absorbed
        target.hp = max(0, target.hp - (damage - absorbed))
        tag = f" {emojis.icon('boom', '💥')} **CRIT**" if crit else ""
        shield = f" ({absorbed} absorbed)" if absorbed else ""
        self.log.append(f"　{emojis.icon('next', '→')} {target.name} takes **{damage}**{shield}{tag}.")
        if not target.alive:
            self.log.append(f"　{emojis.icon('skull', '💀')} {target.name} falls.")
            target.meter = 0
        else:
            self._check_phase(target)

    def _check_phase(self, unit: Unit) -> None:
        """A boss whose hp fell below the next phase's mark enters it (a big hit can skip several marks)."""
        while unit.alive and unit.phase < len(unit.phases) and unit.hp / unit.max_hp < unit.phases[unit.phase].below:
            phase = unit.phases[unit.phase]
            unit.phase += 1
            self.log.append(f"{emojis.icon('flame', '🔥')} **{unit.name}**: {phase.message}")
            if phase.skills:
                unit.skills = list(phase.skills)
                unit.cooldowns.clear()
            for buff in phase.buffs:
                self._apply(buff, unit, unit)
            unit.next_skill = self._choose_skill(unit)

    def _apply(self, effect: SkillEffect, caster: Unit, target: Unit) -> None:
        if effect.kind in target.immune:
            self.log.append(f"　{emojis.icon('cross', '🚫')} {target.name} is immune to {EFFECT_LABELS.get(effect.kind, effect.kind)}.")
            return
        if self.rng.random() * 100 >= effect.chance:
            self.log.append(f"　{emojis.icon('cross', '🙅')} {target.name} resisted.")
            return
        kind = effect.kind
        if kind == "heal":
            gained = min(target.max_hp - target.hp, round(target.max_hp * effect.value))
            target.hp += gained
            self.log.append(f"　{emojis.icon('heart_green', '💚')} {target.name} heals **{gained}**.")
        elif kind == "shield":
            amount = round(caster.max_hp * effect.value)
            target.shield += amount
            self.log.append(f"　{emojis.icon('shield', '🔰')} {target.name} gains a **{amount}** shield.")
        elif kind == "meter":
            full = self.rules.meter_full
            target.meter = min(float(full), max(0.0, target.meter + full * effect.value))
            self.log.append(f"　{emojis.icon('next', '⏩') if effect.value > 0 else emojis.icon('prev', '⏪')} {target.name}'s turn meter {'fills' if effect.value > 0 else 'drains'}.")
        else:
            value = round(caster.eff_attack * effect.value) if kind == "bleed" else effect.value
            fresh = target is caster and self.active is caster
            existing = next((e for e in target.effects if e.kind == kind), None)
            if existing:  # the same effect again refreshes it rather than stacking
                existing.turns, existing.value, existing.fresh = max(existing.turns, effect.turns), max(existing.value, value), fresh
            else:
                target.effects.append(ActiveEffect(kind, effect.turns, value, fresh))
            self.log.append(f"　{EFFECT_LABELS[kind]} on {target.name} ({effect.turns} turn(s)).")


# --- building a fight ----------------------------------------------------------------------------
async def build_player(user: User, registry: Registry | None = None) -> Unit:
    """Turn a player's combat level and equipped sword into a fighting unit."""
    reg = registry or get_registry()
    rules = reg.combat.player
    level = User.xp_to_level((await user.skill("combat")).xp)
    instance = await user.equipped_instance("combat")
    power, kit = 0, "default"
    if instance is not None:
        power = equipment.effective_stats(instance, reg).power
        kit = instance.template_id if instance.template_id in reg.combat.kits else "default"
    extra_hp, extra_defense = tool_effects.sword_stats(power, reg) if instance is not None else (0, 0.0)
    return Unit(
        id="p1",
        name=user.name,
        side="player",
        max_hp=rules.base_hp + rules.hp_per_level * level + extra_hp,
        attack=rules.base_attack + rules.attack_per_power * power + rules.attack_per_level * level,
        defense=round(rules.base_defense + rules.defense_per_level * level + extra_defense),
        speed=rules.speed,
        skills=list(reg.combat.kits[kit]),
    )


def new_battle(player: Unit, encounter_id: str, registry: Registry | None = None, rng: random.Random | None = None) -> Battle:
    reg = registry or get_registry()
    encounter = next((e for e in reg.combat.encounters if e.id == encounter_id), None)
    if encounter is None:
        raise CombatError("That fight doesn't exist.")
    foes = [enemy_unit(reg.enemies[eid], f"e{i + 1}") for i, eid in enumerate(encounter.enemies)]
    battle = Battle(reg.combat, [player, *foes], rng)
    battle.start()
    return battle


@dataclass
class Settlement:
    """What a finished fight paid."""

    xp: int = 0
    kills: int = 0
    items: dict[str, int] = field(default_factory=dict)
    bits: int = 0
    bosses: int = 0
    slain: dict[str, int] = field(default_factory=dict)  # enemy id -> kills, for the Bestiary


async def start_fight(user: User, encounter_id: str, registry: Registry | None = None, rng: random.Random | None = None) -> Battle:
    """Check the level and the key (a key is spent when you walk in, win or lose), then start the fight."""
    reg = registry or get_registry()
    encounter = next((e for e in reg.combat.encounters if e.id == encounter_id), None)
    if encounter is None:
        raise CombatError("That fight doesn't exist.")
    level = User.xp_to_level((await user.skill("combat")).xp)
    if level < encounter.min_level:
        raise CombatError(f"You need combat level {encounter.min_level} for that.")
    player = await build_player(user, reg)
    if encounter.key:
        key = reg.item(encounter.key)
        try:
            await user.remove_item(encounter.key, 1)
        except ValueError:
            raise CombatError(f"You need a {key.name} to go in. The monsters of the graveyard drop them.") from None
    return new_battle(player, encounter_id, reg, rng)


async def settle(user: User, battle: Battle, registry: Registry | None = None, rng: random.Random | None = None) -> Settlement:
    """Pay out a finished fight: combat xp, drops from every monster that fell, and the monsters-slain count.
    Nothing is paid for a loss."""
    reg = registry or get_registry()
    rng = rng or random.Random()
    result = Settlement(xp=battle.xp_earned, kills=battle.kills)
    if battle.outcome != "win":
        return result
    for unit in battle.units:
        if unit.side == "enemy" and not unit.alive:
            if unit.enemy_id:
                result.slain[unit.enemy_id] = result.slain.get(unit.enemy_id, 0) + 1
            result.bosses += unit.boss
            drop = loot.roll_kill(unit.drops, unit.drop_chance, reg, rng)
            if drop is None:
                continue
            result.bits += drop.bits
            if drop.item_id:
                result.items[drop.item_id] = result.items.get(drop.item_id, 0) + drop.quantity
    if result.xp:
        await user.add_xp("combat", result.xp)
    for item_id, quantity in result.items.items():
        await user.add_item(item_id, quantity)
    if result.bits:
        await user.credit("purse", result.bits)
    if result.kills:
        def record(skill) -> None:
            skill.stats.monsters_slain += result.kills
            skill.stats.bosses_slain += result.bosses
            for enemy_id, count in result.slain.items():
                skill.kills[enemy_id] = skill.kills.get(enemy_id, 0) + count

        await user.update_skill("combat", record)
    return result
