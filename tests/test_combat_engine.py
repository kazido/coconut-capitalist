import random

import pytest

from cococap.registry import get_registry
from cococap.services.combat import ActiveEffect, Battle, CombatError, Unit

RULES = get_registry().combat


class FixedRng(random.Random):
    """A generator whose random() is scripted: crits and effect chances become exact."""

    def __init__(self, value: float):
        super().__init__(0)
        self.value = value

    def random(self):
        return self.value


NO_CRIT = FixedRng(0.99)  # never crits, every 100% effect lands, every <100% effect is resisted


def hero(**kw) -> Unit:
    args = dict(id="p1", name="Hero", side="player", max_hp=100, attack=20, defense=0, speed=100, skills=["slash", "cleave", "guard_break", "quick_step", "sanguine_priming", "glistening_haven", "brace"])
    return Unit(**{**args, **kw})


def foe(uid="e1", **kw) -> Unit:
    args = dict(id=uid, name=f"Foe {uid}", side="enemy", max_hp=100, attack=10, defense=0, speed=50, skills=["strike"])
    return Unit(**{**args, **kw})


def fight(*units, rng=NO_CRIT) -> Battle:
    battle = Battle(RULES, list(units), rng)
    battle.start()
    return battle


def test_rage_builds_when_hit_and_from_skills():
    h = hero(resource_kind="rage", resource_max=100)
    f = foe()
    b = Battle(RULES, [h, f], NO_CRIT)
    b._hit(f, h, 1.0)  # a foe's hit lands on the player
    assert h.resource == RULES.resources["rage"].on_hit_taken
    h.resource = 0
    b._use(h, RULES.skills["slash"], [f])  # slash has a gain
    assert h.resource == RULES.skills["slash"].gain


def test_mana_starts_full_and_refills_each_turn():
    mana = RULES.resources["mana"]
    cap = mana.start + mana.per_turn * 2
    h = hero(resource_kind="mana", resource_max=cap)
    b = Battle(RULES, [h, foe()], NO_CRIT)
    b.start()  # the hero acts first here, so the start and its first refill both land
    assert h.resource == min(cap, mana.start + mana.per_turn)
    b._start_turn(h)
    assert h.resource == min(cap, mana.start + mana.per_turn * 2)


def test_focus_builds_only_on_unhurt_turns():
    focus = RULES.resources["focus"]
    h = hero(resource_kind="focus", resource_max=100)
    b = Battle(RULES, [h, foe()], NO_CRIT)
    h.resource, h.hurt = 0, False
    b._start_turn(h)
    assert h.resource == focus.per_unhurt_turn
    h.resource, h.hurt = 0, True
    b._start_turn(h)
    assert h.resource == 0


def test_focus_raises_crit_chance():
    def crits(points: int) -> int:
        h = hero(resource_kind="focus", resource_max=100, resource=points)
        f = foe(max_hp=10**6)
        b = Battle(RULES, [h, f], random.Random(7))
        for _ in range(200):
            b._hit(h, f, 1.0)
        return sum("CRIT" in line for line in b.log)

    assert crits(100) > crits(0)


def test_play_refuses_a_skill_without_its_cost():
    cost = RULES.skills["rampage"].cost
    h = hero(id="p1", resource_kind="rage", resource_max=100, skills=["rampage"])
    b = fight(h, foe())
    assert b.active is h
    with pytest.raises(CombatError):
        b.play("rampage", target_id="e1")
    h.resource = cost
    b.play("rampage", target_id="e1")
    assert h.resource < cost  # the cost was spent (foe hits may refill a little)


def test_chill_slows_the_unit():
    f = foe()
    value = RULES.skills["frost_bolt"].effects[0].value
    f.effects.append(ActiveEffect("chill", 2, value))
    assert f.eff_speed == pytest.approx(f.speed * (1 - value))


def test_shatter_multiplies_a_fire_hit_on_a_chilled_target_and_ends_the_chill():
    rules = RULES.model_copy(update={"crit_chance": 0})
    skill = rules.skills["fireball"]

    def dealt(chilled: bool) -> tuple[int, Unit]:
        h, f = hero(), foe(max_hp=10**6)
        if chilled:
            f.effects.append(ActiveEffect("chill", 2, 0.2))
        b = Battle(rules, [h, f], NO_CRIT)
        b._use(h, skill, [f])
        return 10**6 - f.hp, f

    plain, _ = dealt(False)
    shattered, target = dealt(True)
    assert shattered == pytest.approx(plain * rules.elements.shatter, abs=1)
    assert not target.has("chill")


def test_ignite_detonates_the_old_burn_then_applies_a_fresh_one():
    def hp_lost(burning: bool) -> tuple[int, Unit]:
        h, f = hero(), foe(max_hp=10**6)
        if burning:
            f.effects.append(ActiveEffect("burn", 2, 5.0))
        Battle(RULES, [h, f], NO_CRIT)._use(h, RULES.skills["fireball"], [f])
        return 10**6 - f.hp, f

    base, _ = hp_lost(False)
    ignited, target = hp_lost(True)
    assert ignited - base == round(5.0 * 2)  # the old burn: value x turns, at once
    burn = next(e for e in target.effects if e.kind == "burn")
    assert burn.turns == RULES.skills["fireball"].effects[0].turns


def test_storm_chain_also_hits_a_second_foe():
    h, e1, e2 = hero(), foe("e1"), foe("e2")
    b = Battle(RULES, [h, e1, e2], NO_CRIT)
    b._use(h, RULES.skills["chain_lightning"], [e1])
    assert e2.hp < e2.max_hp


def test_taunt_forces_the_enemy_onto_the_taunting_player():
    def hit_target(taunt: bool) -> tuple[Unit, Unit]:
        p1 = hero(id="p1", hp=50)  # lower hp: the weakest-first rule would pick this one
        p2 = hero(id="p2", name="Mate")
        if taunt:
            p2.effects.append(ActiveEffect("taunt", 2, 0.0))
        e = foe(skills=["strike"])
        b = Battle(RULES, [p1, p2, e], NO_CRIT)
        e.next_skill = "strike"
        b._enemy_turn(e)
        return p1, p2

    p1, p2 = hit_target(taunt=True)
    assert p2.hp < p2.max_hp and p1.hp == 50
    p1, p2 = hit_target(taunt=False)
    assert p1.hp < 50 and p2.hp == p2.max_hp


def test_counter_hits_back_but_is_not_countered():
    h, f = hero(), foe()
    counter = RULES.skills["retaliate"].effects[0].value
    h.effects.append(ActiveEffect("counter", 2, counter))
    b = Battle(RULES, [h, f], NO_CRIT)
    b._hit(f, h, 1.0)
    assert f.hp < f.max_hp

    h2, f2 = hero(), foe()
    for u in (h2, f2):
        u.effects.append(ActiveEffect("counter", 2, counter))
    b2 = Battle(RULES, [h2, f2], NO_CRIT)
    b2._hit(f2, h2, 1.0)
    assert sum("counters!" in line for line in b2.log) == 1


def test_reflect_sends_part_of_the_damage_back():
    value = RULES.skills["taunt"].effects[1].value
    h, f = hero(), foe()
    h.effects.append(ActiveEffect("reflect", 2, value))
    b = Battle(RULES, [h, f], NO_CRIT)
    before = h.hp
    b._hit(f, h, 1.0)
    damage = before - h.hp
    assert f.max_hp - f.hp == max(1, round(damage * value))


def test_play_refuses_another_party_members_turn():
    p1, p2 = hero(id="p1"), hero(id="p2", name="Mate")
    b = fight(p1, p2, foe())
    assert b.active is p1
    with pytest.raises(CombatError):
        b.play("slash", target_id="e1", actor_id="p2")
