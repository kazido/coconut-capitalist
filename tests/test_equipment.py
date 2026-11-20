import pytest

from cococap.models.instance import ItemInstance
from cococap.registry import RegistryError, get_registry, load_registry
from cococap.registry.loader import CONFIG_DIR
from cococap.services.equipment import (
    EquipmentError,
    add_enchant,
    effective_stats,
    equip,
    equipped_stats,
)
from cococap.user import User
from tests.conftest import set_columns


def inst(template_id, enchants=None, rolled=None, id=1):
    return ItemInstance(id=id, owner_id=1, template_id=template_id, enchants=enchants or {}, rolled=rolled or {})


# ---- effective_stats is pure ---------------------------------------------------------------
def test_plain_tool_uses_template_stats():
    stats = effective_stats(inst("tool_dreamnail"))
    assert (stats.power, stats.requirement, stats.ability) == (get_registry().item("tool_dreamnail").tool.power, 10, "enter_the_mind")
    assert stats.flags == frozenset()


def test_enchant_flags_and_rolled_bonuses():
    stats = effective_stats(inst("tool_axe_starter", {"soloist": 1}, {"power": 3}))
    base = get_registry().item("tool_axe_starter").tool.power
    assert stats.has("soloist") and stats.power == base + 3  # the axe's own power + rolled 3


@pytest.fixture
def stat_registry(tmp_path):
    """The shipped data plus two invented stat enchants, to test the maths."""
    import shutil

    for f in CONFIG_DIR.glob("*.toml"):
        shutil.copy(f, tmp_path / f.name)
    with open(tmp_path / "enchants.toml", "a") as f:
        f.write('''
[sharp]
name = "Sharp"
applies_to = ["sword"]
max_level = 3
[[sharp.effects]]
type = "stat_add"
stat = "power"
amount = 5

[mighty]
name = "Mighty"
applies_to = ["sword"]
[[mighty.effects]]
type = "stat_mult"
stat = "power"
amount = 0.5
''')
    return load_registry(tmp_path)


def test_adds_apply_before_multipliers_and_scale_with_level(stat_registry):
    # base + sharp III (+15), then mighty (x1.5); order of dict must not matter
    base = get_registry().item("tool_dreamnail").tool.power
    a = effective_stats(inst("tool_dreamnail", {"sharp": 3, "mighty": 1}), stat_registry)
    b = effective_stats(inst("tool_dreamnail", {"mighty": 1, "sharp": 3}), stat_registry)
    assert a.power == b.power == round((base + 15) * 1.5)


def test_levels_above_the_maximum_are_clamped(stat_registry):
    assert effective_stats(inst("tool_dreamnail", {"sharp": 99}), stat_registry).power == get_registry().item("tool_dreamnail").tool.power + 5 * 3


def test_non_tools_have_no_stats():
    with pytest.raises(EquipmentError):
        effective_stats(inst("fish_cod"))


# ---- registry validation of enchant data -----------------------------------------------------
def test_bad_enchant_data_is_rejected(tmp_path):
    import shutil

    for f in CONFIG_DIR.glob("*.toml"):
        shutil.copy(f, tmp_path / f.name)
    (tmp_path / "enchants.toml").write_text('[x]\nname="X"\napplies_to=["axe"]\n[[x.effects]]\ntype="stat_add"\n')
    with pytest.raises(RegistryError, match=r"enchants\.toml \[x\].*stat"):
        load_registry(tmp_path)


def test_shipped_enchants_apply_to_real_tool_kinds():
    assert get_registry().enchant("soloist").applies_to == ["axe"]


# ---- instances in the database ---------------------------------------------------------------
async def test_give_list_and_ownership(db):
    alice, bob = await User.get(1), await User.get(2)
    sword = await alice.give_instance("tool_dreamnail", enchants={"x": 1}, rolled={"power": 2})
    assert [i.id for i in await alice.instances()] == [sword.id]
    assert await alice.instance(sword.id) == sword
    assert await bob.instance(sword.id) is None  # not yours
    assert await bob.instances() == []


async def test_two_identical_templates_are_independent_objects(db):
    user = await User.get(1)
    a = await user.give_instance("tool_axe_starter")
    b = await user.give_instance("tool_axe_starter")
    await add_enchant(user, a.id, "soloist")
    assert (await user.instance(a.id)).enchants == {"soloist": 1}
    assert (await user.instance(b.id)).enchants == {}


async def test_cannot_equip_someone_elses_instance(db):
    alice, bob = await User.get(1), await User.get(2)
    axe = await alice.give_instance("tool_axe_starter")
    with pytest.raises(ValueError):
        await bob.equip("foraging", axe.id)


async def test_deleting_owner_deletes_instances(db):
    from sqlalchemy import text

    user = await User.get(1)
    await user.give_instance("tool_axe_starter")
    async with db.session() as session:
        await session.execute(text("DELETE FROM users WHERE discord_id = 1"))
        assert (await session.execute(text("SELECT count(*) FROM item_instances"))).scalar() == 0


# ---- equip / enchant rules -------------------------------------------------------------------
async def test_equip_checks_kind_and_level(db):
    user = await User.get(1)
    axe = await user.give_instance("tool_axe_starter")
    pick = await user.give_instance("tool_pickaxe_rookie")
    dream = await user.give_instance("tool_dreamnail")  # sword, needs combat level 10

    await equip(user, "foraging", axe.id)
    assert (await equipped_stats(user, "foraging")).power == get_registry().item("tool_axe_starter").tool.power
    with pytest.raises(EquipmentError, match="can't be used"):
        await equip(user, "foraging", pick.id)  # wrong kind
    with pytest.raises(EquipmentError, match="level 10"):
        await equip(user, "combat", dream.id)
    await user.add_xp("combat", User.level_to_xp(10) + 1)
    await equip(user, "combat", dream.id)
    assert (await equipped_stats(user, "combat")).power == get_registry().item("tool_dreamnail").tool.power
    assert await equipped_stats(user, "mining") is not None  # owned pickaxe gets auto-equipped


async def test_add_enchant_rules(db):
    user = await User.get(1)
    axe = await user.give_instance("tool_axe_starter")
    sword = await user.give_instance("tool_largebranch")
    updated = await add_enchant(user, axe.id, "soloist")
    assert updated.enchants == {"soloist": 1} and effective_stats(updated).has("soloist")
    with pytest.raises(EquipmentError, match="maximum"):
        await add_enchant(user, axe.id, "soloist")
    with pytest.raises(EquipmentError, match="can't be applied"):
        await add_enchant(user, sword.id, "soloist")  # axe-only enchant
    with pytest.raises(EquipmentError, match="own"):
        await add_enchant(user, 9999, "soloist")


async def test_owned_but_unequipped_tool_is_auto_equipped(db):
    # A tool you own but haven't equipped (e.g. freshly smithed) must not make screens say "claim your starter".
    from cococap.services.equipment import equipped_stats

    user = await User.get(9101)
    assert await equipped_stats(user, "foraging") is None  # owns nothing: truly nothing to use
    axe = await user.give_instance("tool_axe_starter")
    assert await equipped_stats(user, "foraging") is not None
    assert (await user.equipped_instance("foraging")).id == axe.id
