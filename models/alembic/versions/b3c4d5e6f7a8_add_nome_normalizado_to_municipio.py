"""add_nome_normalizado_to_municipio

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('municipio', sa.Column('nome_normalizado', sa.TEXT(), nullable=True))
    op.execute("""
        UPDATE municipio
        SET nome_normalizado = lower(
            regexp_replace(
                translate(
                    nome,
                    'ÀÁÂÃÄÅàáâãäåÈÉÊËèéêëÌÍÎÏìíîïÒÓÔÕÖòóôõöÙÚÛÜùúûüÇçÑñ',
                    'AAAAAAaaaaaaEEEEeeeeIIIIiiiiOOOOOoooooUUUUuuuuCcNn'
                ),
                '[^a-z0-9 \-/]', ' ', 'g'
            )
        )
    """)


def downgrade() -> None:
    op.drop_column('municipio', 'nome_normalizado')
