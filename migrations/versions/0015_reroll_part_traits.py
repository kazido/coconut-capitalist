"""reroll the traits of every unsmithed part

Parts only ever rolled the first three generic traits; now that there are five, each part gets a fresh draw (distinct traits, count by
tier). Tier and the restricted flag stay. The pool and counts are copied from `configs/smithing.toml` so this does not depend on it.

Revision ID: 0015
Revises: 0014
"""
import json
import random

from alembic import op
import sqlalchemy as sa


revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None

POOL = ["power_core", "scholar_edge", "appraiser_eye", "lucky_charm", "bountiful"]
FRESH_TRAITS = [1, 1, 2, 2, 3, 3, 3, 3]  # by tier 1..8


def reroll_parts(conn, rng: random.Random | None = None) -> None:
    rng = rng or random.Random()
    rows = conn.execute(sa.text(
        "SELECT id, rolled FROM item_instances WHERE (parts IS NULL OR parts = 'null') AND template_id IN ('part_base', 'part_trim', 'part_accent')"
    )).fetchall()
    for instance_id, rolled in rows:
        data = json.loads(rolled) if isinstance(rolled, str) else (rolled or {})
        count = FRESH_TRAITS[min(max(int(data.get("tier", 1)), 1), len(FRESH_TRAITS)) - 1]
        conn.execute(sa.text("UPDATE item_instances SET traits = :t WHERE id = :id"),
                     {"t": json.dumps(rng.sample(POOL, count)), "id": instance_id})


def upgrade() -> None:
    reroll_parts(op.get_bind())


def downgrade() -> None:
    pass
