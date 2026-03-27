# -*- coding: utf-8 -*-
from fastapi import FastAPI

from router.controller.index import (
    get_desmatamento_alertas_por_tipo,
    get_desmatamento_area_por_estado,
    get_imoveis_area_por_estado,
    get_imoveis_por_status_car,
    get_queimadas_focos_por_estado,
    get_queimadas_focos_por_mes,
    get_queimadas_ultimo_incendio,
    get_resumo_sobreposicoes,
)
from schemas.index import (
    RespostaAgrupada,
    RespostaTemporalQueimada,
    RespostaUltimoIncendio,
    ResumoSobreposicoes,
)


def define_routes(app: FastAPI) -> None:
    # RF-07 #1 — Área total das propriedades por estado
    app.add_api_route(
        "/analytics/imoveis/area-por-estado",
        get_imoveis_area_por_estado,
        methods=["GET"],
        response_model=RespostaAgrupada,
        summary="[RF-07 #1] Área total (ha) dos imóveis rurais por estado",
        tags=["Analytics"],
    )

    # RF-07 #17 — Status do CAR
    app.add_api_route(
        "/analytics/imoveis/status-car",
        get_imoveis_por_status_car,
        methods=["GET"],
        response_model=RespostaAgrupada,
        summary="[RF-07 #17] Distribuição de imóveis por situação cadastral (CAR)",
        tags=["Analytics"],
    )

    # RF-07 #6 — Área desmatada por estado (suporta filtro 12 meses)
    app.add_api_route(
        "/analytics/desmatamento/area-por-estado",
        get_desmatamento_area_por_estado,
        methods=["GET"],
        response_model=RespostaAgrupada,
        summary="[RF-07 #6] Área desmatada (ha) por estado — query param: ultimos_12_meses",
        tags=["Analytics"],
    )

    # RF-07 #7 — Alertas de desmatamento por tipo
    app.add_api_route(
        "/analytics/desmatamento/alertas-por-tipo",
        get_desmatamento_alertas_por_tipo,
        methods=["GET"],
        response_model=RespostaAgrupada,
        summary="[RF-07 #7] Contagem de alertas de desmatamento por tipo",
        tags=["Analytics"],
    )

    # RF-07 #8 — Focos de incêndio por estado
    app.add_api_route(
        "/analytics/queimadas/focos-por-estado",
        get_queimadas_focos_por_estado,
        methods=["GET"],
        response_model=RespostaAgrupada,
        summary="[RF-07 #8] Focos de incêndio por estado",
        tags=["Analytics"],
    )

    # RF-07 #8 — Focos de incêndio por mês (série temporal)
    app.add_api_route(
        "/analytics/queimadas/focos-por-mes",
        get_queimadas_focos_por_mes,
        methods=["GET"],
        response_model=RespostaTemporalQueimada,
        summary="[RF-07 #8] Série temporal de focos de incêndio por mês",
        tags=["Analytics"],
    )

    # RF-07 #9 — Data do último incêndio por estado
    app.add_api_route(
        "/analytics/queimadas/ultimo-incendio-por-estado",
        get_queimadas_ultimo_incendio,
        methods=["GET"],
        response_model=RespostaUltimoIncendio,
        summary="[RF-07 #9] Data do último incêndio detectado por estado",
        tags=["Analytics"],
    )

    # RF-07 #13, #14, #15, #18 — Sobreposições com áreas especiais
    app.add_api_route(
        "/analytics/sobreposicoes/resumo",
        get_resumo_sobreposicoes,
        methods=["GET"],
        response_model=ResumoSobreposicoes,
        summary="[RF-07 #13-15, #18] Imóveis com sobreposição em UC, TI, quilombos e assentamentos",
        tags=["Analytics"],
    )
