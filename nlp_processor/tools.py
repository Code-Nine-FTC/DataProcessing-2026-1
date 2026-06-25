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
from api.services.score_ambiental_service import ScoreAmbientalService
from nlp_processor.pipeline.preprocessor import normalizar

logger = logging.getLogger(__name__)

COMPLEX_POLYGON_TOLERANCE = 0.0002


def _round_float(value: Any, ndigits: int = 4) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), ndigits)
    except (ValueError, TypeError):
        return None


def _fmt_int(value: int) -> str:
    """Formata inteiro no padrão brasileiro (ex: 1.234)."""
    return f"{value:,}".replace(",", ".")


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


async def _score_ambiental_properties(
    session: AsyncSession,
    imovel_id: Any,
    cache: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Campos de score ASG para anexar ao GeoJSON do chat."""
    if not imovel_id:
        return {}

    key = str(imovel_id)
    if cache is not None and key in cache:
        return cache[key]

    try:
        score = await ScoreAmbientalService(session).score_imovel_detalhe(key)
    except Exception as exc:
        logger.warning("Não foi possível calcular score ambiental do imóvel %s: %s", key, exc)
        props: dict[str, Any] = {}
    else:
        props = {
            "score_ambiental": score.score_ambiental,
            "score_social": score.score_social,
            "score_governanca": score.score_governanca,
            "score_geral": score.score_geral,
            "classificacao": score.classificacao,
        }

    if cache is not None:
        cache[key] = props
    return props
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
    RegiaoAdministrativa,
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
    stmt_imovel = (
        select(
            ImovelRural.id,
            ImovelRural.codigo_car,
            ImovelRural.nome_imovel,
            ImovelRural.area_ha,
            ImovelRural.situacao_cadastral,
            Municipio.nome.label("municipio_nome"),
            _geom_as_geojson(ImovelRural.geom).label("geom_json"),
        )
        .join(Municipio, ImovelRural.municipio_id == Municipio.id, isouter=True)
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
    imovel_feature: Optional[dict] = None

    # Inclui o polígono do próprio imóvel no mapa, para servir de contexto
    # visual aos passivos sobrepostos/contidos.
    if imovel_geom_json:
        score_props = await _score_ambiental_properties(session, imovel_db.id)
        imovel_feature = {
            "type": "Feature",
            "geometry": json.loads(imovel_geom_json),
            "properties": {
                "tipo": "imovel_rural",
                "codigo_car": imovel_db.codigo_car,
                "nome_imovel": imovel_db.nome_imovel,
                "area_ha": _round_float(imovel_db.area_ha, 4),
                "municipio": imovel_db.municipio_nome,
                "situacao_cadastral": imovel_db.situacao_cadastral,
                "imovel_id": str(imovel_db.id),
                **score_props,
            },
        }
        features.append(imovel_feature)

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
            "intensidade": _round_float(r.intensidade, 2),
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
            "area_ha": _round_float(r.area_ha, 4),
            "area_intersecao_ha": _round_float(r.area_intersecao_ha, 4),
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
                RelImovelUC.area_intersecao_ha,
                RelImovelUC.percentual_sobreposicao,
                _geom_as_geojson(UnidadeConservacao.geom, COMPLEX_POLYGON_TOLERANCE).label("geom_json"),
            )
            .join(RelImovelUC, RelImovelUC.unidade_conservacao_id == UnidadeConservacao.id)
            .where(RelImovelUC.imovel_rural_id == imovel_db.id)
        )
        rows_uc = (await session.execute(stmt_uc)).all()
        for r in rows_uc:
            area_int = _round_float(r.area_intersecao_ha, 4)
            pct_sob = _round_float(r.percentual_sobreposicao, 2)
            detalhes["unidades_conservacao"]["items"].append({
                "id": str(r.id),
                "nome": r.nome,
                "categoria": r.categoria,
                "area_intersecao_ha": area_int,
                "percentual_sobreposicao": pct_sob,
            })
            if r.geom_json:
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(r.geom_json),
                    "properties": {
                        "tipo": "unidade_conservacao",
                        "nome": r.nome,
                        "categoria": r.categoria,
                        "area_intersecao_ha": area_int,
                        "percentual_sobreposicao": pct_sob,
                        "imovel_id": str(imovel_db.id),
                    },
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
                RelImovelTI.area_intersecao_ha,
                RelImovelTI.percentual_sobreposicao,
                _geom_as_geojson(TerraIndigena.geom, COMPLEX_POLYGON_TOLERANCE).label("geom_json"),
            )
            .join(RelImovelTI, RelImovelTI.terra_indigena_id == TerraIndigena.id)
            .where(RelImovelTI.imovel_rural_id == imovel_db.id)
        )
        rows_ti = (await session.execute(stmt_ti)).all()
        for r in rows_ti:
            area_int = _round_float(r.area_intersecao_ha, 4)
            pct_sob = _round_float(r.percentual_sobreposicao, 2)
            detalhes["terras_indigenas"]["items"].append({
                "id": str(r.id),
                "nome": r.nome,
                "area_intersecao_ha": area_int,
                "percentual_sobreposicao": pct_sob,
            })
            if r.geom_json:
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(r.geom_json),
                    "properties": {
                        "tipo": "terra_indigena",
                        "nome": r.nome,
                        "area_intersecao_ha": area_int,
                        "percentual_sobreposicao": pct_sob,
                        "imovel_id": str(imovel_db.id),
                    },
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
                RelImovelQuilombo.area_intersecao_ha,
                RelImovelQuilombo.percentual_sobreposicao,
                _geom_as_geojson(TerritorioQuilombola.geom, COMPLEX_POLYGON_TOLERANCE).label("geom_json"),
            )
            .join(RelImovelQuilombo, RelImovelQuilombo.territorio_quilombola_id == TerritorioQuilombola.id)
            .where(RelImovelQuilombo.imovel_rural_id == imovel_db.id)
        )
        rows_qm = (await session.execute(stmt_qm)).all()
        for r in rows_qm:
            area_int = _round_float(r.area_intersecao_ha, 4)
            pct_sob = _round_float(r.percentual_sobreposicao, 2)
            detalhes["quilombolas"]["items"].append({
                "id": str(r.id),
                "nome": r.nome,
                "area_intersecao_ha": area_int,
                "percentual_sobreposicao": pct_sob,
            })
            if r.geom_json:
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(r.geom_json),
                    "properties": {
                        "tipo": "quilombo",
                        "nome": r.nome,
                        "area_intersecao_ha": area_int,
                        "percentual_sobreposicao": pct_sob,
                        "imovel_id": str(imovel_db.id),
                    },
                })
        detalhes["quilombolas"]["total"] = len(rows_qm)
    except Exception:
        pass

    area_val = _round_float(imovel_db.area_ha, 2)
    area_str = (
        f"{area_val:,.2f} ha".replace(",", "X").replace(".", ",").replace("X", ".")
        if area_val
        else "área não informada"
    )
    cabecalho = (
        f"**Imóvel** {imovel_db.nome_imovel or imovel_db.codigo_car} "
        f"(`{imovel_db.codigo_car}`)"
    )
    if imovel_db.municipio_nome:
        cabecalho += f" — município de **{imovel_db.municipio_nome}**"
    cabecalho += f" — área: **{area_str}**."

    descricao = (
        f"{cabecalho}\n\n"
        f"**Passivos identificados:** "
        f"{_fmt_int(detalhes['queimadas']['total'])} queimadas, "
        f"{_fmt_int(detalhes['desmatamento']['total'])} desmatamentos, "
        f"{_fmt_int(detalhes['unidades_conservacao']['total'])} UCs, "
        f"{_fmt_int(detalhes['terras_indigenas']['total'])} TIs, "
        f"{_fmt_int(detalhes['quilombolas']['total'])} quilombolas."
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
        "bbox": _build_bbox([imovel_feature] if imovel_feature else features),
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

    stmt_imovel = (
        select(
            ImovelRural.id,
            ImovelRural.nome_imovel,
            ImovelRural.codigo_car,
            ImovelRural.area_ha,
            ImovelRural.situacao_cadastral,
            Municipio.nome.label("municipio_nome"),
            _geom_as_geojson(ImovelRural.geom).label("geom_json"),
        )
        .join(Municipio, ImovelRural.municipio_id == Municipio.id, isouter=True)
        .where(ImovelRural.codigo_car == codigo_car)
    )
    imovel = (await session.execute(stmt_imovel)).first()
    if not imovel:
        return {
            "total": 0,
            "descricao": f"Imóvel com código CAR {codigo_car} não encontrado.",
            "features": [],
            "bbox": None,
            "fontes": [],
            "sql_executado": _stmt_sql(stmt_imovel),
        }

    stmt = (
        select(
            QueimadaEvento.id,
            QueimadaEvento.data_ocorrencia,
            QueimadaEvento.intensidade,
            _geom_as_geojson(QueimadaEvento.geom).label("geom_json"),
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
        .where(RelImovelQueimada.imovel_rural_id == imovel.id)
    )

    if data_inicio:
        stmt = stmt.where(QueimadaEvento.data_ocorrencia >= datetime.fromisoformat(data_inicio))
    if data_fim:
        stmt = stmt.where(QueimadaEvento.data_ocorrencia <= datetime.fromisoformat(data_fim))

    stmt = stmt.order_by(QueimadaEvento.data_ocorrencia.desc()).limit(limite)
    sql_executado = _stmt_sql(stmt)

    rows = (await session.execute(stmt)).all()

    features: list[dict] = []
    imovel_feature: Optional[dict] = None
    if imovel.geom_json:
        score_props = await _score_ambiental_properties(session, imovel.id)
        imovel_feature = {
            "type": "Feature",
            "geometry": json.loads(imovel.geom_json),
            "properties": {
                "tipo": "imovel_rural",
                "codigo_car": imovel.codigo_car,
                "nome_imovel": imovel.nome_imovel,
                "area_ha": _round_float(imovel.area_ha, 4),
                "situacao_cadastral": imovel.situacao_cadastral,
                "municipio": imovel.municipio_nome,
                "imovel_id": str(imovel.id),
                **score_props,
            },
        }
        features.append(imovel_feature)
    fontes: dict[str, dict] = {}
    distancias: list[float] = []
    riscos: list[str] = []
    for row in rows:
        if not row.geom_json:
            continue
        distancia = _round_float(row.distancia_m, 2)
        risco = classificar_nivel_risco_ambiental(
            distancia,
            bool(row.dentro_imovel) if row.dentro_imovel is not None else None,
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
                "intensidade": _round_float(row.intensidade, 2),
                "codigo_car": imovel.codigo_car,
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
        f"Encontrados {_fmt_int(len(rows))} focos de queimada no imóvel {codigo_car}."
    )
    if menor_distancia is not None:
        descricao += f" Menor distância observada: {menor_distancia:.2f} m.".replace(".", ",")
    descricao += f" Nível de risco ambiental: {risco_predominante}."

    return {
        "total": len(rows),
        "features": features,
        "bbox": _build_bbox([imovel_feature] if imovel_feature else features),
        "fontes": list(fontes.values()),
        "descricao": descricao,
        "sql_executado": sql_executado,
    }

# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _geom_as_geojson(geom_col: Any, simplify_tolerance: Optional[float] = None) -> Any:
    """Converte coluna de geometria para texto GeoJSON via PostGIS."""
    geom = func.ST_Transform(geom_col, 4326)
    if simplify_tolerance is not None:
        geom = func.ST_SimplifyPreserveTopology(geom, simplify_tolerance)
    return cast(func.ST_AsGeoJSON(geom, 6), Text)


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


async def _get_regiao_administrativa_id(
    session: AsyncSession, ra_nome: str
) -> tuple[Optional[int], str]:
    """Resolve nome de Região Administrativa para id.

    Aceita o nome canônico (ex.: "RA de Campinas"), a forma normalizada
    ou a sigla (RACAM). Tenta primeiro `nome` exato, depois
    `nome_normalizado`, depois `sigla`.
    """
    ra_norm = normalizar(ra_nome)
    stmt = select(
        RegiaoAdministrativa.id,
        RegiaoAdministrativa.nome,
        RegiaoAdministrativa.nome_normalizado,
        RegiaoAdministrativa.sigla,
    )
    sql_executado = _stmt_sql(stmt)
    rows = (await session.execute(stmt)).all()

    for row_id, nome, nome_norm, sigla in rows:
        if nome == ra_nome:
            return row_id, sql_executado
        if nome_norm and nome_norm == ra_norm:
            return row_id, sql_executado
        if nome and normalizar(nome) == ra_norm:
            return row_id, sql_executado
        if sigla and normalizar(sigla) == ra_norm:
            return row_id, sql_executado

    logger.warning(f"Nenhuma RA encontrada para '{ra_nome}'")
    return None, sql_executado


def _escopo_textual(
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
) -> str:
    """Texto do escopo para as descrições retornadas pelas tools."""
    if municipio:
        return f" em {municipio}"
    if regiao_administrativa:
        return f" na {regiao_administrativa}"
    return " no estado de SP"


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
    regiao_administrativa: Optional[str] = None,
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
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 focos de queimada na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        sql_partes.append(ra_sql)
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
                "intensidade": _round_float(row.intensidade, 2),
                "municipio": row.municipio_nome,
                "bioma": row.bioma,
                "dias_sem_chuva": _round_float(row.dias_sem_chuva, 1),
                "precipitacao_mm": _round_float(row.precipitacao_mm, 1),
                "risco_fogo": _round_float(row.risco_fogo, 2),
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
        "descricao": f"Encontrados {_fmt_int(len(features))} focos de queimada"
        + _escopo_textual(municipio, regiao_administrativa)
        + ".",
        "sql_executado": sql_executado,
    }


async def buscar_desmatamentos(
    session: AsyncSession,
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
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
        .where(
            func.ST_Intersects(
                DesmatamentoAlerta.geom,
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
                "descricao": f"Encontrados 0 alertas de desmatamento em {municipio}.",
                "sql_executado": municipio_sql,
            }
        _mun_geom = (
            select(Municipio.geom)
            .where(Municipio.id == municipio_id)
            .scalar_subquery()
        )
        stmt = stmt.where(func.ST_Intersects(DesmatamentoAlerta.geom, _mun_geom))
        sql_partes.append(municipio_sql)
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 alertas de desmatamento na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        sql_partes.append(ra_sql)
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
                "area_ha": _round_float(row.area_ha, 4),
                "municipio": row.municipio_nome or municipio,
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
        "descricao": f"Encontrados {_fmt_int(len(features))} alertas de desmatamento"
        + _escopo_textual(municipio, regiao_administrativa)
        + ".",
        "sql_executado": sql_executado,
    }


async def buscar_unidades_conservacao(
    session: AsyncSession,
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
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
            _geom_as_geojson(UnidadeConservacao.geom, COMPLEX_POLYGON_TOLERANCE).label("geom_json"),
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
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontradas 0 unidades de conservação na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        sql_partes.append(ra_sql)
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
                "area_ha": _round_float(row.area_ha, 4),
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
        "descricao": f"Encontradas {_fmt_int(len(features))} unidades de conservação"
        + _escopo_textual(municipio, regiao_administrativa)
        + ".",
        "sql_executado": sql_executado,
    }


async def buscar_terras_indigenas(
    session: AsyncSession,
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
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
            _geom_as_geojson(TerraIndigena.geom, COMPLEX_POLYGON_TOLERANCE).label("geom_json"),
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
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontradas 0 terras indígenas na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        sql_partes.append(ra_sql)
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
                "area_ha": _round_float(row.area_ha, 4),
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
        "descricao": f"Encontradas {_fmt_int(len(features))} terras indígenas"
        + _escopo_textual(municipio, regiao_administrativa)
        + ".",
        "sql_executado": sql_executado,
    }


async def buscar_assentamentos(
    session: AsyncSession,
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
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
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 assentamentos rurais na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        sql_partes.append(ra_sql)
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
                "area_ha": _round_float(row.area_ha, 4),
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
        "descricao": f"Encontrados {_fmt_int(len(features))} assentamentos rurais"
        + _escopo_textual(municipio, regiao_administrativa)
        + ".",
        "sql_executado": sql_executado,
    }


async def buscar_territorios_quilombolas(
    session: AsyncSession,
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
) -> dict:
    """Busca territórios quilombolas no estado de São Paulo."""
    sql_partes: list[str] = []
    stmt = (
        select(
            TerritorioQuilombola.id,
            TerritorioQuilombola.nome,
            TerritorioQuilombola.area_ha,
            Municipio.nome.label("municipio_nome"),
            _geom_as_geojson(TerritorioQuilombola.geom, COMPLEX_POLYGON_TOLERANCE).label("geom_json"),
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
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 territórios quilombolas na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        sql_partes.append(ra_sql)

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
                "area_ha": _round_float(row.area_ha, 4),
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
        "descricao": f"Encontrados {_fmt_int(len(features))} territórios quilombolas"
        + _escopo_textual(municipio, regiao_administrativa)
        + ".",
        "sql_executado": sql_executado,
    }


async def buscar_imoveis_rurais(
    session: AsyncSession,
    codigo_car: Optional[str] = None,
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
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
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 imóveis rurais na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        sql_partes.append(ra_sql)

    stmt = stmt.limit(limite)
    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))
    rows = (await session.execute(stmt)).all()

    if codigo_car and not rows:
        return {
            "total": 0,
            "features": [],
            "bbox": None,
            "fontes": [],
            "descricao": (
                f"Imóvel rural com código CAR {codigo_car} não encontrado "
                "na base SICAR/CAR carregada."
            ),
            "sql_executado": sql_executado,
        }

    features = []
    fontes: dict[str, dict] = {}
    score_cache: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row.geom_json:
            continue
        score_props = await _score_ambiental_properties(session, row.id, score_cache)
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "imovel_rural",
                "nome_imovel": row.nome_imovel,
                "codigo_car": row.codigo_car,
                "area_ha": _round_float(row.area_ha, 4),
                "situacao_cadastral": row.situacao_cadastral,
                "municipio": row.municipio_nome,
                "imovel_id": str(row.id),
                **score_props,
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
        "descricao": f"Encontrados {_fmt_int(len(features))} imóveis rurais"
        + _escopo_textual(municipio, regiao_administrativa)
        + ".",
        "sql_executado": sql_executado,
    }


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
            "relevancia": _round_float(1 - float(row.distancia), 4) if row.distancia is not None else None,
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
        "descricao": f"Encontrados {_fmt_int(len(trechos))} trechos de documentos relevantes.",
        "sql_executado": sql_executado,
    }


# ---------------------------------------------------------------------------
# Ferramentas: imóveis relacionados via relações espaciais
# ---------------------------------------------------------------------------


async def buscar_imoveis_por_queimada(
    session: AsyncSession,
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
    limite: int = 500,
) -> dict:
    """Busca imóveis rurais relacionados a queimadas (via rel_imovel_queimada)."""
    sql_partes: list[str] = []
    municipio_id: Optional[int] = None
    ra_id: Optional[int] = None
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
        .where(RelImovelQueimada.dentro_imovel.is_(True))
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
                "descricao": f"Encontrados 0 imóveis com focos de queimada dentro da propriedade em {municipio}.",
                "sql_executado": municipio_sql,
            }
        stmt = stmt.where(Municipio.id == municipio_id)
        # Restringe rels a queimadas que também ocorreram neste município —
        # rel_imovel_queimada é construída por proximidade e pode ligar imóveis
        # a focos de municípios vizinhos.
        stmt = stmt.where(
            RelImovelQueimada.queimada_evento_id.in_(
                select(QueimadaEvento.id).where(QueimadaEvento.municipio_id == municipio_id)
            )
        )
        sql_partes.append(municipio_sql)
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 imóveis com focos de queimada dentro da propriedade na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        # Restringe queimadas a focos cujo município também pertence à RA.
        stmt = stmt.where(
            RelImovelQueimada.queimada_evento_id.in_(
                select(QueimadaEvento.id)
                .join(Municipio, QueimadaEvento.municipio_id == Municipio.id)
                .where(Municipio.regiao_administrativa_id == ra_id)
            )
        )
        sql_partes.append(ra_sql)

    stmt = stmt.order_by(func.count(RelImovelQueimada.id).desc()).limit(limite)
    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))

    rows = (await session.execute(stmt)).all()

    features = []
    fontes: dict[str, dict] = {}
    score_cache: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row.geom_json:
            continue
        score_props = await _score_ambiental_properties(session, row.id, score_cache)
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "imovel_rural_queimada",
                "codigo_car": str(row.codigo_car) if row.codigo_car else None,
                "nome_imovel": row.nome_imovel,
                "area_ha": _round_float(row.area_ha, 4),
                "municipio": row.municipio_nome,
                "imovel_id": str(row.id),
                "num_queimadas": int(row.num_queimadas) if row.num_queimadas else 0,
                "dist_media_m": _round_float(row.dist_media_m, 2),
                "dist_min_m": _round_float(row.dist_min_m, 2),
                "nivel_risco_ambiental": classificar_nivel_risco_ambiental(row.dist_min_m),
                **score_props,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": None,
            }

    total_imoveis = len(features)

    # Features adicionais: focos de queimada relacionados aos imóveis acima.
    # Mesmo filtro `dentro_imovel = True` para que o mapa só exiba focos que
    # efetivamente caíram dentro de algum imóvel (não focos só próximos).
    rel_subq = (
        select(RelImovelQueimada.queimada_evento_id)
        .join(ImovelRural, ImovelRural.id == RelImovelQueimada.imovel_rural_id)
        .join(Municipio, ImovelRural.municipio_id == Municipio.id, isouter=True)
        .join(Estado, Municipio.estado_id == Estado.id, isouter=True)
        .where(Estado.sigla == "SP")
        .where(RelImovelQueimada.dentro_imovel.is_(True))
    )
    if municipio_id is not None:
        rel_subq = rel_subq.where(Municipio.id == municipio_id)
    elif ra_id is not None:
        rel_subq = rel_subq.where(Municipio.regiao_administrativa_id == ra_id)

    queimadas_stmt = (
        select(
            QueimadaEvento.id,
            QueimadaEvento.data_ocorrencia,
            QueimadaEvento.fonte_sensor,
            QueimadaEvento.intensidade,
            QueimadaEvento.risco_fogo,
            _geom_as_geojson(QueimadaEvento.geom).label("geom_json"),
        )
        .where(QueimadaEvento.id.in_(rel_subq))
        .order_by(QueimadaEvento.data_ocorrencia.desc().nullslast())
        .limit(2000)
    )
    if municipio_id is not None:
        queimadas_stmt = queimadas_stmt.where(QueimadaEvento.municipio_id == municipio_id)
    elif ra_id is not None:
        queimadas_stmt = queimadas_stmt.where(
            QueimadaEvento.municipio_id.in_(
                select(Municipio.id).where(Municipio.regiao_administrativa_id == ra_id)
            )
        )
    queimadas_rows = (await session.execute(queimadas_stmt)).all()
    total_queimadas = 0
    for q in queimadas_rows:
        if not q.geom_json:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(q.geom_json),
            "properties": {
                "tipo": "queimada_evento_relacionada",
                "data_ocorrencia": q.data_ocorrencia.isoformat() if q.data_ocorrencia else None,
                "sensor": q.fonte_sensor,
                "intensidade": _round_float(q.intensidade, 2),
                "risco_fogo": _round_float(q.risco_fogo, 2),
            },
        })
        total_queimadas += 1

    if municipio:
        escopo_txt = f"no município de **{municipio}**"
    elif regiao_administrativa:
        escopo_txt = f"na **{regiao_administrativa}**"
    else:
        escopo_txt = "no estado de **São Paulo**"
    return {
        "total": total_imoveis,
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": (
            f"Foram encontrados **{_fmt_int(total_imoveis)} imóveis rurais** com "
            f"**{_fmt_int(total_queimadas)} focos de queimada dentro da propriedade** {escopo_txt}. "
            "O mapa exibe os imóveis (polígonos) e os focos contidos neles (pontos)."
        ),
        "sql_executado": sql_executado,
    }


async def buscar_imoveis_por_desmatamento(
    session: AsyncSession,
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
    limite: int = 500,
) -> dict:
    """Busca imóveis rurais relacionados a alertas de desmatamento (via rel_imovel_desmatamento)."""
    sql_partes: list[str] = []
    municipio_id: Optional[int] = None
    ra_id: Optional[int] = None
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
            func.count(RelImovelDesmatamento.id).label("num_alertas_desmatamento"),
            func.sum(RelImovelDesmatamento.area_intersecao_ha).label("area_total_intersecao_ha"),
            func.avg(RelImovelDesmatamento.percentual_sobreposicao).label("percentual_medio_sobreposicao"),
            func.max(RelImovelDesmatamento.percentual_sobreposicao).label("percentual_max_sobreposicao"),
        )
        .join(RelImovelDesmatamento, ImovelRural.id == RelImovelDesmatamento.imovel_rural_id)
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
                "descricao": f"Encontrados 0 imóveis relacionados a desmatamento em {municipio}.",
                "sql_executado": municipio_sql,
            }
        stmt = stmt.where(Municipio.id == municipio_id)
        # Restringe rels a alertas que também ocorreram neste município.
        stmt = stmt.where(
            RelImovelDesmatamento.desmatamento_alerta_id.in_(
                select(DesmatamentoAlerta.id).where(DesmatamentoAlerta.municipio_id == municipio_id)
            )
        )
        sql_partes.append(municipio_sql)
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 imóveis relacionados a desmatamento na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        stmt = stmt.where(
            RelImovelDesmatamento.desmatamento_alerta_id.in_(
                select(DesmatamentoAlerta.id)
                .join(Municipio, DesmatamentoAlerta.municipio_id == Municipio.id)
                .where(Municipio.regiao_administrativa_id == ra_id)
            )
        )
        sql_partes.append(ra_sql)

    stmt = stmt.order_by(func.count(RelImovelDesmatamento.id).desc()).limit(limite)
    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))

    rows = (await session.execute(stmt)).all()

    features = []
    fontes: dict[str, dict] = {}
    score_cache: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row.geom_json:
            continue
        score_props = await _score_ambiental_properties(session, row.id, score_cache)
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "imovel_rural_desmatamento",
                "codigo_car": str(row.codigo_car) if row.codigo_car else None,
                "nome_imovel": row.nome_imovel,
                "area_ha": _round_float(row.area_ha, 4),
                "municipio": row.municipio_nome,
                "imovel_id": str(row.id),
                "num_alertas_desmatamento": int(row.num_alertas_desmatamento) if row.num_alertas_desmatamento else 0,
                "area_total_intersecao_ha": _round_float(row.area_total_intersecao_ha, 4),
                "percentual_medio_sobreposicao": _round_float(row.percentual_medio_sobreposicao, 2),
                "percentual_max_sobreposicao": _round_float(row.percentual_max_sobreposicao, 2),
                **score_props,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": None,
            }

    total_imoveis = len(features)

    # Features adicionais: alertas de desmatamento relacionados aos imóveis acima.
    rel_subq = (
        select(RelImovelDesmatamento.desmatamento_alerta_id)
        .join(ImovelRural, ImovelRural.id == RelImovelDesmatamento.imovel_rural_id)
        .join(Municipio, ImovelRural.municipio_id == Municipio.id, isouter=True)
        .join(Estado, Municipio.estado_id == Estado.id, isouter=True)
        .where(Estado.sigla == "SP")
    )
    if municipio_id is not None:
        rel_subq = rel_subq.where(Municipio.id == municipio_id)
    elif ra_id is not None:
        rel_subq = rel_subq.where(Municipio.regiao_administrativa_id == ra_id)

    alertas_stmt = (
        select(
            DesmatamentoAlerta.id,
            DesmatamentoAlerta.data_ocorrencia,
            DesmatamentoAlerta.tipo_alerta,
            DesmatamentoAlerta.area_ha,
            _geom_as_geojson(DesmatamentoAlerta.geom).label("geom_json"),
        )
        .where(DesmatamentoAlerta.id.in_(rel_subq))
        .order_by(DesmatamentoAlerta.data_ocorrencia.desc().nullslast())
        .limit(2000)
    )
    if municipio_id is not None:
        alertas_stmt = alertas_stmt.where(DesmatamentoAlerta.municipio_id == municipio_id)
    elif ra_id is not None:
        alertas_stmt = alertas_stmt.where(
            DesmatamentoAlerta.municipio_id.in_(
                select(Municipio.id).where(Municipio.regiao_administrativa_id == ra_id)
            )
        )
    alertas_rows = (await session.execute(alertas_stmt)).all()
    total_alertas = 0
    for a in alertas_rows:
        if not a.geom_json:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(a.geom_json),
            "properties": {
                "tipo": "desmatamento_alerta_relacionado",
                "data_ocorrencia": a.data_ocorrencia.isoformat() if a.data_ocorrencia else None,
                "tipo_alerta": a.tipo_alerta,
                "area_ha": _round_float(a.area_ha, 4),
            },
        })
        total_alertas += 1

    if municipio:
        escopo_txt = f"no município de **{municipio}**"
    elif regiao_administrativa:
        escopo_txt = f"na **{regiao_administrativa}**"
    else:
        escopo_txt = "no estado de **São Paulo**"
    return {
        "total": total_imoveis,
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": (
            f"Foram encontrados **{_fmt_int(total_imoveis)} imóveis rurais** afetados por "
            f"**{_fmt_int(total_alertas)} alertas de desmatamento** {escopo_txt}. "
            "O mapa exibe os imóveis e os polígonos dos alertas relacionados."
        ),
        "sql_executado": sql_executado,
    }


async def buscar_imoveis_por_terra_indigena(
    session: AsyncSession,
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
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
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 imóveis em TI na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        sql_partes.append(ra_sql)

    stmt = stmt.order_by(RelImovelTI.percentual_sobreposicao.desc()).limit(limite)
    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))

    rows = (await session.execute(stmt)).all()

    features = []
    fontes: dict[str, dict] = {}
    score_cache: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row.geom_json:
            continue
        score_props = await _score_ambiental_properties(session, row.id, score_cache)
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "imovel_rural_ti",
                "codigo_car": str(row.codigo_car) if row.codigo_car else None,
                "nome_imovel": row.nome_imovel,
                "area_ha": _round_float(row.area_ha, 4),
                "municipio": row.municipio_nome,
                "imovel_id": str(row.id),
                "terra_indigena": row.ti_nome,
                "area_intersecao_ha": _round_float(row.area_intersecao_ha, 4) or 0,
                "percentual_sobreposicao": _round_float(row.percentual_sobreposicao, 2) or 0,
                **score_props,
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
        "descricao": f"Encontrados {_fmt_int(len(features))} imóveis rurais em Terras Indígenas"
        + _escopo_textual(municipio, regiao_administrativa)
        + ".",
        "sql_executado": sql_executado,
    }


async def buscar_imoveis_por_quilombo(
    session: AsyncSession,
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
    limite: int = 500,
) -> dict:
    """Busca imóveis rurais que sobrepõem territórios quilombolas."""
    sql_partes: list[str] = []
    municipio_id: Optional[int] = None
    ra_id: Optional[int] = None
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
        # Restringe rels a territórios quilombolas que também estão neste município.
        stmt = stmt.where(
            RelImovelQuilombo.territorio_quilombola_id.in_(
                select(TerritorioQuilombola.id).where(TerritorioQuilombola.municipio_id == municipio_id)
            )
        )
        sql_partes.append(municipio_sql)
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 imóveis em quilombos na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        stmt = stmt.where(
            RelImovelQuilombo.territorio_quilombola_id.in_(
                select(TerritorioQuilombola.id)
                .join(Municipio, TerritorioQuilombola.municipio_id == Municipio.id)
                .where(Municipio.regiao_administrativa_id == ra_id)
            )
        )
        sql_partes.append(ra_sql)

    stmt = stmt.order_by(RelImovelQuilombo.percentual_sobreposicao.desc()).limit(limite)
    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))

    rows = (await session.execute(stmt)).all()

    features = []
    fontes: dict[str, dict] = {}
    score_cache: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row.geom_json:
            continue
        score_props = await _score_ambiental_properties(session, row.id, score_cache)
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "imovel_rural_quilombo",
                "codigo_car": str(row.codigo_car) if row.codigo_car else None,
                "nome_imovel": row.nome_imovel,
                "area_ha": _round_float(row.area_ha, 4),
                "municipio": row.municipio_nome,
                "imovel_id": str(row.id),
                "territorio_quilombola": row.quilombo_nome,
                "area_intersecao_ha": _round_float(row.area_intersecao_ha, 4) or 0,
                "percentual_sobreposicao": _round_float(row.percentual_sobreposicao, 2) or 0,
                **score_props,
            },
        })
        if row.fonte_nome:
            fontes[row.fonte_nome] = {
                "nome": row.fonte_nome,
                "orgao": row.orgao_responsavel,
                "url": None,
            }

    total_imoveis = len(features)

    # Features adicionais: territórios quilombolas relacionados aos imóveis acima.
    rel_subq = (
        select(RelImovelQuilombo.territorio_quilombola_id)
        .join(ImovelRural, ImovelRural.id == RelImovelQuilombo.imovel_rural_id)
        .join(Municipio, ImovelRural.municipio_id == Municipio.id, isouter=True)
        .join(Estado, Municipio.estado_id == Estado.id, isouter=True)
        .where(Estado.sigla == "SP")
    )
    if municipio_id is not None:
        rel_subq = rel_subq.where(Municipio.id == municipio_id)
    elif ra_id is not None:
        rel_subq = rel_subq.where(Municipio.regiao_administrativa_id == ra_id)

    quilombos_stmt = (
        select(
            TerritorioQuilombola.id,
            TerritorioQuilombola.nome,
            TerritorioQuilombola.area_ha,
            _geom_as_geojson(TerritorioQuilombola.geom, COMPLEX_POLYGON_TOLERANCE).label("geom_json"),
        )
        .where(TerritorioQuilombola.id.in_(rel_subq))
        .limit(500)
    )
    if municipio_id is not None:
        quilombos_stmt = quilombos_stmt.where(TerritorioQuilombola.municipio_id == municipio_id)
    elif ra_id is not None:
        quilombos_stmt = quilombos_stmt.where(
            TerritorioQuilombola.municipio_id.in_(
                select(Municipio.id).where(Municipio.regiao_administrativa_id == ra_id)
            )
        )
    quilombos_rows = (await session.execute(quilombos_stmt)).all()
    total_quilombos = 0
    for q in quilombos_rows:
        if not q.geom_json:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(q.geom_json),
            "properties": {
                "tipo": "territorio_quilombola_relacionado",
                "nome": q.nome,
                "area_ha": _round_float(q.area_ha, 4),
            },
        })
        total_quilombos += 1

    if municipio:
        escopo_txt = f"no município de **{municipio}**"
    elif regiao_administrativa:
        escopo_txt = f"na **{regiao_administrativa}**"
    else:
        escopo_txt = "no estado de **São Paulo**"
    return {
        "total": total_imoveis,
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": (
            f"Foram encontrados **{_fmt_int(total_imoveis)} imóveis rurais** sobrepostos a "
            f"**{_fmt_int(total_quilombos)} territórios quilombolas** {escopo_txt}. "
            "O mapa exibe os imóveis e os polígonos dos territórios relacionados."
        ),
        "sql_executado": sql_executado,
    }


async def buscar_camadas_estaduais(
    session: AsyncSession,
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
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
            _geom_as_geojson(CamadaEstadualAmbiental.geom, COMPLEX_POLYGON_TOLERANCE).label("geom_json"),
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
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontradas 0 camadas estaduais ambientais na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        sql_partes.append(ra_sql)

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
        "descricao": f"Encontradas {_fmt_int(len(features))} camadas estaduais ambientais"
        + _escopo_textual(municipio, regiao_administrativa)
        + ("" if not tema else f" com tema '{tema}'")
        + ".",
        "sql_executado": sql_executado,
    }


async def buscar_imoveis_com_camadas_estaduais(
    session: AsyncSession,
    municipio: Optional[str] = None,
    regiao_administrativa: Optional[str] = None,
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
    elif regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Encontrados 0 imóveis rurais com camadas ambientais na {regiao_administrativa}.",
                "sql_executado": ra_sql,
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)
        sql_partes.append(ra_sql)

    if tema:
        stmt = stmt.where(func.lower(CamadaEstadualAmbiental.tema).contains(tema.lower()))

    stmt = stmt.limit(limite)
    sql_executado = _join_sql(*sql_partes, _stmt_sql(stmt))

    rows = (await session.execute(stmt)).all()

    features = []
    fontes: dict[str, dict] = {}
    score_cache: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row.geom_json:
            continue
        score_props = await _score_ambiental_properties(session, row.id, score_cache)
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "imovel_com_camada_ambiental",
                "nome_imovel": row.nome_imovel,
                "codigo_car": row.codigo_car,
                "area_ha": _round_float(row.area_ha, 4),
                "situacao_cadastral": row.situacao_cadastral,
                "municipio": row.municipio_nome,
                "imovel_id": str(row.id),
                "camada_nome": row.camada_nome,
                "camada_tema": row.tema,
                "camada_subtipo": row.subtipo,
                "area_intersecao_ha": _round_float(row[10], 4) or 0,
                **score_props,
            },
        })

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": f"Encontrados {_fmt_int(len(features))} imóveis rurais em camadas estaduais ambientais"
        + _escopo_textual(municipio, regiao_administrativa)
        + ("" if not tema else f" com tema '{tema}'")
        + ".",
        "sql_executado": sql_executado,
    }


# ---------------------------------------------------------------------------
# Ferramenta: ranking de municípios por tema (mais/menos)
# ---------------------------------------------------------------------------

# tema -> (Model, rótulo no plural, coluna de data ou None)
_RANKING_TEMAS: dict[str, tuple[Any, str, Any]] = {
    "queimadas": (QueimadaEvento, "focos de queimada", QueimadaEvento.data_ocorrencia),
    "desmatamentos": (DesmatamentoAlerta, "alertas de desmatamento", DesmatamentoAlerta.data_ocorrencia),
    "unidades_conservacao": (UnidadeConservacao, "unidades de conservação", None),
    "terras_indigenas": (TerraIndigena, "terras indígenas", None),
    "quilombolas": (TerritorioQuilombola, "territórios quilombolas", None),
    "imoveis_rurais": (ImovelRural, "imóveis rurais", None),
    "assentamentos": (AssentamentoRural, "assentamentos rurais", None),
    "camadas_estaduais": (CamadaEstadualAmbiental, "camadas ambientais estaduais", None),
}


async def ranking_municipios(
    session: AsyncSession,
    tema: str = "queimadas",
    ordem: str = "desc",
    limite: int = 10,
    regiao_administrativa: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
) -> dict:
    """Agrega registros de um tema por município e devolve o ranking (mais/menos).

    Responde perguntas como "qual cidade teve mais/menos queimadas?" ou
    "top 5 municípios com mais desmatamento", para todos os temas suportados.
    """
    info = _RANKING_TEMAS.get(tema)
    if info is None:
        tema = "queimadas"
        info = _RANKING_TEMAS[tema]
    model, rotulo, data_col = info

    limite = max(1, min(int(limite), 50))
    ordem = "asc" if ordem == "asc" else "desc"

    total_col = func.count(model.id).label("total")
    stmt = (
        select(
            Municipio.id,
            Municipio.nome.label("municipio_nome"),
            total_col,
            _geom_as_geojson(Municipio.geom, COMPLEX_POLYGON_TOLERANCE).label("geom_json"),
        )
        .join(Municipio, model.municipio_id == Municipio.id)
        .join(Estado, Municipio.estado_id == Estado.id)
        .where(Estado.sigla == "SP")
        .group_by(Municipio.id, Municipio.nome, Municipio.geom)
    )

    sql_partes: list[str] = []
    if regiao_administrativa:
        ra_id, ra_sql = await _get_regiao_administrativa_id(session, regiao_administrativa)
        sql_partes.append(ra_sql)
        if ra_id is None:
            return {
                "total": 0,
                "features": [],
                "bbox": None,
                "fontes": [],
                "descricao": f"Não foram encontrados dados de {rotulo} para o ranking"
                + _escopo_textual(None, regiao_administrativa)
                + ".",
                "sql_executado": _join_sql(*sql_partes),
            }
        stmt = stmt.where(Municipio.regiao_administrativa_id == ra_id)

    if data_col is not None and data_inicio:
        stmt = stmt.where(data_col >= data_inicio)
    if data_col is not None and data_fim:
        stmt = stmt.where(data_col <= data_fim)

    ordenacao = total_col.asc() if ordem == "asc" else total_col.desc()
    stmt = stmt.order_by(ordenacao, Municipio.nome.asc()).limit(limite)
    sql_partes.append(_stmt_sql(stmt))

    rows = (await session.execute(stmt)).all()

    # Fonte do tema (apenas para citação; uma é suficiente).
    fontes: dict[str, dict] = {}
    try:
        fonte_stmt = (
            select(FonteDado.nome, FonteDado.orgao_responsavel, FonteDado.url_origem)
            .join(Dataset, Dataset.fonte_dado_id == FonteDado.id)
            .join(model, model.dataset_id == Dataset.id)
            .limit(1)
        )
        fonte_row = (await session.execute(fonte_stmt)).first()
        if fonte_row and fonte_row.nome:
            fontes[fonte_row.nome] = {
                "nome": fonte_row.nome,
                "orgao": fonte_row.orgao_responsavel,
                "url": fonte_row.url_origem,
            }
    except Exception:
        logger.warning("Não foi possível recuperar a fonte do tema '%s' no ranking.", tema)

    features: list[dict] = []
    linhas_ranking: list[str] = []
    for posicao, row in enumerate(rows, start=1):
        nome = row.municipio_nome or "(sem nome)"
        linhas_ranking.append(f"{posicao}. **{nome}** — {_fmt_int(row.total)}")
        if row.geom_json:
            features.append({
                "type": "Feature",
                "geometry": json.loads(row.geom_json),
                "properties": {
                    "tipo": "ranking_municipio",
                    "tema": tema,
                    "municipio": nome,
                    "posicao": posicao,
                    "total": int(row.total),
                },
            })

    escopo = _escopo_textual(None, regiao_administrativa)
    periodo = ""
    if data_inicio and data_fim:
        periodo = f" (entre {data_inicio} e {data_fim})"
    elif data_inicio:
        periodo = f" (a partir de {data_inicio})"

    sentido = "menos" if ordem == "asc" else "mais"
    if not rows:
        descricao = f"Não foram encontrados dados de {rotulo} para gerar o ranking{escopo}{periodo}."
    elif len(rows) == 1:
        # Pergunta singular ("qual cidade...") -> uma única resposta, sem lista.
        topo = rows[0]
        descricao = (
            f"O município com **{sentido}** {rotulo}{escopo}{periodo} é "
            f"**{topo.municipio_nome}**, com {_fmt_int(topo.total)}."
        )
    else:
        topo = rows[0]
        descricao = (
            f"Município com **{sentido}** {rotulo}{escopo}{periodo}: "
            f"**{topo.municipio_nome}** ({_fmt_int(topo.total)}).\n\n"
            f"**Ranking de municípios com {sentido} {rotulo}:**\n"
            + "\n".join(linhas_ranking)
        )

    return {
        "total": len(features),
        "features": features,
        "bbox": _build_bbox(features),
        "fontes": list(fontes.values()),
        "descricao": descricao,
        "sql_executado": _join_sql(*sql_partes),
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
    "buscar_imoveis_por_desmatamento": buscar_imoveis_por_desmatamento,
    "buscar_imoveis_por_terra_indigena": buscar_imoveis_por_terra_indigena,
    "buscar_imoveis_por_quilombo": buscar_imoveis_por_quilombo,
    "buscar_camadas_estaduais": buscar_camadas_estaduais,
    "buscar_imoveis_com_camadas_estaduais": buscar_imoveis_com_camadas_estaduais,
    "buscar_passivos_em_imovel": buscar_passivos_em_imovel,
    "buscar_focos_queimada_imovel": buscar_focos_queimada_imovel,
    "ranking_municipios": ranking_municipios,
}
