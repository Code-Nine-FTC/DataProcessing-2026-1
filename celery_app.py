# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import sys
import traceback
from typing import Any, Dict, List, Optional

from celery import Celery
import redis  # Certifique-se de adicionar 'redis' ao seu requirements.txt / poetry

from api.services.etl_service import EtlService

# Configuração de Logs
logger = logging.getLogger(__name__)

# Configuração do Celery via variáveis de ambiente
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "data_processing_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Inicializa o cliente Redis para o controle do Lock usando a mesma URL do Broker
redis_client = redis.from_url(REDIS_URL)

# Configurações centralizadas e tipadas do Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,  # Permite saber se a tarefa já começou a rodar
    task_acks_late=True,      # Garante que a tarefa só saia da fila após terminar (evita perda se o worker cair)
)


@celery_app.task(bind=True, name="celery_app.run_etl_update_task", max_retries=3, default_retry_delay=60)
def run_etl_update_task(self, pipelines_to_run: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Tarefa Celery para rodar a atualização manual do ETL de forma assíncrona.
    
    Implementa um Mutex (Lock Distribuído) via Redis para garantir que apenas
    uma instância desta tarefa execute por vez, protegendo o banco de dados contra concorrência.
    """
    lock_key = "lock:etl_manual_update"
    
    acquire_lock = redis_client.set(lock_key, "true", nx=True, ex=3600)
    
    if not acquire_lock:
        logger.warning(
            f"Bloqueado: Outro processo de ETL já está em execução. "
            f"Ignorando tarefa duplicada [ID: {self.request.id}]."
        )
        return {
            "status": "Skipped", 
            "reason": "Another instance of ETL is already running. Database is locked."
        }

    logger.info(f"Iniciando tarefa de ETL [ID: {self.request.id}]. Pipelines: {pipelines_to_run}")
    
    try:
        etl_service = EtlService()
        
        asyncio.run(etl_service.run_manual_update(pipelines_to_run=pipelines_to_run))
        
        logger.info(f"Tarefa de ETL [ID: {self.request.id}] concluída com sucesso.")
        return {"status": "Completed", "pipelines_run": pipelines_to_run}
        
    except Exception as e:
        logger.error(f"Erro ao executar a tarefa de ETL [ID: {self.request.id}]: {str(e)}")
        
        self.update_state(
            state="FAILURE",
            meta={
                "exc_type": type(e).__name__,
                "exc_message": str(e),
                "traceback": traceback.format_exc(),
            },
        )
        
        raise
        
    finally:
        logger.info(f"Liberando trava global do ETL [ID: {self.request.id}]")
        redis_client.delete(lock_key)


if __name__ == "__main__":
    worker_args = ["worker", "--loglevel=info"] if len(sys.argv) == 1 else sys.argv
    celery_app.worker_main(argv=worker_args)