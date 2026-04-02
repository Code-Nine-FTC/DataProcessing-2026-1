"""
Extrator base para dados CSV.
Reutilizável para qualquer fonte CSV.
"""
import glob
import logging
from abc import abstractmethod
from typing import Optional

import pandas as pd

from core.models import ExtractedData, DataSource, IExtractor
from core.exceptions import ExtractionException

logger = logging.getLogger(__name__)


class CSVExtractor(IExtractor):
    """Extrator base para dados em CSV."""

    def __init__(self, data_source: DataSource, csv_pattern: str):
        """
        Args:
            data_source: Configuração da fonte
            csv_pattern: Padrão glob para encontrar arquivo (ex: "database/docs/*.csv")
        """
        super().__init__(data_source)
        self.csv_pattern = csv_pattern

    def _find_csv(self) -> Optional[str]:
        """Encontra o arquivo CSV mais recente."""
        files = sorted(glob.glob(self.csv_pattern))
        return files[-1] if files else None

    def _read_csv(self, filepath: str) -> pd.DataFrame:
        """Lê arquivo CSV."""
        logger.info(f"Reading CSV: {filepath}")
        df = pd.read_csv(filepath, encoding="latin-1")
        df.columns = df.columns.str.strip()
        return df

    def extract(self) -> ExtractedData:
        """Extrai dados do CSV."""
        csv_file = self._find_csv()
        if not csv_file:
            raise ExtractionException(f"No CSV found matching pattern: {self.csv_pattern}")

        df = self._read_csv(csv_file)
        logger.info(f"Loaded {len(df)} rows from {csv_file}")

        return ExtractedData(
            source=self.data_source,
            rows=df.to_dict("records"),
            metadata={
                "row_count": len(df),
                "columns": list(df.columns),
                "source_file": csv_file,
            },
        )
