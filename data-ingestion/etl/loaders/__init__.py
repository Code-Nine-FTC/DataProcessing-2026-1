"""
Carregadores - Camada L do ETL
Responsável por inserir dados normalizados no banco.
"""
import logging
import re
from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.models import TransformedRecord, LoadResult
from core.exceptions import LoadException
from infrastructure.repositories import FonteDadoRepository, DatasetRepository
from domain.entities import FonteDado

logger = logging.getLogger(__name__)

_SAFE_TABLE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class BaseLoader(ABC):
    """Classe base para carregadores."""

    def __init__(self, engine: Engine, table_name: str):
        self.engine = engine
        self.table_name = table_name
        self.fonte_repo = FonteDadoRepository(engine)
        self.dataset_repo = DatasetRepository(engine)

    @abstractmethod
    def get_insert_query(self) -> str:
        """Retorna query SQL de inserção. Implementar em subclasses."""
        pass

    def count_rows_for_dataset(self, dataset_id: str) -> int:
        """Quantidade de linhas já carregadas para este dataset na tabela fato."""
        if not _SAFE_TABLE_NAME.match(self.table_name):
            raise LoadException(f"Invalid table name for count: {self.table_name!r}")
        try:
            with self.engine.begin() as conn:
                q = text(
                    f"SELECT COUNT(*) FROM {self.table_name} WHERE dataset_id = :ds"
                )
                row = conn.execute(q, {"ds": dataset_id}).scalar()
                return int(row or 0)
        except Exception as e:
            raise LoadException(
                f"Failed to count rows in {self.table_name}: {str(e)}"
            ) from e

    def load(self, records: list[TransformedRecord], dataset_id: str) -> LoadResult:
        """Carrega registros no banco."""
        if not records:
            logger.warning("No records to load")
            return LoadResult(
                total_records=0,
                inserted_records=0,
                failed_records=0,
            )

        logger.info(f"[{self.table_name}] Loading {len(records)} records...")

        inserted = 0
        failed = 0
        errors = []

        # Tenta bulk insert; se falhar, faz fallback registro a registro
        params_list = [
            self._prepare_record_params(record, dataset_id) for record in records
        ]
        try:
            with self.engine.begin() as conn:
                conn.execute(text(self.get_insert_query()), params_list)
            inserted = len(params_list)
        except Exception as bulk_err:
            logger.warning(
                f"[{self.table_name}] Bulk insert falhou ({bulk_err}). "
                "Tentando registro a registro..."
            )
            for params in params_list:
                try:
                    with self.engine.begin() as conn:
                        conn.execute(text(self.get_insert_query()), [params])
                    inserted += 1
                except Exception as row_err:
                    logger.warning(f"[{self.table_name}] Registro ignorado: {row_err}")
                    errors.append(str(row_err))
                    failed += 1

        logger.info(
            f"[{self.table_name}] Successfully loaded {inserted}/{len(records)} records"
            + (f" ({failed} ignorados)" if failed else "")
        )

        return LoadResult(
            total_records=len(records),
            inserted_records=inserted,
            failed_records=failed,
            errors=errors,
        )

    def _prepare_record_params(
        self, record: TransformedRecord, dataset_id: str
    ) -> dict:
        """Prepara parâmetros de um registro para inserção. Implementar em subclasses."""
        return {
            "id": str(record.id),
            "id_origem": record.id_origem,
            "dataset_id": dataset_id,
        }

    def load_with_logging(
        self, records: list[TransformedRecord], dataset_id: str
    ) -> LoadResult:
        """Carrega com logging."""
        try:
            result = self.load(records, dataset_id)
            logger.info(
                f"[{self.table_name}] Load complete: "
                f"{result.inserted_records}/{result.total_records} records"
            )
            return result
        except Exception as e:
            logger.error(f"[{self.table_name}] Load failed: {str(e)}")
            raise


class GeometricLoader(BaseLoader):
    """Carregador base para dados com geometria."""

    def _prepare_record_params(
        self, record: TransformedRecord, dataset_id: str
    ) -> dict:
        """Prepara parâmetros com geometria."""
        params = super()._prepare_record_params(record, dataset_id)
        params.update(record.attributes)
        params["geom_wkt"] = record.geometry
        return params
