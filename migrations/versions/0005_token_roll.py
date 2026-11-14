"""the hour of a player's last random-token roll

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('last_token_roll', sa.BigInteger(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('last_token_roll')
