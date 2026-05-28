# -*- coding: utf-8 -*-
from api.schemas.municipal import ResponseMunicipal, GeoJSONGeometry, ResponseImovelRuralIntersection, ResponseMunicipioSearch
from models.db_model import Municipio, ImovelRural, Estado
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from api.utils.log import Log
from api.utils.basic_response import BasicResponse
from api.utils.error_handlers import AppException
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
            raise
        except Exception as e:
            self._log.error(msg=f"Erro inesperado ao buscar dados: {e}")
            raise AppException(
                "Erro interno do servidor.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="internal_server_error",
            ) from e

    async def _fetch_data(self) -> list[ResponseMunicipal]:
        results = await Municipio.get_dados_municipais(self._session, self._municipio_id)
        self._data = [ResponseMunicipal(**row._asdict()) for row in results]
        for mun in self._data:
            for schema_list in (
                mun.imoveis_rurais, mun.unidades_conservacao, mun.terras_indigenas,
                mun.assentamentos, mun.quilombolas, mun.alertas_desmatamento,
            ):
                for geom in schema_list:
                    if geom.area_ha is not None:
                        geom.area_ha = round(geom.area_ha, 4)
        return self._data


class MunicipioSearchHandler:
    def __init__(self, session: AsyncSession, search: str | None = None, estado_sigla: str | None = None) -> None:
        self._session = session
        self._search = search
        self._estado_sigla = estado_sigla
        self._data: list[ResponseMunicipioSearch] = []
        self._log = Log()

    async def execute(self) -> BasicResponse[list[ResponseMunicipioSearch]]:
        try:
            self._data = await self._fetch_data()
            return BasicResponse(data=self._data)
        except HTTPException as e:
            self._log.error(msg=f"Erro ao buscar municípios: {e.detail}")
            raise
        except Exception as e:
            self._log.error(msg=f"Erro inesperado ao buscar municípios: {e}")
            raise AppException(
                "Erro interno do servidor.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="internal_server_error",
            ) from e

    async def _fetch_data(self) -> list[ResponseMunicipioSearch]:
        query = select(Municipio, Estado.sigla).join(Estado, Municipio.estado_id == Estado.id).order_by(Municipio.nome)

        if self._search:
            search_normalized = self._search.strip().lower()
            query = query.where(Municipio.nome_normalizado.ilike(f"%{search_normalized}%"))
        if self._estado_sigla:
            query = query.where(Estado.sigla == self._estado_sigla.upper())

        result = await self._session.execute(query)
        rows = result.all()

        self._data = [
            ResponseMunicipioSearch(
                id=municipio.id,
                nome=municipio.nome,
                codigo_ibge=municipio.codigo_ibge,
                estado_sigla=sigla,
            )
            for municipio, sigla in rows
        ]
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
            for item in self._data:
                if item.area_ha is not None:
                    item.area_ha = round(item.area_ha, 4)
            return BasicResponse(data=self._data)
        except HTTPException as e:
            self._log.error(msg=f"Erro ao buscar imóveis por interseção: {e.detail}")
            raise
        except Exception as e:
            self._log.error(msg=f"Erro inesperado ao buscar imóveis por interseção: {e}")
            raise AppException(
                "Erro interno do servidor.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="internal_server_error",
            ) from e
