"""scrap the bank: everything in it goes back to the purse

The `bank` column stays (always 0 now) so nothing has to be dropped; the game no longer reads it.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE users SET purse = purse + bank, bank = 0"))


def downgrade() -> None:
    pass  # the money is simply in the purse; there is nothing to put back
