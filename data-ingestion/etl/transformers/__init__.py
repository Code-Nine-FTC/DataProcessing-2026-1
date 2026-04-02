"""
Transformadores - Camada T do ETL
Responsável por normalizar e validar dados extraídos.
"""
import logging
import json
import math
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Any
from uuid import uuid4

import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon, MultiPolygon

from core.models import ExtractedData, TransformedRecord
from core.exceptions import TransformationException

logger = logging.getLogger(__name__)


class BaseTransformer(ABC):
    """Classe base para transformadores."""

    def __init__(self, table_name: str):
        self.table_name = table_name

    @abstractmethod
    def transform(self, data: ExtractedData) -> list[TransformedRecord]:
        """Transforma dados extraídos. Implementar em subclasses."""
        pass

    def transform_with_logging(self, data: ExtractedData) -> list[TransformedRecord]:
        """Transforma com logging."""
        logger.info(
            f"[{self.table_name}] Transforming {len(data.rows)} records..."
        )
        try:
            records = self.transform(data)
            logger.info(f"[{self.table_name}] Transformed {len(records)} records")
            return records
        except Exception as e:
            logger.error(f"[{self.table_name}] Transformation failed: {str(e)}")
            raise

    @staticmethod
    def pick(row: dict, candidates: Tuple[str, ...], default=None) -> Optional[Any]:
        """Retorna o primeiro valor não-nulo de uma lista de candidatos."""
        for candidate in candidates:
            if candidate not in row:
                continue
            v = row.get(candidate)
            if v is not None and str(v).strip() not in ("", "nan", "None"):
                return v
        return default

    @staticmethod
    def safe_float(val, null_sentinel: Optional[float] = None) -> Optional[float]:
        """Converte valor para float com tratamento de nulos."""
        if val is None:
            return None
        try:
            f = float(val)
            if math.isnan(f):
                return None
            if null_sentinel is not None and f == null_sentinel:
                return None
            return f
        except (TypeError, ValueError):
            return None

    @staticmethod
    def safe_int(val) -> Optional[int]:
        """Converte valor para int com tratamento de nulos."""
        if val is None:
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def ensure_multipolygon(geom) -> Optional[MultiPolygon]:
        """Garante que a geometria é um MultiPolygon."""
        if geom is None or (hasattr(geom, "is_empty") and geom.is_empty):
            return None
        if hasattr(geom, "geom_type") and geom.geom_type == "Polygon":
            return MultiPolygon([geom])
        return geom

    @staticmethod
    def row_to_json(row: dict) -> str:
        """Serializa uma linha para JSON, ignorando geometry."""
        d = {}
        for k, v in row.items():
            if k == "geometry":
                continue
            if isinstance(v, np.integer):
                d[k] = int(v)
            elif isinstance(v, np.floating):
                d[k] = None if np.isnan(v) else float(v)
            elif isinstance(v, np.bool_):
                d[k] = bool(v)
            else:
                try:
                    if pd.isna(v):
                        d[k] = None
                        continue
                except (TypeError, ValueError):
                    pass
                d[k] = v
        return json.dumps(d, default=str)


class GeometricTransformer(BaseTransformer):
    """Transformador para dados com geometria (GDF)."""

    def transform_feature(self, feature: dict) -> Optional[TransformedRecord]:
        """Transforma uma feature GeoJSON em TransformedRecord. Implementar em subclasses."""
        raise NotImplementedError

    def transform(self, data: ExtractedData) -> list[TransformedRecord]:
        """Transforma features geométricos."""
        records = []
        errors = 0

        for feature in data.rows:
            try:
                record = self.transform_feature(feature)
                if record:
                    records.append(record)
            except Exception as e:
                logger.warning(f"Failed to transform feature: {str(e)}")
                errors += 1

        if errors > 0:
            logger.warning(f"Transformation errors: {errors}")

        return records
