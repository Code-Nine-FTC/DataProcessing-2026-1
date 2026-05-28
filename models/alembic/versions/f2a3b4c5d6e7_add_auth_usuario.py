"""add_auth_usuario

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e8f9a0b1c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'usuario',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('nome', sa.Text(), nullable=True),
        sa.Column('senha_hash', sa.Text(), nullable=False),
        sa.Column('role', sa.String(), server_default='user', nullable=False),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('ativo', sa.Boolean(), server_default='true', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_usuario_email'),
    )

    op.add_column('chat', sa.Column('usuario_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_chat_usuario_id',
        'chat', 'usuario',
        ['usuario_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_chat_usuario_id', 'chat', type_='foreignkey')
    op.drop_column('chat', 'usuario_id')
    op.drop_table('usuario')
