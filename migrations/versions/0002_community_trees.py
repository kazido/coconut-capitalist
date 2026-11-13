"""community trees (foraging)

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('community_trees',
    sa.Column('window', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('zone', sa.Integer(), nullable=False),
    sa.Column('max_hp', sa.Integer(), nullable=False),
    sa.Column('hp', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('opens_at', sa.Float(), nullable=False),
    sa.Column('closes_at', sa.Float(), nullable=False),
    sa.Column('settled', sa.Boolean(), nullable=False),
    sa.CheckConstraint('hp >= 0 AND hp <= max_hp', name=op.f('ck_community_trees_hp_in_range')),
    sa.CheckConstraint("status IN ('growing', 'felled', 'expired')", name=op.f('ck_community_trees_status_known')),
    sa.PrimaryKeyConstraint('window', name=op.f('pk_community_trees'))
    )
    op.create_table('tree_chops',
    sa.Column('window', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('damage', sa.Integer(), nullable=False),
    sa.CheckConstraint('damage >= 0', name=op.f('ck_tree_chops_damage_non_negative')),
    sa.ForeignKeyConstraint(['user_id'], ['users.discord_id'], name=op.f('fk_tree_chops_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['window'], ['community_trees.window'], name=op.f('fk_tree_chops_window_community_trees'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('window', 'user_id', name=op.f('pk_tree_chops'))
    )
    op.create_table('tree_rewards',
    sa.Column('window', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('damage', sa.Integer(), nullable=False),
    sa.Column('felled', sa.Boolean(), nullable=False),
    sa.Column('drops', sa.JSON(), nullable=False),
    sa.Column('bits', sa.BigInteger(), nullable=False),
    sa.Column('xp', sa.Integer(), nullable=False),
    sa.Column('claimed', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.discord_id'], name=op.f('fk_tree_rewards_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['window'], ['community_trees.window'], name=op.f('fk_tree_rewards_window_community_trees'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('window', 'user_id', name=op.f('pk_tree_rewards'))
    )


def downgrade() -> None:
    op.drop_table('tree_rewards')
    op.drop_table('tree_chops')
    op.drop_table('community_trees')
