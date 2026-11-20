import random

import pytest

from cococap.registry import get_registry
from cococap.services import combat
from cococap.services.combat import Battle, CombatError, Unit, enemy_unit

RULES = get_registry().combat


class FixedRng(random.Random):
    """A generator whose random() is scripted: crits and effect chances become exact."""

    def __init__(self, value: float):
        super().__init__(0)
        self.value = value

    def random(self):
        return self.value


NO_CRIT = FixedRng(0.99)  # never crits, every 100% effect still lands, every <100% effect is resisted
ALWAYS = FixedRng(0.0)  # always crits and always lands effects


def hero(**kw) -> Unit:
    args = dict(id="p1", name="Hero", side="player", max_hp=100, attack=20, defense=0, speed=100, skills=["slash", "cleave", "berserk", "guard_break", "quick_step", "sanguine_priming", "glistening_haven", "brace"])
    return Unit(**{**args, **kw})


def foe(uid="e1", **kw) -> Unit:
    args = dict(id=uid, name=f"Foe {uid}", side="enemy", max_hp=100, attack=10, defense=0, speed=50, skills=["strike"])
    return Unit(**{**args, **kw})


def fight(*units, rng=NO_CRIT) -> Battle:
    battle = Battle(RULES, list(units), rng)
    battle.start()
    return battle


# ---- data ------------------------------------------------------------------------------------------------------------
def test_shipped_combat_data_loads_and_every_kit_starts_with_a_free_skill():
    reg = get_registry()
    assert reg.combat.encounters and reg.combat.kits["default"] == ["slash"]
    for kit in reg.combat.kits.values():
        assert reg.combat.skills[kit[0]].cooldown == 0


# ---- turn meter ----------------------------------------------------------------------------------------------------
def test_the_faster_unit_acts_more_often():
    b = fight(hero(speed=200), foe(speed=100))
    order = [u.id for u in b.turn_order(6)]
    assert order.count("p1") == 4 and order.count("e1") == 2


def test_turn_order_ties_go_to_the_player_and_the_first_move_is_whoever_is_fastest():
    b = fight(hero(speed=100), foe(speed=100))
    assert b.active.id == "p1"
    slow = fight(hero(speed=50), foe(speed=200))
    assert slow.active.id == "p1" and slow.turns >= 3  # the enemy took its turns before the first player turn


def test_a_speed_buff_and_a_meter_push_change_who_goes_next():
    b = fight(hero(speed=100), foe(speed=120, max_hp=1000))
    b.play("quick_step")  # +30% speed and a 30% meter push
    assert b.unit("p1").has("speed_up") and b.unit("p1").meter >= 0


# ---- damage --------------------------------------------------------------------------------------------------------
def test_damage_is_attack_times_power_reduced_by_defense():
    b = fight(hero(attack=20), foe(defense=100, max_hp=500))
    b.play("slash", "e1")
    assert b.unit("e1").max_hp - b.unit("e1").hp == 10  # 20 x 1.0 x 100 / (100 + 100)


def test_a_crit_hits_harder():
    normal = fight(hero(), foe(max_hp=500)); normal.play("slash", "e1")
    crit = fight(hero(), foe(max_hp=500), rng=ALWAYS); crit.play("slash", "e1")
    lost = lambda b: 500 - b.unit("e1").hp
    assert lost(crit) == round(20 * RULES.crit_damage) > lost(normal) == 20


def test_a_shield_soaks_damage_before_hp():
    b = fight(hero(attack=20), foe(shield=15, max_hp=100))
    b.play("slash", "e1")
    assert (b.unit("e1").shield, b.unit("e1").hp) == (0, 95)


def test_damage_is_never_zero():
    b = fight(hero(attack=1), foe(defense=100000, max_hp=50))
    b.play("slash", "e1")
    assert b.unit("e1").hp == 49


# ---- skills and cooldowns -------------------------------------------------------------------------------------------
def test_cleave_hits_every_enemy():
    b = fight(hero(), foe("e1", max_hp=500), foe("e2", max_hp=500))
    b.play("cleave")
    assert b.unit("e1").hp < 500 and b.unit("e2").hp < 500


def test_a_skill_on_cooldown_cannot_be_used_until_enough_of_your_turns_passed():
    b = fight(hero(speed=300), foe(max_hp=10000, speed=1))
    b.play("cleave")  # cooldown 3
    for _ in range(2):
        with pytest.raises(CombatError, match="recharging"):
            b.play("cleave")
        b.play("slash", "e1")
    with pytest.raises(CombatError, match="recharging"):
        b.play("cleave")
    b.play("slash", "e1")
    b.play("cleave")  # three turns later it is back


def test_you_must_pick_a_valid_target_and_know_the_skill():
    b = fight(hero(), foe("e1"), foe("e2"))
    with pytest.raises(CombatError, match="target"):
        b.play("slash")
    with pytest.raises(CombatError, match="know"):
        b.play("nonsense", "e1")


def test_guard_break_lowers_defense_so_the_next_hit_hurts_more():
    b = fight(hero(speed=300), foe(defense=100, max_hp=1000, speed=1))
    b.play("guard_break", "e1")
    assert b.unit("e1").has("defense_down")
    before = b.unit("e1").hp
    b.play("slash", "e1")
    assert before - b.unit("e1").hp == round(20 * 100 / (100 + 50))  # defense 100 -> 50


def test_sanguine_priming_doubles_only_the_next_damaging_skill():
    b = fight(hero(speed=300), foe(max_hp=1000, speed=1))
    b.play("sanguine_priming")
    assert b.unit("p1").has("empower")
    b.play("slash", "e1")
    assert 1000 - b.unit("e1").hp == 40
    assert not b.unit("p1").has("empower")
    b.play("slash", "e1")
    assert 1000 - b.unit("e1").hp == 60


def test_a_stunned_unit_loses_its_turn_and_the_stun_wears_off():
    b = fight(hero(speed=100), foe(speed=1, max_hp=1000))
    hero_unit = b.unit("p1")
    hero_unit.effects.append(combat.ActiveEffect("stun", 1, 0))
    hero_unit.meter = 0
    b.active = None
    b._advance()  # the hero's meter fills, the stun eats the turn, then it fills again and the hero is up
    assert any("stunned" in line for line in b.log)
    assert not hero_unit.has("stun") and b.active is hero_unit and b.unit("e1").hp == 1000


def test_stun_immunity_protects_bosses_and_others_are_stunned():
    skill = RULES.skills["armor_slam"]
    immune = fight(hero(immune=frozenset({"stun"})), foe(), rng=ALWAYS)
    immune._use(immune.unit("e1"), skill, [immune.unit("p1")])
    assert not immune.unit("p1").has("stun") and any("immune" in line for line in immune.log)
    normal = fight(hero(), foe(), rng=ALWAYS)
    normal._use(normal.unit("e1"), skill, [normal.unit("p1")])
    assert normal.unit("p1").has("stun")


def test_a_self_buff_lasts_its_full_turns_after_the_turn_it_was_cast():
    b = fight(hero(speed=300), foe(max_hp=1000, speed=1))
    b.play("quick_step")  # speed_up for 2 turns
    buff = next(e for e in b.unit("p1").effects if e.kind == "speed_up")
    assert buff.turns == 2  # not eaten by the casting turn
    b.play("slash", "e1")
    assert buff.turns == 1
    b.play("slash", "e1")
    assert not b.unit("p1").has("speed_up")


def test_bleed_hurts_at_the_start_of_the_victims_turn_ignores_defense_and_can_kill():
    b = fight(hero(), foe(max_hp=100, defense=1000))
    victim = b.unit("e1")
    victim.effects.append(combat.ActiveEffect("bleed", 3, 10))
    assert b._start_turn(victim) and victim.hp == 90
    victim.hp = 5
    assert not b._start_turn(victim) and not victim.alive


def test_heal_never_overheals():
    b = fight(hero(speed=300), foe(max_hp=1000, speed=1))
    b.unit("p1").hp = 90
    b.play("glistening_haven", "e1")
    assert b.unit("p1").hp == 100


def test_effects_that_miss_are_reported():
    b = fight(hero(), foe(skills=["armor_slam"], speed=300, max_hp=1000))  # 40% stun, the scripted roll is 0.99
    assert not b.unit("p1").has("stun") and any("resisted" in line for line in b.log)


# ---- the fight itself -----------------------------------------------------------------------------------------------
def test_killing_every_enemy_wins_and_the_fight_stops_taking_actions():
    b = fight(hero(attack=500), foe(max_hp=10))
    b.play("slash", "e1")
    assert b.outcome == "win" and b.active is None
    with pytest.raises(CombatError):
        b.play("slash", "e1")


def test_losing_all_hp_loses():
    b = fight(hero(max_hp=5, defense=0), foe(attack=500, speed=300))
    assert b.outcome == "loss"


def test_a_fight_that_never_ends_is_a_loss():
    b = fight(hero(attack=1), foe(max_hp=10**9, attack=0, speed=100))
    while not b.outcome:
        b.play("slash", "e1")
    assert b.outcome == "loss"


def test_enemies_use_their_first_skill_that_is_off_cooldown_and_show_what_is_next():
    b = fight(hero(max_hp=10**6), enemy_unit(get_registry().enemies["armored_zombie"], "e1"))
    assert b.unit("e1").next_skill == "armor_slam"
    while b.unit("e1").next_skill == "armor_slam":
        b.play("slash", "e1")
    assert b.unit("e1").next_skill == "strike"  # slam is recharging


def test_xp_is_paid_only_for_a_win():
    win = fight(hero(attack=500), foe(max_hp=10, xp=40)); win.play("slash", "e1")
    assert win.xp_earned == 40 and win.kills == 1
    loss = fight(hero(max_hp=1), foe(attack=900, speed=300, xp=40))
    assert loss.xp_earned == 0


def test_a_seeded_fight_is_reproducible():
    def run():
        b = combat.battle_with(hero(), ["armored_zombie", "skeleton", "zombie"], rng=random.Random(7))
        while not b.outcome:
            b.play("slash", b.living("enemy")[0].id)
        return b.log
    assert run() == run()


# ---- building and settling -----------------------------------------------------------------------------------------
async def test_a_fresh_player_fights_bare_handed_and_a_sword_adds_attack_and_skills(db):
    from cococap.user import User

    user = await User.get(1)
    p = RULES.player
    bare = await combat.build_player(user)
    assert bare.skills == ["slash"]
    lv = User.xp_to_level(0)
    assert (bare.max_hp, bare.attack, bare.defense, bare.speed) == (
        p.base_hp + p.hp_per_level * lv, p.base_attack + p.attack_per_level * lv, p.base_defense + p.defense_per_level * lv, p.speed)


async def test_settle_pays_xp_and_counts_kills(db):
    from cococap.user import User

    user = await User.get(1)
    b = fight(hero(attack=500), foe(max_hp=10, xp=40))
    b.play("slash", "e1")
    assert (await combat.settle(user, b)).xp == 40
    assert (await user.skill("combat")).xp == 40 and (await user.skill("combat")).stats.monsters_slain == 1
    # bare hands earn the "unarmed" class xp, and kit unlocks follow the class level
    assert (await user.skill("combat")).class_xp == {combat.UNARMED: 40}
    assert await combat.current_class(user) == (combat.UNARMED, User.xp_to_level(40))


# ---- the final boss ------------------------------------------------------------------------------------------------------------
def test_the_boss_is_stun_immune_telegraphs_and_has_ordered_phases():
    gw = get_registry().enemies["gravewarden"]
    assert "stun" in gw.immune and gw.telegraph
    assert [p.below for p in gw.phases] == sorted((p.below for p in gw.phases), reverse=True) and len(gw.phases) == 2
    assert get_registry().combat.encounters[-1].enemies == ["gravewarden"]


def test_every_kit_fits_one_row_of_buttons():
    for name, kit in RULES.kits.items():
        assert len(kit) <= 5, name
    for cls in RULES.classes.values():
        assert len(cls.kit) <= 25, cls.id  # a pool: the loadout picker is one dropdown
    assert combat.LOADOUT_SIZE <= 5  # the loadout is the fight button row


def test_you_get_the_first_turn_against_the_boss_and_see_the_death_knell_coming():
    b = fight(hero(max_hp=10**6, speed=RULES.player.speed), boss_unit())
    assert b.active.id == "p1" and b.unit("e1").next_skill == "death_knell" and b.unit("e1").telegraph


def boss_unit() -> Unit:
    return enemy_unit(get_registry().enemies["gravewarden"], "e1")


def test_a_boss_phase_starts_once_when_hp_falls_below_its_mark_with_message_buff_and_new_skills():
    b = fight(hero(), boss_unit())
    gw = b.unit("e1")
    gw.hp = int(gw.max_hp * 0.61)
    b._check_phase(gw)
    assert gw.phase == 0  # still above the mark
    gw.hp = int(gw.max_hp * 0.59)
    b._check_phase(gw)
    assert gw.phase == 1 and gw.has("attack_up") and "grave_chill" in gw.skills
    assert any("eyes ignite" in line for line in b.log)
    b._check_phase(gw)
    assert gw.phase == 1 and len([e for e in gw.effects if e.kind == "attack_up"]) == 1  # once, not every hit


def test_a_big_hit_can_skip_straight_through_two_phases():
    b = fight(hero(), boss_unit())
    gw = b.unit("e1")
    gw.hp = int(gw.max_hp * 0.2)
    b._check_phase(gw)
    assert gw.phase == 2 and gw.has("speed_up")
    assert next(e for e in gw.effects if e.kind == "attack_up").value == 0.6  # the enraged value wins, buffs refresh not stack


def test_a_phase_resets_cooldowns_and_replans_the_next_move():
    b = fight(hero(), boss_unit())
    gw = b.unit("e1")
    gw.cooldowns["death_knell"] = 4
    gw.next_skill = "bone_strike"
    gw.hp = int(gw.max_hp * 0.5)
    b._check_phase(gw)
    assert gw.cooldowns == {} and gw.next_skill == "death_knell"


def test_a_phase_comes_from_damage_in_a_real_fight():
    b = fight(hero(attack=300, speed=300, max_hp=10**6), boss_unit())
    while b.unit("e1").phase == 0 and not b.outcome:
        b.play("slash", "e1")
    assert b.unit("e1").phase >= 1 and any("ignite" in line or "enraged" in line for line in b.log)


def test_a_dead_boss_does_not_enter_a_phase():
    b = fight(hero(attack=10**5, speed=300, max_hp=10**6), boss_unit())
    b.play("slash", "e1")
    assert b.outcome == "win" and b.unit("e1").phase == 0


def test_brace_makes_a_big_hit_hurt_about_half_as_much():
    plain = fight(hero(max_hp=10**6, defense=25, speed=1), boss_unit(), rng=NO_CRIT)
    plain._use(plain.unit("e1"), RULES.skills["death_knell"], [plain.unit("p1")])
    braced = fight(hero(max_hp=10**6, defense=25, speed=300), boss_unit(), rng=NO_CRIT)
    braced.play("brace")
    taken_plain = 10**6 - plain.unit("p1").hp
    braced.unit("p1").hp = 10**6
    braced._use(braced.unit("e1"), RULES.skills["death_knell"], [braced.unit("p1")])
    assert (10**6 - braced.unit("p1").hp) < taken_plain * 0.6


def planned(*units) -> Battle:
    battle = Battle(RULES, list(units), NO_CRIT, planned=True)
    battle.start()
    return battle


def test_planned_fight_does_nothing_until_you_play_then_a_faster_enemy_goes_first():
    b = planned(hero(speed=50), foe(speed=200, attack=30))
    assert b.turns == 0 and b.turn_order(1)[0].id == "e1"  # the display shows who is next, nothing has happened
    b.play("slash", "e1")
    assert [side for side, _ in b.steps][-2:] == ["enemy", "you"] and b.unit("p1").hp < 100 and b.unit("e1").hp < 100


def test_planned_fight_stops_after_your_turn_so_slower_enemies_wait():
    b = planned(hero(speed=200), foe(speed=50))
    b.play("slash", "e1")
    assert b.unit("p1").hp == 100 and b.turn_order(1)[0].id == "p1"  # the enemy has not acted yet


def test_berserk_spends_a_full_rage_bar_for_damage_up_and_damage_taken_down():
    b = fight(hero(speed=200, resource_kind="rage", resource=100, resource_max=100), foe(speed=50, max_hp=500))
    b.play("berserk")
    h = b.unit("p1")
    assert h.resource == 0 and h.has("attack_up") and h.has("defense_up")
    low = fight(hero(resource_kind="rage", resource=99, resource_max=100), foe())
    with pytest.raises(CombatError):
        low.play("berserk")
