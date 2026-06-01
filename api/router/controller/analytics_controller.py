# -*- coding: utf-8 -*-
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.index import RespostaAgrupada
from api.services.index import AnalyticsService
from api.utils.basic_response import BasicResponse
from api.utils.error_handlers import AppException
from api.utils.log import Log


class AnalyticsMunicipalHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._log = Log()

    async def imoveis_area_por_municipio(self) -> BasicResponse[RespostaAgrupada]:
        try:
            data = await AnalyticsService(self._session).imoveis_area_por_municipio()
            return BasicResponse(data=data)
        except Exception as exc:
            self._log.error(msg=f"Erro ao buscar área de imóveis por município: {exc}")
            raise AppException(
                "Erro ao buscar área de imóveis por município.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="analytics_imoveis_area_error",
            ) from exc

    async def queimadas_focos_por_municipio(self) -> BasicResponse[RespostaAgrupada]:
        try:
            data = await AnalyticsService(self._session).queimadas_focos_por_municipio()
            return BasicResponse(data=data)
        except Exception as exc:
            self._log.error(msg=f"Erro ao buscar focos de incêndio por município: {exc}")
            raise AppException(
                "Erro ao buscar focos de incêndio por município.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="analytics_queimadas_focos_error",
            ) from exc
