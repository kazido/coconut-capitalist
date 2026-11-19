"""smithing: item instances keep traits, parts, quality and cosmetics

Parts (base, trim, accent) are item instances carrying their tier in `rolled` and picked traits in `traits`. A tool smithed by a
player keeps its `parts`, `quality`, the smith's id (`smith_id`) and cosmetic looks. Game-made items keep smith_id NULL.

Revision ID: 0012
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa


revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('item_instances') as batch:
        batch.add_column(sa.Column('traits', sa.JSON(), nullable=False, server_default='[]'))
        batch.add_column(sa.Column('smith_id', sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column('parts', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('quality', sa.String(), nullable=True))
        batch.add_column(sa.Column('cosmetic', sa.JSON(), nullable=False, server_default='{}'))


def downgrade() -> None:
    with op.batch_alter_table('item_instances') as batch:
        batch.drop_column('cosmetic')
        batch.drop_column('quality')
        batch.drop_column('parts')
        batch.drop_column('smith_id')
        batch.drop_column('traits')
