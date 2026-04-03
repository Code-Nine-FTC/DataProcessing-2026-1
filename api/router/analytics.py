# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.index import (
    RespostaAgrupada,
    RespostaQueimadaDentroFora,
    RespostaTemporalDesmatamento,
    RespostaTemporalQueimada,
    RespostaUltimoIncendio,
    ResumoSobreposicoes,
)
from api.services.index import AnalyticsService
from api.utils.basic_response import BasicResponse
from models.database import SessionConnection

router = APIRouter(prefix="/analytics", tags=["Analytics RF-07"])


# --- Imóveis Rurais ---

@router.get(
    "/imoveis/area-por-estado",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #1] Área total (ha) dos imóveis rurais por estado",
)
async def get_imoveis_area_por_estado(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).imoveis_area_por_estado())


@router.get(
    "/imoveis/status-car",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #17] Distribuição de imóveis por situação cadastral (CAR)",
)
async def get_imoveis_por_status_car(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).imoveis_por_status_car())


# --- Desmatamento ---

@router.get(
    "/desmatamento/area-por-estado",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #6] Área desmatada (ha) por estado",
)
async def get_desmatamento_area_por_estado(
    ultimos_12_meses: bool = Query(False, description="Filtrar apenas os últimos 12 meses"),
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).desmatamento_area_por_estado(ultimos_12_meses))


@router.get(
    "/desmatamento/area-por-mes",
    response_model=BasicResponse[RespostaTemporalDesmatamento],
    summary="[RF-07 #6] Série temporal de área desmatada (ha) por mês",
)
async def get_desmatamento_area_por_mes(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaTemporalDesmatamento]:
    return BasicResponse(data=await AnalyticsService(session).desmatamento_area_por_mes())


@router.get(
    "/desmatamento/alertas-por-tipo",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #7] Contagem de alertas de desmatamento por tipo",
)
async def get_desmatamento_alertas_por_tipo(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).desmatamento_alertas_por_tipo())


@router.get(
    "/desmatamento/area-em-imoveis-por-estado",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #7] Área de desmatamento sobreposta a imóveis rurais por estado",
)
async def get_desmatamento_area_em_imoveis(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).desmatamento_area_em_imoveis())


# --- Queimadas ---

@router.get(
    "/queimadas/focos-por-estado",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #8] Focos de incêndio por estado",
)
async def get_queimadas_focos_por_estado(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).queimadas_focos_por_estado())


@router.get(
    "/queimadas/focos-por-mes",
    response_model=BasicResponse[RespostaTemporalQueimada],
    summary="[RF-07 #8] Série temporal de focos de incêndio por mês",
)
async def get_queimadas_focos_por_mes(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaTemporalQueimada]:
    return BasicResponse(data=await AnalyticsService(session).queimadas_focos_por_mes())


@router.get(
    "/queimadas/focos-por-bioma",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #8] Focos de incêndio por bioma",
)
async def get_queimadas_focos_por_bioma(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).queimadas_focos_por_bioma())


@router.get(
    "/queimadas/intensidade-por-bioma",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #8] Intensidade média (FRP) de queimadas por bioma",
)
async def get_queimadas_intensidade_por_bioma(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).queimadas_intensidade_por_bioma())


@router.get(
    "/queimadas/dias-sem-chuva-por-estado",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #8] Média de dias sem chuva no momento do foco, por estado",
)
async def get_queimadas_dias_sem_chuva(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).queimadas_dias_sem_chuva_por_estado())


@router.get(
    "/queimadas/risco-medio-por-estado",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #8] Risco médio de fogo por estado",
)
async def get_queimadas_risco_medio_por_estado(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).queimadas_risco_medio_por_estado())


@router.get(
    "/queimadas/dentro-fora-imoveis",
    response_model=BasicResponse[RespostaQueimadaDentroFora],
    summary="[RF-07 #8] Queimadas dentro vs. fora de imóveis rurais",
)
async def get_queimadas_dentro_fora(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaQueimadaDentroFora]:
    return BasicResponse(data=await AnalyticsService(session).queimadas_dentro_fora_imoveis())


@router.get(
    "/queimadas/ultimo-incendio-por-estado",
    response_model=BasicResponse[RespostaUltimoIncendio],
    summary="[RF-07 #9] Data do último incêndio detectado por estado",
)
async def get_queimadas_ultimo_incendio(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaUltimoIncendio]:
    return BasicResponse(data=await AnalyticsService(session).queimadas_ultimo_incendio_por_estado())


# --- Áreas Protegidas ---

@router.get(
    "/unidades-conservacao/por-grupo-snuc",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #13] Unidades de Conservação por grupo SNUC",
)
async def get_uc_por_grupo_snuc(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).uc_por_grupo_snuc())


@router.get(
    "/unidades-conservacao/por-esfera",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #13] Unidades de Conservação por esfera (federal/estadual/municipal)",
)
async def get_uc_por_esfera(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).uc_por_esfera())


@router.get(
    "/terras-indigenas/por-fase",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #14] Terras Indígenas por fase de demarcação",
)
async def get_ti_por_fase(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).ti_por_fase())


@router.get(
    "/assentamentos/por-modalidade",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #18] Assentamentos rurais por modalidade",
)
async def get_assentamentos_por_modalidade(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).assentamentos_por_modalidade())


@router.get(
    "/assentamentos/familias-por-estado",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #18] Total de famílias em assentamentos por estado",
)
async def get_assentamentos_familias_por_estado(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    return BasicResponse(data=await AnalyticsService(session).assentamentos_familias_por_estado())


# --- Sobreposições ---

@router.get(
    "/sobreposicoes/resumo",
    response_model=BasicResponse[ResumoSobreposicoes],
    summary="[RF-07 #13-15, #18] Imóveis com sobreposição em UC, TI, quilombos e assentamentos",
)
async def get_resumo_sobreposicoes(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[ResumoSobreposicoes]:
    return BasicResponse(data=await AnalyticsService(session).resumo_sobreposicoes())
