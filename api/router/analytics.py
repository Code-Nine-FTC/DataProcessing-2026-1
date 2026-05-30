# -*- coding: utf-8 -*-
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.index import (
    RespostaAgrupada,
    RespostaBuffer,
    RespostaProximidade,
    RespostaProximidadeQueimada,
    RespostaScoreAssentamentos,
    RespostaScoreImoveis,
    RespostaSobreposicoesAreas,
    RespostaQueimadaDentroFora,
    RespostaTemporalDesmatamento,
    RespostaTemporalQueimada,
    RespostaUltimoIncendio,
    ResumoAmbientalImovel,
    ResumoScoreAmbiental,
    ResumoSobreposicoes,
    ScoreAssentamento,
    ScoreImovel,
    TipoAreaSobreposicao,
)
from api.router.controller.analytics_controller import AnalyticsMunicipalHandler
from api.router.controller.score_ambiental_controller import ScoreAmbientalHandler
from api.services.index import AnalyticsService
from api.utils.basic_response import BasicResponse
from api.utils.cache import cached, DEFAULT_TTL
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
    svc = AnalyticsService(session)
    return BasicResponse(data=await cached("imoveis:area_por_estado", DEFAULT_TTL, svc.imoveis_area_por_estado))


@router.get(
    "/imoveis/area-por-municipio",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #1] Área total (ha) dos imóveis rurais por município",
)
async def get_imoveis_area_por_municipio(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("imoveis:area_por_municipio", DEFAULT_TTL, svc.imoveis_area_por_municipio)
    )


@router.get(
    "/imoveis/status-car",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #17] Distribuição de imóveis por situação cadastral (CAR)",
)
async def get_imoveis_por_status_car(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(data=await cached("imoveis:status_car", DEFAULT_TTL, svc.imoveis_por_status_car))


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
    svc = AnalyticsService(session)
    cache_key = f"desmatamento:area_por_estado:{ultimos_12_meses}"
    return BasicResponse(
        data=await cached(cache_key, DEFAULT_TTL, lambda: svc.desmatamento_area_por_estado(ultimos_12_meses))
    )


@router.get(
    "/desmatamento/area-por-mes",
    response_model=BasicResponse[RespostaTemporalDesmatamento],
    summary="[RF-07 #6] Série temporal de área desmatada (ha) por mês",
)
async def get_desmatamento_area_por_mes(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaTemporalDesmatamento]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("desmatamento:area_por_mes", DEFAULT_TTL, svc.desmatamento_area_por_mes)
    )


@router.get(
    "/desmatamento/alertas-por-tipo",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #7] Contagem de alertas de desmatamento por tipo",
)
async def get_desmatamento_alertas_por_tipo(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("desmatamento:alertas_por_tipo", DEFAULT_TTL, svc.desmatamento_alertas_por_tipo)
    )


@router.get(
    "/desmatamento/area-em-imoveis-por-estado",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #7] Área de desmatamento sobreposta a imóveis rurais por estado",
)
async def get_desmatamento_area_em_imoveis(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("desmatamento:area_em_imoveis", DEFAULT_TTL, svc.desmatamento_area_em_imoveis)
    )


@router.get(
    "/desmatamento/buffer-imoveis",
    response_model=BasicResponse[RespostaBuffer],
    summary="[RF-04] Área de influência (ST_Buffer) de alertas — imóveis dentro do raio",
)
async def get_desmatamento_buffer_imoveis(
    raio_km: float = Query(5.0, description="Raio do buffer em km", ge=0.1, le=200.0),
    limite: int = Query(100, description="Número máximo de resultados", ge=1, le=1000),
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaBuffer]:
    return BasicResponse(
        data=await AnalyticsService(session).desmatamento_buffer_imoveis(raio_km, limite)
    )


@router.get(
    "/desmatamento/distancia-alertas-imoveis",
    response_model=BasicResponse[RespostaProximidade],
    summary="[RF-04] Distância (ST_Distance) entre imóveis rurais e alertas de desmatamento próximos",
)
async def get_desmatamento_distancia_alertas(
    raio_km: float = Query(10.0, description="Raio de busca em km", ge=0.1, le=500.0),
    limite: int = Query(100, description="Número máximo de resultados", ge=1, le=1000),
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaProximidade]:
    return BasicResponse(
        data=await AnalyticsService(session).desmatamento_distancia_alertas(raio_km, limite)
    )


# --- Queimadas ---

@router.get(
    "/queimadas/distancia-imoveis",
    response_model=BasicResponse[RespostaProximidadeQueimada],
    summary="[RF-04] Distância (ST_Distance) entre imóveis rurais e focos de queimada próximos",
)
async def get_queimadas_distancia_imoveis(
    raio_km: float = Query(10.0, description="Raio de busca em km", ge=0.1, le=500.0),
    limite: int = Query(100, description="Número máximo de resultados", ge=1, le=1000),
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaProximidadeQueimada]:
    return BasicResponse(
        data=await AnalyticsService(session).queimadas_distancia_imoveis(raio_km, limite)
    )

@router.get(
    "/queimadas/focos-por-estado",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #8] Focos de incêndio por estado",
)
async def get_queimadas_focos_por_estado(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("queimadas:focos_por_estado", DEFAULT_TTL, svc.queimadas_focos_por_estado)
    )


@router.get(
    "/queimadas/focos-por-municipio",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #8] Focos de incêndio por município",
)
async def get_queimadas_focos_por_municipio(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("queimadas:focos_por_municipio", DEFAULT_TTL, svc.queimadas_focos_por_municipio)
    )


@router.get(
    "/queimadas/focos-por-mes",
    response_model=BasicResponse[RespostaTemporalQueimada],
    summary="[RF-07 #8] Série temporal de focos de incêndio por mês",
)
async def get_queimadas_focos_por_mes(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaTemporalQueimada]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("queimadas:focos_por_mes", DEFAULT_TTL, svc.queimadas_focos_por_mes)
    )


@router.get(
    "/queimadas/focos-por-bioma",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #8] Focos de incêndio por bioma",
)
async def get_queimadas_focos_por_bioma(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("queimadas:focos_por_bioma", DEFAULT_TTL, svc.queimadas_focos_por_bioma)
    )


@router.get(
    "/queimadas/intensidade-por-bioma",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #8] Intensidade média (FRP) de queimadas por bioma",
)
async def get_queimadas_intensidade_por_bioma(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("queimadas:intensidade_por_bioma", DEFAULT_TTL, svc.queimadas_intensidade_por_bioma)
    )


@router.get(
    "/queimadas/dias-sem-chuva-por-estado",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #8] Média de dias sem chuva no momento do foco, por estado",
)
async def get_queimadas_dias_sem_chuva(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("queimadas:dias_sem_chuva", DEFAULT_TTL, svc.queimadas_dias_sem_chuva_por_estado)
    )


@router.get(
    "/queimadas/risco-medio-por-estado",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #8] Risco médio de fogo por estado",
)
async def get_queimadas_risco_medio_por_estado(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("queimadas:risco_medio", DEFAULT_TTL, svc.queimadas_risco_medio_por_estado)
    )


@router.get(
    "/queimadas/dentro-fora-imoveis",
    response_model=BasicResponse[RespostaQueimadaDentroFora],
    summary="[RF-07 #8] Queimadas dentro vs. fora de imóveis rurais",
)
async def get_queimadas_dentro_fora(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaQueimadaDentroFora]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("queimadas:dentro_fora", DEFAULT_TTL, svc.queimadas_dentro_fora_imoveis)
    )


@router.get(
    "/queimadas/ultimo-incendio-por-estado",
    response_model=BasicResponse[RespostaUltimoIncendio],
    summary="[RF-07 #9] Data do último incêndio detectado por estado",
)
async def get_queimadas_ultimo_incendio(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaUltimoIncendio]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("queimadas:ultimo_incendio", DEFAULT_TTL, svc.queimadas_ultimo_incendio_por_estado)
    )


# --- Áreas Protegidas ---

@router.get(
    "/unidades-conservacao/por-grupo-snuc",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #13] Unidades de Conservação por grupo SNUC",
)
async def get_uc_por_grupo_snuc(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(data=await cached("uc:por_grupo_snuc", DEFAULT_TTL, svc.uc_por_grupo_snuc))


@router.get(
    "/unidades-conservacao/por-esfera",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #13] Unidades de Conservação por esfera (federal/estadual/municipal)",
)
async def get_uc_por_esfera(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(data=await cached("uc:por_esfera", DEFAULT_TTL, svc.uc_por_esfera))


@router.get(
    "/terras-indigenas/por-fase",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #14] Terras Indígenas por fase de demarcação",
)
async def get_ti_por_fase(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(data=await cached("ti:por_fase", DEFAULT_TTL, svc.ti_por_fase))


@router.get(
    "/assentamentos/por-modalidade",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #18] Assentamentos rurais por modalidade",
)
async def get_assentamentos_por_modalidade(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(data=await cached("assentamentos:por_modalidade", DEFAULT_TTL, svc.assentamentos_por_modalidade))


@router.get(
    "/assentamentos/familias-por-estado",
    response_model=BasicResponse[RespostaAgrupada],
    summary="[RF-07 #18] Total de famílias em assentamentos por estado",
)
async def get_assentamentos_familias_por_estado(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaAgrupada]:
    svc = AnalyticsService(session)
    return BasicResponse(
        data=await cached("assentamentos:familias_por_estado", DEFAULT_TTL, svc.assentamentos_familias_por_estado)
    )


# --- Sobreposições ---

@router.get(
    "/sobreposicoes/areas",
    response_model=BasicResponse[RespostaSobreposicoesAreas],
    summary="[RF-07 #13-15, #18] Detalhamento de imóveis com sobreposição em áreas especiais",
)
async def get_sobreposicoes_areas(
    tipo_area: TipoAreaSobreposicao = Query(
        TipoAreaSobreposicao.todos,
        description="Filtra por tipo de área: uc, ti, quilombo, assentamento ou todos",
    ),
    limite: int = Query(100, description="Número máximo de resultados", ge=1, le=1000),
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaSobreposicoesAreas]:
    return BasicResponse(data=await AnalyticsService(session).sobreposicoes_areas(tipo_area, limite))


@router.get(
    "/sobreposicoes/resumo",
    response_model=BasicResponse[ResumoSobreposicoes],
    summary="[RF-07 #13-15, #18] Imóveis com sobreposição em UC, TI, quilombos e assentamentos",
)
async def get_resumo_sobreposicoes(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[ResumoSobreposicoes]:
    svc = AnalyticsService(session)
    return BasicResponse(data=await cached("sobreposicoes:resumo", DEFAULT_TTL, svc.resumo_sobreposicoes))


# --- Score Ambiental (ASG) ---

@router.get(
    "/score-ambiental/imoveis",
    response_model=BasicResponse[RespostaScoreImoveis],
    summary="[RF-09] Score ambiental (ASG) dos imóveis rurais",
)
async def get_score_imoveis(
    estado_sigla: Optional[str] = Query(
        None, description="Filtrar por sigla do estado (ex.: SP)", max_length=2
    ),
    municipio_id: Optional[int] = Query(None, description="Filtrar por id do município"),
    limite: int = Query(100, description="Número máximo de resultados", ge=1, le=1000),
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaScoreImoveis]:
    return await ScoreAmbientalHandler(session).score_imoveis(
        estado_sigla, municipio_id, limite
    )


@router.get(
    "/score-ambiental/imoveis/{imovel_id}",
    response_model=BasicResponse[ScoreImovel],
    summary="[RF-09] Score ambiental (ASG) de um imóvel rural específico",
)
async def get_score_imovel_detalhe(
    imovel_id: UUID,
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[ScoreImovel]:
    return await ScoreAmbientalHandler(session).score_imovel_detalhe(imovel_id)


@router.get(
    "/imoveis/{imovel_id}/resumo-ambiental",
    response_model=BasicResponse[ResumoAmbientalImovel],
    summary="[RF-09] Resumo ambiental simplificado de um imóvel para análise rápida",
)
async def get_resumo_ambiental_imovel(
    imovel_id: UUID,
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[ResumoAmbientalImovel]:
    return await ScoreAmbientalHandler(session).resumo_ambiental_imovel(imovel_id)


@router.get(
    "/score-ambiental/assentamentos",
    response_model=BasicResponse[RespostaScoreAssentamentos],
    summary="[RF-09] Score ambiental (ASG) dos assentamentos rurais",
)
async def get_score_assentamentos(
    estado_sigla: Optional[str] = Query(
        None, description="Filtrar por sigla do estado (ex.: SP)", max_length=2
    ),
    municipio_id: Optional[int] = Query(None, description="Filtrar por id do município"),
    limite: int = Query(100, description="Número máximo de resultados", ge=1, le=1000),
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[RespostaScoreAssentamentos]:
    return await ScoreAmbientalHandler(session).score_assentamentos(
        estado_sigla, municipio_id, limite
    )


@router.get(
    "/score-ambiental/assentamentos/{assentamento_id}",
    response_model=BasicResponse[ScoreAssentamento],
    summary="[RF-09] Score ambiental (ASG) de um assentamento rural específico",
)
async def get_score_assentamento_detalhe(
    assentamento_id: UUID,
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[ScoreAssentamento]:
    return await ScoreAmbientalHandler(session).score_assentamento_detalhe(
        assentamento_id
    )


@router.get(
    "/score-ambiental/resumo",
    response_model=BasicResponse[ResumoScoreAmbiental],
    summary="[RF-09] Resumo agregado do score ambiental (ASG) — distribuição por classificação",
)
async def get_score_ambiental_resumo(
    estado_sigla: Optional[str] = Query(
        None, description="Filtrar por sigla do estado (ex.: SP)", max_length=2
    ),
    municipio_id: Optional[int] = Query(None, description="Filtrar por id do município"),
    limite_amostra: int = Query(
        500,
        description="Tamanho da amostra aleatória usada para o resumo",
        ge=1,
        le=5000,
    ),
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[ResumoScoreAmbiental]:
    return await ScoreAmbientalHandler(session).resumo(
        estado_sigla, municipio_id, limite_amostra
    )
