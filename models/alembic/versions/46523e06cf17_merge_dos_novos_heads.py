"""Merge dos novos heads

Revision ID: 46523e06cf17
Revises: d794d5528dee, f3a4b5c6d7e8
Create Date: 2026-05-31 12:27:08.019612

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2 
import pgvector


# revision identifiers, used by Alembic.
revision: str = '46523e06cf17'
down_revision: Union[str, Sequence[str], None] = ('d794d5528dee', 'f3a4b5c6d7e8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass