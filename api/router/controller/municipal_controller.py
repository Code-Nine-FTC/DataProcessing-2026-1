# -*- coding: utf-8 -*-
from api.schemas.municipal import ResponseMunicipal
from models.db_model import Municipio
from sqlalchemy.ext.asyncio import AsyncSession
from api.utils.log import Log
from api.utils.basic_response import BasicResponse
from fastapi import HTTPException, status


class MunicipalHandler:
    def __init__(self, session: AsyncSession, municipio_id: int | None = None) -> None:
        self._session = session
        self._municipio_id = municipio_id
        self._data: list[ResponseMunicipal] = []

    async def execute(self) -> BasicResponse[list[ResponseMunicipal]]:
        try:
            return await self._fetch_data()
        except Exception as e:
            Log.error(f"Erro ao buscar dados: {e}")
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Erro: {e.detail}",
            )


    async def _fetch_data(self) -> list[ResponseMunicipal]:
        results = await Municipio.get_dados_municipais(self._session, self._municipio_id)
        self._data = [ResponseMunicipal(**row._asdict()) for row in results]
        return self._data