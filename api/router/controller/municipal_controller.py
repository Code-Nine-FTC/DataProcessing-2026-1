# -*- coding: utf-8 -*-
from api.schemas.municipal import ResponseMunicipal, GeoJSONGeometry, ResponseImovelRuralIntersection
from models.db_model import Municipio, ImovelRural
from sqlalchemy.ext.asyncio import AsyncSession
from api.utils.log import Log
from api.utils.basic_response import BasicResponse
from fastapi import HTTPException, status
import json


class MunicipalHandler:
    def __init__(self, session: AsyncSession, municipio_id: int | None = None) -> None:
        self._session = session
        self._municipio_id = municipio_id
        self._data: list[ResponseMunicipal] = []
        self._log = Log()

    async def execute(self) -> BasicResponse[list[ResponseMunicipal]]:
        try:
            self._data = await self._fetch_data()
            return BasicResponse(data=self._data)
        except HTTPException as e:
            self._log.error(msg=f"Erro ao buscar dados: {e.detail}")
            raise e
        except Exception as e:
            self._log.error(msg=f"Erro inesperado ao buscar dados: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro interno do servidor: {e}",
            )

    async def _fetch_data(self) -> list[ResponseMunicipal]:
        results = await Municipio.get_dados_municipais(self._session, self._municipio_id)
        self._data = [ResponseMunicipal(**row._asdict()) for row in results]
        return self._data


class IntersectionHandler:
    def __init__(self, session: AsyncSession, geojson_geometry: GeoJSONGeometry) -> None:
        self._session = session
        self._geojson_geometry = geojson_geometry
        self._data: list[ResponseImovelRuralIntersection] = []
        self._log = Log()

    async def execute(self) -> BasicResponse[list[ResponseImovelRuralIntersection]]:
        try:
            geojson_str = json.dumps(self._geojson_geometry.geometry)
            results = await ImovelRural.get_imoveis_intersecting_geometry(self._session, geojson_str)
            self._data = [ResponseImovelRuralIntersection(**row._asdict()) for row in results]
            return BasicResponse(data=self._data)
        except HTTPException as e:
            self._log.error(msg=f"Erro ao buscar imóveis por interseção: {e.detail}")
            raise e
        except Exception as e:
            self._log.error(msg=f"Erro inesperado ao buscar imóveis por interseção: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro interno do servidor: {e}",
            )