# -*- coding: utf-8 -*-
"""
Ferramentas de consulta ao banco de dados para o agente NLP.
Cada função representa uma capabilidade do agente e retorna
features GeoJSON + metadados de fontes.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Integer, Text, and_, cast, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from nlp_processor.pipeline.preprocessor import normalizar

logger = logging.getLogger(__name__)


def _stmt_sql(stmt: Any) -> str:
    try:
        compiled = stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
        return str(compiled)
    except Exception:
        return str(stmt)


def _join_sql(*parts: Optional[str]) -> Optional[str]:
    sql_parts = [part for part in parts if part]
    if not sql_parts:
        return None
    return "\n\n".join(sql_parts)
from models.db_model import (
    AssentamentoRural,
    Dataset,
    DesmatamentoAlerta,
    Documento,
    DocumentoTrecho,
    Estado,
    FonteDado,
    ImovelRural,
    Municipio,
    QueimadaEvento,
    TerraIndigena,
    TerritorioQuilombola,
    UnidadeConservacao,
)

# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _geom_as_geojson(geom_col: Any) -> Any:
    """Converte coluna de geometria para texto GeoJSON via PostGIS."""
    return cast(func.ST_AsGeoJSON(func.ST_Transform(geom_col, 4326)), Text)


def _source_dict(fonte: FonteDado) -> dict:
    return {
        "nome": fonte.nome,
        "orgao": fonte.orgao_responsavel,
        "url": fonte.url_origem,
        "periodicidade": fonte.periodicidade,
    }


async def _get_municipio_id(session: AsyncSession, municipio: str) -> tuple[Optional[int], str]:
    municipio_normalizado = normalizar(municipio)
    logger.info(f"Procurando município: '{municipio}' -> normalizado: '{municipio_normalizado}'")

    # Busca apenas pelos municípios já carregados no banco e normaliza em Python,
    # para não depender de colunas que podem não existir em bases antigas.
    municipios = select(Municipio.id, Municipio.nome).where(Municipio.nome.is_not(None))
    sql_executado = _stmt_sql(municipios)
    result = await session.execute(municipios)
    rows = result.all()

    logger.info(f"Total de municípios no banco: {len(rows)}")

    for row_id, nome in rows:
        nome_norm = normalizar(nome)
        if nome_norm == municipio_normalizado:
            logger.info(f"Encontrado via fallback! ID: {row_id}, nome original: '{nome}'")
            return row_id, sql_executado

    logger.warning(f"Nenhum município encontrado para '{municipio}'")
    return None, sql_executado


def _build_bbox(features: list[dict]) -> Optional[list[float]]:
    """Calcula [minx, miny, maxx, maxy] a partir das features GeoJSON."""
    coords: list[tuple[float, float]] = []

    def _extract(geom: dict) -> None:
        t = geom.get("type", "")
        c = geom.get("coordinates")
        if c is None:
            return
        if t == "Point":
            coords.append((c[0], c[1]))
        elif t in ("LineString", "MultiPoint"):
            coords.extend((p[0], p[1]) for p in c)
        elif t in ("Polygon", "MultiLineString"):
            for ring in c:
                coords.extend((p[0], p[1]) for p in ring)
        elif t == "MultiPolygon":
            for poly in c:
                for ring in poly:
                    coords.extend((p[0], p[1]) for p in ring)
        elif t == "GeometryCollection":
            for g in geom.get("geometries", []):
                _extract(g)

    for f in features:
        if f.get("geometry"):
            _extract(f["geometry"])

    if not coords:
        return None
    xs, ys = zip(*coords)
    return [min(xs), min(ys), max(xs), max(ys)]


# ---------------------------------------------------------------------------
# Ferramenta: queimadas
# ---------------------------------------------------------------------------

async def buscar_queimadas(
    session: AsyncSession,
    municipio: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    limite: int = 500,
) -> dict:
    """Busca focos de queimada no estado de São Paulo."""
    sql_partes: list[str] = []
    stmt = (
        select(
            QueimadaEvento.id,
            QueimadaEvento.data_ocorrencia,
            QueimadaEvento.fonte_sensor,
            QueimadaEvento.intensidade,
            QueimadaEvento.bioma,
            QueimadaEvento.dias_sem_chuva,
            QueimadaEvento.precipitacao_mm,
            QueimadaEvento.risco_fogo,
            Municipio.nome.label("municipio_nome"),
            _geom_as_geojson(QueimadaEvento.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, QueimadaEvento.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, QueimadaEvento.municipio_id == Municipio.id, isouter=True)
        .join(Estado, Municipio.estado_id == Estado.id, isouter=True)
        .where(Estado.sigla == "SP")
    )

    if municipio:
        municipio_id, municipio_sql = await _get_municipio_id(session, municipio)
        if municipio_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 focos de queimada em {municipio}.",
                "sql_executado": municipio_sql,
            }
        stmt = stmt.where(Municipio.id == municipio_id)
        sql_partes.append(municipio_sql)
    if data_inicio:
        stmt = stmt.where(QueimadaEvento.data_ocorrencia >= datetime.fromisoformat(data_inicio))
    if data_fim:
        stmt = stmt.where(QueimadaEvento.data_ocorrencia <= datetime.fromisoformat(data_fim))

    stmt = stmt.order_by(QueimadaEvento.data_ocorrencia.desc()).limit(limite)
    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))

    rows = (await session.execute(stmt)).all()

    features = []
    fontes: dict[str, dict] = {}
    for row in rows:
        if not row.geom_json:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "queimada",
                "data_ocorrencia": str(row.data_ocorrencia) if row.data_ocorrencia else None,
                "fonte_sensor": row.fonte_sensor,
                "intensidade": float(row.intensidade) if row.intensidade else None,
                "municipio": row.municipio_nome,
                "bioma": row.bioma,
                "dias_sem_chuva": float(row.dias_sem_chuva) if row.dias_sem_chuva is not None else None,
                "precipitacao_mm": float(row.precipitacao_mm) if row.precipitacao_mm is not None else None,
                "risco_fogo": float(row.risco_fogo) if row.risco_fogo is not None else None,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": row.url_origem,
            }

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": f"Encontrados {len(features)} focos de queimada"
        + (f" em {municipio}" if municipio else " no estado de SP")
        + ".",
        "sql_executado": sql_executado,
    }


# ---------------------------------------------------------------------------
# Ferramenta: desmatamento
# ---------------------------------------------------------------------------

async def buscar_desmatamentos(
    session: AsyncSession,
    municipio: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    tipo_alerta: Optional[str] = None,
    limite: int = 300,
) -> dict:
    """Busca alertas de desmatamento no estado de São Paulo."""
    sql_partes: list[str] = []
    stmt = (
        select(
            DesmatamentoAlerta.id,
            DesmatamentoAlerta.data_ocorrencia,
            DesmatamentoAlerta.tipo_alerta,
            DesmatamentoAlerta.area_ha,
            Municipio.nome.label("municipio_nome"),
            _geom_as_geojson(DesmatamentoAlerta.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, DesmatamentoAlerta.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, DesmatamentoAlerta.municipio_id == Municipio.id, isouter=True)
        .join(Estado, Municipio.estado_id == Estado.id, isouter=True)
        .where(Estado.sigla == "SP")
    )

    if municipio:
        municipio_id, municipio_sql = await _get_municipio_id(session, municipio)
        if municipio_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 alertas de desmatamento em {municipio}.",
                "sql_executado": municipio_sql,
            }
        stmt = stmt.where(Municipio.id == municipio_id)
        sql_partes.append(municipio_sql)
    if data_inicio:
        stmt = stmt.where(DesmatamentoAlerta.data_ocorrencia >= date.fromisoformat(data_inicio))
    if data_fim:
        stmt = stmt.where(DesmatamentoAlerta.data_ocorrencia <= date.fromisoformat(data_fim))
    if tipo_alerta:
        stmt = stmt.where(func.lower(DesmatamentoAlerta.tipo_alerta) == tipo_alerta.lower())

    stmt = stmt.order_by(DesmatamentoAlerta.data_ocorrencia.desc()).limit(limite)
    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))

    rows = (await session.execute(stmt)).all()

    features = []
    fontes: dict[str, dict] = {}
    for row in rows:
        if not row.geom_json:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "desmatamento",
                "data_ocorrencia": str(row.data_ocorrencia) if row.data_ocorrencia else None,
                "tipo_alerta": row.tipo_alerta,
                "area_ha": float(row.area_ha) if row.area_ha else None,
                "municipio": row.municipio_nome,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": row.url_origem,
            }

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": f"Encontrados {len(features)} alertas de desmatamento"
        + (f" em {municipio}" if municipio else " no estado de SP")
        + ".",
        "sql_executado": sql_executado,
    }


# ---------------------------------------------------------------------------
# Ferramenta: unidades de conservação
# ---------------------------------------------------------------------------

async def buscar_unidades_conservacao(
    session: AsyncSession,
    municipio: Optional[str] = None,
    categoria: Optional[str] = None,
    grupo_snuc: Optional[str] = None,
) -> dict:
    """Busca unidades de conservação no estado de São Paulo."""
    sql_partes: list[str] = []
    stmt = (
        select(
            UnidadeConservacao.id,
            UnidadeConservacao.nome,
            UnidadeConservacao.categoria,
            UnidadeConservacao.esfera,
            UnidadeConservacao.grupo_snuc,
            UnidadeConservacao.area_ha,
            Municipio.nome.label("municipio_nome"),
            _geom_as_geojson(UnidadeConservacao.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, UnidadeConservacao.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, UnidadeConservacao.municipio_id == Municipio.id, isouter=True)
        .where(
            func.ST_Intersects(
                UnidadeConservacao.geom,
                select(Estado.geom).where(Estado.sigla == "SP").scalar_subquery(),
            )
        )
    )

    if municipio:
        municipio_id, municipio_sql = await _get_municipio_id(session, municipio)
        if municipio_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontradas 0 unidades de conservação em {municipio}.",
                "sql_executado": municipio_sql,
            }
        _mun_geom = (
            select(Municipio.geom)
            .where(Municipio.id == municipio_id)
            .scalar_subquery()
        )
        stmt = stmt.where(func.ST_Intersects(UnidadeConservacao.geom, _mun_geom))
        sql_partes.append(municipio_sql)
    if categoria:
        stmt = stmt.where(func.lower(UnidadeConservacao.categoria).contains(categoria.lower()))
    if grupo_snuc:
        stmt = stmt.where(func.lower(UnidadeConservacao.grupo_snuc) == grupo_snuc.lower())

    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))

    rows = (await session.execute(stmt)).all()

    features = []
    fontes: dict[str, dict] = {}
    for row in rows:
        if not row.geom_json:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "unidade_conservacao",
                "nome": row.nome,
                "categoria": row.categoria,
                "esfera": row.esfera,
                "grupo_snuc": row.grupo_snuc,
                "area_ha": float(row.area_ha) if row.area_ha else None,
                "municipio": row.municipio_nome,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": row.url_origem,
            }

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": f"Encontradas {len(features)} unidades de conservação"
        + (f" em {municipio}" if municipio else " no estado de SP")
        + ".",
        "sql_executado": sql_executado,
    }


# ---------------------------------------------------------------------------
# Ferramenta: terras indígenas
# ---------------------------------------------------------------------------

async def buscar_terras_indigenas(
    session: AsyncSession,
    municipio: Optional[str] = None,
    fase: Optional[str] = None,
) -> dict:
    """Busca terras indígenas no estado de São Paulo."""
    sql_partes: list[str] = []
    stmt = (
        select(
            TerraIndigena.id,
            TerraIndigena.nome,
            TerraIndigena.fase,
            TerraIndigena.area_ha,
            Municipio.nome.label("municipio_nome"),
            _geom_as_geojson(TerraIndigena.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, TerraIndigena.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, TerraIndigena.municipio_id == Municipio.id, isouter=True)
        .where(
            func.ST_Intersects(
                TerraIndigena.geom,
                select(Estado.geom).where(Estado.sigla == "SP").scalar_subquery(),
            )
        )
    )

    if municipio:
        municipio_id, municipio_sql = await _get_municipio_id(session, municipio)
        if municipio_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontradas 0 terras indígenas em {municipio}.",
                "sql_executado": municipio_sql,
            }
        _mun_geom = (
            select(Municipio.geom)
            .where(Municipio.id == municipio_id)
            .scalar_subquery()
        )
        stmt = stmt.where(func.ST_Intersects(TerraIndigena.geom, _mun_geom))
        sql_partes.append(municipio_sql)
    if fase:
        stmt = stmt.where(func.lower(TerraIndigena.fase).contains(fase.lower()))

    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))

    rows = (await session.execute(stmt)).all()

    features = []
    fontes: dict[str, dict] = {}
    for row in rows:
        if not row.geom_json:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "terra_indigena",
                "nome": row.nome,
                "fase": row.fase,
                "area_ha": float(row.area_ha) if row.area_ha else None,
                "municipio": row.municipio_nome,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": row.url_origem,
            }

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": f"Encontradas {len(features)} terras indígenas"
        + (f" em {municipio}" if municipio else " no estado de SP")
        + ".",
        "sql_executado": sql_executado,
    }


# ---------------------------------------------------------------------------
# Ferramenta: assentamentos rurais
# ---------------------------------------------------------------------------

async def buscar_assentamentos(
    session: AsyncSession,
    municipio: Optional[str] = None,
    modalidade: Optional[str] = None,
) -> dict:
    """Busca assentamentos rurais do INCRA no estado de São Paulo."""
    sql_partes: list[str] = []
    stmt = (
        select(
            AssentamentoRural.id,
            AssentamentoRural.nome,
            AssentamentoRural.area_ha,
            AssentamentoRural.modalidade,
            AssentamentoRural.familias,
            Municipio.nome.label("municipio_nome"),
            _geom_as_geojson(AssentamentoRural.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, AssentamentoRural.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, AssentamentoRural.municipio_id == Municipio.id, isouter=True)
        .where(
            func.ST_Intersects(
                AssentamentoRural.geom,
                select(Estado.geom).where(Estado.sigla == "SP").scalar_subquery(),
            )
        )
    )

    if municipio:
        municipio_id, municipio_sql = await _get_municipio_id(session, municipio)
        if municipio_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 assentamentos rurais em {municipio}.",
                "sql_executado": municipio_sql,
            }
        _mun_geom = (
            select(Municipio.geom)
            .where(Municipio.id == municipio_id)
            .scalar_subquery()
        )
        stmt = stmt.where(func.ST_Intersects(AssentamentoRural.geom, _mun_geom))
        sql_partes.append(municipio_sql)
    if modalidade:
        stmt = stmt.where(func.lower(AssentamentoRural.modalidade).contains(modalidade.lower()))

    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))

    rows = (await session.execute(stmt)).all()

    features = []
    fontes: dict[str, dict] = {}
    for row in rows:
        if not row.geom_json:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "assentamento_rural",
                "nome": row.nome,
                "area_ha": float(row.area_ha) if row.area_ha else None,
                "modalidade": row.modalidade,
                "familias": row.familias,
                "municipio": row.municipio_nome,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": row.url_origem,
            }

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": f"Encontrados {len(features)} assentamentos rurais"
        + (f" em {municipio}" if municipio else " no estado de SP")
        + ".",
        "sql_executado": sql_executado,
    }


# ---------------------------------------------------------------------------
# Ferramenta: territórios quilombolas
# ---------------------------------------------------------------------------

async def buscar_territorios_quilombolas(
    session: AsyncSession,
    municipio: Optional[str] = None,
) -> dict:
    """Busca territórios quilombolas no estado de São Paulo."""
    sql_partes: list[str] = []
    stmt = (
        select(
            TerritorioQuilombola.id,
            TerritorioQuilombola.nome,
            TerritorioQuilombola.area_ha,
            Municipio.nome.label("municipio_nome"),
            _geom_as_geojson(TerritorioQuilombola.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, TerritorioQuilombola.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, TerritorioQuilombola.municipio_id == Municipio.id, isouter=True)
        .where(
            func.ST_Intersects(
                TerritorioQuilombola.geom,
                select(Estado.geom).where(Estado.sigla == "SP").scalar_subquery(),
            )
        )
    )

    if municipio:
        municipio_id, municipio_sql = await _get_municipio_id(session, municipio)
        if municipio_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 territórios quilombolas em {municipio}.",
                "sql_executado": municipio_sql,
            }
        _mun_geom = (
            select(Municipio.geom)
            .where(Municipio.id == municipio_id)
            .scalar_subquery()
        )
        stmt = stmt.where(func.ST_Intersects(TerritorioQuilombola.geom, _mun_geom))
        sql_partes.append(municipio_sql)

    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))

    rows = (await session.execute(stmt)).all()

    features = []
    fontes: dict[str, dict] = {}
    for row in rows:
        if not row.geom_json:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "territorio_quilombola",
                "nome": row.nome,
                "area_ha": float(row.area_ha) if row.area_ha else None,
                "municipio": row.municipio_nome,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": row.url_origem,
            }

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": f"Encontrados {len(features)} territórios quilombolas"
        + (f" em {municipio}" if municipio else " no estado de SP")
        + ".",
        "sql_executado": sql_executado,
    }


# ---------------------------------------------------------------------------
# Ferramenta: imóveis rurais (CAR)
# ---------------------------------------------------------------------------

async def buscar_imoveis_rurais(
    session: AsyncSession,
    codigo_car: Optional[str] = None,
    municipio: Optional[str] = None,
    limite: int = 100,
) -> dict:
    """Busca imóveis rurais (CAR) no estado de São Paulo."""
    sql_partes: list[str] = []
    stmt = (
        select(
            ImovelRural.id,
            ImovelRural.nome_imovel,
            ImovelRural.codigo_car,
            ImovelRural.area_ha,
            ImovelRural.situacao_cadastral,
            Municipio.nome.label("municipio_nome"),
            _geom_as_geojson(ImovelRural.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, ImovelRural.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, ImovelRural.municipio_id == Municipio.id, isouter=True)
        .where(
            func.ST_Intersects(
                ImovelRural.geom,
                select(Estado.geom).where(Estado.sigla == "SP").scalar_subquery(),
            )
        )
    )

    if codigo_car:
        stmt = stmt.where(ImovelRural.codigo_car == codigo_car)
    if municipio:
        municipio_id, municipio_sql = await _get_municipio_id(session, municipio)
        if municipio_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 imóveis rurais em {municipio}.",
                "sql_executado": municipio_sql,
            }
        _mun_geom = (
            select(Municipio.geom)
            .where(Municipio.id == municipio_id)
            .scalar_subquery()
        )
        stmt = stmt.where(func.ST_Intersects(ImovelRural.geom, _mun_geom))
        sql_partes.append(municipio_sql)

    stmt = stmt.limit(limite)
    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))
    rows = (await session.execute(stmt)).all()

    features = []
    fontes: dict[str, dict] = {}
    for row in rows:
        if not row.geom_json:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "imovel_rural",
                "nome_imovel": row.nome_imovel,
                "codigo_car": row.codigo_car,
                "area_ha": float(row.area_ha) if row.area_ha else None,
                "situacao_cadastral": row.situacao_cadastral,
                "municipio": row.municipio_nome,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": row.url_origem,
            }

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": f"Encontrados {len(features)} imóveis rurais"
        + (f" em {municipio}" if municipio else " no estado de SP")
        + ".",
        "sql_executado": sql_executado,
    }


# ---------------------------------------------------------------------------
# Ferramenta: busca semântica (RAG) em documentos
# ---------------------------------------------------------------------------

async def buscar_documentos_rag(
    session: AsyncSession,
    query_embedding: list[float],
    limite: int = 5,
) -> dict:
    """Busca trechos de documentos relevantes via similaridade vetorial (RAG)."""
    from pgvector.sqlalchemy import Vector

    # Cosine distance search usando pgvector
    distance_expr = DocumentoTrecho.embedding.op("<->")(
        cast(query_embedding, Vector(768))
    )

    stmt = (
        select(
            DocumentoTrecho.id,
            DocumentoTrecho.texto,
            DocumentoTrecho.ordem,
            Documento.titulo,
            Documento.tipo,
            Documento.url_origem,
            distance_expr.label("distancia"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
        )
        .join(Documento, DocumentoTrecho.documento_id == Documento.id)
        .join(Dataset, Documento.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .order_by(distance_expr)
        .limit(limite)
    )

    sql_executado = _stmt_sql(stmt)

    rows = (await session.execute(stmt)).all()

    trechos = []
    fontes: dict[str, dict] = {}
    for row in rows:
        trechos.append({
            "titulo": row.titulo,
            "tipo": row.tipo,
            "url": row.url_origem,
            "texto": row.texto,
            "relevancia": round(1 - float(row.distancia), 4) if row.distancia is not None else None,
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": row.url_origem,
            }

    contexto = "\n\n---\n\n".join(
        f"[{t['titulo']}]: {t['texto']}" for t in trechos
    )

    return {
        "trechos": trechos,
        "contexto_textual": contexto,
        "fontes": list(fontes.values()),
        "descricao": f"Encontrados {len(trechos)} trechos de documentos relevantes.",
        "sql_executado": sql_executado,
    }


# ---------------------------------------------------------------------------
# Registro: nome da ferramenta → função Python
# ---------------------------------------------------------------------------

TOOL_FUNCTIONS = {
    "buscar_queimadas": buscar_queimadas,
    "buscar_desmatamentos": buscar_desmatamentos,
    "buscar_unidades_conservacao": buscar_unidades_conservacao,
    "buscar_terras_indigenas": buscar_terras_indigenas,
    "buscar_assentamentos": buscar_assentamentos,
    "buscar_territorios_quilombolas": buscar_territorios_quilombolas,
    "buscar_imoveis_rurais": buscar_imoveis_rurais,
}
