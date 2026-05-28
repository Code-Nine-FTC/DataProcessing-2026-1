"""
Orquestrador da Pipeline - Coordena execução de todas as ETLs
"""
import logging
import sys
from typing import Dict, List
from pathlib import Path

from sqlalchemy import create_engine

from core.config import AppConfig
from core.exceptions import PipelineException
from infrastructure.wfs_client import WFSClient

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Coordena execução de múltiplas pipelines ETL."""

    def __init__(self, config: AppConfig, engine=None):
        self.config = config
        if engine:
            self.engine = engine
        else:
            self.engine = create_engine(
                config.db.url,
                pool_size=config.db.pool_size,
                max_overflow=config.db.max_overflow,
                echo=config.db.echo,
            )
        self.wfs_client = WFSClient(config.wfs)
        self.pipelines: Dict[str, callable] = {}
        self.results = {}
        self.on_progress = None # Callback function: (name, etapa, status, detalhes, total, inseridos)

    def set_progress_callback(self, callback):
        self.on_progress = callback

    def _report_progress(self, name, etapa, status, detalhes=None, total=0, inseridos=0):
        if self.on_progress:
            try:
                self.on_progress(name, etapa, status, detalhes, total, inseridos)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    def close(self) -> None:
        """Libera as conexões do pool de banco."""
        self.engine.dispose()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def register_pipeline(self, name: str, factory: callable):
        """Registra uma factory de pipeline."""
        self.pipelines[name] = factory
        logger.info(f"Registered pipeline: {name}")

    def run_single(self, pipeline_name: str):
        """Executa uma pipeline específica."""
        if pipeline_name not in self.pipelines:
            raise PipelineException(f"Pipeline '{pipeline_name}' not found")

        logger.info(f"Executing pipeline: {pipeline_name}")
        try:
            factory = self.pipelines[pipeline_name]
            pipeline = factory(self.engine, self.wfs_client)
            
            # Hook the progress callback
            if self.on_progress:
                pipeline.set_progress_callback(self.on_progress)
            
            result = pipeline.run()
            self.results[pipeline_name] = result
            logger.info(f"✓ {pipeline_name}: {result.inserted_records} records inserted")
            return result
        except Exception as e:
            logger.error(f"✗ {pipeline_name} failed: {str(e)}")
            raise

    def run_all(self, order: List[str] = None):
        """Executa todas as pipelines na ordem especificada."""
        pipelines_to_run = order or list(self.pipelines.keys())

        logger.info("="* 70)
        logger.info("PIPELINE ORCHESTRATOR - STARTING")
        logger.info("="* 70)
        logger.info(f"Order: {' → '.join(pipelines_to_run)}\n")

        successful = 0
        failed = 0

        for pipeline_name in pipelines_to_run:
            try:
                self.run_single(pipeline_name)
                successful += 1
            except Exception as e:
                logger.error(f"Pipeline failed: {str(e)}")
                failed += 1

        logger.info("\n" + "="* 70)
        logger.info(f"SUMMARY: {successful} successful, {failed} failed")
        logger.info("="* 70)

        return successful, failed

    def print_summary(self):
        """Imprime resumo dos resultados."""
        print("\n" + "="* 70)
        print("EXECUTION SUMMARY")
        print("="* 70)
        for name, result in self.results.items():
            print(
                f"{name:20} | "
                f"Total: {result.total_records:6} | "
                f"Inserted: {result.inserted_records:6} | "
                f"Failed: {result.failed_records:6}"
            )
