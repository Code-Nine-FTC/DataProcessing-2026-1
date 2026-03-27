# -*- coding: utf-8 -*-
from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import SessionConnection
from schemas.index import (
    RespostaAgrupada,
    RespostaTemporalQueimada,
    RespostaUltimoIncendio,
    ResumoSobreposicoes,
)
from services.index import AnalyticsService


async def get_imoveis_area_por_estado(
    session: AsyncSession = Depends(SessionConnection.session),
) -> RespostaAgrupada:
    return await AnalyticsService(session).imoveis_area_por_estado()


async def get_imoveis_por_status_car(
    session: AsyncSession = Depends(SessionConnection.session),
) -> RespostaAgrupada:
    return await AnalyticsService(session).imoveis_por_status_car()


async def get_desmatamento_area_por_estado(
    ultimos_12_meses: bool = Query(False, description="Filtrar apenas os últimos 12 meses"),
    session: AsyncSession = Depends(SessionConnection.session),
) -> RespostaAgrupada:
    return await AnalyticsService(session).desmatamento_area_por_estado(ultimos_12_meses)


async def get_desmatamento_alertas_por_tipo(
    session: AsyncSession = Depends(SessionConnection.session),
) -> RespostaAgrupada:
    return await AnalyticsService(session).desmatamento_alertas_por_tipo()


async def get_queimadas_focos_por_estado(
    session: AsyncSession = Depends(SessionConnection.session),
) -> RespostaAgrupada:
    return await AnalyticsService(session).queimadas_focos_por_estado()


async def get_queimadas_focos_por_mes(
    session: AsyncSession = Depends(SessionConnection.session),
) -> RespostaTemporalQueimada:
    return await AnalyticsService(session).queimadas_focos_por_mes()


async def get_queimadas_ultimo_incendio(
    session: AsyncSession = Depends(SessionConnection.session),
) -> RespostaUltimoIncendio:
    return await AnalyticsService(session).queimadas_ultimo_incendio_por_estado()


async def get_resumo_sobreposicoes(
    session: AsyncSession = Depends(SessionConnection.session),
) -> ResumoSobreposicoes:
    return await AnalyticsService(session).resumo_sobreposicoes()
