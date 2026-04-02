"""
Pipeline ETL - Orquestração de Extract → Transform → Load
"""
import logging
from abc import ABC, abstractmethod
from datetime import date

from core.models import IPipeline, LoadResult, DataSource
from core.exceptions import PipelineException
from infrastructure.repositories import FonteDadoRepository, DatasetRepository
from domain.entities import FonteDado
from etl.extractors import BaseExtractor
from etl.transformers import BaseTransformer
from etl.loaders import BaseLoader

logger = logging.getLogger(__name__)


class BasePipeline(IPipeline, ABC):
    """Pipeline ETL base que coordena Extract → Transform → Load."""

    def __init__(
        self,
        extractor: BaseExtractor,
        transformer: BaseTransformer,
        loader: BaseLoader,
        fonte_dado: DataSource,
    ):
        self.extractor = extractor
        self.transformer = transformer
        self.loader = loader
        self.fonte_dado = fonte_dado

        self.fonte_repo = FonteDadoRepository(loader.engine)
        self.dataset_repo = DatasetRepository(loader.engine)

    def _datasource_to_fontedado(self, ds: DataSource) -> FonteDado:
        """Converte DataSource (DTO) para FonteDado (entidade de domínio)."""
        return FonteDado(
            nome=ds.name,
            orgao_responsavel=ds.agency,
            url_origem=ds.url,
            formato=ds.format,
            periodicidade=ds.frequency,
            escopo_geografico=ds.scope,
            licenca=ds.license,
        )

    def run(self) -> LoadResult:
        """Executa a pipeline completa."""
        logger.info(f"Starting pipeline: {self.fonte_dado.name}")

        try:
            # 1. Extract
            logger.info("→ Extract phase")
            extracted_data = self.extractor.extract_with_logging()

            # 2. Ensure FonteDado exists
            logger.info("→ Ensure FonteDado")
            fonte_entity = self._datasource_to_fontedado(self.fonte_dado)
            fonte_id = self.fonte_repo.create(fonte_entity)

            # 3. Create Dataset
            logger.info("→ Create Dataset")
            dataset_id, is_new = self.dataset_repo.create(
                fonte_id=fonte_id,
                nome=self._get_dataset_name(),
                descricao=self._get_dataset_description(),
                versao=str(date.today().year),
                data_referencia=date.today(),
            )

            # If dataset already exists, skip (avoid duplicates)
            if not is_new:
                logger.warning("Dataset already imported - skipping")
                return LoadResult(
                    total_records=0,
                    inserted_records=0,
                    failed_records=0,
                )

            # 4. Transform
            logger.info("→ Transform phase")
            transformed_records = self.transformer.transform_with_logging(
                extracted_data
            )

            # 5. Load
            logger.info("→ Load phase")
            load_result = self.loader.load_with_logging(
                transformed_records, dataset_id
            )

            logger.info(f"✓ Pipeline completed: {self.fonte_dado.name}")
            return load_result

        except Exception as e:
            logger.error(f"✗ Pipeline failed: {str(e)}")
            raise

    @abstractmethod
    def _get_dataset_name(self) -> str:
        """Nome do dataset. Implementar em subclasses."""
        pass

    @abstractmethod
    def _get_dataset_description(self) -> str:
        """Descrição do dataset. Implementar em subclasses."""
        pass
