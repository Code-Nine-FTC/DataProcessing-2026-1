"""bbox_resultado nullable

Revision ID: c301f9ab1d23
Revises: b512e8facc01
Create Date: 2026-04-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = 'c301f9ab1d23'
down_revision: Union[str, Sequence[str], None] = 'b512e8facc01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'resposta_sistema',
        'bbox_resultado',
        existing_type=geoalchemy2.types.Geometry(
            geometry_type='POLYGON', srid=4326, dimension=2,
            from_text='ST_GeomFromEWKT', name='geometry', nullable=False,
        ),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'resposta_sistema',
        'bbox_resultado',
        existing_type=geoalchemy2.types.Geometry(
            geometry_type='POLYGON', srid=4326, dimension=2,
            from_text='ST_GeomFromEWKT', name='geometry', nullable=True,
        ),
        nullable=False,
    )
