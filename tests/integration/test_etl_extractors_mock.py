import json
import os
import tempfile
from unittest.mock import patch

import pytest

from core.config import WFSConfig
from core.exceptions import ExtractionException
from core.models import DataSource, ExtractedData
from etl.extractors import WFSExtractor, CSVExtractor, ShapefileExtractor
from infrastructure.wfs_client import WFSClient

pytestmark = pytest.mark.integration


def _mock_geojson_bytes(features: list[dict]) -> bytes:
    """Cria bytes GeoJSON para mock de resposta WFS."""
    fc = {"type": "FeatureCollection", "features": features}
    return json.dumps(fc).encode("utf-8")


def _point_feature(lon: float, lat: float, props: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def _polygon_feature(coords: list, props: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [coords],
        },
        "properties": props,
    }


_MOCK_INPE_CSV_HEADER = (
    "Latitude,Longitude,DataHora,Satelite,FRP,RiscoFogo,Bioma,Municipio,Estado\n"
)
_MOCK_INPE_CSV_ROWS = (
    "-23.20,-45.92,2026/01/15 13:00:00,MODIS,85.0,0.90,Mata Atlantica,Sao Jose dos Campos,SP\n"
    "-23.19,-45.93,2026/01/20 14:00:00,MODIS,75.0,0.80,Mata Atlantica,Sao Jose dos Campos,SP\n"
)

_MOCK_PRODES_FEATURES = [
    _polygon_feature(
        [[[-46.0, -23.3], [-45.9, -23.3], [-45.9, -23.2], [-46.0, -23.2], [-46.0, -23.3]]],
        {
            "gid": 1,
            "year": 2025,
            "state": "SP",
            "class_name": "DESMATAMENTO",
            "areameters": 50000.0,
            "municipio": "Sao Jose dos Campos",
        },
    ),
    _polygon_feature(
        [[[-46.1, -23.4], [-46.0, -23.4], [-46.0, -23.3], [-46.1, -23.3], [-46.1, -23.4]]],
        {
            "gid": 2,
            "year": 2025,
            "state": "SP",
            "class_name": "DESMATAMENTO",
            "areameters": 30000.0,
            "municipio": "Jacarei",
        },
    ),
]

_MOCK_SICAR_FEATURES = [
    _polygon_feature(
        [[[-45.95, -23.22], [-45.90, -23.22], [-45.90, -23.18], [-45.95, -23.18], [-45.95, -23.22]]],
        {
            "gid": 1,
            "codigo_car": "SP-350000-000000000001",
            "nome_prop": "Fazenda Teste Alpha",
            "area_hectare": 120.5,
            "municipio": "Sao Jose dos Campos",
            "uf": "SP",
        },
    ),
]


class _MockResponse:
    """Mock de response do requests."""

    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")


class TestWFSExtractor:
    """Testa WFSExtractor com respostas HTTP mockadas."""

    @pytest.fixture
    def wfs_config(self):
        return WFSConfig(timeout=5, batch_size=10)

    @pytest.fixture
    def wfs_source(self):
        return DataSource(
            name="Test-WFS",
            url="http://test.wfs.server/geoserver/wfs",
            format="WFS/GeoJSON",
            agency="Test",
        )

    async def test_wfs_extract_returns_extracted_data(
        self, wfs_source, wfs_config
    ):
        mock_bytes = _mock_geojson_bytes([
            _polygon_feature(
                [[[-45.95, -23.22], [-45.90, -23.22], [-45.90, -23.18], [-45.95, -23.18], [-45.95, -23.22]]],
                {"id": 1, "nome": "Poligono A"},
            ),
        ])

        with patch("requests.get", return_value=_MockResponse(mock_bytes)):
            wfs_client = WFSClient(wfs_config)
            extractor = WFSExtractor(wfs_source, wfs_client, "test:layer")
            data = extractor.extract()

        assert isinstance(data, ExtractedData)
        assert len(data.rows) == 1
        assert data.source.name == "Test-WFS"

    async def test_wfs_extract_multiple_pages(self, wfs_source, wfs_config):
        page1_bytes = _mock_geojson_bytes([
            _polygon_feature(
                [[[-45.95, -23.22], [-45.90, -23.22], [-45.90, -23.18], [-45.95, -23.18], [-45.95, -23.22]]],
                {"id": 1},
            ),
            _polygon_feature(
                [[[-46.05, -23.35], [-46.00, -23.35], [-46.00, -23.30], [-46.05, -23.30], [-46.05, -23.35]]],
                {"id": 2},
            ),
        ])
        page2_bytes = _mock_geojson_bytes([
            _polygon_feature(
                [[[-45.75, -23.15], [-45.70, -23.15], [-45.70, -23.10], [-45.75, -23.10], [-45.75, -23.15]]],
                {"id": 3},
            ),
        ])
        empty_bytes = _mock_geojson_bytes([])

        call_count = [0]

        def _side_effect(url, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _MockResponse(page1_bytes)
            elif call_count[0] == 2:
                return _MockResponse(page2_bytes)
            else:
                return _MockResponse(empty_bytes)

        with patch("requests.get", side_effect=_side_effect):
            wfs_client = WFSClient(wfs_config)
            extractor = WFSExtractor(wfs_source, wfs_client, "test:layer")
            data = extractor.extract()

        # batch_size default 500 excede as 2 features da pagina 1, entao a paginacao para
        assert len(data.rows) == 2

    async def test_wfs_extract_http_error_raises(self, wfs_source, wfs_config):
        with patch(
            "requests.get",
            return_value=_MockResponse(b"", status_code=500),
        ):
            wfs_client = WFSClient(wfs_config)
            extractor = WFSExtractor(wfs_source, wfs_client, "test:layer")
            with pytest.raises(ExtractionException):
                extractor.extract()

    async def test_wfs_extract_connection_error_raises(self, wfs_source, wfs_config):
        with patch("requests.get", side_effect=ConnectionError("No route to host")):
            wfs_client = WFSClient(wfs_config)
            extractor = WFSExtractor(wfs_source, wfs_client, "test:layer")
            with pytest.raises(ExtractionException):
                extractor.extract()

    async def test_wfs_extract_empty_response_returns_empty(
        self, wfs_source, wfs_config
    ):
        empty_bytes = _mock_geojson_bytes([])
        with patch("requests.get", return_value=_MockResponse(empty_bytes)):
            wfs_client = WFSClient(wfs_config)
            extractor = WFSExtractor(wfs_source, wfs_client, "test:layer")
            data = extractor.extract()
        assert len(data.rows) == 0
        assert data.metadata["feature_count"] == 0


class TestPRODESExtractor:
    """Testa PRODESExtractor com respostas WFS mockadas."""

    @pytest.fixture
    def wfs_config(self):
        return WFSConfig(timeout=5, batch_size=10)

    @pytest.fixture
    def prodes_source(self):
        return DataSource(
            name="PRODES Test",
            url="http://terrabrasilis.dpi.inpe.br/geoserver/wfs",
            format="WFS/GeoJSON",
            agency="INPE",
        )

    async def test_prodes_extract_returns_features(self, wfs_config, prodes_source):
        mock_bytes = _mock_geojson_bytes(_MOCK_PRODES_FEATURES)

        with patch("requests.get", return_value=_MockResponse(mock_bytes)):
            from sources.prodes_desmatamento import PRODESExtractor

            wfs_client = WFSClient(wfs_config)
            extractor = PRODESExtractor(wfs_client)
            extractor.data_source = prodes_source
            data = extractor.extract()

        assert len(data.rows) == 2
        for row in data.rows:
            assert "gid" in row
            assert "geometry" in row

    async def test_prodes_extract_raises_on_empty(self, wfs_config, prodes_source):
        mock_bytes = _mock_geojson_bytes([])

        with patch("requests.get", return_value=_MockResponse(mock_bytes)):
            from sources.prodes_desmatamento import PRODESExtractor

            wfs_client = WFSClient(wfs_config)
            extractor = PRODESExtractor(wfs_client)
            extractor.data_source = prodes_source
            with pytest.raises(ExtractionException, match="Nenhuma feature"):
                extractor.extract()


class TestCARExtractor:
    """Testa CARExtractor com GetCapabilities e WFS mockados."""

    @pytest.fixture
    def wfs_config(self):
        return WFSConfig(timeout=5, batch_size=10)

    async def test_car_extract_com_wfs_success(self, wfs_config):
        capabilities_xml = """<?xml version="1.0"?>
<WFS_Capabilities>
  <FeatureTypeList>
    <FeatureType>
      <Name>prodes-car:car_properties</Name>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>"""

        wfs_bytes = _mock_geojson_bytes(_MOCK_SICAR_FEATURES)
        call_log = []

        def _side_effect(url, *args, **kwargs):
            params = kwargs.get("params", args[1] if len(args) > 1 else {})
            call_log.append((url, params))
            is_capabilities = (
                "GetCapabilities" in url
                or (isinstance(params, dict) and "GetCapabilities" in str(params.get("request", "")))
            )
            if is_capabilities:
                return _MockResponse(capabilities_xml.encode("utf-8"))
            return _MockResponse(wfs_bytes)

        with patch("requests.get", side_effect=_side_effect):
            from sources.car import CARExtractor

            wfs_client = WFSClient(wfs_config)
            extractor = CARExtractor(wfs_client)
            data = extractor.extract()

        assert len(data.rows) == 1
        assert data.metadata["feature_count"] == 1

    async def test_car_extract_fallback_quando_wfs_falha(self, wfs_config):
        with patch("requests.get", side_effect=Exception("WFS unavailable")):
            from sources.car import CARExtractor

            wfs_client = WFSClient(wfs_config)
            extractor = CARExtractor(wfs_client)
            with pytest.raises(Exception):
                extractor.extract()


class TestCSVExtractor:
    """Testa CSVExtractor com arquivos CSV temporários."""

    @pytest.fixture
    def csv_source(self):
        return DataSource(
            name="Test-CSV",
            url="file://test.csv",
            format="CSV",
            agency="Test",
        )

    async def test_csv_extract_reads_rows(self, csv_source):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(_MOCK_INPE_CSV_HEADER)
            f.write(_MOCK_INPE_CSV_ROWS)
            csv_path = f.name

        try:
            extractor = CSVExtractor(csv_source, csv_pattern=csv_path)
            data = extractor.extract()
            assert len(data.rows) == 2
            assert data.metadata["row_count"] == 2
            assert data.rows[0]["Latitude"] == -23.2
            assert data.rows[0]["Satelite"] == "MODIS"
        finally:
            os.unlink(csv_path)

    async def test_csv_extract_sem_arquivo_retorna_vazio(self, csv_source):
        extractor = CSVExtractor(
            csv_source,
            csv_pattern="/tmp/nao_existe_*.csv",
        )
        data = extractor.extract()
        assert len(data.rows) == 0
        assert data.metadata["row_count"] == 0

    async def test_csv_extract_multiplas_colunas(self, csv_source):
        header = "id,nome,valor,data\n"
        rows = "1,Item A,100.5,2026-01-01\n2,Item B,200.0,2026-02-01\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(header)
            f.write(rows)
            csv_path = f.name

        try:
            extractor = CSVExtractor(csv_source, csv_pattern=csv_path)
            data = extractor.extract()
            assert len(data.rows) == 2
            assert data.rows[1]["nome"] == "Item B"
            assert float(data.rows[1]["valor"]) == 200.0
        finally:
            os.unlink(csv_path)

    async def test_csv_extract_latin1_encoding(self, csv_source):
        header = "nome,municipio\n"
        rows = "Fazenda Teste,São José dos Campos\nSítio Beta,Jacareí\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="latin-1"
        ) as f:
            f.write(header)
            f.write(rows)
            csv_path = f.name

        try:
            extractor = CSVExtractor(csv_source, csv_pattern=csv_path)
            data = extractor.extract()
            assert len(data.rows) == 2
            assert "São" in str(data.rows[0])
        finally:
            os.unlink(csv_path)


class TestShapefileExtractor:
    """Testa ShapefileExtractor com cenários de erro e fallback."""

    @pytest.fixture
    def shp_source(self):
        return DataSource(
            name="Test-Shapefile",
            url="file://test.shp",
            format="SHP",
            agency="Test",
        )

    async def test_shapefile_sem_arquivo_retorna_vazio(self, shp_source):
        extractor = ShapefileExtractor(
            shp_source,
            shp_path="/tmp/nao_existe/*.shp",
        )
        data = extractor.extract()
        assert len(data.rows) == 0
        assert data.metadata["row_count"] == 0

    async def test_shapefile_diretorio_sem_shp_retorna_vazio(self, shp_source):
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ShapefileExtractor(shp_source, shp_path=tmpdir)
            data = extractor.extract()
        assert len(data.rows) == 0


class TestExtractorErrors:
    """Testa cenários de erro e exceções nos extractors."""

    async def test_wfs_invalid_geojson_raises(self):
        wfs_config = WFSConfig(timeout=5)
        source = DataSource(name="Test-Error", url="http://test/wfs", format="WFS", agency="T")

        with patch(
            "requests.get",
            return_value=_MockResponse(b"not geojson content"),
        ):
            wfs_client = WFSClient(wfs_config)
            extractor = WFSExtractor(source, wfs_client, "test:layer")
            with pytest.raises(ExtractionException):
                extractor.extract()

    async def test_wfs_empty_content_returns_empty(self):
        wfs_config = WFSConfig(timeout=5)
        source = DataSource(name="Test-Empty", url="http://test/wfs", format="WFS", agency="T")

        with patch(
            "requests.get",
            return_value=_MockResponse(_mock_geojson_bytes([])),
        ):
            wfs_client = WFSClient(wfs_config)
            extractor = WFSExtractor(source, wfs_client, "test:layer")
            data = extractor.extract()
            assert len(data.rows) == 0

    async def test_extract_with_logging_does_not_swallow_errors(self):
        class _BrokenExtractor(WFSExtractor):
            def extract(self) -> ExtractedData:
                raise ValueError("Erro interno simulato")

        wfs_config = WFSConfig(timeout=5)
        source = DataSource(name="Test-Broken", url="http://test/wfs", format="WFS", agency="T")

        with patch("requests.get", return_value=_MockResponse(b"{}")):
            wfs_client = WFSClient(wfs_config)
            extractor = _BrokenExtractor(source, wfs_client, "test:layer")
            with pytest.raises(Exception, match="Erro interno simulato"):
                extractor.extract_with_logging()
