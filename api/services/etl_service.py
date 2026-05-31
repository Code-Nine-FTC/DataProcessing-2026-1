# -*- coding: utf-8 -*-
import logging
from datetime import datetime
import os
from typing import Any, Dict, List, Optional, Tuple
from typing import List, Optional, Tuple

from sqlalchemy import select, text, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine


import sys
from datetime import datetime
from typing import List, Optional

# Configuração do path para permitir a importação dos módulos do data-ingestion
ingestion_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data-ingestion"))
if ingestion_path not in sys.path:
    sys.path.insert(0, ingestion_path)

from core.config import AppConfig
from etl.orchestrator import PipelineOrchestrator
from models.db_model import HistoricoEtl

logger = logging.getLogger(__name__)


class EtlService:
    def __init__(self):
        self.config = AppConfig.from_env()

    async def get_status(self, session: AsyncSession) -> dict:
        """Retorna o status atual do processo de ETL baseado no histórico do banco."""
        stmt = select(HistoricoEtl).order_by(HistoricoEtl.data_inicio.desc()).limit(20)
        result = await session.execute(stmt)
        passos = result.scalars().all()
        
        status_atual = "IDLE"
        if passos:
            if any(p.status == "EM_PROCESSAMENTO" for p in passos[:5]):
                status_atual = "RUNNING"
            elif any(p.status == "ERRO" for p in passos[:5]):
                status_atual = "FAILED"
            else:
                status_atual = "COMPLETED"

        return {
            "status_atual": status_atual,
            "ultima_atualizacao": datetime.utcnow(),
            "passos": passos
        }

    def _prepare_engines(self) -> Tuple[AsyncEngine, any]:
        """Gera de maneira limpa as engines assíncronas e síncronas necessárias."""
        base_url = self.config.db.url
        
        async_url = base_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        if "postgresql+asyncpg://" not in async_url:
            async_url = base_url
            
        sync_url = base_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

        async_engine = create_async_engine(
            async_url, 
            pool_size=self.config.db.pool_size, 
            max_overflow=self.config.db.max_overflow, 
            echo=self.config.db.echo
        )
        
        sync_engine = create_engine(
            sync_url, 
            pool_size=self.config.db.pool_size, 
            max_overflow=self.config.db.max_overflow, 
            echo=self.config.db.echo
        )
        
        return async_engine, sync_engine

    async def run_manual_update(self, pipelines_to_run: Optional[List[str]] = None) -> None:
        """
        Executa o pipeline completo de ETL.
        Este método roda dentro do contexto isolado do Worker do Celery.
        """
        if pipelines_to_run:
            pipelines_to_run = [p for p in pipelines_to_run if p and p != "string"]

        async_engine, sync_engine = self._prepare_engines()
        orchestrator = PipelineOrchestrator(self.config, engine=sync_engine)

        # Registro explícito e profissional das pipelines disponíveis
        self._register_pipelines(orchestrator)

        # Definição do callback de progresso (Injeção de Comportamento)
        def progress_callback(name: str, etapa: str, status: str, detalhes: str, total: int, inseridos: int):
            """
            Callback síncrono exigido pelo Orchestrator. Ele gerencia as conexões
            síncronas locais para não quebrar o loop do Celery.
            """
            with sync_engine.connect() as conn:
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
                conn.commit()

        orchestrator.set_progress_callback(progress_callback)

        try:
            from main import DEFAULT_PIPELINE_ORDER 
            order = pipelines_to_run or DEFAULT_PIPELINE_ORDER
            
            successful, _ = orchestrator.run_all(order)
            
            if successful > 0:
                progress_callback("SISTEMA", "PÓS-PROCESSAMENTO", "EM_PROCESSAMENTO", "Iniciando cálculos espaciais...", 0, 0)
                try:
                    from sources.relacoes_espaciais import run_post_processing
                    run_post_processing(orchestrator.engine)
                    progress_callback("SISTEMA", "PÓS-PROCESSAMENTO", "SUCESSO", "Cálculos espaciais finalizados", 0, 0)
                except Exception as e:
                    logger.error(f"Erro no pós-processamento: {e}")
                    progress_callback("SISTEMA", "PÓS-PROCESSAMENTO", "ERRO", f"Erro no pós-processamento: {e}", 0, 0)

        except Exception as e:
            logger.exception(f"Falha crítica no processamento manual do ETL: {e}")
            raise e
        finally:
            await async_engine.dispose()
            sync_engine.dispose()

    def _register_pipelines(self, orchestrator: PipelineOrchestrator) -> None:
        """Encapsula o registro de fontes (Princípio da Responsabilidade Única)"""
        from sources.icmbio import create_pipeline as create_icmbio
        from sources.funai import create_pipeline as create_funai
        from sources.incra import create_pipeline as create_incra
        from sources.palmares import create_pipeline as create_palmares
        from sources.datageo_sp import create_pipeline as create_datageo_sp
        from sources.inpe import create_pipeline as create_inpe
        from sources.prodes_desmatamento import create_pipeline as create_prodes_desmatamento

        orchestrator.register_pipeline("icmbio", create_icmbio)
        orchestrator.register_pipeline("funai", create_funai)
        orchestrator.register_pipeline("incra", create_incra)
        orchestrator.register_pipeline("palmares", create_palmares)
        orchestrator.register_pipeline("datageo_sp", create_datageo_sp)
        orchestrator.register_pipeline("inpe", create_inpe)
        orchestrator.register_pipeline("prodes_desmatamento", create_prodes_desmatamento)