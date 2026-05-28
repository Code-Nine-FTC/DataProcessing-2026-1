"""add_performance_indexes

Revision ID: e1f2a3b4c5d6
Revises: d7e8f9a0b1c2
Create Date: 2026-05-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'e8f9a0b1c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- FK indexes: municipio_id (todos os JOINs de analytics passam por aqui) ---
    op.create_index('idx_imovel_rural_municipio_id', 'imovel_rural', ['municipio_id'])
    op.create_index('idx_queimada_evento_municipio_id', 'queimada_evento', ['municipio_id'])
    op.create_index('idx_desmatamento_alerta_municipio_id', 'desmatamento_alerta', ['municipio_id'])
    op.create_index('idx_unidade_conservacao_municipio_id', 'unidade_conservacao', ['municipio_id'])
    op.create_index('idx_terra_indigena_municipio_id', 'terra_indigena', ['municipio_id'])
    op.create_index('idx_assentamento_rural_municipio_id', 'assentamento_rural', ['municipio_id'])
    op.create_index('idx_territorio_quilombola_municipio_id', 'territorio_quilombola', ['municipio_id'])

    # --- FK indexes: imovel_rural_id nas tabelas de relacionamento ---
    op.create_index('idx_rel_imovel_queimada_imovel_id', 'rel_imovel_queimada', ['imovel_rural_id'])
    op.create_index('idx_rel_imovel_desmatamento_imovel_id', 'rel_imovel_desmatamento', ['imovel_rural_id'])
    op.create_index('idx_rel_imovel_uc_imovel_id', 'rel_imovel_uc', ['imovel_rural_id'])
    op.create_index('idx_rel_imovel_ti_imovel_id', 'rel_imovel_ti', ['imovel_rural_id'])
    op.create_index('idx_rel_imovel_assentamento_imovel_id', 'rel_imovel_assentamento', ['imovel_rural_id'])
    op.create_index('idx_rel_imovel_quilombo_imovel_id', 'rel_imovel_quilombo', ['imovel_rural_id'])

    # --- Filtros temporais (série temporal e filtro de 12 meses) ---
    op.create_index('idx_desmatamento_alerta_data_ocorrencia', 'desmatamento_alerta', ['data_ocorrencia'])
    op.create_index('idx_queimada_evento_data_ocorrencia', 'queimada_evento', ['data_ocorrencia'])

    # --- dentro_imovel (queimadas_dentro_fora_imoveis usa GROUP BY nessa coluna) ---
    op.create_index('idx_rel_imovel_queimada_dentro_imovel', 'rel_imovel_queimada', ['dentro_imovel'])


def downgrade() -> None:
    op.drop_index('idx_rel_imovel_queimada_dentro_imovel', table_name='rel_imovel_queimada')

    op.drop_index('idx_queimada_evento_data_ocorrencia', table_name='queimada_evento')
    op.drop_index('idx_desmatamento_alerta_data_ocorrencia', table_name='desmatamento_alerta')

    op.drop_index('idx_rel_imovel_quilombo_imovel_id', table_name='rel_imovel_quilombo')
    op.drop_index('idx_rel_imovel_assentamento_imovel_id', table_name='rel_imovel_assentamento')
    op.drop_index('idx_rel_imovel_ti_imovel_id', table_name='rel_imovel_ti')
    op.drop_index('idx_rel_imovel_uc_imovel_id', table_name='rel_imovel_uc')
    op.drop_index('idx_rel_imovel_desmatamento_imovel_id', table_name='rel_imovel_desmatamento')
    op.drop_index('idx_rel_imovel_queimada_imovel_id', table_name='rel_imovel_queimada')

    op.drop_index('idx_territorio_quilombola_municipio_id', table_name='territorio_quilombola')
    op.drop_index('idx_assentamento_rural_municipio_id', table_name='assentamento_rural')
    op.drop_index('idx_terra_indigena_municipio_id', table_name='terra_indigena')
    op.drop_index('idx_unidade_conservacao_municipio_id', table_name='unidade_conservacao')
    op.drop_index('idx_desmatamento_alerta_municipio_id', table_name='desmatamento_alerta')
    op.drop_index('idx_queimada_evento_municipio_id', table_name='queimada_evento')
    op.drop_index('idx_imovel_rural_municipio_id', table_name='imovel_rural')
