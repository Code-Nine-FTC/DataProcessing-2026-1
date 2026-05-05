# -*- coding: utf-8 -*-
from sqlalchemy import select, func, desc, cast, Float
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from models.db_model import (
    Estado, Municipio, QueimadaEvento, DesmatamentoAlerta, 
    TerraIndigena, TerritorioQuilombola, UnidadeConservacao, 
    ImovelRural
)
from api.schemas.dashboard import DashboardCompleto, EstadoKpis, RankingItem
from api.utils.log import Log
from api.utils.basic_response import BasicResponse

class DashboardHandler:
    def __init__(self, session: AsyncSession, sigla_estado: str = "SP") -> None:
        self._session = session
        self._sigla = sigla_estado
        self._log = Log()

    async def execute(self) -> BasicResponse[DashboardCompleto]:
        try:
            estado_res = await self._session.execute(
                select(Estado).where(Estado.sigla == self._sigla)
            )
            estado = estado_res.scalar_one_or_none()
            
            if not estado:
                raise HTTPException(status_code=404, detail="Estado não encontrado")

            data = await self._assemble_dashboard(estado)
            return BasicResponse(data=data)

        except Exception as e:
            self._log.error(msg=f"Erro no DashboardHandler: {e}")
            if isinstance(e, HTTPException): raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro interno: {str(e)}"
            )

    async def _assemble_dashboard(self, estado: Estado) -> DashboardCompleto:
        area_uc = await self._get_area(UnidadeConservacao, estado.id)
        area_ti = await self._get_area(TerraIndigena, estado.id)

        kpis = EstadoKpis(
            id=estado.id,
            nome=estado.nome,
            sigla=estado.sigla,
            total_municipios=await self._get_total(Municipio, estado.id, True),
            area_protegida_total_ha=float(area_uc + area_ti), # Soma segura
            focos_queimada_periodo=await self._get_total(QueimadaEvento, estado.id),
            total_alertas_desmatamento=await self._get_total(DesmatamentoAlerta, estado.id),
            total_imoveis_rurais=await self._get_total(ImovelRural, estado.id)
        )

        rankings = {
            "queimadas": await self._fetch_top_15(QueimadaEvento, "focos", estado.id, True),
            "desmatamento": await self._fetch_top_15(DesmatamentoAlerta, "ha", estado.id),
            "terras_indigenas": await self._fetch_top_15(TerraIndigena, "ha", estado.id),
            "quilombolas": await self._fetch_top_15(TerritorioQuilombola, "ha", estado.id),
            "unidades_conservacao": await self._fetch_top_15(UnidadeConservacao, "ha", estado.id),
            "imoveis_rurais": await self._fetch_top_15(ImovelRural, "ha", estado.id)
        }

        return DashboardCompleto(estado=kpis, rankings=rankings)

    async def _get_total(self, model, estado_id, is_mun=False) -> int:
        q = select(func.count(model.id))
        q = q.where(model.estado_id == estado_id) if is_mun else q.join(Municipio).where(Municipio.estado_id == estado_id)
        res = await self._session.execute(q)
        return int(res.scalar() or 0)

    async def _get_area(self, model, estado_id) -> float:
        """Helper com cast explícito para float"""
        q = select(func.sum(model.area_ha)).join(Municipio).where(Municipio.estado_id == estado_id)
        res = await self._session.execute(q)
        valor = res.scalar()
        return float(valor) if valor is not None else 0.0

    async def _fetch_top_15(self, model, unit, estado_id, is_count=False):
        val_col = func.count(model.id) if is_count else func.sum(model.area_ha)
        
        total_query = select(val_col).join(Municipio).where(Municipio.estado_id == estado_id)
        total_res = await self._session.execute(total_query)
        total_st = float(total_res.scalar() or 1) 

        query = (
            select(
                Municipio.nome, 
                Estado.sigla, 
                cast(val_col, Float).label("v"), # Cast no SQL
                (cast(val_col, Float) / total_st * 100).label("p")
            )
            .join(Municipio, model.municipio_id == Municipio.id)
            .join(Estado, Municipio.estado_id == Estado.id)
            .where(Estado.id == estado_id)
            .group_by(Municipio.id, Estado.sigla)
            .order_by(desc("v")).limit(10)
        )
        res = await self._session.execute(query)
        return [
            RankingItem(
                municipio=r.nome, 
                uf=r.sigla, 
                valor=float(r.v or 0), 
                unidade=unit, 
                percentual_do_estado=round(float(r.p or 0), 2)
            ) for r in res
        ]