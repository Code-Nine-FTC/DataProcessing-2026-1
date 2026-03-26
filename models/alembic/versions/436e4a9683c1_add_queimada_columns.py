"""add_queimada_columns

Revision ID: 436e4a9683c1
Revises: 
Create Date: 2026-03-19 13:13:11.246172

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '436e4a9683c1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("queimada_evento", sa.Column("bioma", sa.Text(), nullable=True))
    op.add_column("queimada_evento", sa.Column("dias_sem_chuva", sa.Integer(), nullable=True))
    op.add_column("queimada_evento", sa.Column("precipitacao_mm", sa.Numeric(), nullable=True))
    op.add_column("queimada_evento", sa.Column("risco_fogo", sa.Numeric(), nullable=True))
    op.create_index("idx_queimada_bioma", "queimada_evento", ["bioma"])
    op.create_index("idx_queimada_risco", "queimada_evento", ["risco_fogo"])


def downgrade() -> None:
    op.drop_index("idx_queimada_risco", table_name="queimada_evento")
    op.drop_index("idx_queimada_bioma", table_name="queimada_evento")
    op.drop_column("queimada_evento", "risco_fogo")
    op.drop_column("queimada_evento", "precipitacao_mm")
    op.drop_column("queimada_evento", "dias_sem_chuva")
    op.drop_column("queimada_evento", "bioma")
