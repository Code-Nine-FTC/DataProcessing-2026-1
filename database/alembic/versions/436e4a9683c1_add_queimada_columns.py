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
    """ALTER TABLE queimada_evento
    ADD COLUMN bioma           TEXT,
    ADD COLUMN dias_sem_chuva  INT,
    ADD COLUMN precipitacao_mm NUMERIC,
    ADD COLUMN risco_fogo      NUMERIC;

    -- Índice para filtragem por bioma (muito comum em queries ambientais)
    CREATE INDEX idx_queimada_bioma ON queimada_evento (bioma);

    -- Índice para análises de risco
    CREATE INDEX idx_queimada_risco ON queimada_evento (risco_fogo);"""
    pass


def downgrade() -> None:
    """ALTER TABLE queimada_evento
    DROP COLUMN bioma,
    DROP COLUMN dias_sem_chuva,
    DROP COLUMN precipitacao_mm,
    DROP COLUMN risco_fogo;

    -- Remove índices
    DROP INDEX idx_queimada_bioma;
    DROP INDEX idx_queimada_risco;"""
    pass
