"""community state (fishing community book and monthly quests)

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('community_state',
    sa.Column('key', sa.String(), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_community_state'))
    )


def downgrade() -> None:
    op.drop_table('community_state')
