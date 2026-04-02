# -*- coding: utf-8 -*-
import json
from datetime import datetime, date
from typing import Any, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    TEXT, VARCHAR, UUID as SQLAlchemyUUID, ForeignKey, 
    Integer, Numeric, Boolean, DateTime, Date, func, 
    CheckConstraint, text, SMALLINT, String, CheckConstraint, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector
from typing import Optional
from uuid import UUID
import uuid
from sqlalchemy import ForeignKey, Numeric, Integer, String, SmallInteger, DateTime, func, CheckConstraint, Index, UniqueConstraint

from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.engine import Row




class Base(AsyncAttrs, DeclarativeBase):
    pass

# --- 1. INFRAESTRUTURA E GESTÃO DE DADOS ---

class FonteDado(Base):
    __tablename__ = "fonte_dado"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    nome: Mapped[str] = mapped_column(TEXT, nullable=False)
    orgao_responsavel: Mapped[Optional[str]] = mapped_column(TEXT)
    url_origem: Mapped[Optional[str]] = mapped_column(TEXT)
    formato: Mapped[Optional[str]] = mapped_column(TEXT)
    periodicidade: Mapped[Optional[str]] = mapped_column(TEXT)
    escopo_geografico: Mapped[Optional[str]] = mapped_column(TEXT)
    licenca: Mapped[Optional[str]] = mapped_column(TEXT)
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true")

class Dataset(Base):
    __tablename__ = "dataset"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    fonte_dado_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("fonte_dado.id"))
    nome: Mapped[str] = mapped_column(TEXT, nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(TEXT)
    versao: Mapped[Optional[str]] = mapped_column(TEXT)
    data_coleta: Mapped[Optional[datetime]] = mapped_column(DateTime)
    data_referencia: Mapped[Optional[date]] = mapped_column(Date)
    hash_arquivo: Mapped[Optional[str]] = mapped_column(TEXT)
    caminho_arquivo: Mapped[Optional[str]] = mapped_column(TEXT)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB)

class Processamento(Base):
    __tablename__ = "processamento"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    dataset_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("dataset.id"))
    tipo_processamento: Mapped[Optional[str]] = mapped_column(TEXT)
    data_execucao: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[Optional[str]] = mapped_column(TEXT)
    log_execucao: Mapped[Optional[str]] = mapped_column(TEXT)
    parametros_json: Mapped[Optional[dict]] = mapped_column(JSONB)

# --- 2. BASE GEOGRÁFICA (ESTADOS, MUNICÍPIOS, BACIAS) ---

class Estado(Base):
    __tablename__ = "estado"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sigla: Mapped[Optional[str]] = mapped_column(VARCHAR(2))
    nome: Mapped[Optional[str]] = mapped_column(TEXT)
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))

    @staticmethod
    async def get_all(session: AsyncSession) -> list[Row]:
        result = await session.execute(
            text("SELECT id, sigla, nome FROM estado ORDER BY nome")
        )
        return result.all()

    @staticmethod
    async def get_municipios(session: AsyncSession, estado_id: int) -> list[Row]:
        result = await session.execute(
            text(
                "SELECT id, nome, codigo_ibge FROM municipio "
                "WHERE estado_id = :estado_id ORDER BY nome"
            ),
            {"estado_id": estado_id},
        )
        return result.all()

class Municipio(Base):
    __tablename__ = "municipio"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo_ibge: Mapped[Optional[str]] = mapped_column(VARCHAR(10))
    nome: Mapped[Optional[str]] = mapped_column(TEXT)
    estado_id: Mapped[Optional[int]] = mapped_column(ForeignKey("estado.id"))
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))

    @staticmethod
    async def get_dados_municipais(session: AsyncSession, municipio_id: int | None = None) -> list[Row]:
        query = text("""
            WITH cte_imoveis AS (
                SELECT municipio_id, jsonb_agg(jsonb_build_object(
                    'id', CAST(id AS TEXT), 
                    'nome', nome_imovel, 
                    'area_ha', area_ha,
                    'geom', ST_AsText(geom), 
                    'atributos_json', atributos_json
                )) AS dados FROM imovel_rural 
                WHERE (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER)) 
                GROUP BY municipio_id
            ),
            cte_ucs AS (
                SELECT municipio_id, jsonb_agg(jsonb_build_object(
                    'id', CAST(id AS TEXT), 
                    'nome', nome, 
                    'area_ha', area_ha,
                    'geom', ST_AsText(geom), 
                    'atributos_json', atributos_json
                )) AS dados FROM unidade_conservacao 
                WHERE (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER)) 
                GROUP BY municipio_id
            ),
            cte_tis AS (
                SELECT municipio_id, jsonb_agg(jsonb_build_object(
                    'id', CAST(id AS TEXT), 
                    'nome', nome, 
                    'area_ha', area_ha,
                    'geom', ST_AsText(geom), 
                    'atributos_json', atributos_json
                )) AS dados FROM terra_indigena 
                WHERE (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER)) 
                GROUP BY municipio_id
            ),
            cte_assentamentos AS (
                SELECT municipio_id, jsonb_agg(jsonb_build_object(
                    'id', CAST(id AS TEXT), 
                    'nome', nome, 
                    'area_ha', area_ha,
                    'geom', ST_AsText(geom), 
                    'atributos_json', atributos_json
                )) AS dados FROM assentamento_rural 
                WHERE (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER)) 
                GROUP BY municipio_id
            ),
            cte_quilombolas AS (
                SELECT municipio_id, jsonb_agg(jsonb_build_object(
                    'id', CAST(id AS TEXT), 
                    'nome', nome, 
                    'area_ha', area_ha,
                    'geom', ST_AsText(geom), 
                    'atributos_json', atributos_json
                )) AS dados FROM territorio_quilombola 
                WHERE (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER)) 
                GROUP BY municipio_id
            ),
            cte_alertas AS (
                SELECT municipio_id, jsonb_agg(jsonb_build_object(
                    'id', CAST(id AS TEXT), 
                    'nome', tipo_alerta, 
                    'area_ha', area_ha,
                    'geom', ST_AsText(geom), 
                    'atributos_json', atributos_json
                )) AS dados FROM desmatamento_alerta 
                WHERE (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER)) 
                GROUP BY municipio_id
            )

            SELECT 
                m.id, 
                m.nome, 
                m.codigo_ibge, 
                e.sigla AS estado_sigla,
                ST_AsText(m.geom) AS geom,
                -- ATENÇÃO: Verifique se no seu Schema Pydantic é 'imovel_rural' ou 'imoveis_rurais'
                COALESCE(i.dados, '[]'::jsonb) AS imoveis_rurais, 
                COALESCE(u.dados, '[]'::jsonb) AS unidades_conservacao,
                COALESCE(t.dados, '[]'::jsonb) AS terras_indigenas,
                COALESCE(s.dados, '[]'::jsonb) AS assentamentos,
                COALESCE(q.dados, '[]'::jsonb) AS quilombolas,
                COALESCE(a.dados, '[]'::jsonb) AS alertas_desmatamento
            FROM municipio m
            JOIN estado e ON m.estado_id = e.id
            LEFT JOIN cte_imoveis i      ON m.id = i.municipio_id
            LEFT JOIN cte_ucs u          ON m.id = u.municipio_id
            LEFT JOIN cte_tis t          ON m.id = t.municipio_id
            LEFT JOIN cte_assentamentos s ON m.id = s.municipio_id
            LEFT JOIN cte_quilombolas q  ON m.id = q.municipio_id
            LEFT JOIN cte_alertas a      ON m.id = a.municipio_id
            WHERE (CAST(:mun_id AS INTEGER) IS NULL OR m.id = CAST(:mun_id AS INTEGER))
        """)

        result = await session.execute(query, {"mun_id": municipio_id})
        return result.all()

    @staticmethod
    async def get_estatisticas(session: AsyncSession, municipio_id: int) -> dict:
        result = await session.execute(
            text("""
                SELECT
                    m.id, m.nome, m.codigo_ibge, e.sigla AS estado_sigla,
                    (SELECT COUNT(*) FROM imovel_rural          WHERE municipio_id = m.id) AS total_imoveis,
                    (SELECT COUNT(*) FROM terra_indigena         WHERE municipio_id = m.id) AS total_tis,
                    (SELECT COUNT(*) FROM unidade_conservacao    WHERE municipio_id = m.id) AS total_ucs,
                    (SELECT COUNT(*) FROM assentamento_rural     WHERE municipio_id = m.id) AS total_assentamentos,
                    (SELECT COUNT(*) FROM territorio_quilombola  WHERE municipio_id = m.id) AS total_quilombolas,
                    (SELECT COUNT(*) FROM desmatamento_alerta    WHERE municipio_id = m.id) AS total_alertas,
                    (SELECT COUNT(*) FROM queimada_evento        WHERE municipio_id = m.id) AS total_queimadas,
                    (SELECT CAST(COALESCE(SUM(area_ha), 0) AS float) FROM imovel_rural       WHERE municipio_id = m.id) AS area_imoveis_ha,
                    (SELECT CAST(COALESCE(SUM(area_ha), 0) AS float) FROM desmatamento_alerta WHERE municipio_id = m.id) AS area_desmatamento_ha
                FROM municipio m
                JOIN estado e ON m.estado_id = e.id
                WHERE m.id = :mun_id
            """),
            {"mun_id": municipio_id},
        )
        row = result.first()
        if row is None:
            return {}
        return dict(row._mapping)

    GEOJSON_LAYERS = [
        "municipios",
        "estados",
        "bacias",
        "imoveis_rurais",
        "terras_indigenas",
        "unidades_conservacao",
        "assentamentos",
        "quilombolas",
        "alertas_desmatamento",
        "queimadas",
        "camadas_estaduais",
    ]

    @staticmethod
    async def get_geojson_layer(
        session: AsyncSession,
        layer: str,
        municipio_id: int | None = None,
    ) -> dict:
        _QUERIES: dict[str, str] = {
            "municipios": """
                SELECT id, nome, codigo_ibge,
                       ST_AsGeoJSON(geom) AS geometry
                FROM municipio
                WHERE geom IS NOT NULL
                  AND (CAST(:mun_id AS INTEGER) IS NULL OR id = CAST(:mun_id AS INTEGER))
            """,
            "estados": """
                SELECT id, sigla, nome,
                       ST_AsGeoJSON(geom) AS geometry
                FROM estado
                WHERE geom IS NOT NULL
            """,
            "bacias": """
                SELECT id, nome, codigo,
                       ST_AsGeoJSON(geom) AS geometry
                FROM bacia_hidrografica
                WHERE geom IS NOT NULL
            """,
            "imoveis_rurais": """
                SELECT CAST(id AS TEXT) AS id, nome_imovel AS nome, codigo_car,
                       CAST(area_ha AS float) AS area_ha, situacao_cadastral, municipio_id,
                       ST_AsGeoJSON(geom) AS geometry
                FROM imovel_rural
                WHERE geom IS NOT NULL
                  AND (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER))
            """,
            "terras_indigenas": """
                SELECT CAST(id AS TEXT) AS id, nome, fase,
                       CAST(area_ha AS float) AS area_ha, municipio_id,
                       ST_AsGeoJSON(geom) AS geometry
                FROM terra_indigena
                WHERE geom IS NOT NULL
                  AND (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER))
            """,
            "unidades_conservacao": """
                SELECT CAST(id AS TEXT) AS id, nome, categoria, esfera, grupo_snuc,
                       CAST(area_ha AS float) AS area_ha, municipio_id,
                       ST_AsGeoJSON(geom) AS geometry
                FROM unidade_conservacao
                WHERE geom IS NOT NULL
                  AND (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER))
            """,
            "assentamentos": """
                SELECT CAST(id AS TEXT) AS id, nome,
                       CAST(area_ha AS float) AS area_ha, modalidade, familias, municipio_id,
                       ST_AsGeoJSON(geom) AS geometry
                FROM assentamento_rural
                WHERE geom IS NOT NULL
                  AND (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER))
            """,
            "quilombolas": """
                SELECT CAST(id AS TEXT) AS id, nome,
                       CAST(area_ha AS float) AS area_ha, municipio_id,
                       ST_AsGeoJSON(geom) AS geometry
                FROM territorio_quilombola
                WHERE geom IS NOT NULL
                  AND (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER))
            """,
            "alertas_desmatamento": """
                SELECT CAST(id AS TEXT) AS id, tipo_alerta AS nome,
                       CAST(area_ha AS float) AS area_ha,
                       CAST(data_ocorrencia AS TEXT) AS data_ocorrencia,
                       municipio_id,
                       ST_AsGeoJSON(geom) AS geometry
                FROM desmatamento_alerta
                WHERE geom IS NOT NULL
                  AND (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER))
            """,
            "queimadas": """
                SELECT CAST(id AS TEXT) AS id, fonte_sensor,
                       CAST(intensidade AS float) AS intensidade,
                       CAST(data_ocorrencia AS TEXT) AS data_ocorrencia,
                       municipio_id,
                       ST_AsGeoJSON(geom) AS geometry
                FROM queimada_evento
                WHERE geom IS NOT NULL
                  AND (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER))
            """,
            "camadas_estaduais": """
                SELECT CAST(id AS TEXT) AS id, nome, subtipo, tema, municipio_id,
                       ST_AsGeoJSON(geom) AS geometry
                FROM camada_estadual_ambiental
                WHERE geom IS NOT NULL
                  AND (CAST(:mun_id AS INTEGER) IS NULL OR municipio_id = CAST(:mun_id AS INTEGER))
            """,
        }

        if layer not in _QUERIES:
            return {"type": "FeatureCollection", "name": layer, "features": []}

        result = await session.execute(text(_QUERIES[layer]), {"mun_id": municipio_id})
        rows = result.mappings().all()

        features = [
            {
                "type": "Feature",
                "geometry": json.loads(row["geometry"]),
                "properties": {k: v for k, v in row.items() if k != "geometry"},
            }
            for row in rows
            if row["geometry"] is not None
        ]

        return {
            "type": "FeatureCollection",
            "name": layer,
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
            },
            "features": features,
        }


class GradeEspacial(Base):
    __tablename__ = "grade_espacial"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[Optional[str]] = mapped_column(TEXT)
    codigo: Mapped[Optional[str]] = mapped_column(TEXT)
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))

class BaciaHidrografica(Base):
    __tablename__ = "bacia_hidrografica"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[Optional[str]] = mapped_column(TEXT)
    codigo: Mapped[Optional[str]] = mapped_column(TEXT)
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))

# --- 3. DOMÍNIO AMBIENTAL (IMÓVEIS E ALERTAS) ---

class ImovelRural(Base):
    __tablename__ = "imovel_rural"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    id_origem: Mapped[Optional[str]] = mapped_column(TEXT)
    dataset_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("dataset.id"))
    nome_imovel: Mapped[Optional[str]] = mapped_column(TEXT)
    codigo_car: Mapped[Optional[str]] = mapped_column(TEXT)
    area_ha: Mapped[Optional[float]] = mapped_column(Numeric)
    municipio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("municipio.id"))
    situacao_cadastral: Mapped[Optional[str]] = mapped_column(TEXT)
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    centroid: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326))
    atributos_json: Mapped[Optional[dict]] = mapped_column(JSONB)

    @staticmethod
    async def get_by_id(session: AsyncSession, imovel_id: str) -> Row | None:
        result = await session.execute(
            text("""
                SELECT CAST(id AS TEXT) AS id, nome_imovel, codigo_car,
                       CAST(area_ha AS float) AS area_ha, situacao_cadastral,
                       municipio_id, ST_AsText(geom) AS geom
                FROM imovel_rural WHERE CAST(id AS TEXT) = :iid
            """),
            {"iid": imovel_id},
        )
        return result.first()

    @staticmethod
    async def get_queimadas(session: AsyncSession, imovel_id: str) -> list[Row]:
        result = await session.execute(
            text("""
                SELECT CAST(q.id AS TEXT) AS id, q.data_ocorrencia, q.fonte_sensor,
                       CAST(q.intensidade AS float) AS intensidade,
                       r.distancia_m, r.dentro_imovel
                FROM rel_imovel_queimada r
                JOIN queimada_evento q ON q.id = r.queimada_evento_id
                WHERE CAST(r.imovel_rural_id AS TEXT) = :iid
                ORDER BY q.data_ocorrencia DESC
            """),
            {"iid": imovel_id},
        )
        return result.all()

    @staticmethod
    async def get_desmatamentos(session: AsyncSession, imovel_id: str) -> list[Row]:
        result = await session.execute(
            text("""
                SELECT CAST(d.id AS TEXT) AS id, d.tipo_alerta,
                       CAST(d.area_ha AS float) AS area_ha,
                       CAST(d.data_ocorrencia AS TEXT) AS data_ocorrencia,
                       CAST(r.area_intersecao_ha AS float) AS area_intersecao_ha,
                       CAST(r.percentual_sobreposicao AS float) AS percentual_sobreposicao
                FROM rel_imovel_desmatamento r
                JOIN desmatamento_alerta d ON d.id = r.desmatamento_alerta_id
                WHERE CAST(r.imovel_rural_id AS TEXT) = :iid
                ORDER BY d.data_ocorrencia DESC
            """),
            {"iid": imovel_id},
        )
        return result.all()

class QueimadaEvento(Base):
    __tablename__ = "queimada_evento"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    id_origem: Mapped[Optional[str]] = mapped_column(TEXT)
    dataset_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("dataset.id"))
    data_ocorrencia: Mapped[Optional[datetime]] = mapped_column(DateTime)
    fonte_sensor: Mapped[Optional[str]] = mapped_column(TEXT)
    intensidade: Mapped[Optional[float]] = mapped_column(Numeric)
    municipio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("municipio.id"))
    geom: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326))
    atributos_json: Mapped[Optional[dict]] = mapped_column(JSONB)

class DesmatamentoAlerta(Base):
    __tablename__ = "desmatamento_alerta"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    id_origem: Mapped[Optional[str]] = mapped_column(TEXT)
    dataset_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("dataset.id"))
    data_ocorrencia: Mapped[Optional[date]] = mapped_column(Date)
    tipo_alerta: Mapped[Optional[str]] = mapped_column(TEXT)
    area_ha: Mapped[Optional[float]] = mapped_column(Numeric)
    municipio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("municipio.id"))
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    atributos_json: Mapped[Optional[dict]] = mapped_column(JSONB)

# --- 4. ÁREAS PROTEGIDAS E ESPECIAIS ---

class UnidadeConservacao(Base):
    __tablename__ = "unidade_conservacao"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    id_origem: Mapped[Optional[str]] = mapped_column(TEXT)
    dataset_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("dataset.id"))
    nome: Mapped[Optional[str]] = mapped_column(TEXT)
    categoria: Mapped[Optional[str]] = mapped_column(TEXT)
    esfera: Mapped[Optional[str]] = mapped_column(TEXT)
    grupo_snuc: Mapped[Optional[str]] = mapped_column(TEXT)
    area_ha: Mapped[Optional[float]] = mapped_column(Numeric)
    municipio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("municipio.id"))
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    atributos_json: Mapped[Optional[dict]] = mapped_column(JSONB)

class TerraIndigena(Base):
    __tablename__ = "terra_indigena"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    id_origem: Mapped[Optional[str]] = mapped_column(TEXT)
    dataset_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("dataset.id"))
    nome: Mapped[Optional[str]] = mapped_column(TEXT)
    fase: Mapped[Optional[str]] = mapped_column(TEXT)
    area_ha: Mapped[Optional[float]] = mapped_column(Numeric)
    municipio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("municipio.id"))
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    atributos_json: Mapped[Optional[dict]] = mapped_column(JSONB)

class AssentamentoRural(Base):
    __tablename__ = "assentamento_rural"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    id_origem: Mapped[Optional[str]] = mapped_column(TEXT)
    dataset_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("dataset.id"))
    nome: Mapped[Optional[str]] = mapped_column(TEXT)
    area_ha: Mapped[Optional[float]] = mapped_column(Numeric)
    modalidade: Mapped[Optional[str]] = mapped_column(TEXT)
    familias: Mapped[Optional[int]] = mapped_column(Integer)
    municipio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("municipio.id"))
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    atributos_json: Mapped[Optional[dict]] = mapped_column(JSONB)

class TerritorioQuilombola(Base):
    __tablename__ = "territorio_quilombola"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    id_origem: Mapped[Optional[str]] = mapped_column(TEXT)
    dataset_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("dataset.id"))
    nome: Mapped[Optional[str]] = mapped_column(TEXT)
    area_ha: Mapped[Optional[float]] = mapped_column(Numeric)
    municipio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("municipio.id"))
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    atributos_json: Mapped[Optional[dict]] = mapped_column(JSONB)

class CamadaEstadualAmbiental(Base):
    __tablename__ = "camada_estadual_ambiental"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    id_origem: Mapped[Optional[str]] = mapped_column(TEXT)
    dataset_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("dataset.id"))
    nome: Mapped[Optional[str]] = mapped_column(TEXT)
    subtipo: Mapped[Optional[str]] = mapped_column(TEXT)
    tema: Mapped[Optional[str]] = mapped_column(TEXT)
    municipio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("municipio.id"))
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    atributos_json: Mapped[Optional[dict]] = mapped_column(JSONB)


# --- 5. RELACIONAMENTOS E CRUZAMENTOS ESPACIAIS ---

class RelImovelQueimada(Base):
    __tablename__ = "rel_imovel_queimada"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()")) #
    imovel_rural_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("imovel_rural.id")) #
    queimada_evento_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("queimada_evento.id")) #
    distancia_m: Mapped[Optional[float]] = mapped_column(Numeric) #
    dentro_imovel: Mapped[Optional[bool]] = mapped_column(Boolean) #
    data_calculo: Mapped[Optional[datetime]] = mapped_column(DateTime) #

class RelImovelDesmatamento(Base):
    __tablename__ = "rel_imovel_desmatamento"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()")) #
    imovel_rural_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("imovel_rural.id")) #
    desmatamento_alerta_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("desmatamento_alerta.id")) #
    area_intersecao_ha: Mapped[Optional[float]] = mapped_column(Numeric) #
    percentual_sobreposicao: Mapped[Optional[float]] = mapped_column(Numeric) #
    data_calculo: Mapped[Optional[datetime]] = mapped_column(DateTime) #

class RelImovelUC(Base):
    __tablename__ = "rel_imovel_uc"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()")) #
    imovel_rural_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("imovel_rural.id")) #
    unidade_conservacao_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("unidade_conservacao.id")) #
    area_intersecao_ha: Mapped[Optional[float]] = mapped_column(Numeric) #
    percentual_sobreposicao: Mapped[Optional[float]] = mapped_column(Numeric) #
    tipo_relacao: Mapped[Optional[str]] = mapped_column(TEXT) #

class RelImovelTI(Base):
    __tablename__ = "rel_imovel_ti"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()")) #
    imovel_rural_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("imovel_rural.id")) #
    terra_indigena_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("terra_indigena.id")) #
    area_intersecao_ha: Mapped[Optional[float]] = mapped_column(Numeric) #
    percentual_sobreposicao: Mapped[Optional[float]] = mapped_column(Numeric) #
    tipo_relacao: Mapped[Optional[str]] = mapped_column(TEXT) #

class RelImovelAssentamento(Base):
    __tablename__ = "rel_imovel_assentamento"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()")) #
    imovel_rural_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("imovel_rural.id")) #
    assentamento_rural_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("assentamento_rural.id")) #
    area_intersecao_ha: Mapped[Optional[float]] = mapped_column(Numeric) #
    percentual_sobreposicao: Mapped[Optional[float]] = mapped_column(Numeric) #
    tipo_relacao: Mapped[Optional[str]] = mapped_column(TEXT) #

class RelImovelQuilombo(Base):
    __tablename__ = "rel_imovel_quilombo"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()")) #
    imovel_rural_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("imovel_rural.id")) #
    territorio_quilombola_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("territorio_quilombola.id")) #
    area_intersecao_ha: Mapped[Optional[float]] = mapped_column(Numeric) #
    percentual_sobreposicao: Mapped[Optional[float]] = mapped_column(Numeric) #
    tipo_relacao: Mapped[Optional[str]] = mapped_column(TEXT) #

# --- 6. INTELIGÊNCIA ARTIFICIAL E CHAT (RAG) ---
class Conceito(Base):
    __tablename__ = "conceito"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    nome_canonico: Mapped[Optional[str]] = mapped_column(TEXT)
    tipo_conceito: Mapped[Optional[str]] = mapped_column(TEXT)

class ConceitoAlias(Base):
    __tablename__ = "conceito_alias"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    coceito_id: Mapped[UUID] = mapped_column(ForeignKey("conceito.id"))
    alias: Mapped[Optional[str]] = mapped_column(TEXT)

class Documento(Base):
    __tablename__ = "documento"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    dataset_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("dataset.id"))
    titulo: Mapped[Optional[str]] = mapped_column(TEXT)
    tipo: Mapped[Optional[str]] = mapped_column(TEXT)
    data_criacao: Mapped[Optional[datetime]] = mapped_column(DateTime)
    texto_integral: Mapped[Optional[str]] = mapped_column(TEXT)
    url_origem: Mapped[Optional[str]] = mapped_column(TEXT)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB)


class DocumentoTrecho(Base):
    __tablename__ = "documento_trecho"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    documento_id: Mapped[UUID] = mapped_column(ForeignKey("documento.id"))
    texto: Mapped[Optional[str]] = mapped_column(TEXT)
    ordem: Mapped[Optional[int]] = mapped_column(Integer)
    embedding: Mapped[Vector] = mapped_column(Vector(1536))
    tokens_count: Mapped[Optional[int]] = mapped_column(Integer)
    __table_args__ = (
        Index(
            "idx_trecho_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

class Chat(Base):
    __tablename__ = "chat"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    title: Mapped[Optional[str]] = mapped_column(TEXT)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

class IntencaoConsulta(Base): # Adicionado conforme melhorias
    __tablename__ = "intencao_consulta"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    nome: Mapped[Optional[str]] = mapped_column(TEXT)

class ConsultaUsuario(Base):
    __tablename__ = "consulta_usuario"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    pergunta: Mapped[Optional[str]] = mapped_column(TEXT)
    data_hora: Mapped[Optional[datetime]] = mapped_column(DateTime)
    intencao_detectada: Mapped[Optional[str]] = mapped_column(TEXT)
    entidades_detectadas_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    filtros_detectados_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    chat_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("chat.id"))
    intencao_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("intencao_consulta.id"))
    intencao_score: Mapped[Optional[float]] = mapped_column(Numeric)
    turno: Mapped[Optional[int]] = mapped_column(Integer)
    __table_args__ = (
        UniqueConstraint("chat_id", "turno", name="idx_consulta_chat_turno"),
    )

class RespostaSistema(Base):
    __tablename__ = "resposta_sistema"
    id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, primary_key=True, server_default=text("gen_random_uuid()"))
    consulta_usuario_id: Mapped[UUID] = mapped_column(ForeignKey("consulta_usuario.id"))
    texto_resposta: Mapped[Optional[str]] = mapped_column(TEXT)
    sql_executado: Mapped[Optional[str]] = mapped_column(TEXT)
    fontes_utilizadas_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    bbox_resultado: Mapped[Any] = mapped_column(Geometry("POLYGON", srid=4326))
    tempo_resposta_ms: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String, 
        server_default="sucesso",
        nullable=False
    )
    mensagem_erro: Mapped[Optional[str]] = mapped_column(String)
    __table_args__ = (
        CheckConstraint(status.in_(['sucesso', 'erro', 'fallback', 'sem_resultado']), name="check_status_resposta"),
    )

class FeedbackResposta(Base):
    __tablename__ = "feedback_resposta"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    resposta_sistema_id: Mapped[UUID] = mapped_column(ForeignKey("resposta_sistema.id"), index=True)
    avaliacao: Mapped[int] = mapped_column(SmallInteger)
    comentario: Mapped[Optional[str]] = mapped_column(String)
    data_hora: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (CheckConstraint(avaliacao.in_([-1, 0, 1]), name="check_avaliacao_valor"),)

class RelImovelBacia(Base):
    __tablename__ = "rel_imovel_bacia"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    imovel_rural_id: Mapped[UUID] = mapped_column(ForeignKey("imovel_rural.id"))
    bacia_hidrografica_id: Mapped[int] = mapped_column(ForeignKey("bacia_hidrografica.id"))
    area_intersecao_ha: Mapped[Optional[float]] = mapped_column(Numeric)
    percentual_sobreposicao: Mapped[Optional[float]] = mapped_column(Numeric)
    tipo_relacao: Mapped[Optional[str]] = mapped_column(String) # 'dentro', 'parcial', etc.