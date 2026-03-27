# -*- coding: utf-8 -*-
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.index import (
    GrupoItem,
    RespostaAgrupada,
    RespostaTemporalQueimada,
    RespostaUltimoIncendio,
    ResumoSobreposicoes,
    SerieTemporalItem,
    UltimoIncendioItem,
)


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # RF-07 #1 — Área total das propriedades agrupada por estado
    async def imoveis_area_por_estado(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT e.sigla AS label,
                       ROUND(SUM(i.area_ha)::numeric, 2)::float AS valor
                FROM imovel_rural i
                JOIN municipio m ON m.id = i.municipio_id
                JOIN estado e ON e.id = m.estado_id
                WHERE i.area_ha IS NOT NULL
                GROUP BY e.sigla
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=round(sum(g.valor for g in grupos), 2))

    # RF-07 #6 — Área desmatada (ha) por estado (últimos 12 meses)
    async def desmatamento_area_por_estado(self, ultimos_12_meses: bool = False) -> RespostaAgrupada:
        filtro_data = (
            "AND d.data_ocorrencia >= CURRENT_DATE - INTERVAL '12 months'"
            if ultimos_12_meses
            else ""
        )
        result = await self._session.execute(
            text(f"""
                SELECT e.sigla AS label,
                       ROUND(SUM(d.area_ha)::numeric, 2)::float AS valor
                FROM desmatamento_alerta d
                JOIN municipio m ON m.id = d.municipio_id
                JOIN estado e ON e.id = m.estado_id
                WHERE d.area_ha IS NOT NULL {filtro_data}
                GROUP BY e.sigla
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=round(sum(g.valor for g in grupos), 2))

    # RF-07 #7 — Alertas de desmatamento agrupados por tipo
    async def desmatamento_alertas_por_tipo(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT COALESCE(tipo_alerta, 'Não informado') AS label,
                       COUNT(*)::float AS valor
                FROM desmatamento_alerta
                GROUP BY tipo_alerta
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=sum(g.valor for g in grupos))

    # RF-07 #8 — Focos de incêndio agrupados por estado
    async def queimadas_focos_por_estado(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT e.sigla AS label, COUNT(q.id)::float AS valor
                FROM queimada_evento q
                JOIN municipio m ON m.id = q.municipio_id
                JOIN estado e ON e.id = m.estado_id
                GROUP BY e.sigla
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=sum(g.valor for g in grupos))

    # RF-07 #8 — Focos de incêndio por mês (série temporal)
    async def queimadas_focos_por_mes(self) -> RespostaTemporalQueimada:
        result = await self._session.execute(
            text("""
                SELECT TO_CHAR(data_ocorrencia, 'YYYY-MM') AS periodo,
                       COUNT(*)::int AS total
                FROM queimada_evento
                WHERE data_ocorrencia IS NOT NULL
                GROUP BY periodo
                ORDER BY periodo
            """)
        )
        series = [SerieTemporalItem(periodo=row.periodo, total=row.total) for row in result]
        return RespostaTemporalQueimada(series=series, total=sum(s.total for s in series))

    # RF-07 #9 — Data do último incêndio por estado
    async def queimadas_ultimo_incendio_por_estado(self) -> RespostaUltimoIncendio:
        result = await self._session.execute(
            text("""
                SELECT e.sigla AS estado,
                       TO_CHAR(MAX(q.data_ocorrencia), 'YYYY-MM-DD') AS data_ultimo_incendio
                FROM queimada_evento q
                JOIN municipio m ON m.id = q.municipio_id
                JOIN estado e ON e.id = m.estado_id
                WHERE q.data_ocorrencia IS NOT NULL
                GROUP BY e.sigla
                ORDER BY e.sigla
            """)
        )
        estados = [
            UltimoIncendioItem(estado=row.estado, data_ultimo_incendio=row.data_ultimo_incendio)
            for row in result
        ]
        return RespostaUltimoIncendio(estados=estados)

    # RF-07 #17 — Status do CAR (situação cadastral dos imóveis)
    async def imoveis_por_status_car(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT COALESCE(situacao_cadastral, 'Não informado') AS label,
                       COUNT(*)::float AS valor
                FROM imovel_rural
                GROUP BY situacao_cadastral
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=sum(g.valor for g in grupos))

    # RF-07 #13, #14, #15, #18 — Sobreposições de imóveis com áreas especiais
    async def resumo_sobreposicoes(self) -> ResumoSobreposicoes:
        result = await self._session.execute(
            text("""
                SELECT
                    (SELECT COUNT(DISTINCT imovel_rural_id) FROM rel_imovel_uc)::int           AS qtd_uc,
                    (SELECT COUNT(DISTINCT imovel_rural_id) FROM rel_imovel_ti)::int            AS qtd_ti,
                    (SELECT COUNT(DISTINCT imovel_rural_id) FROM rel_imovel_quilombo)::int      AS qtd_quilombo,
                    (SELECT COUNT(DISTINCT imovel_rural_id) FROM rel_imovel_assentamento)::int  AS qtd_assentamento,
                    (SELECT COUNT(*) FROM imovel_rural)::int                                    AS total_imoveis
            """)
        )
        row = result.one()
        return ResumoSobreposicoes(
            imoveis_com_sobreposicao_uc=row.qtd_uc,
            imoveis_com_sobreposicao_ti=row.qtd_ti,
            imoveis_com_sobreposicao_quilombola=row.qtd_quilombo,
            imoveis_com_sobreposicao_assentamento=row.qtd_assentamento,
            total_imoveis=row.total_imoveis,
        )
