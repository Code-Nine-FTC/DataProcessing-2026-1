# -*- coding: utf-8 -*-
import logging
import traceback
import sys
import os
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

# Configuração do path para permitir a importação dos módulos do data-ingestion
ingestion_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data-ingestion"))
if ingestion_path not in sys.path:
    sys.path.insert(0, ingestion_path)

from sqlalchemy import select, text, create_engine
from sqlalchemy.ext.asyncio import AsyncSession

# Importações diretas do data-ingestion (agora no sys.path)
from core.config import AppConfig
from etl.orchestrator import PipelineOrchestrator
from models.db_model import HistoricoEtl

logger = logging.getLogger(__name__)

class EtlService:
    def __init__(self):
        self.config = AppConfig.from_env()
        self._is_running = False
        self._last_run_time = None

    async def get_status(self, session: AsyncSession):
        stmt = select(HistoricoEtl).order_by(HistoricoEtl.data_inicio.desc()).limit(20)
        result = await session.execute(stmt)
        passos = result.scalars().all()
        
        status_atual = "RUNNING" if self._is_running else "IDLE"
        
        # Determina o status geral verificando as etapas mais recentes da última execução
        if not self._is_running and passos and any(p.status == "ERRO" for p in passos[:5]):
            status_atual = "FAILED"
        elif not self._is_running and passos:
            status_atual = "COMPLETED"

        return {
            "status_atual": status_atual,
            "ultima_atualizacao": datetime.now(),
            "passos": passos
        }

    async def run_manual_update(self, pipelines_to_run: Optional[List[str]] = None):
        if self._is_running:
            logger.warning("ETL already running. Skipping manual trigger.")
            return

        # Filtra o valor "string" (padrão do Swagger UI) e valores vazios para evitar erro de pipeline não encontrada
        if pipelines_to_run:
            pipelines_to_run = [p for p in pipelines_to_run if p and p != "string"]

        # Engine síncrona para o callback de progresso conseguir gravar no banco
        # enquanto a thread principal do orchestrator (síncrona) executa as pipelines.
        sync_db_url = self.config.db.url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        sync_engine = create_engine(sync_db_url)
        self._last_run_time = datetime.now()
        
        self._is_running = True
        try:
            orchestrator = PipelineOrchestrator(self.config)
            
            from sources.icmbio import create_pipeline as create_icmbio
            from sources.funai import create_pipeline as create_funai
            from sources.incra import create_pipeline as create_incra
            from sources.palmares import create_pipeline as create_palmares
            from sources.datageo_sp import create_pipeline as create_datageo_sp
            from sources.car import create_pipeline as create_car
            from sources.inpe import create_pipeline as create_inpe
            from sources.prodes_desmatamento import create_pipeline as create_prodes_desmatamento

            orchestrator.register_pipeline("icmbio", create_icmbio)
            orchestrator.register_pipeline("funai", create_funai)
            orchestrator.register_pipeline("incra", create_incra)
            orchestrator.register_pipeline("palmares", create_palmares)
            orchestrator.register_pipeline("datageo_sp", create_datageo_sp)
            orchestrator.register_pipeline("car", create_car)
            orchestrator.register_pipeline("inpe", create_inpe)
            orchestrator.register_pipeline("prodes_desmatamento", create_prodes_desmatamento)

            def progress_callback(name, etapa, status, detalhes, total, inseridos):
                """Atualiza ou cria registros na tabela historico_etl."""
                with sync_engine.begin() as conn:
                    sel_stmt = text("""
                        SELECT id FROM historico_etl 
                        WHERE pipeline_name = :name AND etapa = :etapa 
                        AND data_inicio > NOW() - INTERVAL '1 hour'
                        ORDER BY data_inicio DESC LIMIT 1
                    """)
                    res = conn.execute(sel_stmt, {"name": name, "etapa": etapa}).fetchone()
                    
                    if res:
                        upd_stmt = text("""
                            UPDATE historico_etl 
                            SET status = :status, detalhes = :detalhes, 
                                total_registros = :total, registros_inseridos = :inseridos,
                                data_fim = CASE WHEN :status IN ('SUCESSO', 'ERRO', 'IGNORADO', 'AVISO') THEN NOW() ELSE data_fim END
                            WHERE id = :id
                        """)
                        conn.execute(upd_stmt, {
                            "id": res[0], "status": status, "detalhes": detalhes,
                            "total": total, "inseridos": inseridos
                        })
                    else:
                        ins_stmt = text("""
                            INSERT INTO historico_etl 
                            (id, pipeline_name, etapa, status, detalhes, total_registros, registros_inseridos, data_inicio)
                            VALUES (gen_random_uuid(), :name, :etapa, :status, :detalhes, :total, :inseridos, NOW())
                        """)
                        conn.execute(ins_stmt, {
                            "name": name, "etapa": etapa, "status": status, 
                            "detalhes": detalhes, "total": total, "inseridos": inseridos
                        })

            orchestrator.set_progress_callback(progress_callback)

            # Importação dinâmica do DEFAULT_PIPELINE_ORDER definido no data-ingestion/main.py
            from main import DEFAULT_PIPELINE_ORDER 
            order = pipelines_to_run or DEFAULT_PIPELINE_ORDER
            
            successful, failed = orchestrator.run_all(order)
            
            if successful > 0:
                progress_callback("SISTEMA", "PÓS-PROCESSAMENTO", "EM_PROCESSAMENTO", "Iniciando cálculos espaciais...", 0, 0)
                try:
                    from sources.relacoes_espaciais import run_post_processing
                    run_post_processing(orchestrator.engine)
                    progress_callback("SISTEMA", "PÓS-PROCESSAMENTO", "SUCESSO", "Cálculos espaciais finalizados", 0, 0)
                except Exception as e:
                    logger.error(f"Erro no pós-processamento: {e}")
                    progress_callback("SISTEMA", "PÓS-PROCESSAMENTO", "ERRO", f"Erro no pós-processamento: {e}", 0, 0)

            orchestrator.close()
        except Exception as e:
            logger.error(f"Manual ETL failed: {e}")
            traceback.print_exc()
        finally:
            self._is_running = False
            sync_engine.dispose()
