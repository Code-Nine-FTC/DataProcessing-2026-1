import pytest

from api.router.controller.dashboard import DashboardHandler
from api.services.index import AnalyticsService

pytestmark = pytest.mark.integration


class TestDashboardHandler:
    async def test_execute_retorna_dashboard_sp(self, db_session):
        handler = DashboardHandler(session=db_session, sigla_estado="SP")
        result = await handler.execute()

        assert result.data is not None
        estado = result.data.estado
        assert estado.nome == "São Paulo"
        assert estado.sigla == "SP"
        assert estado.total_municipios == 3
        assert estado.total_imoveis_rurais == 3
        assert estado.focos_queimada_periodo == 5
        assert estado.area_protegida_total_ha == 0.0
        assert estado.total_alertas_desmatamento == 0

    async def test_execute_rankings_possuem_seis_chaves(self, db_session):
        handler = DashboardHandler(session=db_session, sigla_estado="SP")
        result = await handler.execute()

        rankings = result.data.rankings
        expected_keys = {
            "queimadas", "desmatamento", "terras_indigenas",
            "quilombolas", "unidades_conservacao", "imoveis_rurais",
        }
        assert set(rankings.keys()) == expected_keys

    async def test_execute_ranking_queimadas_tem_dados(self, db_session):
        handler = DashboardHandler(session=db_session, sigla_estado="SP")
        result = await handler.execute()

        queimadas = result.data.rankings["queimadas"]
        nomes = {r.municipio for r in queimadas}
        assert "Caçapava" in nomes
        assert "Jacareí" in nomes
        assert "São José dos Campos" in nomes
        total = sum(r.valor for r in queimadas)
        assert total == 5.0

    async def test_execute_ranking_imoveis_tem_dados(self, db_session):
        handler = DashboardHandler(session=db_session, sigla_estado="SP")
        result = await handler.execute()

        imoveis = result.data.rankings["imoveis_rurais"]
        total = sum(r.valor for r in imoveis)
        assert total == 365.5

    async def test_execute_ranking_vazio_quando_sem_dados(self, db_session):
        handler = DashboardHandler(session=db_session, sigla_estado="SP")
        result = await handler.execute()

        for key in ("desmatamento", "terras_indigenas", "quilombolas", "unidades_conservacao"):
            assert result.data.rankings[key] == []

    async def test_execute_estado_inexistente_404(self, db_session):
        handler = DashboardHandler(session=db_session, sigla_estado="XX")
        with pytest.raises(Exception):
            await handler.execute()


class TestAnalyticsService:
    @pytest.fixture
    def service(self, db_session):
        return AnalyticsService(db_session)

    async def test_queimadas_focos_por_municipio(self, service):
        result = await service.queimadas_focos_por_municipio()

        assert len(result.grupos) == 3
        labels = {g.label for g in result.grupos}
        assert any("Caçapava" in l for l in labels)
        assert any("Jacareí" in l for l in labels)
        assert any("São José dos Campos" in l for l in labels)
        assert result.total == 5.0

    async def test_queimadas_focos_por_estado(self, service):
        result = await service.queimadas_focos_por_estado()

        assert len(result.grupos) == 1
        assert result.grupos[0].label == "SP"
        assert result.grupos[0].valor == 5.0
        assert result.total == 5.0

    async def test_queimadas_focos_por_mes(self, service):
        result = await service.queimadas_focos_por_mes()

        assert result.total == 5
        periodos = {s.periodo for s in result.series}
        assert "2026-01" in periodos
        assert "2026-02" in periodos
        assert "2026-03" in periodos

    async def test_queimadas_dentro_fora_imoveis(self, service):
        result = await service.queimadas_dentro_fora_imoveis()

        assert result.total == 5
        for g in result.grupos:
            if g.dentro_imovel:
                assert g.total == 1
            else:
                assert g.total == 4

    async def test_queimadas_ultimo_incendio_por_estado(self, service):
        result = await service.queimadas_ultimo_incendio_por_estado()

        assert len(result.estados) == 1
        assert result.estados[0].estado == "SP"
        assert result.estados[0].data_ultimo_incendio == "2026-03-05"

    async def test_queimadas_risco_medio_por_estado(self, service):
        result = await service.queimadas_risco_medio_por_estado()

        assert len(result.grupos) == 1
        assert result.grupos[0].label == "SP"
        assert result.grupos[0].valor > 0

    async def test_imoveis_area_por_estado(self, service):
        result = await service.imoveis_area_por_estado()

        assert len(result.grupos) == 1
        assert result.grupos[0].label == "SP"
        assert result.grupos[0].valor == 365.5
        assert result.total == 365.5

    async def test_imoveis_area_por_municipio(self, service):
        result = await service.imoveis_area_por_municipio()

        assert len(result.grupos) == 3
        assert result.total == 365.5

    async def test_imoveis_por_status_car(self, service):
        result = await service.imoveis_por_status_car()

        assert len(result.grupos) == 1
        assert result.grupos[0].label == "Não informado"
        assert result.grupos[0].valor == 3.0

    async def test_sobreposicoes_areas_todos_vazio(self, service):
        result = await service.sobreposicoes_areas()

        assert result.total == 0
        assert result.itens == []
        assert result.tipo_area == "todos"

    async def test_sobreposicoes_resumo_vazio(self, service):
        result = await service.resumo_sobreposicoes()

        assert result.imoveis_com_sobreposicao_uc == 0
        assert result.imoveis_com_sobreposicao_ti == 0
        assert result.imoveis_com_sobreposicao_quilombola == 0
        assert result.imoveis_com_sobreposicao_assentamento == 0
        assert result.total_imoveis == 3
