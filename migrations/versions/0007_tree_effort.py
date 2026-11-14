"""community tree chops remember how good each chop was

foraging xp is now paid for the quality of every chop (grain, good chops), not for the hp an axe took off, so a stronger axe
fells faster without paying more xp. Chops made before this have effort 0 (their trees are long settled).

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tree_chops", sa.Column("effort", sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("tree_chops", "effort")
