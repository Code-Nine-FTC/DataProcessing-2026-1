# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_model import (
    AssentamentoRural,
    CamadaEstadualAmbiental,
    Dataset,
    DesmatamentoAlerta,
    Estado,
    FonteDado,
    ImovelRural,
    Municipio,
    QueimadaEvento,
    RelImovelDesmatamento,
    RelImovelQueimada,
    RelImovelTI,
    RelImovelUC,
    RelMunicipioQuilombo,
    RelMunicipioTI,
    RelMunicipioUC,
    RegiaoAdministrativa,
    TerraIndigena,
    TerritorioQuilombola,
    UnidadeConservacao,
)
from nlp_processor.domain.contracts import Fonte, QuerySpec, ToolResult
from nlp_processor.domain.enums import Dominio, Operacao
from nlp_processor.engine.geo_helpers import (
    build_bbox,
    geom_as_geojson,
    geom_clipped_municipio,
    geom_clipped_sp,
    round_float,
    stmt_para_sql,
)

logger = logging.getLogger(__name__)

_LIMITE_RANKING = 10
_LIMITE_EVENTOS_SOBREPOSTOS = 300
_SP_GEOM = select(Estado.geom).where(Estado.sigla == "SP").scalar_subquery()

_CONTEXT_MODEL: dict[Dominio, Any] = {
    Dominio.TERRA_INDIGENA: TerraIndigena,
    Dominio.UNIDADE_CONSERVACAO: UnidadeConservacao,
    Dominio.QUILOMBOLA: TerritorioQuilombola,
    Dominio.ASSENTAMENTO: AssentamentoRural,
}


def _aplicar_local(stmt: Any, spec: QuerySpec, model: Any) -> tuple[Any, Optional[Any]]:
    mun_geom = None
    if spec.onde.municipio_id:
        mun_geom = select(Municipio.geom).where(
            Municipio.id == spec.onde.municipio_id
        ).scalar_subquery()
        stmt = stmt.where(func.ST_Intersects(model.geom, mun_geom))
    elif spec.onde.regiao_administrativa_id:
        stmt = stmt.where(
            Municipio.regiao_administrativa_id == spec.onde.regiao_administrativa_id
        )
    return stmt, mun_geom


def _aplicar_periodo_queimada(stmt: Any, spec: QuerySpec) -> Any:
    if spec.periodo and spec.periodo.data_inicio:
        stmt = stmt.where(
            QueimadaEvento.data_ocorrencia >= datetime.fromisoformat(spec.periodo.data_inicio)
        )
    if spec.periodo and spec.periodo.data_fim:
        stmt = stmt.where(
            QueimadaEvento.data_ocorrencia <= datetime.fromisoformat(spec.periodo.data_fim)
        )
    return stmt


def _aplicar_periodo_desmatamento(stmt: Any, spec: QuerySpec) -> Any:
    if spec.periodo and spec.periodo.data_inicio:
        stmt = stmt.where(
            DesmatamentoAlerta.data_ocorrencia >= date.fromisoformat(spec.periodo.data_inicio)
        )
    if spec.periodo and spec.periodo.data_fim:
        stmt = stmt.where(
            DesmatamentoAlerta.data_ocorrencia <= date.fromisoformat(spec.periodo.data_fim)
        )
    return stmt


def _aplicar_contexto_espacial(stmt: Any, spec: QuerySpec, model: Any) -> Any:
    ctx = spec.contexto_espacial
    if not ctx or not ctx.dentro_de:
        return stmt
    area_model = _CONTEXT_MODEL.get(ctx.dentro_de)
    if area_model is None:
        return stmt
    return stmt.where(
        func.ST_Intersects(model.geom, select(area_model.geom).scalar_subquery())
    )


def _aplicar_sobreposicao_imovel(stmt: Any, spec: QuerySpec) -> Any:
    ctx = spec.contexto_espacial
    if not ctx or not ctx.dentro_de:
        return stmt

    dominio = ctx.dentro_de

    if dominio == Dominio.QUEIMADA:
        sub = select(RelImovelQueimada.imovel_rural_id).join(
            QueimadaEvento, RelImovelQueimada.queimada_evento_id == QueimadaEvento.id
        )
        if spec.periodo and spec.periodo.data_inicio:
            sub = sub.where(QueimadaEvento.data_ocorrencia >= datetime.fromisoformat(spec.periodo.data_inicio))
        if spec.periodo and spec.periodo.data_fim:
            sub = sub.where(QueimadaEvento.data_ocorrencia <= datetime.fromisoformat(spec.periodo.data_fim))
        return stmt.where(ImovelRural.id.in_(sub))

    if dominio == Dominio.DESMATAMENTO:
        sub = select(RelImovelDesmatamento.imovel_rural_id).join(
            DesmatamentoAlerta, RelImovelDesmatamento.desmatamento_alerta_id == DesmatamentoAlerta.id
        )
        if spec.periodo and spec.periodo.data_inicio:
            sub = sub.where(DesmatamentoAlerta.data_ocorrencia >= date.fromisoformat(spec.periodo.data_inicio))
        if spec.periodo and spec.periodo.data_fim:
            sub = sub.where(DesmatamentoAlerta.data_ocorrencia <= date.fromisoformat(spec.periodo.data_fim))
        return stmt.where(ImovelRural.id.in_(sub))

    if dominio == Dominio.TERRA_INDIGENA:
        return stmt.where(ImovelRural.id.in_(select(RelImovelTI.imovel_rural_id)))

    if dominio == Dominio.UNIDADE_CONSERVACAO:
        return stmt.where(ImovelRural.id.in_(select(RelImovelUC.imovel_rural_id)))

    return stmt


def _fontes_de_rows(rows: list[Any]) -> list[Fonte]:
    vistas: dict[str, Fonte] = {}
    for row in rows:
        if hasattr(row, "fonte_nome") and row.fonte_nome:
            vistas[row.fonte_nome] = Fonte(
                nome=row.fonte_nome,
                orgao=getattr(row, "orgao_responsavel", None),
                url=getattr(row, "url_origem", None),
            )
    return list(vistas.values())


async def _listar_queimadas(session: AsyncSession, spec: QuerySpec) -> ToolResult:
    geom_expr = geom_as_geojson(QueimadaEvento.geom)

    stmt = (
        select(
            QueimadaEvento.data_ocorrencia,
            QueimadaEvento.fonte_sensor,
            QueimadaEvento.intensidade,
            QueimadaEvento.bioma,
            QueimadaEvento.dias_sem_chuva,
            QueimadaEvento.precipitacao_mm,
            QueimadaEvento.risco_fogo,
            Municipio.nome.label("municipio_nome"),
            geom_expr.label("geom_json"),
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

    stmt, _ = _aplicar_local(stmt, spec, QueimadaEvento)
    stmt = _aplicar_periodo_queimada(stmt, spec)
    stmt = _aplicar_contexto_espacial(stmt, spec, QueimadaEvento)

    if spec.filtros.bioma:
        stmt = stmt.where(func.lower(QueimadaEvento.bioma).contains(spec.filtros.bioma.lower()))
    if spec.filtros.sensor:
        stmt = stmt.where(func.lower(QueimadaEvento.fonte_sensor).contains(spec.filtros.sensor.lower()))

    stmt = stmt.order_by(QueimadaEvento.data_ocorrencia.desc()).limit(spec.filtros.limite)
    sql = stmt_para_sql(stmt)
    rows = (await session.execute(stmt)).all()

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "queimada",
                "data_ocorrencia": str(row.data_ocorrencia) if row.data_ocorrencia else None,
                "fonte_sensor": row.fonte_sensor,
                "intensidade": round_float(row.intensidade, 2),
                "bioma": row.bioma,
                "municipio": row.municipio_nome,
                "dias_sem_chuva": round_float(row.dias_sem_chuva, 1),
                "risco_fogo": round_float(row.risco_fogo, 2),
            },
        }
        for row in rows
        if row.geom_json
    ]

    return ToolResult(
        dominio=Dominio.QUEIMADA,
        operacao=Operacao.LISTAR,
        total=len(features),
        features=features,
        fontes=_fontes_de_rows(rows),
        spec=spec,
        bbox=build_bbox(features),
        sql_executado=sql,
    )


async def _listar_desmatamentos(session: AsyncSession, spec: QuerySpec) -> ToolResult:
    stmt = (
        select(
            DesmatamentoAlerta.data_ocorrencia,
            DesmatamentoAlerta.tipo_alerta,
            DesmatamentoAlerta.area_ha,
            Municipio.nome.label("municipio_nome"),
            geom_as_geojson(DesmatamentoAlerta.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, DesmatamentoAlerta.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, DesmatamentoAlerta.municipio_id == Municipio.id, isouter=True)
        .where(func.ST_Intersects(DesmatamentoAlerta.geom, _SP_GEOM))
    )

    stmt, _ = _aplicar_local(stmt, spec, DesmatamentoAlerta)
    stmt = _aplicar_periodo_desmatamento(stmt, spec)
    stmt = _aplicar_contexto_espacial(stmt, spec, DesmatamentoAlerta)

    if spec.filtros.tipo_alerta:
        stmt = stmt.where(func.lower(DesmatamentoAlerta.tipo_alerta) == spec.filtros.tipo_alerta.lower())

    stmt = stmt.order_by(DesmatamentoAlerta.data_ocorrencia.desc()).limit(spec.filtros.limite)
    sql = stmt_para_sql(stmt)
    rows = (await session.execute(stmt)).all()

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "desmatamento",
                "data_ocorrencia": str(row.data_ocorrencia) if row.data_ocorrencia else None,
                "tipo_alerta": row.tipo_alerta,
                "area_ha": round_float(row.area_ha, 4),
                "municipio": row.municipio_nome,
            },
        }
        for row in rows
        if row.geom_json
    ]

    return ToolResult(
        dominio=Dominio.DESMATAMENTO,
        operacao=Operacao.LISTAR,
        total=len(features),
        features=features,
        fontes=_fontes_de_rows(rows),
        spec=spec,
        bbox=build_bbox(features),
        sql_executado=sql,
    )


async def _listar_uc(session: AsyncSession, spec: QuerySpec) -> ToolResult:
    mun_geom = None
    if spec.onde.municipio_id:
        mun_geom = select(Municipio.geom).where(
            Municipio.id == spec.onde.municipio_id
        ).scalar_subquery()

    geom_expr = (
        geom_clipped_municipio(UnidadeConservacao.geom, mun_geom)
        if mun_geom is not None
        else geom_clipped_sp(UnidadeConservacao.geom)
    )

    stmt = (
        select(
            UnidadeConservacao.nome,
            UnidadeConservacao.categoria,
            UnidadeConservacao.esfera,
            UnidadeConservacao.grupo_snuc,
            UnidadeConservacao.area_ha,
            Municipio.nome.label("municipio_nome"),
            geom_expr.label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, UnidadeConservacao.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, UnidadeConservacao.municipio_id == Municipio.id, isouter=True)
        .where(func.ST_Intersects(UnidadeConservacao.geom, _SP_GEOM))
    )

    if mun_geom is not None:
        stmt = stmt.where(func.ST_Intersects(UnidadeConservacao.geom, mun_geom))
    elif spec.onde.regiao_administrativa_id:
        stmt = stmt.where(
            Municipio.regiao_administrativa_id == spec.onde.regiao_administrativa_id
        )

    if spec.filtros.categoria_uc:
        stmt = stmt.where(
            func.unaccent(func.lower(UnidadeConservacao.categoria)).contains(
                spec.filtros.categoria_uc.lower()
            )
        )
    if spec.filtros.grupo_snuc:
        codigo = {"protecao integral": "PI", "uso sustentavel": "US"}.get(
            spec.filtros.grupo_snuc.lower()
        )
        if codigo:
            stmt = stmt.where(func.upper(UnidadeConservacao.grupo_snuc) == codigo)
    if spec.filtros.esfera_uc:
        stmt = stmt.where(func.lower(UnidadeConservacao.esfera) == spec.filtros.esfera_uc.lower())

    sql = stmt_para_sql(stmt)
    rows = (await session.execute(stmt)).all()

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "unidade_conservacao",
                "nome": row.nome,
                "categoria": row.categoria,
                "esfera": row.esfera,
                "grupo_snuc": row.grupo_snuc,
                "area_ha": round_float(row.area_ha, 4),
                "municipio": row.municipio_nome,
            },
        }
        for row in rows
        if row.geom_json
    ]

    return ToolResult(
        dominio=Dominio.UNIDADE_CONSERVACAO,
        operacao=Operacao.LISTAR,
        total=len(features),
        features=features,
        fontes=_fontes_de_rows(rows),
        spec=spec,
        bbox=build_bbox(features),
        sql_executado=sql,
    )


async def _listar_ti(session: AsyncSession, spec: QuerySpec) -> ToolResult:
    mun_geom = None
    if spec.onde.municipio_id:
        mun_geom = select(Municipio.geom).where(
            Municipio.id == spec.onde.municipio_id
        ).scalar_subquery()

    geom_expr = (
        geom_clipped_municipio(TerraIndigena.geom, mun_geom)
        if mun_geom is not None
        else geom_clipped_sp(TerraIndigena.geom)
    )

    stmt = (
        select(
            TerraIndigena.nome,
            TerraIndigena.fase,
            TerraIndigena.area_ha,
            Municipio.nome.label("municipio_nome"),
            geom_expr.label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, TerraIndigena.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, TerraIndigena.municipio_id == Municipio.id, isouter=True)
        .where(func.ST_Intersects(TerraIndigena.geom, _SP_GEOM))
    )

    if mun_geom is not None:
        stmt = stmt.where(func.ST_Intersects(TerraIndigena.geom, mun_geom))
    elif spec.onde.regiao_administrativa_id:
        stmt = stmt.where(
            Municipio.regiao_administrativa_id == spec.onde.regiao_administrativa_id
        )

    if spec.filtros.fase_ti:
        stmt = stmt.where(func.lower(TerraIndigena.fase).contains(spec.filtros.fase_ti.lower()))

    sql = stmt_para_sql(stmt)
    rows = (await session.execute(stmt)).all()

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "terra_indigena",
                "nome": row.nome,
                "fase": row.fase,
                "area_ha": round_float(row.area_ha, 4),
                "municipio": row.municipio_nome,
            },
        }
        for row in rows
        if row.geom_json
    ]

    return ToolResult(
        dominio=Dominio.TERRA_INDIGENA,
        operacao=Operacao.LISTAR,
        total=len(features),
        features=features,
        fontes=_fontes_de_rows(rows),
        spec=spec,
        bbox=build_bbox(features),
        sql_executado=sql,
    )


async def _listar_quilombolas(session: AsyncSession, spec: QuerySpec) -> ToolResult:
    mun_geom = None
    if spec.onde.municipio_id:
        mun_geom = select(Municipio.geom).where(
            Municipio.id == spec.onde.municipio_id
        ).scalar_subquery()

    geom_expr = (
        geom_clipped_municipio(TerritorioQuilombola.geom, mun_geom)
        if mun_geom is not None
        else geom_clipped_sp(TerritorioQuilombola.geom)
    )

    stmt = (
        select(
            TerritorioQuilombola.nome,
            TerritorioQuilombola.area_ha,
            Municipio.nome.label("municipio_nome"),
            geom_expr.label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, TerritorioQuilombola.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, TerritorioQuilombola.municipio_id == Municipio.id, isouter=True)
        .where(func.ST_Intersects(TerritorioQuilombola.geom, _SP_GEOM))
    )

    if mun_geom is not None:
        stmt = stmt.where(func.ST_Intersects(TerritorioQuilombola.geom, mun_geom))
    elif spec.onde.regiao_administrativa_id:
        stmt = stmt.where(
            Municipio.regiao_administrativa_id == spec.onde.regiao_administrativa_id
        )

    sql = stmt_para_sql(stmt)
    rows = (await session.execute(stmt)).all()

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "quilombola",
                "nome": row.nome,
                "area_ha": round_float(row.area_ha, 4),
                "municipio": row.municipio_nome,
            },
        }
        for row in rows
        if row.geom_json
    ]

    return ToolResult(
        dominio=Dominio.QUILOMBOLA,
        operacao=Operacao.LISTAR,
        total=len(features),
        features=features,
        fontes=_fontes_de_rows(rows),
        spec=spec,
        bbox=build_bbox(features),
        sql_executado=sql,
    )


async def _listar_assentamentos(session: AsyncSession, spec: QuerySpec) -> ToolResult:
    stmt = (
        select(
            AssentamentoRural.nome,
            AssentamentoRural.area_ha,
            AssentamentoRural.modalidade,
            AssentamentoRural.familias,
            Municipio.nome.label("municipio_nome"),
            geom_as_geojson(AssentamentoRural.geom).label("geom_json"),
            FonteDado.nome.label("fonte_nome"),
            FonteDado.orgao_responsavel,
            FonteDado.url_origem,
        )
        .join(Dataset, AssentamentoRural.dataset_id == Dataset.id, isouter=True)
        .join(FonteDado, Dataset.fonte_dado_id == FonteDado.id, isouter=True)
        .join(Municipio, AssentamentoRural.municipio_id == Municipio.id, isouter=True)
        .where(func.ST_Intersects(AssentamentoRural.geom, _SP_GEOM))
    )

    stmt, _ = _aplicar_local(stmt, spec, AssentamentoRural)
    stmt = _aplicar_contexto_espacial(stmt, spec, AssentamentoRural)
    stmt = stmt.order_by(AssentamentoRural.area_ha.desc().nullslast()).limit(spec.filtros.limite)

    sql = stmt_para_sql(stmt)
    rows = (await session.execute(stmt)).all()

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "assentamento_rural",
                "nome": row.nome,
                "area_ha": round_float(row.area_ha, 4),
                "modalidade": row.modalidade,
                "familias": row.familias,
                "municipio": row.municipio_nome,
            },
        }
        for row in rows
        if row.geom_json
    ]

    return ToolResult(
        dominio=Dominio.ASSENTAMENTO,
        operacao=Operacao.LISTAR,
        total=len(features),
        features=features,
        fontes=_fontes_de_rows(rows),
        spec=spec,
        bbox=build_bbox(features),
        sql_executado=sql,
    )


async def _listar_imoveis(session: AsyncSession, spec: QuerySpec) -> ToolResult:
    stmt = (
        select(
            ImovelRural.id,
            ImovelRural.codigo_car,
            ImovelRural.nome_imovel,
            ImovelRural.area_ha,
            Municipio.nome.label("municipio_nome"),
            geom_as_geojson(ImovelRural.geom).label("geom_json"),
        )
        .join(Municipio, ImovelRural.municipio_id == Municipio.id, isouter=True)
        .where(func.ST_Intersects(ImovelRural.geom, _SP_GEOM))
    )

    if spec.onde.codigo_car:
        stmt = stmt.where(ImovelRural.codigo_car == spec.onde.codigo_car)
    else:
        stmt, _ = _aplicar_local(stmt, spec, ImovelRural)

    stmt = _aplicar_sobreposicao_imovel(stmt, spec)

    stmt = stmt.order_by(ImovelRural.area_ha.desc().nullslast()).limit(spec.filtros.limite)
    sql = stmt_para_sql(stmt)
    rows = (await session.execute(stmt)).all()

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "imovel_rural",
                "codigo_car": row.codigo_car,
                "nome": row.nome_imovel,
                "area_ha": round_float(row.area_ha, 4),
                "municipio": row.municipio_nome,
            },
        }
        for row in rows
        if row.geom_json
    ]

    eventos = await _features_eventos_sobrepostos(session, spec, [row.id for row in rows])

    return ToolResult(
        dominio=Dominio.IMOVEL_RURAL,
        operacao=Operacao.LISTAR,
        total=len(features),
        features=features + eventos,
        fontes=[],
        spec=spec,
        bbox=build_bbox(features + eventos),
        sql_executado=sql,
    )


async def _features_eventos_sobrepostos(
    session: AsyncSession, spec: QuerySpec, imovel_ids: list[int]
) -> list[dict]:
    ctx = spec.contexto_espacial
    if not ctx or not ctx.dentro_de or not imovel_ids:
        return []

    if ctx.dentro_de == Dominio.QUEIMADA:
        stmt = (
            select(
                QueimadaEvento.data_ocorrencia,
                QueimadaEvento.fonte_sensor,
                QueimadaEvento.risco_fogo,
                geom_as_geojson(QueimadaEvento.geom).label("geom_json"),
            )
            .join(RelImovelQueimada, RelImovelQueimada.queimada_evento_id == QueimadaEvento.id)
            .where(RelImovelQueimada.imovel_rural_id.in_(imovel_ids))
        )
        if spec.periodo and spec.periodo.data_inicio:
            stmt = stmt.where(QueimadaEvento.data_ocorrencia >= datetime.fromisoformat(spec.periodo.data_inicio))
        if spec.periodo and spec.periodo.data_fim:
            stmt = stmt.where(QueimadaEvento.data_ocorrencia <= datetime.fromisoformat(spec.periodo.data_fim))
        stmt = stmt.order_by(QueimadaEvento.data_ocorrencia.desc()).limit(_LIMITE_EVENTOS_SOBREPOSTOS)
        rows = (await session.execute(stmt)).all()
        return [
            {
                "type": "Feature",
                "geometry": json.loads(row.geom_json),
                "properties": {
                    "tipo": "queimada",
                    "data_ocorrencia": str(row.data_ocorrencia) if row.data_ocorrencia else None,
                    "fonte_sensor": row.fonte_sensor,
                    "risco_fogo": round_float(row.risco_fogo, 2),
                },
            }
            for row in rows
            if row.geom_json
        ]

    if ctx.dentro_de == Dominio.DESMATAMENTO:
        stmt = (
            select(
                DesmatamentoAlerta.data_ocorrencia,
                DesmatamentoAlerta.tipo_alerta,
                DesmatamentoAlerta.area_ha,
                geom_as_geojson(DesmatamentoAlerta.geom).label("geom_json"),
            )
            .join(RelImovelDesmatamento, RelImovelDesmatamento.desmatamento_alerta_id == DesmatamentoAlerta.id)
            .where(RelImovelDesmatamento.imovel_rural_id.in_(imovel_ids))
        )
        if spec.periodo and spec.periodo.data_inicio:
            stmt = stmt.where(DesmatamentoAlerta.data_ocorrencia >= date.fromisoformat(spec.periodo.data_inicio))
        if spec.periodo and spec.periodo.data_fim:
            stmt = stmt.where(DesmatamentoAlerta.data_ocorrencia <= date.fromisoformat(spec.periodo.data_fim))
        stmt = stmt.order_by(DesmatamentoAlerta.data_ocorrencia.desc()).limit(_LIMITE_EVENTOS_SOBREPOSTOS)
        rows = (await session.execute(stmt)).all()
        return [
            {
                "type": "Feature",
                "geometry": json.loads(row.geom_json),
                "properties": {
                    "tipo": "desmatamento",
                    "data_ocorrencia": str(row.data_ocorrencia) if row.data_ocorrencia else None,
                    "tipo_alerta": row.tipo_alerta,
                    "area_ha": round_float(row.area_ha, 4),
                },
            }
            for row in rows
            if row.geom_json
        ]

    return []


async def _passivos_imovel(session: AsyncSession, spec: QuerySpec) -> ToolResult:
    if not spec.onde.codigo_car and not spec.onde.municipio_id:
        return ToolResult(
            dominio=Dominio.IMOVEL_RURAL,
            operacao=Operacao.PASSIVOS,
            total=0,
            spec=spec,
        )

    stmt_imovel = select(ImovelRural.id, ImovelRural.codigo_car).limit(1)
    if spec.onde.codigo_car:
        stmt_imovel = stmt_imovel.where(ImovelRural.codigo_car == spec.onde.codigo_car)

    row = (await session.execute(stmt_imovel)).first()
    if not row:
        return ToolResult(
            dominio=Dominio.IMOVEL_RURAL,
            operacao=Operacao.PASSIVOS,
            total=0,
            spec=spec,
        )

    imovel_id = row.id
    features: list[dict] = []
    sqls: list[str] = []

    stmt_q = (
        select(
            QueimadaEvento.data_ocorrencia,
            QueimadaEvento.bioma,
            geom_as_geojson(QueimadaEvento.geom).label("geom_json"),
        )
        .join(RelImovelQueimada, RelImovelQueimada.queimada_evento_id == QueimadaEvento.id)
        .where(RelImovelQueimada.imovel_rural_id == imovel_id)
    )
    sqls.append(stmt_para_sql(stmt_q))
    for r in (await session.execute(stmt_q)).all():
        if r.geom_json:
            features.append({
                "type": "Feature",
                "geometry": json.loads(r.geom_json),
                "properties": {"tipo": "passivo_queimada", "data": str(r.data_ocorrencia)},
            })

    stmt_d = (
        select(
            DesmatamentoAlerta.tipo_alerta,
            DesmatamentoAlerta.area_ha,
            geom_as_geojson(DesmatamentoAlerta.geom).label("geom_json"),
        )
        .join(RelImovelDesmatamento, RelImovelDesmatamento.desmatamento_alerta_id == DesmatamentoAlerta.id)
        .where(RelImovelDesmatamento.imovel_rural_id == imovel_id)
    )
    sqls.append(stmt_para_sql(stmt_d))
    for r in (await session.execute(stmt_d)).all():
        if r.geom_json:
            features.append({
                "type": "Feature",
                "geometry": json.loads(r.geom_json),
                "properties": {"tipo": "passivo_desmatamento", "area_ha": round_float(r.area_ha, 4)},
            })

    stmt_ti = (
        select(
            TerraIndigena.nome,
            TerraIndigena.area_ha,
            geom_clipped_sp(TerraIndigena.geom).label("geom_json"),
        )
        .join(RelImovelTI, RelImovelTI.terra_indigena_id == TerraIndigena.id)
        .where(RelImovelTI.imovel_rural_id == imovel_id)
    )
    sqls.append(stmt_para_sql(stmt_ti))
    for r in (await session.execute(stmt_ti)).all():
        if r.geom_json:
            features.append({
                "type": "Feature",
                "geometry": json.loads(r.geom_json),
                "properties": {"tipo": "sobreposicao_ti", "nome": r.nome},
            })

    stmt_uc = (
        select(
            UnidadeConservacao.nome,
            UnidadeConservacao.categoria,
            geom_clipped_sp(UnidadeConservacao.geom).label("geom_json"),
        )
        .join(RelImovelUC, RelImovelUC.unidade_conservacao_id == UnidadeConservacao.id)
        .where(RelImovelUC.imovel_rural_id == imovel_id)
    )
    sqls.append(stmt_para_sql(stmt_uc))
    for r in (await session.execute(stmt_uc)).all():
        if r.geom_json:
            features.append({
                "type": "Feature",
                "geometry": json.loads(r.geom_json),
                "properties": {"tipo": "sobreposicao_uc", "nome": r.nome, "categoria": r.categoria},
            })

    return ToolResult(
        dominio=Dominio.IMOVEL_RURAL,
        operacao=Operacao.PASSIVOS,
        total=len(features),
        features=features,
        spec=spec,
        bbox=build_bbox(features),
        sql_executado="\n\n---\n\n".join(sqls),
    )


async def _rankear(session: AsyncSession, spec: QuerySpec) -> ToolResult:
    tema = spec.filtros.tema_ranking
    limite = spec.filtros.limite or _LIMITE_RANKING
    features: list[dict] = []
    sqls: list[str] = []

    temas_ocorrencia = {
        "queimadas": (QueimadaEvento, func.count(QueimadaEvento.id), "focos"),
        "desmatamentos": (DesmatamentoAlerta, func.sum(DesmatamentoAlerta.area_ha), "ha"),
    }
    temas_area = {
        "terras_indigenas": (RelMunicipioTI, TerraIndigena, "terras indígenas"),
        "unidades_conservacao": (RelMunicipioUC, UnidadeConservacao, "UCs"),
        "quilombolas": (RelMunicipioQuilombo, TerritorioQuilombola, "quilombolas"),
    }

    temas_executar = [tema] if tema else list(temas_ocorrencia) + list(temas_area)

    for t in temas_executar:
        if t in temas_ocorrencia:
            model_t, agg, unidade = temas_ocorrencia[t]
            stmt = (
                select(
                    Municipio.nome,
                    agg.label("valor"),
                    geom_as_geojson(Municipio.geom).label("geom_json"),
                )
                .join(model_t, func.ST_Contains(Municipio.geom, model_t.geom))
                .group_by(Municipio.id, Municipio.nome)
                .order_by(agg.desc())
                .limit(limite)
            )
            sqls.append(stmt_para_sql(stmt))
            for i, row in enumerate((await session.execute(stmt)).all(), 1):
                valor = round_float(row.valor) or 0
                if row.geom_json:
                    features.append({
                        "type": "Feature",
                        "geometry": json.loads(row.geom_json),
                        "properties": {
                            "tipo": "ranking",
                            "posicao": i,
                            "municipio": row.nome,
                            "valor": valor,
                            "unidade": unidade,
                            "tema": t,
                        },
                    })

        elif t in temas_area:
            rel_model, _, label = temas_area[t]
            area_col = getattr(rel_model, "area_intersecao_ha", None)

            if area_col is None:
                continue

            target_id = next(
                (
                    getattr(rel_model, col_name)
                    for col_name in [
                        "terra_indigena_id",
                        "unidade_conservacao_id",
                        "territorio_quilombola_id",
                    ]
                    if hasattr(rel_model, col_name)
                ),
                None,
            )

            if target_id is None:
                continue

            stmt = (
                select(
                    Municipio.nome,
                    func.sum(area_col).label("area_total"),
                    func.count(func.distinct(target_id)).label("qtd"),
                    geom_as_geojson(Municipio.geom).label("geom_json"),
                )
                .join(rel_model, rel_model.municipio_id == Municipio.id)
                .group_by(Municipio.id, Municipio.nome)
                .order_by(func.count(func.distinct(target_id)).desc(), func.sum(area_col).desc())
                .limit(limite)
            )
            sqls.append(stmt_para_sql(stmt))
            for i, row in enumerate((await session.execute(stmt)).all(), 1):
                if row.geom_json:
                    features.append({
                        "type": "Feature",
                        "geometry": json.loads(row.geom_json),
                        "properties": {
                            "tipo": "ranking",
                            "posicao": i,
                            "municipio": row.nome,
                            "area_ha": round_float(row.area_total, 2),
                            "qtd": int(row.qtd or 0),
                            "tema": t,
                            "label": label,
                        },
                    })

    return ToolResult(
        dominio=spec.dominio,
        operacao=Operacao.RANKEAR,
        total=len(features),
        features=features,
        spec=spec,
        bbox=build_bbox(features),
        sql_executado="\n\n---\n\n".join(sqls) if sqls else None,
    )


async def _listar_camadas_estaduais(session: AsyncSession, spec: QuerySpec) -> ToolResult:
    stmt = (
        select(
            CamadaEstadualAmbiental.nome,
            CamadaEstadualAmbiental.subtipo,
            CamadaEstadualAmbiental.tema,
            Municipio.nome.label("municipio_nome"),
            geom_as_geojson(CamadaEstadualAmbiental.geom).label("geom_json"),
        )
        .join(Municipio, CamadaEstadualAmbiental.municipio_id == Municipio.id, isouter=True)
        .where(func.ST_Intersects(CamadaEstadualAmbiental.geom, _SP_GEOM))
    )

    stmt, _ = _aplicar_local(stmt, spec, CamadaEstadualAmbiental)
    stmt = stmt.limit(spec.filtros.limite)
    sql = stmt_para_sql(stmt)
    rows = (await session.execute(stmt)).all()

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(row.geom_json),
            "properties": {
                "tipo": "camada_estadual",
                "nome": row.nome,
                "subtipo": row.subtipo,
                "tema": row.tema,
                "municipio": row.municipio_nome,
            },
        }
        for row in rows
        if row.geom_json
    ]

    return ToolResult(
        dominio=Dominio.CAMADA_ESTADUAL,
        operacao=Operacao.LISTAR,
        total=len(features),
        features=features,
        fontes=[],
        spec=spec,
        bbox=build_bbox(features),
        sql_executado=sql,
    )


async def _listar_documentos(session: AsyncSession, spec: QuerySpec) -> ToolResult:
    from nlp_processor.infrastructure.rag import buscar_trechos

    pergunta = spec.onde.municipio_nome or ""
    trechos = await buscar_trechos(session, pergunta, limite=spec.filtros.limite)

    features = [
        {
            "type": "Feature",
            "geometry": None,
            "properties": {
                "tipo": "documento",
                "texto": t["texto"],
                "relevancia": t["relevancia"],
            },
        }
        for t in trechos
    ]

    return ToolResult(
        dominio=Dominio.DOCUMENTO,
        operacao=Operacao.LISTAR,
        total=len(features),
        features=features,
        spec=spec,
    )


_LISTAR_HANDLERS = {
    Dominio.QUEIMADA: _listar_queimadas,
    Dominio.DESMATAMENTO: _listar_desmatamentos,
    Dominio.UNIDADE_CONSERVACAO: _listar_uc,
    Dominio.TERRA_INDIGENA: _listar_ti,
    Dominio.QUILOMBOLA: _listar_quilombolas,
    Dominio.ASSENTAMENTO: _listar_assentamentos,
    Dominio.IMOVEL_RURAL: _listar_imoveis,
    Dominio.CAMADA_ESTADUAL: _listar_camadas_estaduais,
    Dominio.DOCUMENTO: _listar_documentos,
}


async def _executar_spec(session: AsyncSession, spec: QuerySpec) -> ToolResult:
    if spec.operacao == Operacao.RANKEAR:
        return await _rankear(session, spec)

    if spec.operacao == Operacao.PASSIVOS:
        return await _passivos_imovel(session, spec)

    handler = _LISTAR_HANDLERS.get(spec.dominio)
    if handler is None:
        logger.warning("Domínio sem handler: %s", spec.dominio)
        return ToolResult(
            dominio=spec.dominio,
            operacao=spec.operacao,
            total=0,
            spec=spec,
        )

    try:
        return await handler(session, spec)
    except Exception as exc:
        logger.exception("Erro ao executar spec %s/%s: %s", spec.dominio, spec.operacao, exc)
        return ToolResult(
            dominio=spec.dominio,
            operacao=spec.operacao,
            total=0,
            spec=spec,
        )


async def executar(session: AsyncSession, specs: list[QuerySpec]) -> list[ToolResult]:
    if not specs:
        return []
    tarefas = [_executar_spec(session, spec) for spec in specs]
    return list(await asyncio.gather(*tarefas))
