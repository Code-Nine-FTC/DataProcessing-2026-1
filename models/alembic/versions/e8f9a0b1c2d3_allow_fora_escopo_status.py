"""allow_fora_escopo_status

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-05-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("check_status_resposta", "resposta_sistema", type_="check")
    op.create_check_constraint(
        "check_status_resposta",
        "resposta_sistema",
        "status IN ('sucesso', 'erro', 'fallback', 'sem_resultado', 'fora_escopo')",
    )


def downgrade() -> None:
    op.drop_constraint("check_status_resposta", "resposta_sistema", type_="check")
    op.create_check_constraint(
        "check_status_resposta",
        "resposta_sistema",
        "status IN ('sucesso', 'erro', 'fallback', 'sem_resultado')",
    )
