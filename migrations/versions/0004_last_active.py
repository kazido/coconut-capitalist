"""when a player last did anything (to take idle players out of parties)

Revision ID: 0004
Revises: 0003
"""
import time

from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('last_active', sa.Float(), nullable=False, server_default='0'))
    # Everyone who exists now counts as active right now, so nobody is kicked the moment this ships.
    op.execute(sa.text("UPDATE users SET last_active = :now").bindparams(now=time.time()))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('last_active')
