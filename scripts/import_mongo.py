"""One-off import of the production MongoDB into the SQLite database.

    pip install pymongo                      # only needed for this script
    python -m scripts.import_mongo --uri "mongodb+srv://..." --db discordbot            # dry run
    python -m scripts.import_mongo --uri "..." --db discordbot --write                  # writes data/cococap.db

Read-only against MongoDB. Refuses to write into a database that already has users unless
--force is given. Prints every anomaly it had to fix (negative balances, renamed items, ...).
"""

import argparse
import asyncio
import sys
from collections import Counter
from datetime import datetime

from sqlalchemy import select

from cococap import constants
from cococap.db import Database, init_database
from cococap.db.tables import (
    ItemInstanceRow,
    ItemRow,
    MegadropRow,
    PartyMemberRow,
    PartyRow,
    SkillRow,
    StatRow,
    UserRow,
)
from cococap.migrations import convert_mongo_user


def read_mongo(uri: str, db_name: str):
    from pymongo import MongoClient

    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    db = client[db_name]
    users = list(db["users"].find({}))
    parties = list(db["parties"].find({}))
    special = list(db["special_entities"].find({}))
    client.close()
    return users, parties, special


async def write_sqlite(database: Database, converted, parties, special, force: bool) -> Counter:
    counts = Counter()
    async with database.session() as session:
        if (await session.scalars(select(UserRow).limit(1))).first() and not force:
            raise SystemExit("Target database already has users. Use a fresh file, or pass --force.")
        for u in converted:
            session.add(UserRow(discord_id=u.discord_id, **u.columns))
            counts["users"] += 1
        await session.flush()
        for u in converted:
            for name, value in u.stats.items():
                session.add(StatRow(user_id=u.discord_id, name=name, value=value))
                counts["stats"] += 1
            for name, s in u.skills.items():
                session.add(SkillRow(user_id=u.discord_id, skill=name, **s))
                counts["skills"] += 1
            made: dict[str, int] = {}  # template id -> first instance id (for equipping)
            for template_id in u.instances:
                row = ItemInstanceRow(owner_id=u.discord_id, template_id=template_id, rolled={}, enchants={})
                session.add(row)
                await session.flush()
                made.setdefault(template_id, row.id)
                counts["tools"] += 1
            for skill, template_id in u.equipped.items():
                if skill in u.skills:
                    sk = await session.get(SkillRow, (u.discord_id, skill))
                    sk.equipped_instance_id = made.get(template_id)
                else:
                    session.add(
                        SkillRow(user_id=u.discord_id, skill=skill, xp=0, data={},
                                 equipped_instance_id=made.get(template_id))
                    )
            for item_id, quantity in u.items.items():
                session.add(ItemRow(user_id=u.discord_id, item_id=item_id, quantity=quantity))
                counts["item stacks"] += 1
        known = {u.discord_id for u in converted}
        for p in parties:
            members = [m for m in p.get("party_members", []) if m in known]
            if p.get("party_owner") not in known or not members:
                continue
            session.add(PartyRow(party_id=p["party_id"], owner_id=p["party_owner"]))
            await session.flush()
            for m in members:
                session.add(PartyMemberRow(user_id=m, party_id=p["party_id"]))
            counts["parties"] += 1
        mega = next((d for d in special if "total_drops_missed" in d), None)
        if mega:
            session.add(
                MegadropRow(
                    id=1,
                    amount=mega.get("amount", 0),
                    total_drops=mega.get("total_drops", 0),
                    total_drops_missed=mega.get("total_drops_missed", 0),
                    counter=mega.get("counter", 0),
                    times_missed=mega.get("times_missed", 0),
                    last_winner=mega.get("last_winner"),
                    date_started=str(mega.get("date_started") or datetime.now().strftime("%m-%d-%Y")),
                )
            )
            counts["megadrop"] = 1
    return counts


async def main(args) -> None:
    users, parties, special = read_mongo(args.uri, args.db)
    converted, seen = [], set()
    for doc in users:
        if "discord_id" not in doc:
            print(f"skipping document without discord_id: {doc.get('_id')}")
            continue
        if doc["discord_id"] in seen:
            print(f"duplicate discord_id {doc['discord_id']}: keeping the first document only")
            continue
        seen.add(doc["discord_id"])
        converted.append(convert_mongo_user(doc))

    warnings = Counter(w.split("(")[0].strip() for u in converted for w in u.warnings)
    for u in converted:
        for w in u.warnings:
            print(f"  user {u.discord_id}: {w}")
    print(f"\n{len(users)} mongo users -> {len(converted)} convertible; {len(parties)} parties")
    for text, n in warnings.most_common():
        print(f"  {n:>4} x {text}")

    if not args.write:
        print("\nDRY RUN: nothing written. Re-run with --write to create", constants.DATABASE_PATH)
        return
    database = await init_database(Database.from_path(args.out or constants.DATABASE_PATH))
    counts = await write_sqlite(database, converted, parties, special, args.force)
    await database.close()
    print("\nWRITTEN:", ", ".join(f"{n} {k}" for k, n in counts.items()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--uri", required=True, help="MongoDB connection string")
    ap.add_argument("--db", default="discordbot")
    ap.add_argument("--out", help="SQLite file (default: DATABASE_PATH / data/cococap.db)")
    ap.add_argument("--write", action="store_true", help="actually write (default is a dry run)")
    ap.add_argument("--force", action="store_true", help="allow writing into a non-empty database")
    sys.exit(asyncio.run(main(ap.parse_args())))
