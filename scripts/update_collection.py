import asyncio
import copy
from cococap.models import UserDocument
from cococap.constants import URI
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from typing import get_origin, get_args, Optional as TypingOptional, Union


def is_optional(field):
    typ = field.outer_type_ if hasattr(field, "outer_type_") else field.annotation
    return get_origin(typ) is TypingOptional or (
        get_origin(typ) is Union and type(None) in get_args(typ)
    )


# Dynamically get default values for all fields (including those with no explicit class attribute)
MODEL_DEFAULTS = {}
OPTIONAL_FIELDS = set()
for name, field in UserDocument.model_fields.items():
    if field.default is not None:
        MODEL_DEFAULTS[name] = copy.deepcopy(field.default)
    elif is_optional(field):
        OPTIONAL_FIELDS.add(name)

VALID_FIELDS = set(MODEL_DEFAULTS) | OPTIONAL_FIELDS | {"_id"}


async def fix_documents_raw():
    client = AsyncIOMotorClient(URI)
    db = client.discordbot
    collection = db["users"]

    docs = collection.find({})
    removed_summary = {}
    added_summary = {}
    fixed_removed = 0
    fixed_added = 0
    for doc in await docs.to_list(length=None):
        update = {}
        # Remove extra fields
        extra_fields = set(doc.keys()) - VALID_FIELDS
        if extra_fields:
            unset = {field: "" for field in extra_fields}
            await collection.update_one({"_id": doc["_id"]}, {"$unset": unset})
            for field in extra_fields:
                removed_summary[field] = removed_summary.get(field, 0) + 1
            fixed_removed += 1
        # Add missing/default fields
        added_fields = []
        for field, default in MODEL_DEFAULTS.items():
            if field not in doc or doc[field] is None:
                update[field] = copy.deepcopy(default)
                added_fields.append(field)
        if update:
            await collection.update_one({"_id": doc["_id"]}, {"$set": update})
            for field in added_fields:
                added_summary[field] = added_summary.get(field, 0) + 1
            fixed_added += 1
    print(f"Removed extra fields from {fixed_removed} user documents.")
    if removed_summary:
        print("Fields removed:")
        for field, count in removed_summary.items():
            print(f"  {field}: {count} document(s)")
    print(f"Added missing/default fields to {fixed_added} user documents.")
    if added_summary:
        print("Fields added:")
        for field, count in added_summary.items():
            print(f"  {field}: {count} document(s)")

    # Now you can use Beanie safely
    await init_beanie(database=db, document_models=[UserDocument])
    result = await UserDocument.inspect_collection()
    print(result)


async def main():
    await fix_documents_raw()


if __name__ == "__main__":
    asyncio.run(main())
