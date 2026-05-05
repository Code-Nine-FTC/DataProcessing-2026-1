"""add_nivel_risco_ambiental_to_rel_imovel_queimada

Revision ID: d7e8f9a0b1c2
Revises: c4d5e6f7a8b9
Create Date: 2026-05-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'rel_imovel_queimada',
        sa.Column('nivel_risco_ambiental', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('rel_imovel_queimada', 'nivel_risco_ambiental')