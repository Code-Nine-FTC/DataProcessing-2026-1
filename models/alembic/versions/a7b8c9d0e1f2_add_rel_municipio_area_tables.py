"""add rel_municipio_ti/uc/quilombo

Revision ID: a7b8c9d0e1f2
Revises: 46523e06cf17
Create Date: 2026-06-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "46523e06cf17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABELAS = (
    ("rel_municipio_ti", "terra_indigena_id", "terra_indigena"),
    ("rel_municipio_uc", "unidade_conservacao_id", "unidade_conservacao"),
    ("rel_municipio_quilombo", "territorio_quilombola_id", "territorio_quilombola"),
)


def upgrade() -> None:
    for tabela, alvo_col, alvo_tabela in _TABELAS:
        op.create_table(
            tabela,
            sa.Column("id", UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("municipio_id", sa.Integer(),
                      sa.ForeignKey("municipio.id"), nullable=False),
            sa.Column(alvo_col, UUID(as_uuid=True),
                      sa.ForeignKey(f"{alvo_tabela}.id"), nullable=False),
            sa.Column("area_intersecao_ha", sa.Numeric(), nullable=True),
            sa.Column("percentual_sobreposicao", sa.Numeric(), nullable=True),
        )
        op.create_index(f"idx_{tabela}_municipio_id", tabela, ["municipio_id"])
        op.create_index(f"idx_{tabela}_{alvo_col}", tabela, [alvo_col])


def downgrade() -> None:
    for tabela, _alvo_col, _alvo_tabela in _TABELAS:
        op.drop_table(tabela)
