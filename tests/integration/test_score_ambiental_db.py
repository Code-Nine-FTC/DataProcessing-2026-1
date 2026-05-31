from uuid import uuid4

import pytest
from sqlalchemy import select

from api.services.score_ambiental_service import ScoreAmbientalService
from models.db_model import ImovelRural

pytestmark = pytest.mark.integration


class TestScoreAmbientalImoveis:
    @pytest.fixture
    def service(self, db_session):
        return ScoreAmbientalService(db_session)

    async def test_score_imoveis_retorna_todos(self, service):
        result = await service.score_imoveis()

        assert result.total == 3
        assert len(result.itens) == 3
        assert result.score_medio > 0

    async def test_score_imoveis_ordenados_decrescente(self, service):
        result = await service.score_imoveis()

        scores = [item.score_geral for item in result.itens]
        assert scores == sorted(scores, reverse=True)

    async def test_score_imoveis_campos_preenchidos(self, service):
        result = await service.score_imoveis()

        for item in result.itens:
            assert item.imovel_id is not None
            assert item.codigo_car is not None
            assert item.nome_imovel is not None
            assert item.estado == "SP"
            assert item.score_ambiental >= 0
            assert item.score_social >= 0
            assert item.score_governanca >= 0
            assert 0 <= item.score_geral <= 100
            assert item.classificacao in ("A", "B", "C", "D", "E")

    async def test_score_imoveis_governanca_car_sem_status(self, service):
        result = await service.score_imoveis()

        for item in result.itens:
            assert item.score_governanca == 30.0

    async def test_score_imoveis_indicadores_presentes(self, service):
        result = await service.score_imoveis()

        for item in result.itens:
            ind = item.indicadores
            assert ind.focos_queimada_dentro >= 0
            assert ind.focos_queimada_proximos >= 0
            assert 0 <= ind.perc_desmatamento_max <= 100
            assert 0 <= ind.perc_sobreposicao_uc_max <= 100
            assert 0 <= ind.perc_sobreposicao_ti_max <= 100
            assert 0 <= ind.perc_sobreposicao_quilombo_max <= 100

    async def test_score_imoveis_queimadas_contabilizadas(self, service):
        result = await service.score_imoveis()

        for item in result.itens:
            if item.nome_imovel == "Fazenda Teste Alpha":
                assert item.score_ambiental < 100
                break

    async def test_score_imoveis_filtro_municipio(self, service, db_session):
        stmt = select(ImovelRural.municipio_id).limit(1)
        mun_id = (await db_session.execute(stmt)).scalar_one()

        result = await service.score_imoveis(municipio_id=mun_id)

        assert result.total >= 1
        for item in result.itens:
            assert item.score_geral > 0

    async def test_score_imoveis_filtro_estado_sigla(self, service):
        result = await service.score_imoveis(estado_sigla="SP")
        assert result.total == 3

    async def test_score_imoveis_filtro_estado_sem_dados(self, service):
        result = await service.score_imoveis(estado_sigla="RJ")
        assert result.total == 0

    async def test_score_imoveis_limite(self, service):
        result = await service.score_imoveis(limite=1)
        assert result.total == 1
        assert len(result.itens) == 1


class TestScoreAmbientalImovelDetalhe:
    @pytest.fixture
    def service(self, db_session):
        return ScoreAmbientalService(db_session)

    async def test_score_imovel_detalhe_existente(self, service):
        imovel_id = "b0000000-0000-0000-0000-000000000001"
        result = await service.score_imovel_detalhe(imovel_id)

        assert result.imovel_id == imovel_id
        assert result.codigo_car == "SP-350000-000000000001"
        assert result.nome_imovel == "Fazenda Teste Alpha"
        assert result.estado == "SP"
        assert 0 <= result.score_geral <= 100

    async def test_score_imovel_detalhe_com_queimadas(self, service):
        imovel_id = "b0000000-0000-0000-0000-000000000001"
        result = await service.score_imovel_detalhe(imovel_id)

        assert result.indicadores.focos_queimada_dentro == 0
        assert result.indicadores.focos_queimada_proximos == 2

    async def test_score_imovel_detalhe_404(self, service):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await service.score_imovel_detalhe(str(uuid4()))
        assert exc.value.status_code == 404


class TestScoreAmbientalResumo:
    @pytest.fixture
    def service(self, db_session):
        return ScoreAmbientalService(db_session)

    async def test_resumo_retorna_distribuicao(self, service):
        result = await service.resumo()

        assert result.total_imoveis_avaliados == 3
        assert result.score_medio_imoveis > 0
        assert len(result.distribuicao_imoveis) == 5

    async def test_resumo_distribuicao_percentuais_somam_100(self, service):
        result = await service.resumo()

        total_pct = sum(item.percentual for item in result.distribuicao_imoveis)
        assert total_pct == 100.0

    async def test_resumo_classificacoes_ordenadas(self, service):
        result = await service.resumo()

        classes = [item.classificacao for item in result.distribuicao_imoveis]
        assert classes == ["A", "B", "C", "D", "E"]
