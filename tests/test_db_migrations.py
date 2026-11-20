import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from cococap.db import Database, close_database, init_database
from cococap.db.migrate import upgrade_sync
from cococap.db.tables import Base
from cococap.user import User


def test_migrations_produce_exactly_the_model_schema(tmp_path):
    """If someone edits tables.py without adding a migration, this fails."""
    path = tmp_path / "m.db"
    upgrade_sync(f"sqlite:///{path}")
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"tables.py differs from migrations: {diff}"


def test_migrating_twice_is_a_noop(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    upgrade_sync(url)
    upgrade_sync(url)


async def test_bot_startup_path_uses_migrations_and_enforces_constraints(tmp_path):
    db = await init_database(Database.from_path(tmp_path / "prod.db"), migrate=True)
    try:
        user = await User.get(1)
        await user.add_item("fish_cod", 2)
        assert await user.items() == {"fish_cod": 2}
        async with db.session() as session:
            with pytest.raises(IntegrityError):  # CHECK constraints exist in the migrated schema too
                await session.execute(text("UPDATE users SET purse = -5"))
    finally:
        await close_database()


async def test_wal_mode_and_foreign_keys_are_on(db):
    async with db.session() as session:
        assert (await session.execute(text("PRAGMA journal_mode"))).scalar() == "wal"
        assert (await session.execute(text("PRAGMA foreign_keys"))).scalar() == 1


def test_the_material_cull_refunds_the_removed_items_at_their_sell_price(tmp_path):
    """Migration 0008: whoever held a removed material gets its sell price per item in bits, and the stack is deleted."""
    import sqlite3

    from cococap.db.migrate import upgrade_sync

    url = f"sqlite:///{tmp_path / 'old.db'}"
    upgrade_sync(url, "0007")
    con = sqlite3.connect(tmp_path / "old.db")
    # every required column gets a filler (the old schema has no database defaults), then the purse
    cols = [(r[1], r[2]) for r in con.execute("PRAGMA table_info(users)") if r[3] and r[4] is None]
    for uid, purse in ((1, 1000), (2, 5)):
        values = {name: (uid if name == "discord_id" else purse if name == "purse" else "x" if "CHAR" in kind.upper() or kind.upper() == "TEXT" else 0) for name, kind in cols}
        con.execute(f"INSERT INTO users ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values()))
    con.executemany(
        "INSERT INTO user_items (user_id, item_id, quantity) VALUES (?, ?, ?)",
        [(1, "pine_resin", 3), (1, "golden_pollen", 2), (1, "material_hardwood", 7), (2, "material_copper_ore", 4)],
    )
    con.commit()
    con.close()
    upgrade_sync(url)
    con = sqlite3.connect(tmp_path / "old.db")
    purses = dict(con.execute("SELECT discord_id, purse FROM users"))
    items = set(con.execute("SELECT user_id, item_id FROM user_items"))
    assert purses == {1: 1000 + 3 * 3500 + 2 * 50000, 2: 5}
    assert items == {(1, "material_hardwood"), (2, "material_copper_ore")}


def test_prefixed_ids_migration_renames_every_stored_id_and_back(tmp_path):
    """Migration 0009: inventory, tool templates, skill/pethouse JSON and starter stats all get the new ids; downgrade restores them."""
    import json
    import sqlite3

    url = f"sqlite:///{tmp_path / 'old.db'}"
    upgrade_sync(url, "0008")
    con = sqlite3.connect(tmp_path / "old.db")
    cols = [(r[1], r[2]) for r in con.execute("PRAGMA table_info(users)") if r[3] and r[4] is None]
    values = {name: (1 if name == "discord_id" else "x" if "CHAR" in kind.upper() or kind.upper() == "TEXT" else 0) for name, kind in cols}
    values["pethouse"] = json.dumps({"active": "dog", "pets": {"dog": {"stars": 1}, "cat": {"stars": 2}}})
    con.execute(f"INSERT INTO users ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values()))
    con.executemany("INSERT INTO user_items (user_id, item_id, quantity) VALUES (1, ?, ?)", [("cod", 2), ("copper_ore", 3), ("scroll_double_strike", 1)])
    con.execute("INSERT INTO item_instances (owner_id, template_id, rolled, enchants) VALUES (1, 'rookiepickaxe', '{}', '{}')")
    con.execute("INSERT INTO user_skills (user_id, skill, xp, data) VALUES (1, 'farming', 0, ?)", [json.dumps({"seeds": {"apple_seed": 4}, "plots": [{"crop": "apple"}]})])
    con.execute("INSERT INTO user_stats (user_id, name, value) VALUES (1, 'starter_claimed_starter_rod', 1), (1, 'hl_wins', 5)")
    con.commit()
    con.close()

    upgrade_sync(url)
    con = sqlite3.connect(tmp_path / "old.db")
    assert dict(con.execute("SELECT item_id, quantity FROM user_items")) == {"fish_cod": 2, "material_copper_ore": 3, "scroll_double_strike": 1}
    assert con.execute("SELECT template_id FROM item_instances").fetchone() == ("tool_pickaxe_rookie",)
    assert json.loads(con.execute("SELECT data FROM user_skills").fetchone()[0]) == {"seeds": {"seed_apple": 4}, "plots": [{"crop": "crop_apple"}]}
    house = json.loads(con.execute("SELECT pethouse FROM users").fetchone()[0])
    assert house == {"active": "cinder", "pets": {"cinder": {"stars": 1}, "drizzle": {"stars": 2}}}
    assert dict(con.execute("SELECT name, value FROM user_stats")) == {"starter_claimed_tool_rod_starter": 1, "hl_wins": 5}
    con.close()

    from alembic import command

    from cococap.db.migrate import _config

    command.downgrade(_config(url), "0008")
    con = sqlite3.connect(tmp_path / "old.db")
    assert dict(con.execute("SELECT item_id, quantity FROM user_items")) == {"cod": 2, "copper_ore": 3, "scroll_double_strike": 1}
    assert json.loads(con.execute("SELECT pethouse FROM users").fetchone()[0])["active"] == "dog"


def test_cutting_the_zone_materials_swaps_them_for_a_few_original_ones(tmp_path):
    """Migration 0010: each distinct zone material held (any star) becomes 2 plant fiber + 2 compost; the stacks are deleted."""
    import sqlite3

    url = f"sqlite:///{tmp_path / 'old.db'}"
    upgrade_sync(url, "0009")
    con = sqlite3.connect(tmp_path / "old.db")
    cols = [(r[1], r[2]) for r in con.execute("PRAGMA table_info(users)") if r[3] and r[4] is None]
    for uid in (1, 2):
        values = {name: (uid if name == "discord_id" else "x" if "CHAR" in kind.upper() or kind.upper() == "TEXT" else 0) for name, kind in cols}
        con.execute(f"INSERT INTO users ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values()))
    con.executemany(
        "INSERT INTO user_items (user_id, item_id, quantity) VALUES (?, ?, ?)",
        [(1, "material_slime_goo", 50), (1, "material_slime_goo_s2", 3), (1, "material_pale_bloom", 9), (1, "material_compost", 10), (2, "material_copper_ore", 4)],
    )
    con.commit()
    con.close()
    upgrade_sync(url)
    con = sqlite3.connect(tmp_path / "old.db")
    items = {(u, i): q for u, i, q in con.execute("SELECT user_id, item_id, quantity FROM user_items")}
    assert items == {(1, "material_plant_fiber"): 4, (1, "material_compost"): 14, (2, "material_copper_ore"): 4}


def test_retiring_the_stat_scrolls_pays_them_out_and_strips_their_enchants(tmp_path):
    """Migration 0013: held scrolls (any star) pay their sell price in bits and the stacks go; retired enchants leave tools."""
    import json
    import sqlite3

    url = f"sqlite:///{tmp_path / 'old.db'}"
    upgrade_sync(url, "0012")
    con = sqlite3.connect(tmp_path / "old.db")
    cols = [(r[1], r[2]) for r in con.execute("PRAGMA table_info(users)") if r[3] and r[4] is None]
    for uid in (1, 2):
        values = {name: (uid if name == "discord_id" else 1000 if name == "purse" else "x" if "CHAR" in kind.upper() or kind.upper() == "TEXT" else 0) for name, kind in cols}
        con.execute(f"INSERT INTO users ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values()))
    icols = [(r[1], r[2]) for r in con.execute("PRAGMA table_info(item_instances)") if r[3] and r[4] is None and not r[5]]
    for enchants in ('{"keen": 2, "soloist": 1}', '{"lure": 1}'):
        values = {name: ("x" if "CHAR" in kind.upper() or kind.upper() == "TEXT" else 0) for name, kind in icols}
        values["enchants"] = enchants
        con.execute(f"INSERT INTO item_instances ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values()))
    con.executemany(
        "INSERT INTO user_items (user_id, item_id, quantity) VALUES (?, ?, ?)",
        [(1, "scroll_keen", 3), (1, "scroll_bounty_s2", 2), (1, "scroll_lure", 1), (2, "material_copper_ore", 4)],
    )
    con.commit()
    con.close()
    upgrade_sync(url, "0013")
    con = sqlite3.connect(tmp_path / "old.db")
    purses = dict(con.execute("SELECT discord_id, purse FROM users"))
    items = {(u, i): q for u, i, q in con.execute("SELECT user_id, item_id, quantity FROM user_items")}
    enchants = [json.loads(e) for (e,) in con.execute("SELECT enchants FROM item_instances ORDER BY id")]
    assert purses == {1: 1000 + 5 * 400000, 2: 1000}
    assert items == {(1, "scroll_lure"): 1, (2, "material_copper_ore"): 4}
    assert enchants == [{"soloist": 1}, {"lure": 1}]


def test_retiring_five_more_scrolls_pays_them_out_and_strips_their_enchants(tmp_path):
    """Migration 0014: held Lure, Seasoning, Iron Frame, Deepcall and Gleaner scrolls (any star) pay bits; their enchants leave tools."""
    import json
    import sqlite3

    url = f"sqlite:///{tmp_path / 'old.db'}"
    upgrade_sync(url, "0013")
    con = sqlite3.connect(tmp_path / "old.db")
    cols = [(r[1], r[2]) for r in con.execute("PRAGMA table_info(users)") if r[3] and r[4] is None]
    for uid in (1, 2):
        values = {name: (uid if name == "discord_id" else 1000 if name == "purse" else "x" if "CHAR" in kind.upper() or kind.upper() == "TEXT" else 0) for name, kind in cols}
        con.execute(f"INSERT INTO users ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values()))
    icols = [(r[1], r[2]) for r in con.execute("PRAGMA table_info(item_instances)") if r[3] and r[4] is None and not r[5]]
    for enchants in ('{"lure": 1, "soloist": 1}', '{"double_hook": 2}'):
        values = {name: ("x" if "CHAR" in kind.upper() or kind.upper() == "TEXT" else 0) for name, kind in icols}
        values["enchants"] = enchants
        con.execute(f"INSERT INTO item_instances ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values()))
    con.executemany(
        "INSERT INTO user_items (user_id, item_id, quantity) VALUES (?, ?, ?)",
        [(1, "scroll_lure", 1), (1, "scroll_seasoned_s2", 2), (1, "scroll_double_hook", 1), (2, "material_copper_ore", 4)],
    )
    con.commit()
    con.close()
    upgrade_sync(url)
    con = sqlite3.connect(tmp_path / "old.db")
    purses = dict(con.execute("SELECT discord_id, purse FROM users"))
    items = {(u, i): q for u, i, q in con.execute("SELECT user_id, item_id, quantity FROM user_items")}
    enchants = [json.loads(e) for (e,) in con.execute("SELECT enchants FROM item_instances ORDER BY id")]
    assert purses == {1: 1000 + 3 * 400000, 2: 1000}
    assert items == {(1, "scroll_double_hook"): 1, (2, "material_copper_ore"): 4}
    assert enchants == [{"soloist": 1}, {"double_hook": 2}]


def test_star_tiers_migration_moves_each_starred_stack_down_one_tier(tmp_path):
    """Migration 0011: plain stays plain; _s2 becomes _s1 and _s3 becomes _s2 (the old 2-/3-star stacks lose one star)."""
    import sqlite3

    url = f"sqlite:///{tmp_path / 'old.db'}"
    upgrade_sync(url, "0010")
    con = sqlite3.connect(tmp_path / "old.db")
    cols = [(r[1], r[2]) for r in con.execute("PRAGMA table_info(users)") if r[3] and r[4] is None]
    values = {name: (1 if name == "discord_id" else "x" if "CHAR" in kind.upper() or kind.upper() == "TEXT" else 0) for name, kind in cols}
    con.execute(f"INSERT INTO users ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values()))
    con.executemany(
        "INSERT INTO user_items (user_id, item_id, quantity) VALUES (?, ?, ?)",
        [(1, "material_iron_ore", 5), (1, "material_iron_ore_s2", 3), (1, "material_iron_ore_s3", 2)],
    )
    con.commit()
    con.close()
    upgrade_sync(url)
    con = sqlite3.connect(tmp_path / "old.db")
    items = dict(con.execute("SELECT item_id, quantity FROM user_items"))
    assert items == {"material_iron_ore": 5, "material_iron_ore_s1": 3, "material_iron_ore_s2": 2}


def test_upgrade_backs_up_an_existing_database_first(tmp_path):
    url = f"sqlite:///{tmp_path / 'live.db'}"
    upgrade_sync(url, "0001")  # brand-new file: nothing to lose, no backup
    assert not (tmp_path / "backups").exists()
    upgrade_sync(url)  # an existing, out-of-date file is copied before it changes
    assert len(list((tmp_path / "backups").glob("live.pre-migrate-*.db"))) == 1
    upgrade_sync(url)  # already current: no second copy
    assert len(list((tmp_path / "backups").glob("live.pre-migrate-*.db"))) == 1
