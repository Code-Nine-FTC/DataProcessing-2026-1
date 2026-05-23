# -*- coding: utf-8 -*-
import unicodedata
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.index import (
    IndicadoresScoreAssentamento,
    IndicadoresScoreImovel,
    RespostaScoreAssentamentos,
    RespostaScoreImoveis,
    ResumoScoreAmbiental,
    ScoreAssentamento,
    ScoreDistribuicaoItem,
    ScoreImovel,
)

# Cap interno pra evitar OOM no top-N: pegamos até este número de imóveis
# do banco, calculamos o score em Python e ordenamos. Para `limite` maior
# que o cap, expandimos pra atender o pedido do usuário.
_INTERNAL_FETCH_CAP = 2000


def _classificar_score(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    return "E"


def _normalizar_situacao(situacao: Optional[str]) -> str:
    if not situacao:
        return ""
    s = unicodedata.normalize("NFD", situacao.strip())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.upper()


def _score_governanca_car(situacao: Optional[str]) -> float:
    s = _normalizar_situacao(situacao)
    if not s:
        return 30.0
    if any(tok in s for tok in ("ATIVO", "ANALISADO", "VALIDADO")) or s == "AT":
        return 100.0
    if any(tok in s for tok in ("PENDENTE", "AGUARDANDO")) or s == "PE":
        return 70.0
    if "SUSPENSO" in s or s == "SU":
        return 40.0
    if "CANCELADO" in s:
        return 10.0
    return 50.0


def _score_ambiental_imovel(
    perc_desmatamento: float,
    focos_dentro: int,
    focos_proximos: int,
) -> float:
    penalidade = (
        min(50.0, perc_desmatamento * 0.7)
        + min(30.0, focos_dentro * 6.0)
        + min(20.0, focos_proximos * 2.0)
    )
    return max(0.0, round(100.0 - penalidade, 2))


def _score_social_imovel(perc_uc: float, perc_ti: float, perc_quilombo: float) -> float:
    penalidade = (
        min(35.0, perc_uc * 0.4)
        + min(35.0, perc_ti * 0.5)
        + min(30.0, perc_quilombo * 0.5)
    )
    return max(0.0, round(100.0 - penalidade, 2))


def _score_geral(amb: float, soc: float, gov: float) -> float:
    return round(amb * 0.5 + soc * 0.25 + gov * 0.25, 2)


def _score_ambiental_assentamento(
    perc_desmatamento: float,
    focos_dentro: int,
    focos_proximos: int,
) -> float:
    penalidade = (
        min(55.0, perc_desmatamento * 0.8)
        + min(30.0, focos_dentro * 0.5)
        + min(15.0, focos_proximos * 0.2)
    )
    return max(0.0, round(100.0 - penalidade, 2))


def _score_social_assentamento(perc_uc: float, perc_ti: float) -> float:
    penalidade = min(50.0, perc_uc * 0.5) + min(50.0, perc_ti * 0.5)
    return max(0.0, round(100.0 - penalidade, 2))


def _completude_assentamento(
    tem_modalidade: bool,
    tem_familias: bool,
    tem_area: bool,
) -> float:
    """% de campos descritivos preenchidos. Também usado como score de governança."""
    flags = [tem_modalidade, tem_familias, tem_area]
    return round(sum(flags) / len(flags) * 100.0, 2)


class ScoreAmbientalService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def score_imoveis(
        self,
        estado_sigla: Optional[str] = None,
        municipio_id: Optional[int] = None,
        limite: int = 100,
        _random_sample: bool = False,
    ) -> RespostaScoreImoveis:
        # Pra retornar top-N por score, buscamos mais que `limite` quando possível
        # e ordenamos em Python (a fórmula de score é complexa pra traduzir em SQL).
        fetch_limit = limite if _random_sample else max(limite, _INTERNAL_FETCH_CAP)
        params = {
            "estado_sigla": estado_sigla.upper() if estado_sigla else None,
            "municipio_id": municipio_id,
            "limite": fetch_limit,
        }
        order_clause = "ORDER BY random()" if _random_sample else "ORDER BY i.id"
        result = await self._session.execute(
            text(
                f"""
                SELECT
                    i.id::text AS imovel_id,
                    i.codigo_car,
                    i.nome_imovel,
                    i.area_ha::float AS area_ha,
                    i.situacao_cadastral,
                    m.nome AS municipio,
                    e.sigla AS estado,
                    COALESCE((
                        SELECT MAX(rd.percentual_sobreposicao)::float
                        FROM rel_imovel_desmatamento rd
                        WHERE rd.imovel_rural_id = i.id
                    ), 0)::float AS perc_desmatamento_max,
                    COALESCE((
                        SELECT SUM(rd.area_intersecao_ha)::float
                        FROM rel_imovel_desmatamento rd
                        WHERE rd.imovel_rural_id = i.id
                    ), 0)::float AS area_desmatamento_ha,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM rel_imovel_queimada rq
                        WHERE rq.imovel_rural_id = i.id
                          AND rq.dentro_imovel IS TRUE
                    ), 0)::int AS focos_dentro,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM rel_imovel_queimada rq
                        WHERE rq.imovel_rural_id = i.id
                          AND COALESCE(rq.dentro_imovel, FALSE) IS FALSE
                          AND rq.distancia_m IS NOT NULL
                          AND rq.distancia_m <= 5000
                    ), 0)::int AS focos_proximos,
                    COALESCE((
                        SELECT MAX(ru.percentual_sobreposicao)::float
                        FROM rel_imovel_uc ru
                        WHERE ru.imovel_rural_id = i.id
                    ), 0)::float AS perc_uc_max,
                    COALESCE((
                        SELECT MAX(rt.percentual_sobreposicao)::float
                        FROM rel_imovel_ti rt
                        WHERE rt.imovel_rural_id = i.id
                    ), 0)::float AS perc_ti_max,
                    COALESCE((
                        SELECT MAX(rq.percentual_sobreposicao)::float
                        FROM rel_imovel_quilombo rq
                        WHERE rq.imovel_rural_id = i.id
                    ), 0)::float AS perc_quilombo_max
                FROM imovel_rural i
                LEFT JOIN municipio m ON m.id = i.municipio_id
                LEFT JOIN estado e ON e.id = m.estado_id
                WHERE (CAST(:estado_sigla AS TEXT) IS NULL OR e.sigla = CAST(:estado_sigla AS TEXT))
                  AND (CAST(:municipio_id AS INTEGER) IS NULL OR m.id = CAST(:municipio_id AS INTEGER))
                {order_clause}
                LIMIT :limite
                """
            ),
            params,
        )

        itens: list[ScoreImovel] = []
        soma_score = 0.0
        for row in result:
            score_amb = _score_ambiental_imovel(
                row.perc_desmatamento_max, row.focos_dentro, row.focos_proximos
            )
            score_soc = _score_social_imovel(
                row.perc_uc_max, row.perc_ti_max, row.perc_quilombo_max
            )
            score_gov = _score_governanca_car(row.situacao_cadastral)
            score_geral = _score_geral(score_amb, score_soc, score_gov)
            soma_score += score_geral
            itens.append(
                ScoreImovel(
                    imovel_id=row.imovel_id,
                    codigo_car=row.codigo_car,
                    nome_imovel=row.nome_imovel,
                    municipio=row.municipio,
                    estado=row.estado,
                    area_ha=round(row.area_ha, 4) if row.area_ha is not None else None,
                    score_ambiental=score_amb,
                    score_social=score_soc,
                    score_governanca=score_gov,
                    score_geral=score_geral,
                    classificacao=_classificar_score(score_geral),
                    indicadores=IndicadoresScoreImovel(
                        perc_desmatamento_max=round(row.perc_desmatamento_max, 2),
                        area_desmatamento_ha=round(row.area_desmatamento_ha, 2),
                        focos_queimada_dentro=row.focos_dentro,
                        focos_queimada_proximos=row.focos_proximos,
                        perc_sobreposicao_uc_max=round(row.perc_uc_max, 2),
                        perc_sobreposicao_ti_max=round(row.perc_ti_max, 2),
                        perc_sobreposicao_quilombo_max=round(row.perc_quilombo_max, 2),
                        situacao_cadastral=row.situacao_cadastral,
                    ),
                )
            )

        itens.sort(key=lambda x: x.score_geral, reverse=True)
        if not _random_sample:
            itens = itens[:limite]
        soma_final = sum(it.score_geral for it in itens)
        score_medio = round(soma_final / len(itens), 2) if itens else 0.0
        return RespostaScoreImoveis(itens=itens, total=len(itens), score_medio=score_medio)

    async def score_imovel_detalhe(self, imovel_id: str) -> ScoreImovel:
        result = await self._session.execute(
            text(
                """
                SELECT
                    i.id::text AS imovel_id,
                    i.codigo_car,
                    i.nome_imovel,
                    i.area_ha::float AS area_ha,
                    i.situacao_cadastral,
                    m.nome AS municipio,
                    e.sigla AS estado,
                    COALESCE((
                        SELECT MAX(rd.percentual_sobreposicao)::float
                        FROM rel_imovel_desmatamento rd
                        WHERE rd.imovel_rural_id = i.id
                    ), 0)::float AS perc_desmatamento_max,
                    COALESCE((
                        SELECT SUM(rd.area_intersecao_ha)::float
                        FROM rel_imovel_desmatamento rd
                        WHERE rd.imovel_rural_id = i.id
                    ), 0)::float AS area_desmatamento_ha,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM rel_imovel_queimada rq
                        WHERE rq.imovel_rural_id = i.id
                          AND rq.dentro_imovel IS TRUE
                    ), 0)::int AS focos_dentro,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM rel_imovel_queimada rq
                        WHERE rq.imovel_rural_id = i.id
                          AND COALESCE(rq.dentro_imovel, FALSE) IS FALSE
                          AND rq.distancia_m IS NOT NULL
                          AND rq.distancia_m <= 5000
                    ), 0)::int AS focos_proximos,
                    COALESCE((
                        SELECT MAX(ru.percentual_sobreposicao)::float
                        FROM rel_imovel_uc ru
                        WHERE ru.imovel_rural_id = i.id
                    ), 0)::float AS perc_uc_max,
                    COALESCE((
                        SELECT MAX(rt.percentual_sobreposicao)::float
                        FROM rel_imovel_ti rt
                        WHERE rt.imovel_rural_id = i.id
                    ), 0)::float AS perc_ti_max,
                    COALESCE((
                        SELECT MAX(rq.percentual_sobreposicao)::float
                        FROM rel_imovel_quilombo rq
                        WHERE rq.imovel_rural_id = i.id
                    ), 0)::float AS perc_quilombo_max
                FROM imovel_rural i
                LEFT JOIN municipio m ON m.id = i.municipio_id
                LEFT JOIN estado e ON e.id = m.estado_id
                WHERE i.id = CAST(:imovel_id AS UUID)
                """
            ),
            {"imovel_id": imovel_id},
        )
        row = result.first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Imóvel rural com id={imovel_id} não encontrado",
            )

        score_amb = _score_ambiental_imovel(
            row.perc_desmatamento_max, row.focos_dentro, row.focos_proximos
        )
        score_soc = _score_social_imovel(
            row.perc_uc_max, row.perc_ti_max, row.perc_quilombo_max
        )
        score_gov = _score_governanca_car(row.situacao_cadastral)
        score_geral = _score_geral(score_amb, score_soc, score_gov)

        return ScoreImovel(
            imovel_id=row.imovel_id,
            codigo_car=row.codigo_car,
            nome_imovel=row.nome_imovel,
            municipio=row.municipio,
            estado=row.estado,
            area_ha=round(row.area_ha, 4) if row.area_ha is not None else None,
            score_ambiental=score_amb,
            score_social=score_soc,
            score_governanca=score_gov,
            score_geral=score_geral,
            classificacao=_classificar_score(score_geral),
            indicadores=IndicadoresScoreImovel(
                perc_desmatamento_max=round(row.perc_desmatamento_max, 2),
                area_desmatamento_ha=round(row.area_desmatamento_ha, 2),
                focos_queimada_dentro=row.focos_dentro,
                focos_queimada_proximos=row.focos_proximos,
                perc_sobreposicao_uc_max=round(row.perc_uc_max, 2),
                perc_sobreposicao_ti_max=round(row.perc_ti_max, 2),
                perc_sobreposicao_quilombo_max=round(row.perc_quilombo_max, 2),
                situacao_cadastral=row.situacao_cadastral,
            ),
        )

    async def score_assentamentos(
        self,
        estado_sigla: Optional[str] = None,
        municipio_id: Optional[int] = None,
        limite: int = 100,
        _random_sample: bool = False,
    ) -> RespostaScoreAssentamentos:
        fetch_limit = limite if _random_sample else max(limite, _INTERNAL_FETCH_CAP)
        params = {
            "estado_sigla": estado_sigla.upper() if estado_sigla else None,
            "municipio_id": municipio_id,
            "limite": fetch_limit,
        }
        order_clause = "ORDER BY random()" if _random_sample else "ORDER BY a.id"
        # Quando o filtro por município está ativo, restringe os passivos ao mesmo
        # município (passivos com municipio_id NULL ainda passam — fallback espacial
        # pelo ST_Intersects continua valendo).
        result = await self._session.execute(
            text(
                f"""
                SELECT
                    a.id::text AS assentamento_id,
                    a.nome,
                    a.modalidade,
                    a.familias,
                    a.area_ha::float AS area_ha,
                    m.nome AS municipio,
                    e.sigla AS estado,
                    COALESCE((
                        SELECT SUM(
                            ST_Area(ST_Intersection(d.geom, a.geom)::geography) / 10000.0
                        )::float
                        FROM desmatamento_alerta d
                        WHERE ST_Intersects(d.geom, a.geom)
                          AND (
                              CAST(:municipio_id AS INTEGER) IS NULL
                              OR d.municipio_id IS NULL
                              OR d.municipio_id = CAST(:municipio_id AS INTEGER)
                          )
                    ), 0)::float AS area_desmatamento_ha,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM queimada_evento q
                        WHERE ST_Within(q.geom, a.geom)
                          AND (
                              CAST(:municipio_id AS INTEGER) IS NULL
                              OR q.municipio_id IS NULL
                              OR q.municipio_id = CAST(:municipio_id AS INTEGER)
                          )
                    ), 0)::int AS focos_dentro,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM queimada_evento q
                        WHERE ST_DWithin(q.geom::geography, a.geom::geography, 5000)
                          AND NOT ST_Within(q.geom, a.geom)
                          AND (
                              CAST(:municipio_id AS INTEGER) IS NULL
                              OR q.municipio_id IS NULL
                              OR q.municipio_id = CAST(:municipio_id AS INTEGER)
                          )
                    ), 0)::int AS focos_proximos,
                    COALESCE((
                        SELECT SUM(
                            ST_Area(ST_Intersection(u.geom, a.geom)::geography) / 10000.0
                        )::float
                        FROM unidade_conservacao u
                        WHERE ST_Intersects(u.geom, a.geom)
                          AND (
                              CAST(:municipio_id AS INTEGER) IS NULL
                              OR u.municipio_id IS NULL
                              OR u.municipio_id = CAST(:municipio_id AS INTEGER)
                          )
                    ), 0)::float AS area_uc_ha,
                    COALESCE((
                        SELECT SUM(
                            ST_Area(ST_Intersection(t.geom, a.geom)::geography) / 10000.0
                        )::float
                        FROM terra_indigena t
                        WHERE ST_Intersects(t.geom, a.geom)
                          AND (
                              CAST(:municipio_id AS INTEGER) IS NULL
                              OR t.municipio_id IS NULL
                              OR t.municipio_id = CAST(:municipio_id AS INTEGER)
                          )
                    ), 0)::float AS area_ti_ha
                FROM assentamento_rural a
                LEFT JOIN municipio m ON m.id = a.municipio_id
                LEFT JOIN estado e ON e.id = m.estado_id
                WHERE (CAST(:estado_sigla AS TEXT) IS NULL OR e.sigla = CAST(:estado_sigla AS TEXT))
                  AND (CAST(:municipio_id AS INTEGER) IS NULL OR m.id = CAST(:municipio_id AS INTEGER))
                {order_clause}
                LIMIT :limite
                """
            ),
            params,
        )

        itens: list[ScoreAssentamento] = []
        soma_score = 0.0
        for row in result:
            area_ha = float(row.area_ha) if row.area_ha is not None else 0.0
            perc_desm = (row.area_desmatamento_ha / area_ha * 100.0) if area_ha > 0 else 0.0
            perc_uc = (row.area_uc_ha / area_ha * 100.0) if area_ha > 0 else 0.0
            perc_ti = (row.area_ti_ha / area_ha * 100.0) if area_ha > 0 else 0.0

            perc_desm = min(perc_desm, 100.0)
            perc_uc = min(perc_uc, 100.0)
            perc_ti = min(perc_ti, 100.0)

            score_amb = _score_ambiental_assentamento(
                perc_desm, row.focos_dentro, row.focos_proximos
            )
            score_soc = _score_social_assentamento(perc_uc, perc_ti)
            completude = _completude_assentamento(
                row.modalidade is not None,
                row.familias is not None and row.familias > 0,
                row.area_ha is not None and area_ha > 0,
            )
            score_gov = completude
            score_geral = _score_geral(score_amb, score_soc, score_gov)
            soma_score += score_geral
            itens.append(
                ScoreAssentamento(
                    assentamento_id=row.assentamento_id,
                    nome=row.nome,
                    modalidade=row.modalidade,
                    familias=row.familias,
                    municipio=row.municipio,
                    estado=row.estado,
                    area_ha=round(row.area_ha, 4) if row.area_ha is not None else None,
                    score_ambiental=score_amb,
                    score_social=score_soc,
                    score_governanca=score_gov,
                    score_geral=score_geral,
                    classificacao=_classificar_score(score_geral),
                    indicadores=IndicadoresScoreAssentamento(
                        perc_desmatamento=round(perc_desm, 2),
                        area_desmatamento_ha=round(row.area_desmatamento_ha, 2),
                        focos_queimada_dentro=row.focos_dentro,
                        focos_queimada_proximos=row.focos_proximos,
                        perc_sobreposicao_uc=round(perc_uc, 2),
                        perc_sobreposicao_ti=round(perc_ti, 2),
                        completude_dados=completude,
                    ),
                )
            )

        itens.sort(key=lambda x: x.score_geral, reverse=True)
        if not _random_sample:
            itens = itens[:limite]
        soma_final = sum(it.score_geral for it in itens)
        score_medio = round(soma_final / len(itens), 2) if itens else 0.0
        return RespostaScoreAssentamentos(
            itens=itens, total=len(itens), score_medio=score_medio
        )

    async def score_assentamento_detalhe(self, assentamento_id: str) -> ScoreAssentamento:
        result = await self._session.execute(
            text(
                """
                SELECT
                    a.id::text AS assentamento_id,
                    a.nome,
                    a.modalidade,
                    a.familias,
                    a.area_ha::float AS area_ha,
                    m.nome AS municipio,
                    e.sigla AS estado,
                    COALESCE((
                        SELECT SUM(
                            ST_Area(ST_Intersection(d.geom, a.geom)::geography) / 10000.0
                        )::float
                        FROM desmatamento_alerta d
                        WHERE ST_Intersects(d.geom, a.geom)
                    ), 0)::float AS area_desmatamento_ha,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM queimada_evento q
                        WHERE ST_Within(q.geom, a.geom)
                    ), 0)::int AS focos_dentro,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM queimada_evento q
                        WHERE ST_DWithin(q.geom::geography, a.geom::geography, 5000)
                          AND NOT ST_Within(q.geom, a.geom)
                    ), 0)::int AS focos_proximos,
                    COALESCE((
                        SELECT SUM(
                            ST_Area(ST_Intersection(u.geom, a.geom)::geography) / 10000.0
                        )::float
                        FROM unidade_conservacao u
                        WHERE ST_Intersects(u.geom, a.geom)
                    ), 0)::float AS area_uc_ha,
                    COALESCE((
                        SELECT SUM(
                            ST_Area(ST_Intersection(t.geom, a.geom)::geography) / 10000.0
                        )::float
                        FROM terra_indigena t
                        WHERE ST_Intersects(t.geom, a.geom)
                    ), 0)::float AS area_ti_ha
                FROM assentamento_rural a
                LEFT JOIN municipio m ON m.id = a.municipio_id
                LEFT JOIN estado e ON e.id = m.estado_id
                WHERE a.id = CAST(:assentamento_id AS UUID)
                """
            ),
            {"assentamento_id": assentamento_id},
        )
        row = result.first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assentamento rural com id={assentamento_id} não encontrado",
            )

        area_ha = float(row.area_ha) if row.area_ha is not None else 0.0
        perc_desm = (row.area_desmatamento_ha / area_ha * 100.0) if area_ha > 0 else 0.0
        perc_uc = (row.area_uc_ha / area_ha * 100.0) if area_ha > 0 else 0.0
        perc_ti = (row.area_ti_ha / area_ha * 100.0) if area_ha > 0 else 0.0
        perc_desm = min(perc_desm, 100.0)
        perc_uc = min(perc_uc, 100.0)
        perc_ti = min(perc_ti, 100.0)

        score_amb = _score_ambiental_assentamento(
            perc_desm, row.focos_dentro, row.focos_proximos
        )
        score_soc = _score_social_assentamento(perc_uc, perc_ti)
        completude = _completude_assentamento(
            row.modalidade is not None,
            row.familias is not None and row.familias > 0,
            row.area_ha is not None and area_ha > 0,
        )
        score_gov = completude
        score_geral = _score_geral(score_amb, score_soc, score_gov)

        return ScoreAssentamento(
            assentamento_id=row.assentamento_id,
            nome=row.nome,
            modalidade=row.modalidade,
            familias=row.familias,
            municipio=row.municipio,
            estado=row.estado,
            area_ha=round(row.area_ha, 4) if row.area_ha is not None else None,
            score_ambiental=score_amb,
            score_social=score_soc,
            score_governanca=score_gov,
            score_geral=score_geral,
            classificacao=_classificar_score(score_geral),
            indicadores=IndicadoresScoreAssentamento(
                perc_desmatamento=round(perc_desm, 2),
                area_desmatamento_ha=round(row.area_desmatamento_ha, 2),
                focos_queimada_dentro=row.focos_dentro,
                focos_queimada_proximos=row.focos_proximos,
                perc_sobreposicao_uc=round(perc_uc, 2),
                perc_sobreposicao_ti=round(perc_ti, 2),
                completude_dados=completude,
            ),
        )

    async def resumo(
        self,
        estado_sigla: Optional[str] = None,
        municipio_id: Optional[int] = None,
        limite_amostra: int = 500,
    ) -> ResumoScoreAmbiental:
        # Para o resumo precisamos de uma amostra estatística, não do top-N
        # por score — senão a distribuição A-E fica enviesada pra A.
        imoveis = await self.score_imoveis(
            estado_sigla=estado_sigla,
            municipio_id=municipio_id,
            limite=limite_amostra,
            _random_sample=True,
        )
        assentamentos = await self.score_assentamentos(
            estado_sigla=estado_sigla,
            municipio_id=municipio_id,
            limite=limite_amostra,
            _random_sample=True,
        )
        return ResumoScoreAmbiental(
            total_imoveis_avaliados=imoveis.total,
            score_medio_imoveis=imoveis.score_medio,
            distribuicao_imoveis=_distribuir([i.classificacao for i in imoveis.itens]),
            total_assentamentos_avaliados=assentamentos.total,
            score_medio_assentamentos=assentamentos.score_medio,
            distribuicao_assentamentos=_distribuir(
                [a.classificacao for a in assentamentos.itens]
            ),
        )


def _distribuir(classificacoes: list[str]) -> list[ScoreDistribuicaoItem]:
    total = len(classificacoes)
    if total == 0:
        return []
    contagem: dict[str, int] = {}
    for c in classificacoes:
        contagem[c] = contagem.get(c, 0) + 1
    itens: list[ScoreDistribuicaoItem] = []
    for letra in ["A", "B", "C", "D", "E"]:
        qtd = contagem.get(letra, 0)
        itens.append(
            ScoreDistribuicaoItem(
                classificacao=letra,
                total=qtd,
                percentual=round(qtd / total * 100.0, 2),
            )
        )
    return itens
