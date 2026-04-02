# -*- coding: utf-8 -*-
from api.schemas.estado import ResponseEstado, ResponseMunicipioSimples
from models.db_model import Estado
from sqlalchemy.ext.asyncio import AsyncSession
from api.utils.log import Log
from api.utils.basic_response import BasicResponse
from fastapi import HTTPException


class EstadoHandler:
    def __init__(self, session: AsyncSession, estado_id: int | None = None) -> None:
        self._session = session
        self._estado_id = estado_id
        self._log = Log()

    async def execute_list(self) -> BasicResponse[list[ResponseEstado]]:
        try:
            rows = await Estado.get_all(self._session)
            data = [ResponseEstado(**row._asdict()) for row in rows]
            return BasicResponse(data=data)
        except Exception as e:
            self._log.error(msg=f"Erro ao buscar estados: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def execute_municipios(self) -> BasicResponse[list[ResponseMunicipioSimples]]:
        try:
            rows = await Estado.get_municipios(self._session, self._estado_id)
            data = [ResponseMunicipioSimples(**row._asdict()) for row in rows]
            return BasicResponse(data=data)
        except Exception as e:
            self._log.error(msg=f"Erro ao buscar municípios do estado: {e}")
            raise HTTPException(status_code=500, detail=str(e))
