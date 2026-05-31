import json
from pathlib import Path
from uuid import uuid4

import geopandas as gpd
import pytest
from shapely.geometry import Point
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from core.crs_handler import standardize_geodataframe
from core.models import DataSource, ExtractedData, TransformedRecord, LoadResult
from domain.entities import FonteDado
from etl.extractors import BaseExtractor
from etl.loaders import GeometricLoader
from etl.pipeline import BasePipeline
from etl.transformers import GeometricTransformer

pytestmark = pytest.mark.integration

FIXTURES_DIR = Path(__file__).parents[1] / "fixtures" / "data"


class GeoJSONFileExtractor(BaseExtractor):
    """Extractor que lê um arquivo GeoJSON do diretório de fixtures."""

    def __init__(self, data_source: DataSource, geojson_path: Path):
        super().__init__(data_source)
        self.file_path = str(geojson_path)

    def extract(self) -> ExtractedData:
        gdf = gpd.read_file(self.file_path)
        gdf = standardize_geodataframe(gdf)
        return ExtractedData(
            source=self.data_source,
            rows=gdf.to_dict("records"),
            metadata={
                "feature_count": len(gdf),
                "crs": str(gdf.crs),
                "source_file": self.file_path,
            },
        )


class TestGeoJSONExtractor:
    """Fase E — Extração de dados de arquivos GeoJSON de fixture."""

    @pytest.mark.parametrize(
        "filename,expected_count",
        [
            ("01_municipios.geojson", 3),
            ("02_imoveis.geojson", 3),
            ("03_queimadas.geojson", 5),
        ],
    )
    async def test_extract_fixture_count(self, filename, expected_count):
        source_name = f"test-extract-{filename}"
        extractor = GeoJSONFileExtractor(
            DataSource(name=source_name, format="GeoJSON", agency="Test"),
            FIXTURES_DIR / filename,
        )
        data = extractor.extract()
        assert len(data.rows) == expected_count
        assert data.metadata["feature_count"] == expected_count
        assert data.source.name == source_name

    async def test_extract_imoveis_has_expected_fields(self):
        extractor = GeoJSONFileExtractor(
            DataSource(name="test-extract-fields", format="GeoJSON", agency="Test"),
            FIXTURES_DIR / "02_imoveis.geojson",
        )
        data = extractor.extract()
        row = data.rows[0]
        assert "codigo_car" in row
        assert "nome_imovel" in row
        assert "area_ha" in row
        assert "geometry" in row

    async def test_extract_queimadas_has_expected_fields(self):
        extractor = GeoJSONFileExtractor(
            DataSource(name="test-extract-queimadas", format="GeoJSON", agency="Test"),
            FIXTURES_DIR / "03_queimadas.geojson",
        )
        data = extractor.extract()
        row = data.rows[0]
        assert "data_ocorrencia" in row
        assert "fonte_sensor" in row
        assert "intensidade" in row
        assert "geometry" in row

    async def test_extract_municipios_crs_4326(self):
        extractor = GeoJSONFileExtractor(
            DataSource(name="test-extract-crs", format="GeoJSON", agency="Test"),
            FIXTURES_DIR / "01_municipios.geojson",
        )
        data = extractor.extract()
        assert data.metadata["crs"] == "EPSG:4326"

    async def test_extract_file_not_found(self):
        extractor = GeoJSONFileExtractor(
            DataSource(name="test-extract-notfound", format="GeoJSON", agency="Test"),
            FIXTURES_DIR / "nao_existe.geojson",
        )
        with pytest.raises(Exception):
            extractor.extract()


class TestPipelineTransform:
    """Fase T — Transformação de dados extraídos em TransformedRecord."""

    FIXTURE_SOURCE = DataSource(name="test-transform", format="GeoJSON", agency="Test")

    def test_transform_imovel_feature_has_wkt_geometry(self):
        gdf = gpd.read_file(FIXTURES_DIR / "02_imoveis.geojson")
        gdf = standardize_geodataframe(gdf)
        rows = gdf.to_dict("records")
        row = rows[0]
        geom = row.get("geometry")
        assert geom is not None
        wkt = geom.wkt
        assert wkt.startswith("MULTIPOLYGON")
        assert geom.is_valid

    def test_transform_queimada_feature_has_wkt_geometry(self):
        gdf = gpd.read_file(FIXTURES_DIR / "03_queimadas.geojson")
        gdf = standardize_geodataframe(gdf)
        rows = gdf.to_dict("records")
        row = rows[0]
        geom = row.get("geometry")
        assert geom is not None
        assert isinstance(geom, Point)
        assert geom.is_valid

    def test_transform_imoveis_to_transformed_records(self):
        gdf = gpd.read_file(FIXTURES_DIR / "02_imoveis.geojson")
        gdf = standardize_geodataframe(gdf)
        records = []
        for row in gdf.to_dict("records"):
            geom = row.get("geometry")
            geom_wkt = geom.wkt if geom and not geom.is_empty else None
            record = TransformedRecord(
                id=str(uuid4()),
                id_origem=str(row.get("codigo_car", "")),
                table_name="imovel_rural",
                geometry=geom_wkt,
                attributes={
                    "nome_imovel": row.get("nome_imovel"),
                    "codigo_car": row.get("codigo_car"),
                    "area_ha": row.get("area_ha"),
                },
            )
            records.append(record)
        assert len(records) == 3
        assert all(r.geometry for r in records)
        assert records[0].table_name == "imovel_rural"
        assert records[0].id_origem.startswith("SP-")

    def test_transform_municipios_extrai_estado_sigla(self):
        gdf = gpd.read_file(FIXTURES_DIR / "01_municipios.geojson")
        gdf = standardize_geodataframe(gdf)
        row = gdf.to_dict("records")[0]
        assert row.get("estado_sigla") == "SP"
        assert row.get("codigo_ibge") == "3548708"

    def test_transform_preserva_queimada_intensidade(self):
        gdf = gpd.read_file(FIXTURES_DIR / "03_queimadas.geojson")
        gdf = standardize_geodataframe(gdf)
        rows = gdf.to_dict("records")
        intensidades = [r["intensidade"] for r in rows]
        assert intensidades == [0.85, 0.75, 0.60, 0.55, 0.90]


class _TestImovelTransformer(GeometricTransformer):
    """Transformador de teste: mapeia fixture 02_imoveis.geojson → imovel_rural."""

    def __init__(self):
        super().__init__(table_name="imovel_rural")

    def transform_feature(self, feature: dict) -> TransformedRecord:
        geom = feature.get("geometry")
        geom_wkt = geom.wkt if geom and not geom.is_empty else None
        return TransformedRecord(
            id=str(uuid4()),
            id_origem=str(feature.get("codigo_car", str(uuid4()))),
            table_name=self.table_name,
            geometry=geom_wkt,
            attributes={
                "nome_imovel": feature.get("nome_imovel"),
                "codigo_car": feature.get("codigo_car"),
                "area_ha": feature.get("area_ha"),
                "atributos_json": self.row_to_json(feature),
            },
        )


class _TestImovelLoader(GeometricLoader):
    """Loader de teste: insere em imovel_rural com campos da fixture."""

    def __init__(self, engine):
        super().__init__(engine, table_name="imovel_rural")

    def get_insert_query(self) -> str:
        return """
            INSERT INTO imovel_rural
                (id, id_origem, dataset_id, nome_imovel, codigo_car,
                 area_ha, geom, centroid, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :nome_imovel, :codigo_car,
                 :area_ha,
                 ST_GeomFromText(:geom_wkt, 4326),
                 ST_PointOnSurface(ST_GeomFromText(:geom_wkt, 4326)),
                 CAST(:atributos_json AS JSONB))
        """


class _TestPipeline(BasePipeline):
    """Pipeline de teste para carregar fixture GeoJSON no banco."""

    def __init__(self, dataset_name, dataset_desc, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dataset_name = dataset_name
        self._dataset_desc = dataset_desc

    def _get_dataset_name(self) -> str:
        return self._dataset_name

    def _get_dataset_description(self) -> str:
        return self._dataset_desc


class TestPipelineLoad:
    """Fase L — Carga de TransformedRecord no banco real via GeometricLoader."""

    @pytest.fixture(scope="class")
    def sync_engine(self, postgis_container):
        _container, host, port = postgis_container
        url = f"postgresql+psycopg2://test:test@{host}:{port}/test_db"
        engine = create_engine(url, poolclass=NullPool)
        yield engine
        engine.dispose()

    @pytest.fixture(scope="class", autouse=True)
    def cleanup_loader_data(self, sync_engine):
        yield
        with sync_engine.begin() as conn:
            ds_to_delete = [
                row[0] for row in
                conn.execute(
                    text("SELECT id FROM dataset WHERE nome LIKE 'TEST_DATASET_%'")
                ).fetchall()
            ]
            for ds_id in ds_to_delete:
                conn.execute(
                    text("DELETE FROM imovel_rural WHERE dataset_id = :ds"),
                    {"ds": ds_id},
                )
                conn.execute(
                    text("DELETE FROM dataset WHERE id = :ds"),
                    {"ds": ds_id},
                )
            conn.execute(
                text("DELETE FROM fonte_dado WHERE nome LIKE 'test-loader-%'")
            )

    @pytest.fixture
    def dataset_id(self, sync_engine):
        from datetime import date
        import uuid as _uuid
        from infrastructure.repositories import FonteDadoRepository, DatasetRepository
        from domain.entities import FonteDado

        fonte_repo = FonteDadoRepository(sync_engine)
        dataset_repo = DatasetRepository(sync_engine)

        fonte_id = fonte_repo.create(
            FonteDado(
                nome=f"test-loader-{_uuid.uuid4().hex[:8]}",
                orgao_responsavel="Test",
                url_origem="file://test",
                formato="GeoJSON",
            )
        )
        ds_id, _ = dataset_repo.create(
            fonte_id=fonte_id,
            nome=f"TEST_DATASET_{_uuid.uuid4().hex[:8]}",
            descricao="Test dataset for loader tests",
            versao="2026",
            data_referencia=date.today(),
        )
        yield ds_id
        with sync_engine.begin() as conn:
            conn.execute(text("DELETE FROM imovel_rural WHERE dataset_id = :ds"), {"ds": ds_id})
            conn.execute(text("DELETE FROM dataset WHERE id = :ds"), {"ds": ds_id})

    async def test_geometric_loader_inserts_imovel_rural(
        self, sync_engine, db_session, dataset_id
    ):
        gdf = gpd.read_file(FIXTURES_DIR / "02_imoveis.geojson")
        gdf = standardize_geodataframe(gdf)
        records = []
        for row in gdf.to_dict("records"):
            geom = row.get("geometry")
            geom_wkt = geom.wkt if geom and not geom.is_empty else None
            records.append(
                TransformedRecord(
                    id=str(uuid4()),
                    id_origem=str(row.get("codigo_car", str(uuid4()))),
                    table_name="imovel_rural",
                    geometry=geom_wkt,
                    attributes={
                        "nome_imovel": row.get("nome_imovel"),
                        "codigo_car": row.get("codigo_car"),
                        "area_ha": row.get("area_ha"),
                        "atributos_json": json.dumps({"fonte": "test"}),
                    },
                )
            )

        loader = _TestImovelLoader(sync_engine)
        result = loader.load(records, dataset_id=dataset_id)
        assert result.inserted_records == 3
        assert result.total_records == 3
        assert result.failed_records == 0

        rows = (
            await db_session.execute(
                text(
                    "SELECT nome_imovel, codigo_car, area_ha "
                    "FROM imovel_rural WHERE dataset_id = :ds ORDER BY nome_imovel"
                ),
                {"ds": dataset_id},
            )
        ).all()
        assert len(rows) == 3
        nomes = [r[0] for r in rows]
        assert "Fazenda Teste Alpha" in nomes
        assert "Fazenda Teste Gamma" in nomes

    async def test_geometric_loader_inserts_geometry(self, sync_engine, db_session, dataset_id):
        gdf = gpd.read_file(FIXTURES_DIR / "02_imoveis.geojson")
        gdf = standardize_geodataframe(gdf)
        row0 = gdf.to_dict("records")[0]
        geom_wkt = row0["geometry"].wkt

        records = [
            TransformedRecord(
                id=str(uuid4()),
                id_origem="geom-test",
                table_name="imovel_rural",
                geometry=geom_wkt,
                attributes={
                    "nome_imovel": "Geometria Teste",
                    "codigo_car": "SP-TEST-GEOM",
                    "area_ha": 10.0,
                    "atributos_json": json.dumps({"test": "geometry"}),
                },
            )
        ]

        loader = _TestImovelLoader(sync_engine)
        loader.load(records, dataset_id=dataset_id)

        row = (
            await db_session.execute(
                text(
                    "SELECT ST_AsText(geom), ST_GeometryType(geom) "
                    "FROM imovel_rural WHERE dataset_id = :ds"
                ),
                {"ds": dataset_id},
            )
        ).one()
        assert row[1] == "ST_MultiPolygon"

    async def test_loader_with_empty_records(self, sync_engine, db_session):
        loader = _TestImovelLoader(sync_engine)
        result = loader.load([], dataset_id=str(uuid4()))
        assert result.inserted_records == 0
        assert result.total_records == 0

    async def test_loader_creates_fonte_dado_and_dataset(
        self, sync_engine, db_session
    ):
        source_name = f"test-loader-fonte-{uuid4().hex[:8]}"
        fonte_dado = DataSource(
            name=source_name,
            url="file://test",
            format="GeoJSON",
            agency="Test",
        )
        gdf = gpd.read_file(FIXTURES_DIR / "02_imoveis.geojson")
        gdf = standardize_geodataframe(gdf)
        row0 = gdf.to_dict("records")[0]

        record = TransformedRecord(
            id=str(uuid4()),
            id_origem="fonte-test",
            table_name="imovel_rural",
            geometry=row0["geometry"].wkt,
            attributes={
                "nome_imovel": "Fonte Teste",
                "codigo_car": "SP-FONTE-TEST",
                "area_ha": 5.0,
                "atributos_json": json.dumps({"fonte": source_name}),
            },
        )

        from etl.pipeline import BasePipeline
        from infrastructure.repositories import FonteDadoRepository

        fonte_repo = FonteDadoRepository(sync_engine)
        fonte_id = fonte_repo.create(
            FonteDado(
                nome=source_name,
                orgao_responsavel="Test",
                url_origem="file://test",
                formato="GeoJSON",
            )
        )
        assert fonte_id is not None
        fonte_db = await db_session.execute(
            text("SELECT nome FROM fonte_dado WHERE id = :id"), {"id": fonte_id}
        )
        assert fonte_db.scalar_one() == source_name

    async def test_cleanup_pipeline_data(self, sync_engine, db_session, dataset_id):
        gdf = gpd.read_file(FIXTURES_DIR / "02_imoveis.geojson")
        gdf = standardize_geodataframe(gdf)
        records = [
            TransformedRecord(
                id=str(uuid4()),
                id_origem=str(r.get("codigo_car", str(uuid4()))),
                table_name="imovel_rural",
                geometry=r["geometry"].wkt,
                attributes={
                    "nome_imovel": r.get("nome_imovel"),
                    "codigo_car": r.get("codigo_car"),
                    "area_ha": r.get("area_ha"),
                    "atributos_json": json.dumps({"test": "cleanup"}),
                },
            )
            for r in gdf.to_dict("records")
        ]
        loader = _TestImovelLoader(sync_engine)
        result = loader.load(records, dataset_id=dataset_id)
        assert result.inserted_records == 3

        with sync_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM imovel_rural WHERE dataset_id = :ds"),
                {"ds": dataset_id},
            )

        count = (
            await db_session.execute(
                text("SELECT COUNT(*) FROM imovel_rural WHERE dataset_id = :ds"),
                {"ds": dataset_id},
            )
        ).scalar_one()
        assert count == 0


class TestFullPipeline:
    """Testa o pipeline ETL completo (E → T → L) com fixture GeoJSON."""

    @pytest.fixture(scope="class")
    def sync_engine(self, postgis_container):
        _container, host, port = postgis_container
        url = f"postgresql+psycopg2://test:test@{host}:{port}/test_db"
        engine = create_engine(url, poolclass=NullPool)
        yield engine
        engine.dispose()

    @pytest.fixture(scope="class", autouse=True)
    def cleanup_pipeline_data(self, sync_engine):
        yield
        with sync_engine.begin() as conn:
            ds_to_delete = [
                row[0] for row in
                conn.execute(
                    text("SELECT id FROM dataset WHERE nome LIKE 'TEST_%'")
                ).fetchall()
            ]
            for ds_id in ds_to_delete:
                conn.execute(
                    text("DELETE FROM imovel_rural WHERE dataset_id = :ds"),
                    {"ds": ds_id},
                )
                conn.execute(
                    text("DELETE FROM queimada_evento WHERE dataset_id = :ds"),
                    {"ds": ds_id},
                )
                conn.execute(
                    text("DELETE FROM dataset WHERE id = :ds"),
                    {"ds": ds_id},
                )
            conn.execute(
                text("DELETE FROM fonte_dado WHERE nome LIKE 'test-pipeline-%'")
            )

    async def test_full_etl_pipeline_imoveis(self, sync_engine, db_session):
        uid = uuid4().hex[:8]
        pname = f"test-pipeline-imoveis-{uid}"
        extractor = GeoJSONFileExtractor(
            DataSource(
                name=pname,
                url="file://fixtures/data/02_imoveis.geojson",
                format="GeoJSON",
                agency="Test",
            ),
            FIXTURES_DIR / "02_imoveis.geojson",
        )
        transformer = _TestImovelTransformer()
        loader = _TestImovelLoader(sync_engine)

        pipeline = _TestPipeline(
            dataset_name=f"TEST_IMOVEIS_{uid}",
            dataset_desc="Teste de pipeline ETL com fixture imoveis",
            extractor=extractor,
            transformer=transformer,
            loader=loader,
            fonte_dado=DataSource(
                name=pname,
                url="file://fixtures/data/02_imoveis.geojson",
                format="GeoJSON",
                agency="Test",
            ),
        )

        result = pipeline.run()
        assert result.inserted_records == 3
        assert result.failed_records == 0

        rows = (
            await db_session.execute(
                text(
                    "SELECT nome_imovel, codigo_car, area_ha "
                    "FROM imovel_rural WHERE nome_imovel LIKE 'Fazenda Teste%'"
                )
            )
        ).all()
        nomes = {r[0] for r in rows}
        assert "Fazenda Teste Alpha" in nomes

    async def test_full_etl_pipeline_queimadas_point(self, sync_engine, db_session):
        uid = uuid4().hex[:8]
        pname = f"test-pipeline-queimadas-{uid}"

        class _QueimadaTransformer(GeometricTransformer):
            def __init__(self):
                super().__init__(table_name="queimada_evento")

            def transform_feature(self, feature: dict) -> TransformedRecord:
                geom = feature.get("geometry")
                geom_wkt = geom.wkt if geom and not geom.is_empty else None
                return TransformedRecord(
                    id=str(uuid4()),
                    id_origem=f"test-{uuid4().hex[:8]}",
                    table_name=self.table_name,
                    geometry=geom_wkt,
                    attributes={
                        "data_ocorrencia": feature.get("data_ocorrencia"),
                        "fonte_sensor": feature.get("fonte_sensor"),
                        "intensidade": feature.get("intensidade"),
                        "risco_fogo": feature.get("risco_fogo"),
                        "atributos_json": json.dumps({"test": uid}),
                    },
                )

        class _QueimadaLoader(GeometricLoader):
            def __init__(self, engine):
                super().__init__(engine, table_name="queimada_evento")

            def get_insert_query(self) -> str:
                return """
                    INSERT INTO queimada_evento
                        (id, id_origem, dataset_id, data_ocorrencia,
                         fonte_sensor, intensidade, risco_fogo,
                         geom, atributos_json)
                    VALUES
                        (:id, :id_origem, :dataset_id, :data_ocorrencia,
                         :fonte_sensor, :intensidade, :risco_fogo,
                         ST_GeomFromText(:geom_wkt, 4326),
                         CAST(:atributos_json AS JSONB))
                """

        extractor = GeoJSONFileExtractor(
            DataSource(
                name=pname,
                url="file://fixtures/data/03_queimadas.geojson",
                format="GeoJSON",
                agency="Test",
            ),
            FIXTURES_DIR / "03_queimadas.geojson",
        )
        transformer = _QueimadaTransformer()
        loader = _QueimadaLoader(sync_engine)

        pipeline = _TestPipeline(
            dataset_name=f"TEST_QUEIMADAS_{uid}",
            dataset_desc="Teste de pipeline ETL com fixture queimadas",
            extractor=extractor,
            transformer=transformer,
            loader=loader,
            fonte_dado=DataSource(
                name=pname,
                url="file://fixtures/data/03_queimadas.geojson",
                format="GeoJSON",
                agency="Test",
            ),
        )

        result = pipeline.run()
        assert result.inserted_records == 5
        assert result.failed_records == 0

        count = (
            await db_session.execute(
                text(
                    "SELECT COUNT(*) FROM queimada_evento "
                    "WHERE atributos_json->>'test' = :uid"
                ),
                {"uid": uid},
            )
        ).scalar_one()
        assert count == 5

    async def test_pipeline_deduplication_skips_duplicate(
        self, sync_engine, db_session
    ):
        uid = uuid4().hex[:8]
        pname = f"test-pipeline-dedup-{uid}"

        extractor = GeoJSONFileExtractor(
            DataSource(
                name=pname,
                url="file://fixtures/data/02_imoveis.geojson",
                format="GeoJSON",
                agency="Test",
            ),
            FIXTURES_DIR / "02_imoveis.geojson",
        )
        transformer = _TestImovelTransformer()
        loader = _TestImovelLoader(sync_engine)

        pipeline = _TestPipeline(
            dataset_name=f"TEST_DEDUP_{uid}",
            dataset_desc="Teste de deduplicacao",
            extractor=extractor,
            transformer=transformer,
            loader=loader,
            fonte_dado=DataSource(
                name=pname,
                url="file://fixtures/data/02_imoveis.geojson",
                format="GeoJSON",
                agency="Test",
            ),
        )

        result1 = pipeline.run()
        assert result1.inserted_records == 3

        result2 = pipeline.run()
        assert result2.inserted_records == 0
        assert result2.total_records == 0

    async def test_pipeline_error_propagation(self, sync_engine, db_session):
        class _FailingExtractor(BaseExtractor):
            def extract(self) -> ExtractedData:
                raise RuntimeError("Falha simulada na extracao")

        pipeline = _TestPipeline(
            dataset_name="TEST_ERROR",
            dataset_desc="Teste de erro",
            extractor=_FailingExtractor(
                DataSource(
                    name="test-error-extractor",
                    format="GeoJSON",
                    agency="Test",
                )
            ),
            transformer=_TestImovelTransformer(),
            loader=_TestImovelLoader(sync_engine),
            fonte_dado=DataSource(
                name="test-error-extractor",
                format="GeoJSON",
                agency="Test",
            ),
        )

        with pytest.raises(RuntimeError, match="Falha simulada na extracao"):
            pipeline.run()



