"""Server-wide shared state, one small JSON document per key.

Every change is a read-modify-write inside ONE serialized database transaction (the same guarantee ``update_skill``
gives), so any number of players can donate or add progress at the same moment without losing or double-counting
anything, and "this finishes the book" can only happen once.
"""

import copy
from collections.abc import Callable
from typing import TypeVar

from cococap.db import get_database
from cococap.db.tables import CommunityStateRow

T = TypeVar("T")


async def read(key: str, default: dict) -> dict:
    async with get_database().session() as session:
        row = await session.get(CommunityStateRow, key)
        return copy.deepcopy(row.data) if row is not None else copy.deepcopy(default)


async def update(key: str, default: dict, change: Callable[[dict], T]) -> T:
    """Run ``change(data)`` on the document for ``key`` (created from ``default`` if new) and save it."""
    async with get_database().session() as session:
        row = await session.get(CommunityStateRow, key)
        data = copy.deepcopy(row.data) if row is not None else copy.deepcopy(default)
        result = change(data)
        if row is None:
            session.add(CommunityStateRow(key=key, data=data))
        else:
            row.data = data  # a new object, so the JSON change is noticed
    return result
