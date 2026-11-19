"""cut the 14 farm-zone byproduct materials; whoever held any gets a few of the original farming materials

The zone materials were a short-lived placeholder (the zone tables use only the five original farming materials now). Every distinct zone
material a player held (any star) turns into 2 Plant Fiber and 2 Rich Compost: a small thank-you, not a pile. The stacks are deleted.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

CUT = ["slime_goo", "meadow_clover", "dusk_petal", "oasis_date", "scrap_sprout", "hydro_nutrient", "market_seedpack", "rooftop_honey",
       "cloud_cotton", "windmill_grain", "stardew_pollen", "comet_ember", "pale_bloom", "ambrosia_nectar"]
IDS = [f"material_{name}{suffix}" for name in CUT for suffix in ("", "_s2", "_s3")]
GIFT = {"material_plant_fiber": 2, "material_compost": 2}  # per distinct zone material held


def upgrade() -> None:
    conn = op.get_bind()
    holders = conn.execute(
        sa.text("SELECT user_id, COUNT(DISTINCT REPLACE(REPLACE(item_id, '_s2', ''), '_s3', '')) FROM user_items "
                "WHERE item_id IN (" + ",".join(f"'{i}'" for i in IDS) + ") AND quantity > 0 GROUP BY user_id")
    ).fetchall()
    for user_id, kinds in holders:
        for item_id, each in GIFT.items():
            conn.execute(
                sa.text("INSERT INTO user_items (user_id, item_id, quantity) VALUES (:u, :i, :q) "
                        "ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + :q"),
                {"u": user_id, "i": item_id, "q": each * kinds},
            )
    conn.execute(sa.text("DELETE FROM user_items WHERE item_id IN (" + ",".join(f"'{i}'" for i in IDS) + ")"))


def downgrade() -> None:
    pass  # the gift stays; the items no longer exist
