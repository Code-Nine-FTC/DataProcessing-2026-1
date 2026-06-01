"""add_regiao_administrativa (merge auth + performance heads)

Revision ID: f3a4b5c6d7e8
Revises: e1f2a3b4c5d6, f2a3b4c5d6e7
Create Date: 2026-05-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from geoalchemy2 import Geometry

revision: str = 'f3a4b5c6d7e8'

down_revision: Union[str, Sequence[str], None] = ('e1f2a3b4c5d6', 'f2a3b4c5d6e7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if 'regiao_administrativa' not in inspector.get_table_names():
        op.create_table(
            'regiao_administrativa',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('nome', sa.TEXT(), nullable=False, unique=True),
            sa.Column('nome_normalizado', sa.TEXT(), nullable=True),
            sa.Column('sigla', sa.VARCHAR(20), nullable=True),
            sa.Column('tipo', sa.VARCHAR(20), nullable=True),
            sa.Column('estado_id', sa.Integer(), sa.ForeignKey('estado.id'), nullable=True),
            sa.Column('geom', Geometry('MULTIPOLYGON', srid=4326), nullable=True),
        )

    municipio_cols = [c['name'] for c in inspector.get_columns('municipio')]
    if 'regiao_administrativa_id' not in municipio_cols:
        op.add_column(
            'municipio',
            sa.Column(
                'regiao_administrativa_id',
                sa.Integer(),
                sa.ForeignKey('regiao_administrativa.id'),
                nullable=True,
            ),
        )


def downgrade() -> None:
    op.drop_column('municipio', 'regiao_administrativa_id')
    op.drop_table('regiao_administrativa')
