"""retire five more scrolls: Lure, Seasoning, Iron Frame, Deepcall and Gleaner

Their bonuses now come from mastery, pets and accessories, so the enchants are gone from the game. Anybody holding their scrolls
(any star) gets bits equal to the scroll's sell price per scroll, and the stacks are deleted. Enchants of those kinds already on
a tool are stripped from the tool's `enchants`. The prices are written out here (copied from `configs/items.toml` before the items
were removed) so this migration does not depend on the config.

Revision ID: 0013
Revises: 0012
"""
import json

from alembic import op
import sqlalchemy as sa


revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None

# scroll item id -> sell price (bits)
RETIRED = {
    "scroll_lure": 400000, "scroll_seasoned": 400000, "scroll_iron_frame": 400000,
    "scroll_deepcall": 400000, "scroll_gleaner": 400000,
}
RETIRED_ENCHANTS = {"lure", "seasoned", "iron_frame", "deepcall", "gleaner"}


def retire_scrolls(conn) -> None:
    """Pay out and delete every held stack of a retired scroll (star variants too), then strip retired enchants from tools."""
    for scroll_id, price in RETIRED.items():
        for item_id in (scroll_id, f"{scroll_id}_s2", f"{scroll_id}_s3"):
            held = conn.execute(
                sa.text("SELECT user_id, quantity FROM user_items WHERE item_id = :item AND quantity > 0"), {"item": item_id}
            ).fetchall()
            for user_id, quantity in held:
                conn.execute(
                    sa.text("UPDATE users SET purse = purse + :bits WHERE discord_id = :u"),
                    {"bits": price * quantity, "u": user_id},
                )
            conn.execute(sa.text("DELETE FROM user_items WHERE item_id = :item"), {"item": item_id})

    rows = conn.execute(sa.text("SELECT id, enchants FROM item_instances WHERE enchants IS NOT NULL")).fetchall()
    for instance_id, enchants in rows:
        data = json.loads(enchants) if isinstance(enchants, str) else enchants
        if not isinstance(data, dict) or not RETIRED_ENCHANTS & data.keys():
            continue
        kept = {k: v for k, v in data.items() if k not in RETIRED_ENCHANTS}
        conn.execute(
            sa.text("UPDATE item_instances SET enchants = :e WHERE id = :id"),
            {"e": json.dumps(kept), "id": instance_id},
        )


def upgrade() -> None:
    retire_scrolls(op.get_bind())


def downgrade() -> None:
    pass  # the bits stay; the scrolls and their enchants no longer exist
