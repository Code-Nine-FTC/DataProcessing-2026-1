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
from sqlalchemy import Float
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
    CamadaEstadualAmbiental,
    Dataset,
    DesmatamentoAlerta,
    Documento,
    DocumentoTrecho,
    Estado,
    FonteDado,
    ImovelRural,
    Municipio,
    QueimadaEvento,
    RelImovelDesmatamento,
    RelImovelQueimada,
    RelImovelUC,
    RelImovelTI,
    RelImovelQuilombo,
    classificar_nivel_risco_ambiental,
    TerraIndigena,
    TerritorioQuilombola,
    UnidadeConservacao,
)

# ---------------------------------------------------------------------------
# Ferramenta: passivos ambientais dentro de um imóvel (por código CAR ou id)
# ---------------------------------------------------------------------------

async def buscar_passivos_em_imovel(
    session: AsyncSession,
    codigo_car: Optional[str] = None,
    imovel_id: Optional[str] = None,
) -> dict:
    """Retorna os passivos ambientais (queimadas, desmatamento, UCs, TIs, Quilombolas)
    relacionados a um imóvel identificado por `codigo_car` ou `imovel_id`.

    Retorno: resumo com contagens e lista de features para cada tipo.
    """
    if not codigo_car and not imovel_id:
        return {
            "total": 0,
            "descricao": "É necessário informar 'codigo_car' ou 'imovel_id'.",
            "detalhes": {},
            "features": [],
            "sql_executado": None,
        }

    # Localiza o imóvel
    stmt_imovel = select(
        ImovelRural.id,
        ImovelRural.codigo_car,
        ImovelRural.nome_imovel,
        _geom_as_geojson(ImovelRural.geom).label("geom_json"),
    )
    if codigo_car:
        stmt_imovel = stmt_imovel.where(ImovelRural.codigo_car == codigo_car)
    if imovel_id:
        stmt_imovel = stmt_imovel.where(ImovelRural.id == imovel_id)

    row = (await session.execute(stmt_imovel)).first()
    if not row:
        return {
            "total": 0,
            "descricao": "Imóvel não encontrado.",
            "detalhes": {},
            "features": [],
            "sql_executado": _stmt_sql(stmt_imovel),
        }

    imovel_db = row
    imovel_geom_json = imovel_db.geom_json

    detalhes: dict[str, Any] = {}
    features: list[dict] = []

    # Queimadas via rel_imovel_queimada
    stmt_q = (
        select(
            QueimadaEvento.id,
            QueimadaEvento.data_ocorrencia,
            QueimadaEvento.intensidade,
            _geom_as_geojson(QueimadaEvento.geom).label("geom_json"),
        )
        .join(RelImovelQueimada, RelImovelQueimada.queimada_evento_id == QueimadaEvento.id)
        .where(RelImovelQueimada.imovel_rural_id == imovel_db.id)
        .order_by(QueimadaEvento.data_ocorrencia.desc())
    )
    rows_q = (await session.execute(stmt_q)).all()
    detalhes["queimadas"] = {
        "total": len(rows_q),
        "items": [],
    }
    for r in rows_q:
        if not r.geom_json:
            continue
        detalhes["queimadas"]["items"].append({
            "id": str(r.id),
            "data_ocorrencia": str(r.data_ocorrencia) if r.data_ocorrencia else None,
            "intensidade": float(r.intensidade) if r.intensidade else None,
        })
        features.append({
            "type": "Feature",
            "geometry": json.loads(r.geom_json),
            "properties": {"tipo": "queimada", "imovel_id": str(imovel_db.id)},
        })

    # Desmatamento via rel_imovel_desmatamento
    stmt_d = (
        select(
            DesmatamentoAlerta.id,
            DesmatamentoAlerta.data_ocorrencia,
            DesmatamentoAlerta.area_ha,
            _geom_as_geojson(DesmatamentoAlerta.geom).label("geom_json"),
            RelImovelDesmatamento.area_intersecao_ha,
        )
        .join(RelImovelDesmatamento, RelImovelDesmatamento.desmatamento_alerta_id == DesmatamentoAlerta.id)
        .where(RelImovelDesmatamento.imovel_rural_id == imovel_db.id)
        .order_by(DesmatamentoAlerta.data_ocorrencia.desc())
    )
    try:
        rows_d = (await session.execute(stmt_d)).all()
    except Exception:
        rows_d = []

    detalhes["desmatamento"] = {"total": len(rows_d), "items": []}
    for r in rows_d:
        if not r.geom_json:
            continue
        detalhes["desmatamento"]["items"].append({
            "id": str(r.id),
            "data_ocorrencia": str(r.data_ocorrencia) if r.data_ocorrencia else None,
            "area_ha": float(r.area_ha) if r.area_ha else None,
            "area_intersecao_ha": float(r.area_intersecao_ha) if r.area_intersecao_ha else None,
        })
        features.append({
            "type": "Feature",
            "geometry": json.loads(r.geom_json),
            "properties": {"tipo": "desmatamento", "imovel_id": str(imovel_db.id)},
        })

    # Unidades de Conservacao via rel_imovel_uc if exists else ST_Intersects
    detalhes["unidades_conservacao"] = {"total": 0, "items": []}
    try:
        stmt_uc = (
            select(
                UnidadeConservacao.id,
                UnidadeConservacao.nome,
                UnidadeConservacao.categoria,
                _geom_as_geojson(UnidadeConservacao.geom).label("geom_json"),
            )
            .join(RelImovelUC, RelImovelUC.imovel_rural_id == imovel_db.id)
            .where(RelImovelUC.imovel_rural_id == imovel_db.id)
        )
        rows_uc = (await session.execute(stmt_uc)).all()
        for r in rows_uc:
            detalhes["unidades_conservacao"]["items"].append({
                "id": str(r.id),
                "nome": r.nome,
                "categoria": r.categoria,
            })
            if r.geom_json:
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(r.geom_json),
                    "properties": {"tipo": "unidade_conservacao", "imovel_id": str(imovel_db.id)},
                })
        detalhes["unidades_conservacao"]["total"] = len(rows_uc)
    except Exception:
        pass

    # Terras Indigenas via rel_imovel_ti
    detalhes["terras_indigenas"] = {"total": 0, "items": []}
    try:
        stmt_ti = (
            select(
                TerraIndigena.id,
                TerraIndigena.nome,
                _geom_as_geojson(TerraIndigena.geom).label("geom_json"),
            )
            .join(RelImovelTI, RelImovelTI.imovel_rural_id == imovel_db.id)
            .where(RelImovelTI.imovel_rural_id == imovel_db.id)
        )
        rows_ti = (await session.execute(stmt_ti)).all()
        for r in rows_ti:
            detalhes["terras_indigenas"]["items"].append({"id": str(r.id), "nome": r.nome})
            if r.geom_json:
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(r.geom_json),
                    "properties": {"tipo": "terra_indigena", "imovel_id": str(imovel_db.id)},
                })
        detalhes["terras_indigenas"]["total"] = len(rows_ti)
    except Exception:
        pass

    # Quilombolas via rel_imovel_quilombo
    detalhes["quilombolas"] = {"total": 0, "items": []}
    try:
        stmt_qm = (
            select(
                TerritorioQuilombola.id,
                TerritorioQuilombola.nome,
                _geom_as_geojson(TerritorioQuilombola.geom).label("geom_json"),
            )
            .join(RelImovelQuilombo, RelImovelQuilombo.imovel_rural_id == imovel_db.id)
            .where(RelImovelQuilombo.imovel_rural_id == imovel_db.id)
        )
        rows_qm = (await session.execute(stmt_qm)).all()
        for r in rows_qm:
            detalhes["quilombolas"]["items"].append({"id": str(r.id), "nome": r.nome})
            if r.geom_json:
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(r.geom_json),
                    "properties": {"tipo": "quilombo", "imovel_id": str(imovel_db.id)},
                })
        detalhes["quilombolas"]["total"] = len(rows_qm)
    except Exception:
        pass

    descricao = (
        f"Passivos encontrados para o imóvel {imovel_db.nome_imovel or imovel_db.codigo_car}: "
        f"{detalhes['queimadas']['total']} queimadas, {detalhes['desmatamento']['total']} desmatamentos, "
        f"{detalhes['unidades_conservacao']['total']} UCs, {detalhes['terras_indigenas']['total']} TIs, "
        f"{detalhes['quilombolas']['total']} quilombolas."
    )

    return {
        "total": sum([
            detalhes["queimadas"]["total"],
            detalhes["desmatamento"]["total"],
            detalhes["unidades_conservacao"]["total"],
            detalhes["terras_indigenas"]["total"],
            detalhes["quilombolas"]["total"],
        ]),
        "descricao": descricao,
        "detalhes": detalhes,
        "features": features,
        "sql_executado": None,
    }


# ---------------------------------------------------------------------------
# Ferramenta: focos de queimada em um imóvel por período
# ---------------------------------------------------------------------------

async def buscar_focos_queimada_imovel(
    session: AsyncSession,
    codigo_car: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    limite: int = 500,
) -> dict:
    if not codigo_car:
        return {
            "total": 0,
            "descricao": "É necessário informar o código CAR do imóvel.",
            "features": [],
            "bbox": None,
            "fontes": [],
            "sql_executado": None,
        }

    stmt = (
        select(
            QueimadaEvento.id,
            QueimadaEvento.data_ocorrencia,
            QueimadaEvento.intensidade,
            _geom_as_geojson(QueimadaEvento.geom).label("geom_json"),
            ImovelRural.id.label("imovel_id"),
            ImovelRural.codigo_car,
            RelImovelQueimada.distancia_m,
            RelImovelQueimada.dentro_imovel,
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(RelImovelQueimada, RelImovelQueimada.queimada_evento_id == QueimadaEvento.id)
        .join(ImovelRural, ImovelRural.id == RelImovelQueimada.imovel_rural_id)
        .join(Dataset, QueimadaEvento.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .where(ImovelRural.codigo_car == codigo_car)
    )

    if data_inicio:
        stmt = stmt.where(QueimadaEvento.data_ocorrencia >= datetime.fromisoformat(data_inicio))
    if data_fim:
        stmt = stmt.where(QueimadaEvento.data_ocorrencia <= datetime.fromisoformat(data_fim))

    stmt = stmt.order_by(QueimadaEvento.data_ocorrencia.desc()).limit(limite)
    sql_executado = _stmt_sql(stmt)

    rows = (await session.execute(stmt)).all()

    features: list[dict] = []
    fontes: dict[str, dict] = {}
    distancias: list[float] = []
    riscos: list[str] = []
    for row in rows:
        if not row.geom_json:
            continue
        distancia = float(row.distancia_m) if row.distancia_m is not None else None
        risco = classificar_nivel_risco_ambiental(
            distancia,
            bool(row.dentro_imovel),
        )
        if distancia is not None:
            distancias.append(distancia)
        riscos.append(risco)
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "queimada",
                "data_ocorrencia": str(row.data_ocorrencia) if row.data_ocorrencia else None,
                "intensidade": float(row.intensidade) if row.intensidade else None,
                "codigo_car": row.codigo_car,
                "distancia_m": distancia,
                "dentro_imovel": bool(row.dentro_imovel) if row.dentro_imovel is not None else None,
                "nivel_risco_ambiental": risco,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": row.url_origem,
            }

    risco_prioridade = {
        "muito alto": 4,
        "alto": 3,
        "médio": 2,
        "baixo": 1,
        "muito baixo": 0,
        "não classificado": -1,
    }
    menor_distancia = min(distancias) if distancias else None
    risco_predominante = max(riscos, key=lambda item: risco_prioridade.get(item, -1)) if riscos else "não classificado"

    descricao = (
        f"Encontrados {len(features)} focos de queimada no imóvel {codigo_car}."
    )
    if menor_distancia is not None:
        descricao += f" Menor distância observada: {menor_distancia:.1f} m."
    descricao += f" Nível de risco ambiental: {risco_predominante}."

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": descricao,
        "sql_executado": sql_executado,
    }

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
    distance_expr = DocumentoTrecho.embedding.op("<->", return_type=Float())(
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
# Ferramentas: imóveis relacionados via relações espaciais
# ---------------------------------------------------------------------------


async def buscar_imoveis_por_queimada(
    session: AsyncSession,
    municipio: Optional[str] = None,
    limite: int = 500,
) -> dict:
    """Busca imóveis rurais relacionados a queimadas (via rel_imovel_queimada)."""
    sql_partes: list[str] = []
    stmt = (
        select(
            ImovelRural.id,
            ImovelRural.codigo_car,
            ImovelRural.nome_imovel,
            ImovelRural.area_ha,
            Municipio.nome.label("municipio_nome"),
            _geom_as_geojson(ImovelRural.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            func.count(RelImovelQueimada.id).label("num_queimadas"),
            func.avg(RelImovelQueimada.distancia_m).label("dist_media_m"),
            func.min(RelImovelQueimada.distancia_m).label("dist_min_m"),
        )
        .join(RelImovelQueimada, ImovelRural.id == RelImovelQueimada.imovel_rural_id)
        .join(Municipio, ImovelRural.municipio_id == Municipio.id, isouter=True)
        .join(Estado, Municipio.estado_id == Estado.id, isouter=True)
        .join(Dataset, ImovelRural.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .where(Estado.sigla == "SP")
        .group_by(
            ImovelRural.id,
            ImovelRural.codigo_car,
            ImovelRural.nome_imovel,
            ImovelRural.area_ha,
            Municipio.nome,
            ImovelRural.geom,
            FonteDado.nome,
            FonteDado.orgao_responsavel,
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
                "descricao": f"Encontrados 0 imóveis relacionados a queimadas em {municipio}.",
                "sql_executado": municipio_sql,
            }
        stmt = stmt.where(Municipio.id == municipio_id)
        sql_partes.append(municipio_sql)

    stmt = stmt.order_by(func.count(RelImovelQueimada.id).desc()).limit(limite)
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
                "tipo": "imovel_rural_queimada",
                "codigo_car": str(row.codigo_car) if row.codigo_car else None,
                "nome_imovel": row.nome_imovel,
                "area_ha": float(row.area_ha) if row.area_ha else None,
                "municipio": row.municipio_nome,
                "num_queimadas": int(row.num_queimadas) if row.num_queimadas else 0,
                "dist_media_m": float(row.dist_media_m) if row.dist_media_m else None,
                "dist_min_m": float(row.dist_min_m) if row.dist_min_m else None,
                "nivel_risco_ambiental": classificar_nivel_risco_ambiental(row.dist_min_m),
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": None,
            }

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": f"Encontrados {len(features)} imóveis rurais relacionados a queimadas"
        + (f" em {municipio}" if municipio else " no estado de SP")
        + ".",
        "sql_executado": sql_executado,
    }


async def buscar_imoveis_por_terra_indigena(
    session: AsyncSession,
    municipio: Optional[str] = None,
    limite: int = 500,
) -> dict:
    """Busca imóveis rurais que sobrepõem terras indígenas."""
    sql_partes: list[str] = []
    stmt = (
        select(
            ImovelRural.id,
            ImovelRural.codigo_car,
            ImovelRural.nome_imovel,
            ImovelRural.area_ha,
            Municipio.nome.label("municipio_nome"),
            TerraIndigena.nome.label("ti_nome"),
            RelImovelTI.area_intersecao_ha,
            RelImovelTI.percentual_sobreposicao,
            _geom_as_geojson(ImovelRural.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
        )
        .join(RelImovelTI, ImovelRural.id == RelImovelTI.imovel_rural_id)
        .join(TerraIndigena, RelImovelTI.terra_indigena_id == TerraIndigena.id)
        .join(Municipio, ImovelRural.municipio_id == Municipio.id, isouter=True)
        .join(Estado, Municipio.estado_id == Estado.id, isouter=True)
        .join(Dataset, ImovelRural.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
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
                "descricao": f"Encontrados 0 imóveis em TI em {municipio}.",
                "sql_executado": municipio_sql,
            }
        stmt = stmt.where(Municipio.id == municipio_id)
        sql_partes.append(municipio_sql)

    stmt = stmt.order_by(RelImovelTI.percentual_sobreposicao.desc()).limit(limite)
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
                "tipo": "imovel_rural_ti",
                "codigo_car": str(row.codigo_car) if row.codigo_car else None,
                "nome_imovel": row.nome_imovel,
                "area_ha": float(row.area_ha) if row.area_ha else None,
                "municipio": row.municipio_nome,
                "terra_indigena": row.ti_nome,
                "area_intersecao_ha": float(row.area_intersecao_ha) if row.area_intersecao_ha else 0,
                "percentual_sobreposicao": float(row.percentual_sobreposicao) if row.percentual_sobreposicao else 0,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": None,
            }

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": f"Encontrados {len(features)} imóveis rurais em Terras Indígenas"
        + (f" em {municipio}" if municipio else " no estado de SP")
        + ".",
        "sql_executado": sql_executado,
    }


async def buscar_imoveis_por_quilombo(
    session: AsyncSession,
    municipio: Optional[str] = None,
    limite: int = 500,
) -> dict:
    """Busca imóveis rurais que sobrepõem territórios quilombolas."""
    sql_partes: list[str] = []
    stmt = (
        select(
            ImovelRural.id,
            ImovelRural.codigo_car,
            ImovelRural.nome_imovel,
            ImovelRural.area_ha,
            Municipio.nome.label("municipio_nome"),
            TerritorioQuilombola.nome.label("quilombo_nome"),
            RelImovelQuilombo.area_intersecao_ha,
            RelImovelQuilombo.percentual_sobreposicao,
            _geom_as_geojson(ImovelRural.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
        )
        .join(RelImovelQuilombo, ImovelRural.id == RelImovelQuilombo.imovel_rural_id)
        .join(TerritorioQuilombola, RelImovelQuilombo.territorio_quilombola_id == TerritorioQuilombola.id)
        .join(Municipio, ImovelRural.municipio_id == Municipio.id, isouter=True)
        .join(Estado, Municipio.estado_id == Estado.id, isouter=True)
        .join(Dataset, ImovelRural.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
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
                "descricao": f"Encontrados 0 imóveis em quilombos em {municipio}.",
                "sql_executado": municipio_sql,
            }
        stmt = stmt.where(Municipio.id == municipio_id)
        sql_partes.append(municipio_sql)

    stmt = stmt.order_by(RelImovelQuilombo.percentual_sobreposicao.desc()).limit(limite)
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
                "tipo": "imovel_rural_quilombo",
                "codigo_car": str(row.codigo_car) if row.codigo_car else None,
                "nome_imovel": row.nome_imovel,
                "area_ha": float(row.area_ha) if row.area_ha else None,
                "municipio": row.municipio_nome,
                "territorio_quilombola": row.quilombo_nome,
                "area_intersecao_ha": float(row.area_intersecao_ha) if row.area_intersecao_ha else 0,
                "percentual_sobreposicao": float(row.percentual_sobreposicao) if row.percentual_sobreposicao else 0,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": None,
            }

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": f"Encontrados {len(features)} imóveis rurais em Territórios Quilombolas"
        + (f" em {municipio}" if municipio else " no estado de SP")
        + ".",
        "sql_executado": sql_executado,
    }


# ---------------------------------------------------------------------------
# Ferramenta: camadas estaduais ambientais (DataGeo SP)
# ---------------------------------------------------------------------------

async def buscar_camadas_estaduais(
    session: AsyncSession,
    municipio: Optional[str] = None,
    tema: Optional[str] = None,
    limite: int = 200,
) -> dict:
    """Busca camadas estaduais ambientais (DataGeo SP) no estado de São Paulo."""
    sql_partes: list[str] = []
    stmt = (
        select(
            CamadaEstadualAmbiental.id,
            CamadaEstadualAmbiental.nome,
            CamadaEstadualAmbiental.tema,
            CamadaEstadualAmbiental.subtipo,
            Municipio.nome.label("municipio_nome"),
            _geom_as_geojson(CamadaEstadualAmbiental.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, CamadaEstadualAmbiental.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, CamadaEstadualAmbiental.municipio_id == Municipio.id, isouter=True)
        .where(
            func.ST_Intersects(
                CamadaEstadualAmbiental.geom,
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
                "descricao": f"Encontradas 0 camadas estaduais ambientais em {municipio}.",
                "sql_executado": municipio_sql,
            }
        _mun_geom = (
            select(Municipio.geom)
            .where(Municipio.id == municipio_id)
            .scalar_subquery()
        )
        stmt = stmt.where(func.ST_Intersects(CamadaEstadualAmbiental.geom, _mun_geom))
        sql_partes.append(municipio_sql)

    if tema:
        stmt = stmt.where(func.lower(CamadaEstadualAmbiental.tema).contains(tema.lower()))

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
                "tipo": "camada_estadual_ambiental",
                "nome": row.nome,
                "tema": row.tema,
                "subtipo": row.subtipo,
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
        "descricao": f"Encontradas {len(features)} camadas estaduais ambientais"
        + (f" em {municipio}" if municipio else " no estado de SP")
        + ("" if not tema else f" com tema '{tema}'")
        + ".",
        "sql_executado": sql_executado,
    }


# ---------------------------------------------------------------------------
# Ferramenta: imoveis rurais com camadas estaduais ambientais
# ---------------------------------------------------------------------------

async def buscar_imoveis_com_camadas_estaduais(
    session: AsyncSession,
    municipio: Optional[str] = None,
    tema: Optional[str] = None,
    limite: int = 100,
) -> dict:
    """Busca imóveis rurais que intersectam camadas estaduais ambientais."""
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
            CamadaEstadualAmbiental.nome.label("camada_nome"),
            CamadaEstadualAmbiental.tema,
            CamadaEstadualAmbiental.subtipo,
            func.ST_Area(
                func.ST_Intersection(ImovelRural.geom, CamadaEstadualAmbiental.geom)
            ) / 10000.0,  # convertendo para hectares
        )
        .join(Dataset, ImovelRural.dataset_id == Dataset.id, isouter=True)
        .join(Municipio, ImovelRural.municipio_id == Municipio.id, isouter=True)
        .join(
            CamadaEstadualAmbiental,
            func.ST_Intersects(ImovelRural.geom, CamadaEstadualAmbiental.geom),
            isouter=True,
        )
        .where(
            func.ST_Intersects(
                ImovelRural.geom,
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
                "descricao": f"Encontrados 0 imóveis rurais com camadas ambientais em {municipio}.",
                "sql_executado": municipio_sql,
            }
        stmt = stmt.where(Municipio.id == municipio_id)
        sql_partes.append(municipio_sql)

    if tema:
        stmt = stmt.where(func.lower(CamadaEstadualAmbiental.tema).contains(tema.lower()))

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
                "tipo": "imovel_com_camada_ambiental",
                "nome_imovel": row.nome_imovel,
                "codigo_car": row.codigo_car,
                "area_ha": float(row.area_ha) if row.area_ha else None,
                "situacao_cadastral": row.situacao_cadastral,
                "municipio": row.municipio_nome,
                "camada_nome": row.camada_nome,
                "camada_tema": row.tema,
                "camada_subtipo": row.subtipo,
                "area_intersecao_ha": float(row[10]) if row[10] else 0,  # area from ST_Area
            },
        })

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": f"Encontrados {len(features)} imóveis rurais em camadas estaduais ambientais"
        + (f" em {municipio}" if municipio else " no estado de SP")
        + ("" if not tema else f" com tema '{tema}'")
        + ".",
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
    "buscar_imoveis_por_queimada": buscar_imoveis_por_queimada,
    "buscar_imoveis_por_terra_indigena": buscar_imoveis_por_terra_indigena,
    "buscar_imoveis_por_quilombo": buscar_imoveis_por_quilombo,
    "buscar_camadas_estaduais": buscar_camadas_estaduais,
    "buscar_imoveis_com_camadas_estaduais": buscar_imoveis_com_camadas_estaduais,
    "buscar_passivos_em_imovel": buscar_passivos_em_imovel,
    "buscar_focos_queimada_imovel": buscar_focos_queimada_imovel,
}
