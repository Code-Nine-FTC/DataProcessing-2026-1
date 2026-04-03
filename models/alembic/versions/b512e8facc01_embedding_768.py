"""embedding_768

Revision ID: b512e8facc01
Revises: a411c3dacc50
Create Date: 2026-04-01 13:51:45.336390

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2 
import pgvector


# revision identifiers, used by Alembic.
revision: str = 'b512e8facc01'
down_revision: Union[str, Sequence[str], None] = 'a411c3dacc50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Altera coluna embedding de vector(1536) para vector(768)."""
    op.execute("ALTER TABLE documento_trecho ALTER COLUMN embedding TYPE vector(768) USING embedding::text::vector(768)")


def downgrade() -> None:
    """Reverte coluna embedding de vector(768) para vector(1536)."""
    op.execute("ALTER TABLE documento_trecho ALTER COLUMN embedding TYPE vector(1536) USING embedding::text::vector(1536)")