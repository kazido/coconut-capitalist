"""Migrate production user documents from the legacy flat-dict schema to the nested models.

    python -m scripts.migrate_legacy_users            # DRY RUN: prints what would change
    python -m scripts.migrate_legacy_users --apply    # writes the changes

Back up first (``mongodump --uri "$URI" --db discordbot``). Nothing is ever $unset, so legacy-only
fields (e.g. ``pets``) are preserved. Safe to re-run: already-migrated skills are skipped.

This replaces the old update_collection.py, which $unset every field missing from models.py (i.e.
deleted player data) and no longer worked with the nested Pydantic models.
"""

import asyncio
import sys
from collections import Counter

from motor.motor_asyncio import AsyncIOMotorClient

from cococap import constants
from cococap.migrations import migrate_legacy_user


async def main(apply: bool) -> None:
    constants.require_secrets()
    client = AsyncIOMotorClient(constants.URI)
    users = client.discordbot["users"]

    migrated = Counter()
    scanned = 0
    async for doc in users.find({}):
        scanned += 1
        updates = migrate_legacy_user(doc)
        if not updates:
            continue
        migrated.update(updates.keys())
        if apply:
            await users.update_one({"_id": doc["_id"]}, {"$set": updates})

    print(("APPLIED" if apply else "DRY RUN (nothing written; pass --apply to write)"))
    print(f"scanned {scanned} user documents")
    for skill, count in sorted(migrated.items()):
        print(f"  {skill}: {count} document(s) {'migrated' if apply else 'would be migrated'}")
    if not migrated:
        print("  nothing to migrate")
    client.close()


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv[1:]))
