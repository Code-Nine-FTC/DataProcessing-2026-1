# -*- coding: utf-8 -*-
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.index import (
    RespostaScoreAssentamentos,
    RespostaScoreImoveis,
    ResumoAmbientalImovel,
    ResumoScoreAmbiental,
    ScoreAssentamento,
    ScoreImovel,
)
from api.services.score_ambiental_service import ScoreAmbientalService
from api.utils.basic_response import BasicResponse
from api.utils.error_handlers import AppException
from api.utils.log import Log


class ScoreAmbientalHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._service = ScoreAmbientalService(session)
        self._log = Log()

    async def score_imoveis(
        self,
        estado_sigla: Optional[str],
        municipio_id: Optional[int],
        limite: int,
    ) -> BasicResponse[RespostaScoreImoveis]:
        try:
            data = await self._service.score_imoveis(estado_sigla, municipio_id, limite)
            return BasicResponse(data=data)
        except HTTPException:
            raise
        except Exception as exc:
            self._log.error(msg=f"Erro ao calcular score ambiental de imóveis: {exc}")
            raise AppException(
                "Erro ao calcular score ambiental de imóveis.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="score_imoveis_error",
            ) from exc

    async def score_imovel_detalhe(self, imovel_id: UUID) -> BasicResponse[ScoreImovel]:
        try:
            data = await self._service.score_imovel_detalhe(str(imovel_id))
            return BasicResponse(data=data)
        except HTTPException:
            raise
        except Exception as exc:
            self._log.error(msg=f"Erro ao calcular score ambiental do imóvel {imovel_id}: {exc}")
            raise AppException(
                "Erro ao calcular score ambiental do imóvel.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="score_imovel_error",
            ) from exc

    async def score_assentamentos(
        self,
        estado_sigla: Optional[str],
        municipio_id: Optional[int],
        limite: int,
    ) -> BasicResponse[RespostaScoreAssentamentos]:
        try:
            data = await self._service.score_assentamentos(
                estado_sigla, municipio_id, limite
            )
            return BasicResponse(data=data)
        except HTTPException:
            raise
        except Exception as exc:
            self._log.error(msg=f"Erro ao calcular score ambiental de assentamentos: {exc}")
            raise AppException(
                "Erro ao calcular score ambiental de assentamentos.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="score_assentamentos_error",
            ) from exc

    async def score_assentamento_detalhe(
        self, assentamento_id: UUID
    ) -> BasicResponse[ScoreAssentamento]:
        try:
            data = await self._service.score_assentamento_detalhe(str(assentamento_id))
            return BasicResponse(data=data)
        except HTTPException:
            raise
        except Exception as exc:
            self._log.error(
                msg=f"Erro ao calcular score ambiental do assentamento {assentamento_id}: {exc}"
            )
            raise AppException(
                "Erro ao calcular score ambiental do assentamento.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="score_assentamento_error",
            ) from exc

    async def resumo_ambiental_imovel(
        self, imovel_id: UUID
    ) -> BasicResponse[ResumoAmbientalImovel]:
        try:
            data = await self._service.resumo_ambiental_imovel(str(imovel_id))
            return BasicResponse(data=data)
        except HTTPException:
            raise
        except Exception as exc:
            self._log.error(
                msg=f"Erro ao gerar resumo ambiental do imóvel {imovel_id}: {exc}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao gerar resumo ambiental do imóvel",
            )

    async def resumo(
        self,
        estado_sigla: Optional[str],
        municipio_id: Optional[int],
        limite_amostra: int,
    ) -> BasicResponse[ResumoScoreAmbiental]:
        try:
            data = await self._service.resumo(
                estado_sigla=estado_sigla,
                municipio_id=municipio_id,
                limite_amostra=limite_amostra,
            )
            return BasicResponse(data=data)
        except HTTPException:
            raise
        except Exception as exc:
            self._log.error(msg=f"Erro ao gerar resumo de score ambiental: {exc}")
            raise AppException(
                "Erro ao gerar resumo de score ambiental.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="score_resumo_error",
            ) from exc
