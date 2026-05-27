# -*- coding: utf-8 -*-
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.index import (
    BufferResultItem,
    GrupoItem,
    ProximidadeItem,
    ProximidadeQueimadaItem,
    RespostaSobreposicoesAreas,
    QueimadaDentroForaItem,
    RespostaAgrupada,
    RespostaBuffer,
    RespostaProximidade,
    RespostaProximidadeQueimada,
    RespostaQueimadaDentroFora,
    RespostaTemporalDesmatamento,
    RespostaTemporalQueimada,
    RespostaUltimoIncendio,
    ResumoSobreposicoes,
    SobreposicaoAreaItem,
    TipoAreaSobreposicao,
    SerieTemporalAreaItem,
    SerieTemporalItem,
    UltimoIncendioItem,
)
from models.db_model import classificar_nivel_risco_ambiental


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Área total das propriedades por estado
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Área total das propriedades por município
    # ------------------------------------------------------------------
    async def imoveis_area_por_municipio(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT CONCAT(m.nome, ' - ', e.sigla) AS label,
                       ROUND(SUM(i.area_ha)::numeric, 2)::float AS valor
                FROM imovel_rural i
                JOIN municipio m ON m.id = i.municipio_id
                JOIN estado e ON e.id = m.estado_id
                WHERE i.area_ha IS NOT NULL
                GROUP BY m.nome, e.sigla
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=round(sum(g.valor for g in grupos), 2))

    # ------------------------------------------------------------------
    # Área desmatada (ha) por estado, com filtro de 12 meses
    # ------------------------------------------------------------------
    async def desmatamento_area_por_estado(self, ultimos_12_meses: bool = False) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT e.sigla AS label,
                       ROUND(SUM(d.area_ha)::numeric, 2)::float AS valor
                FROM desmatamento_alerta d
                JOIN municipio m ON m.id = d.municipio_id
                JOIN estado e ON e.id = m.estado_id
                WHERE d.area_ha IS NOT NULL
                  AND (NOT :filtrar_12m OR d.data_ocorrencia >= CURRENT_DATE - INTERVAL '12 months')
                GROUP BY e.sigla
                ORDER BY valor DESC
            """),
            {"filtrar_12m": ultimos_12_meses},
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=round(sum(g.valor for g in grupos), 2))

    # ------------------------------------------------------------------
    # Desmatamento: série temporal por mês (área total ha)
    # ------------------------------------------------------------------
    async def desmatamento_area_por_mes(self) -> RespostaTemporalDesmatamento:
        result = await self._session.execute(
            text("""
                SELECT TO_CHAR(data_ocorrencia, 'YYYY-MM') AS periodo,
                       ROUND(SUM(area_ha)::numeric, 2)::float AS area_ha
                FROM desmatamento_alerta
                WHERE data_ocorrencia IS NOT NULL AND area_ha IS NOT NULL
                GROUP BY periodo
                ORDER BY periodo
            """)
        )
        series = [SerieTemporalAreaItem(periodo=row.periodo, area_ha=row.area_ha) for row in result]
        return RespostaTemporalDesmatamento(
            series=series,
            total_ha=round(sum(s.area_ha for s in series), 2),
        )

    # ------------------------------------------------------------------
    # Alertas de desmatamento por tipo (contagem)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Área de desmatamento sobreposta a imóveis rurais
    # ------------------------------------------------------------------
    async def desmatamento_area_em_imoveis(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT e.sigla AS label,
                       ROUND(SUM(rd.area_intersecao_ha)::numeric, 2)::float AS valor
                FROM rel_imovel_desmatamento rd
                JOIN imovel_rural i ON i.id = rd.imovel_rural_id
                JOIN municipio m ON m.id = i.municipio_id
                JOIN estado e ON e.id = m.estado_id
                WHERE rd.area_intersecao_ha IS NOT NULL
                GROUP BY e.sigla
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=round(sum(g.valor for g in grupos), 2))

    # ------------------------------------------------------------------
    # Focos de incêndio por estado
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Focos de incêndio por município
    # ------------------------------------------------------------------
    async def queimadas_focos_por_municipio(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT CONCAT(COALESCE(m.nome, 'Não informado'), ' - ', e.sigla) AS label,
                       COUNT(q.id)::float AS valor
                FROM queimada_evento q
                JOIN municipio m ON m.id = q.municipio_id
                JOIN estado e ON e.id = m.estado_id
                GROUP BY m.nome, e.sigla
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=sum(g.valor for g in grupos))

    # ------------------------------------------------------------------
    # Focos de incêndio por mês (série temporal)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Focos por bioma
    # ------------------------------------------------------------------
    async def queimadas_focos_por_bioma(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT COALESCE(bioma, 'Não informado') AS label,
                       COUNT(*)::float AS valor
                FROM queimada_evento
                GROUP BY bioma
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=sum(g.valor for g in grupos))

    # ------------------------------------------------------------------
    # Intensidade média (FRP) por bioma
    # ------------------------------------------------------------------
    async def queimadas_intensidade_por_bioma(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT COALESCE(bioma, 'Não informado') AS label,
                       ROUND(AVG(intensidade)::numeric, 2)::float AS valor
                FROM queimada_evento
                WHERE intensidade IS NOT NULL
                GROUP BY bioma
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        total = round(sum(g.valor for g in grupos) / len(grupos), 2) if grupos else 0.0
        return RespostaAgrupada(grupos=grupos, total=total)

    # ------------------------------------------------------------------
    # Dias sem chuva médio por estado
    # ------------------------------------------------------------------
    async def queimadas_dias_sem_chuva_por_estado(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT e.sigla AS label,
                       ROUND(AVG(q.dias_sem_chuva)::numeric, 1)::float AS valor
                FROM queimada_evento q
                JOIN municipio m ON m.id = q.municipio_id
                JOIN estado e ON e.id = m.estado_id
                WHERE q.dias_sem_chuva IS NOT NULL
                GROUP BY e.sigla
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        total = round(sum(g.valor for g in grupos) / len(grupos), 1) if grupos else 0.0
        return RespostaAgrupada(grupos=grupos, total=total)

    # ------------------------------------------------------------------
    # Risco médio de fogo por estado
    # ------------------------------------------------------------------
    async def queimadas_risco_medio_por_estado(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT e.sigla AS label,
                       ROUND(AVG(q.risco_fogo)::numeric, 2)::float AS valor
                FROM queimada_evento q
                JOIN municipio m ON m.id = q.municipio_id
                JOIN estado e ON e.id = m.estado_id
                WHERE q.risco_fogo IS NOT NULL
                GROUP BY e.sigla
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        total = round(sum(g.valor for g in grupos) / len(grupos), 2) if grupos else 0.0
        return RespostaAgrupada(grupos=grupos, total=total)

    # ------------------------------------------------------------------
    # Queimadas dentro vs. fora de imóveis rurais
    # ------------------------------------------------------------------
    async def queimadas_dentro_fora_imoveis(self) -> RespostaQueimadaDentroFora:
        result = await self._session.execute(
            text("""
                SELECT dentro_imovel, COUNT(*)::int AS total
                FROM rel_imovel_queimada
                WHERE dentro_imovel IS NOT NULL
                GROUP BY dentro_imovel
            """)
        )
        grupos = [QueimadaDentroForaItem(dentro_imovel=row.dentro_imovel, total=row.total) for row in result]
        return RespostaQueimadaDentroFora(grupos=grupos, total=sum(g.total for g in grupos))

    # ------------------------------------------------------------------
    # Data do último incêndio por estado
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Unidades de Conservação por grupo SNUC
    # ------------------------------------------------------------------
    async def uc_por_grupo_snuc(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT COALESCE(grupo_snuc, 'Não informado') AS label,
                       COUNT(*)::float AS valor
                FROM unidade_conservacao
                GROUP BY grupo_snuc
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=sum(g.valor for g in grupos))

    # ------------------------------------------------------------------
    # Unidades de Conservação por esfera (federal/estadual/municipal)
    # ------------------------------------------------------------------
    async def uc_por_esfera(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT COALESCE(esfera, 'Não informado') AS label,
                       COUNT(*)::float AS valor
                FROM unidade_conservacao
                GROUP BY esfera
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=sum(g.valor for g in grupos))

    # ------------------------------------------------------------------
    # Terras Indígenas por fase de demarcação
    # ------------------------------------------------------------------
    async def ti_por_fase(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT COALESCE(fase, 'Não informado') AS label,
                       COUNT(*)::float AS valor
                FROM terra_indigena
                GROUP BY fase
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=sum(g.valor for g in grupos))

    # ------------------------------------------------------------------
    # Assentamentos por modalidade
    # ------------------------------------------------------------------
    async def assentamentos_por_modalidade(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT COALESCE(modalidade, 'Não informado') AS label,
                       COUNT(*)::float AS valor
                FROM assentamento_rural
                GROUP BY modalidade
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=sum(g.valor for g in grupos))

    # ------------------------------------------------------------------
    # Famílias em assentamentos por estado
    # ------------------------------------------------------------------
    async def assentamentos_familias_por_estado(self) -> RespostaAgrupada:
        result = await self._session.execute(
            text("""
                SELECT e.sigla AS label,
                       SUM(a.familias)::float AS valor
                FROM assentamento_rural a
                JOIN municipio m ON m.id = a.municipio_id
                JOIN estado e ON e.id = m.estado_id
                WHERE a.familias IS NOT NULL
                GROUP BY e.sigla
                ORDER BY valor DESC
            """)
        )
        grupos = [GrupoItem(label=row.label, valor=row.valor) for row in result]
        return RespostaAgrupada(grupos=grupos, total=sum(g.valor for g in grupos))

    # ------------------------------------------------------------------
    # Status do CAR
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # [RF-04] Distância (ST_Distance) entre imóveis e alertas de desmatamento próximos
    # Retorna pares (imóvel, alerta) que estão dentro do raio mas sem sobreposição
    # ------------------------------------------------------------------
    async def desmatamento_distancia_alertas(
        self, raio_km: float = 10.0, limite: int = 100
    ) -> RespostaProximidade:
        result = await self._session.execute(
            text("""
                SELECT
                    i.id::text   AS imovel_id,
                    i.nome_imovel,
                    m.nome       AS municipio,
                    d.id::text   AS alerta_id,
                    d.tipo_alerta,
                    dist.distancia_m
                FROM imovel_rural i
                JOIN desmatamento_alerta d
                    ON ST_DWithin(i.geom::geography, d.geom::geography, :raio_m)
                   AND NOT ST_Intersects(i.geom, d.geom)
                JOIN LATERAL (
                    SELECT ROUND(ST_Distance(i.geom::geography, d.geom::geography)::numeric, 2)::float AS distancia_m
                ) dist ON true
                LEFT JOIN municipio m ON m.id = i.municipio_id
                ORDER BY dist.distancia_m
                LIMIT :limite
            """),
            {"raio_m": raio_km * 1000, "limite": limite},
        )
        itens = [
            ProximidadeItem(
                imovel_id=row.imovel_id,
                nome_imovel=row.nome_imovel,
                municipio=row.municipio,
                alerta_id=row.alerta_id,
                tipo_alerta=row.tipo_alerta,
                distancia_m=row.distancia_m,
            )
            for row in result
        ]
        return RespostaProximidade(itens=itens, total=len(itens))

    # ------------------------------------------------------------------
    # [RF-04] Área de influência (ST_Buffer) de alertas de desmatamento
    # Cria buffer ao redor de cada alerta e retorna imóveis que caem dentro
    # ------------------------------------------------------------------
    async def desmatamento_buffer_imoveis(
        self, raio_km: float = 5.0, limite: int = 100
    ) -> RespostaBuffer:
        result = await self._session.execute(
            text("""
                SELECT
                    d.id::text          AS alerta_id,
                    d.tipo_alerta,
                    m.nome              AS municipio,
                    i.id::text          AS imovel_id,
                    i.nome_imovel,
                    ROUND(
                        (ST_Area(
                            ST_Buffer(d.geom::geography, :raio_m)::geometry
                        ) / 10000.0)::numeric, 2
                    )::float            AS area_buffer_ha,
                    ST_AsGeoJSON(
                        ST_Buffer(d.geom::geography, :raio_m)::geometry
                    )                   AS buffer_geojson
                FROM desmatamento_alerta d
                JOIN imovel_rural i
                    ON ST_Intersects(
                        ST_Buffer(d.geom::geography, :raio_m)::geometry,
                        i.geom
                    )
                LEFT JOIN municipio m ON m.id = d.municipio_id
                ORDER BY d.id, i.id
                LIMIT :limite
            """),
            {"raio_m": raio_km * 1000, "limite": limite},
        )
        itens = [
            BufferResultItem(
                alerta_id=row.alerta_id,
                tipo_alerta=row.tipo_alerta,
                municipio=row.municipio,
                imovel_id=row.imovel_id,
                nome_imovel=row.nome_imovel,
                area_buffer_ha=row.area_buffer_ha,
                buffer_geojson=row.buffer_geojson,
            )
            for row in result
        ]
        return RespostaBuffer(raio_km=raio_km, itens=itens, total=len(itens))

    # ------------------------------------------------------------------
    # [RF-04] Distância (ST_Distance) entre imóveis e focos de queimada próximos
    # Retorna pares (imóvel, queimada) que estão dentro do raio mas sem sobreposição
    # ------------------------------------------------------------------
    async def queimadas_distancia_imoveis(
        self, raio_km: float = 10.0, limite: int = 100
    ) -> RespostaProximidadeQueimada:
        result = await self._session.execute(
            text("""
                SELECT
                    i.id::text   AS imovel_id,
                    i.nome_imovel,
                    m.nome       AS municipio,
                    q.id::text   AS queimada_id,
                    q.bioma      AS bioma,
                    dist.distancia_m
                FROM imovel_rural i
                JOIN queimada_evento q
                    ON ST_DWithin(i.geom::geography, q.geom::geography, :raio_m)
                   AND NOT ST_Intersects(i.geom, q.geom)
                JOIN LATERAL (
                    SELECT ROUND(ST_Distance(i.geom::geography, q.geom::geography)::numeric, 2)::float AS distancia_m
                ) dist ON true
                LEFT JOIN municipio m ON m.id = i.municipio_id
                ORDER BY dist.distancia_m
                LIMIT :limite
            """),
            {"raio_m": raio_km * 1000, "limite": limite},
        )
        itens = [
            ProximidadeQueimadaItem(
                imovel_id=row.imovel_id,
                nome_imovel=row.nome_imovel,
                municipio=row.municipio,
                queimada_id=row.queimada_id,
                bioma=row.bioma,
                distancia_m=row.distancia_m,
                nivel_risco_ambiental=classificar_nivel_risco_ambiental(row.distancia_m),
            )
            for row in result
        ]
        return RespostaProximidadeQueimada(itens=itens, total=len(itens))

    # ------------------------------------------------------------------
    # Sobreposições com áreas especiais (contagem)
    # ------------------------------------------------------------------
    async def resumo_sobreposicoes(self) -> ResumoSobreposicoes:
        result = await self._session.execute(
            text("""
                SELECT
                    COUNT(DISTINCT uc.imovel_rural_id)::int          AS qtd_uc,
                    COUNT(DISTINCT ti.imovel_rural_id)::int           AS qtd_ti,
                    COUNT(DISTINCT qu.imovel_rural_id)::int           AS qtd_quilombo,
                    COUNT(DISTINCT as_.imovel_rural_id)::int          AS qtd_assentamento,
                    COUNT(DISTINCT i.id)::int                         AS total_imoveis
                FROM imovel_rural i
                LEFT JOIN rel_imovel_uc          uc  ON uc.imovel_rural_id  = i.id
                LEFT JOIN rel_imovel_ti          ti  ON ti.imovel_rural_id  = i.id
                LEFT JOIN rel_imovel_quilombo    qu  ON qu.imovel_rural_id  = i.id
                LEFT JOIN rel_imovel_assentamento as_ ON as_.imovel_rural_id = i.id
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

    async def sobreposicoes_areas(
        self,
        tipo_area: TipoAreaSobreposicao = TipoAreaSobreposicao.todos,
        limite: int = 100,
    ) -> RespostaSobreposicoesAreas:
        consultas = {
            TipoAreaSobreposicao.uc.value: """
                SELECT
                    'uc'::text AS tipo_area,
                    i.id::text AS imovel_id,
                    i.codigo_car,
                    i.nome_imovel,
                    COALESCE(m.nome, 'Não informado') AS municipio,
                    COALESCE(e.sigla, 'N/D') AS estado,
                    u.id::text AS area_id,
                    u.nome AS area_nome,
                    i.area_ha AS area_imovel_ha,
                    ru.area_intersecao_ha,
                    ru.percentual_sobreposicao,
                    ru.tipo_relacao
                FROM rel_imovel_uc ru
                JOIN imovel_rural i ON i.id = ru.imovel_rural_id
                JOIN unidade_conservacao u ON u.id = ru.unidade_conservacao_id
                LEFT JOIN municipio m ON m.id = i.municipio_id
                LEFT JOIN estado e ON e.id = m.estado_id
            """,
            TipoAreaSobreposicao.ti.value: """
                SELECT
                    'ti'::text AS tipo_area,
                    i.id::text AS imovel_id,
                    i.codigo_car,
                    i.nome_imovel,
                    COALESCE(m.nome, 'Não informado') AS municipio,
                    COALESCE(e.sigla, 'N/D') AS estado,
                    t.id::text AS area_id,
                    t.nome AS area_nome,
                    i.area_ha AS area_imovel_ha,
                    rt.area_intersecao_ha,
                    rt.percentual_sobreposicao,
                    rt.tipo_relacao
                FROM rel_imovel_ti rt
                JOIN imovel_rural i ON i.id = rt.imovel_rural_id
                JOIN terra_indigena t ON t.id = rt.terra_indigena_id
                LEFT JOIN municipio m ON m.id = i.municipio_id
                LEFT JOIN estado e ON e.id = m.estado_id
            """,
            TipoAreaSobreposicao.quilombo.value: """
                SELECT
                    'quilombo'::text AS tipo_area,
                    i.id::text AS imovel_id,
                    i.codigo_car,
                    i.nome_imovel,
                    COALESCE(m.nome, 'Não informado') AS municipio,
                    COALESCE(e.sigla, 'N/D') AS estado,
                    q.id::text AS area_id,
                    q.nome AS area_nome,
                    i.area_ha AS area_imovel_ha,
                    rq.area_intersecao_ha,
                    rq.percentual_sobreposicao,
                    rq.tipo_relacao
                FROM rel_imovel_quilombo rq
                JOIN imovel_rural i ON i.id = rq.imovel_rural_id
                JOIN territorio_quilombola q ON q.id = rq.territorio_quilombola_id
                LEFT JOIN municipio m ON m.id = i.municipio_id
                LEFT JOIN estado e ON e.id = m.estado_id
            """,
            TipoAreaSobreposicao.assentamento.value: """
                SELECT
                    'assentamento'::text AS tipo_area,
                    i.id::text AS imovel_id,
                    i.codigo_car,
                    i.nome_imovel,
                    COALESCE(m.nome, 'Não informado') AS municipio,
                    COALESCE(e.sigla, 'N/D') AS estado,
                    a.id::text AS area_id,
                    a.nome AS area_nome,
                    i.area_ha AS area_imovel_ha,
                    ra.area_intersecao_ha,
                    ra.percentual_sobreposicao,
                    ra.tipo_relacao
                FROM rel_imovel_assentamento ra
                JOIN imovel_rural i ON i.id = ra.imovel_rural_id
                JOIN assentamento_rural a ON a.id = ra.assentamento_rural_id
                LEFT JOIN municipio m ON m.id = i.municipio_id
                LEFT JOIN estado e ON e.id = m.estado_id
            """,
        }

        if tipo_area == TipoAreaSobreposicao.todos:
            sql = "SELECT * FROM (" + " UNION ALL ".join(consultas.values()) + ") AS sobreposicoes "
            sql += "ORDER BY COALESCE(percentual_sobreposicao, 0) DESC, COALESCE(area_intersecao_ha, 0) DESC, tipo_area ASC "
            sql += "LIMIT :limite"
        else:
            sql = consultas[tipo_area.value] + " "
            sql += "ORDER BY COALESCE(percentual_sobreposicao, 0) DESC, COALESCE(area_intersecao_ha, 0) DESC "
            sql += "LIMIT :limite"

        result = await self._session.execute(text(sql), {"limite": limite})
        itens = [
            SobreposicaoAreaItem(
                tipo_area=row.tipo_area,
                imovel_id=row.imovel_id,
                codigo_car=row.codigo_car,
                nome_imovel=row.nome_imovel,
                municipio=row.municipio,
                estado=row.estado,
                area_id=row.area_id,
                area_nome=row.area_nome,
                area_imovel_ha=round(float(row.area_imovel_ha), 4) if row.area_imovel_ha is not None else None,
                area_intersecao_ha=round(float(row.area_intersecao_ha), 4) if row.area_intersecao_ha is not None else None,
                percentual_sobreposicao=round(float(row.percentual_sobreposicao), 2) if row.percentual_sobreposicao is not None else None,
                tipo_relacao=row.tipo_relacao,
            )
            for row in result
        ]
        return RespostaSobreposicoesAreas(tipo_area=tipo_area.value, itens=itens, total=len(itens))
