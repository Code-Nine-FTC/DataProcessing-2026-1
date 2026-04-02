# -*- coding: utf-8 -*-
from api.schemas.imovel import ResponseImovel, ResponseQueimadaRelacao, ResponseDesmatamentoRelacao
from models.db_model import ImovelRural
from sqlalchemy.ext.asyncio import AsyncSession
from api.utils.log import Log
from api.utils.basic_response import BasicResponse
from fastapi import HTTPException


class ImovelHandler:
    def __init__(self, session: AsyncSession, imovel_id: str) -> None:
        self._session = session
        self._imovel_id = imovel_id
        self._log = Log()

    async def execute_detail(self) -> BasicResponse[ResponseImovel]:
        try:
            row = await ImovelRural.get_by_id(self._session, self._imovel_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Imóvel não encontrado")
            return BasicResponse(data=ResponseImovel(**row._asdict()))
        except HTTPException:
            raise
        except Exception as e:
            self._log.error(msg=f"Erro ao buscar imóvel: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def execute_queimadas(self) -> BasicResponse[list[ResponseQueimadaRelacao]]:
        try:
            rows = await ImovelRural.get_queimadas(self._session, self._imovel_id)
            data = [ResponseQueimadaRelacao(**row._asdict()) for row in rows]
            return BasicResponse(data=data)
        except Exception as e:
            self._log.error(msg=f"Erro ao buscar queimadas do imóvel: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def execute_desmatamentos(self) -> BasicResponse[list[ResponseDesmatamentoRelacao]]:
        try:
            rows = await ImovelRural.get_desmatamentos(self._session, self._imovel_id)
            data = [ResponseDesmatamentoRelacao(**row._asdict()) for row in rows]
            return BasicResponse(data=data)
        except Exception as e:
            self._log.error(msg=f"Erro ao buscar desmatamentos do imóvel: {e}")
            raise HTTPException(status_code=500, detail=str(e))
