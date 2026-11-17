"""refund the materials that were removed from the game

Nineteen materials had no use (the foraging species drops, plus golden pollen). Anybody holding some gets bits
equal to what selling them would have paid, and the stacks are deleted. The prices are written out here (copied
from `configs/items.toml` before the items were removed) so this migration does not depend on the config.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None

# item id -> sell price (bits)
REMOVED = {
    "pine_resin": 3500, "amber_cone": 150000, "chestnut_burr": 4000, "glossy_chestnut": 180000,
    "cherry_petal": 4500, "blossom_crown": 220000, "palm_frond": 5000, "sunfruit": 260000,
    "redwood_cone": 6000, "giants_heartwood": 800000, "ember_bark": 7000, "phoenix_cinder": 1200000,
    "birch_bark": 1500, "oak_gall": 1800, "willow_switch": 2500, "silver_catkin": 60000,
    "heart_acorn": 70000, "weeping_pearl": 90000, "golden_pollen": 50000,
}


def upgrade() -> None:
    conn = op.get_bind()
    for item_id, price in REMOVED.items():
        conn.execute(
            sa.text(
                "UPDATE users SET purse = purse + :price * "
                "(SELECT quantity FROM user_items WHERE user_items.user_id = users.discord_id AND item_id = :item) "
                "WHERE discord_id IN (SELECT user_id FROM user_items WHERE item_id = :item)"
            ),
            {"price": price, "item": item_id},
        )
        conn.execute(sa.text("DELETE FROM user_items WHERE item_id = :item"), {"item": item_id})


def downgrade() -> None:
    pass  # the bits stay in the purse; the items no longer exist
