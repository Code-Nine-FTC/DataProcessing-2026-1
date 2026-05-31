import pytest

pytestmark = pytest.mark.integration


class TestDashboardRouter:
    async def test_get_dashboard_sp_retorna_200(self, test_client):
        resp = await test_client.get("/dashboard/sp")
        assert resp.status_code == 200

    async def test_get_dashboard_sp_tem_estado_kpis(self, test_client):
        resp = await test_client.get("/dashboard/sp")
        data = resp.json()["data"]
        estado = data["estado"]
        assert estado["nome"] == "São Paulo"
        assert estado["sigla"] == "SP"
        assert estado["total_municipios"] == 3
        assert estado["total_imoveis_rurais"] == 3
        assert estado["focos_queimada_periodo"] == 5

    async def test_get_dashboard_sp_tem_rankings(self, test_client):
        resp = await test_client.get("/dashboard/sp")
        data = resp.json()["data"]
        rankings = data["rankings"]
        assert "queimadas" in rankings
        assert "imoveis_rurais" in rankings
        assert "desmatamento" in rankings

    async def test_get_dashboard_sp_ranking_queimadas(self, test_client):
        resp = await test_client.get("/dashboard/sp")
        data = resp.json()["data"]
        queimadas = data["rankings"]["queimadas"]
        assert len(queimadas) == 3
        municipios = {r["municipio"] for r in queimadas}
        assert "Caçapava" in municipios
        assert "Jacareí" in municipios
        assert "São José dos Campos" in municipios
        total = sum(r["valor"] for r in queimadas)
        assert total == 5.0


class TestAnalyticsRouter:
    async def test_get_queimadas_focos_por_municipio(self, test_client):
        resp = await test_client.get("/analytics/queimadas/focos-por-municipio")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["grupos"]) == 3
        assert data["total"] == 5.0

    async def test_get_queimadas_focos_por_estado(self, test_client):
        resp = await test_client.get("/analytics/queimadas/focos-por-estado")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["grupos"]) == 1
        assert data["grupos"][0]["label"] == "SP"
        assert data["grupos"][0]["valor"] == 5.0

    async def test_get_queimadas_focos_por_mes(self, test_client):
        resp = await test_client.get("/analytics/queimadas/focos-por-mes")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 5
        assert len(data["series"]) >= 3

    async def test_get_queimadas_dentro_fora(self, test_client):
        resp = await test_client.get("/analytics/queimadas/dentro-fora-imoveis")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 5

    async def test_get_queimadas_ultimo_incendio(self, test_client):
        resp = await test_client.get("/analytics/queimadas/ultimo-incendio-por-estado")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["estados"][0]["estado"] == "SP"
        assert data["estados"][0]["data_ultimo_incendio"] == "2026-03-05"

    async def test_get_queimadas_risco_medio(self, test_client):
        resp = await test_client.get("/analytics/queimadas/risco-medio-por-estado")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["grupos"]) == 1
        assert data["grupos"][0]["label"] == "SP"
        assert data["grupos"][0]["valor"] > 0

    async def test_get_queimadas_dias_sem_chuva(self, test_client):
        resp = await test_client.get("/analytics/queimadas/dias-sem-chuva-por-estado")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["grupos"]) >= 0

    async def test_get_imoveis_area_por_estado(self, test_client):
        resp = await test_client.get("/analytics/imoveis/area-por-estado")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 365.5
        assert data["grupos"][0]["label"] == "SP"
        assert data["grupos"][0]["valor"] == 365.5

    async def test_get_imoveis_area_por_municipio(self, test_client):
        resp = await test_client.get("/analytics/imoveis/area-por-municipio")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 365.5
        assert len(data["grupos"]) == 3

    async def test_get_imoveis_status_car(self, test_client):
        resp = await test_client.get("/analytics/imoveis/status-car")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["grupos"]) == 1
        assert data["grupos"][0]["label"] == "Não informado"
        assert data["grupos"][0]["valor"] == 3.0

    async def test_get_sobreposicoes_resumo(self, test_client):
        resp = await test_client.get("/analytics/sobreposicoes/resumo")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_imoveis"] == 3
        assert data["imoveis_com_sobreposicao_uc"] == 0

    async def test_get_sobreposicoes_areas(self, test_client):
        resp = await test_client.get("/analytics/sobreposicoes/areas")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 0
        assert data["tipo_area"] == "todos"

    async def test_get_score_ambiental_imoveis(self, test_client):
        resp = await test_client.get("/analytics/score-ambiental/imoveis")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 3
        assert data["score_medio"] > 0
        for item in data["itens"]:
            assert "imovel_id" in item
            assert "score_geral" in item
            assert "classificacao" in item

    async def test_get_score_ambiental_resumo(self, test_client):
        resp = await test_client.get("/analytics/score-ambiental/resumo")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_imoveis_avaliados"] == 3
        assert data["score_medio_imoveis"] > 0
        assert len(data["distribuicao_imoveis"]) == 5
