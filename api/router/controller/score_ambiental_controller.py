# -*- coding: utf-8 -*-
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.index import (
    RespostaScoreAssentamentos,
    RespostaScoreImoveis,
    ResumoScoreAmbiental,
    ScoreAssentamento,
    ScoreImovel,
)
from api.services.score_ambiental_service import ScoreAmbientalService
from api.utils.basic_response import BasicResponse
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
        except Exception as exc:
            self._log.error(msg=f"Erro ao calcular score ambiental de imóveis: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao calcular score ambiental de imóveis",
            )

    async def score_imovel_detalhe(self, imovel_id: UUID) -> BasicResponse[ScoreImovel]:
        try:
            data = await self._service.score_imovel_detalhe(str(imovel_id))
            return BasicResponse(data=data)
        except HTTPException:
            raise
        except Exception as exc:
            self._log.error(msg=f"Erro ao calcular score ambiental do imóvel {imovel_id}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao calcular score ambiental do imóvel",
            )

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
        except Exception as exc:
            self._log.error(msg=f"Erro ao calcular score ambiental de assentamentos: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao calcular score ambiental de assentamentos",
            )

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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao calcular score ambiental do assentamento",
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
        except Exception as exc:
            self._log.error(msg=f"Erro ao gerar resumo de score ambiental: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao gerar resumo de score ambiental",
            )
