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


def clean_dict(doc_dict, model_dict):
    """
    Recursively remove extra fields and add missing/default fields in a dict,
    matching the structure of model_dict.
    Returns (cleaned_dict, removed_fields, added_fields)
    """
    cleaned = {}
    removed = set()
    added = set()
    for key, value in model_dict.items():
        if key in doc_dict:
            if isinstance(value, dict) and isinstance(doc_dict[key], dict):
                cleaned[key], r, a = clean_dict(doc_dict[key], value)
                removed |= {f"{key}.{sub}" for sub in r}
                added |= {f"{key}.{sub}" for sub in a}
            else:
                cleaned[key] = doc_dict[key]
        else:
            cleaned[key] = copy.deepcopy(value)
            added.add(key)
    # Remove extra fields
    for key in doc_dict:
        if key not in model_dict:
            removed.add(key)
    return cleaned, removed, added


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
        unset = {}
        # Remove extra fields at root
        extra_fields = set(doc.keys()) - VALID_FIELDS
        for field in extra_fields:
            unset[field] = ""
            removed_summary[field] = removed_summary.get(field, 0) + 1
        # Recursively clean nested dict fields
        for field, default in MODEL_DEFAULTS.items():
            if isinstance(default, dict):
                doc_val = doc.get(field, {}) if isinstance(doc.get(field, {}), dict) else {}
                cleaned, removed, added = clean_dict(doc_val, default)
                if removed:
                    for r in removed:
                        removed_summary[f"{field}.{r}"] = removed_summary.get(f"{field}.{r}", 0) + 1
                    fixed_removed += 1
                if added:
                    for a in added:
                        added_summary[f"{field}.{a}"] = added_summary.get(f"{field}.{a}", 0) + 1
                    fixed_added += 1
                update[field] = cleaned
            else:
                if field not in doc or doc[field] is None:
                    update[field] = copy.deepcopy(default)
                    added_summary[field] = added_summary.get(field, 0) + 1
                    fixed_added += 1
        if unset:
            await collection.update_one({"_id": doc["_id"]}, {"$unset": unset})
        if update:
            await collection.update_one({"_id": doc["_id"]}, {"$set": update})
    print(f"Removed extra fields from user documents.")
    if removed_summary:
        print("Fields removed:")
        for field, count in removed_summary.items():
            print(f"  {field}: {count} document(s)")
    print(f"Added missing/default fields to user documents.")
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
