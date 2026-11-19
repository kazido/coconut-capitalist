"""starred materials get a no-star tier: every starred stack drops one star (2-star -> 1-star, 3-star -> 2-star)

Plain materials were the 1-star ones; now plain means no star and stars are the special drops. Players keep their plain stacks and their starred
stacks move down one tier (`_s2` -> `_s1`, then `_s3` -> `_s2`; in that order so nothing collides).

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa


revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for old, new in (("_s2", "_s1"), ("_s3", "_s2")):
        conn.execute(sa.text(
            f"UPDATE user_items SET item_id = SUBSTR(item_id, 1, LENGTH(item_id) - 3) || '{new}' "
            f"WHERE SUBSTR(item_id, -3) = '{old}'"))  # exact suffix (LIKE would treat _ as a wildcard)


def downgrade() -> None:
    pass  # a stack's old tier cannot be told apart from a new one
