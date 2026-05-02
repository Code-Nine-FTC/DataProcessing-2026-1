import asyncio
from types import SimpleNamespace

from api.schemas.index import TipoAreaSobreposicao
from api.services.index import AnalyticsService


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.last_sql = None
        self.last_params = None

    async def execute(self, statement, params=None):
        self.last_sql = str(statement)
        self.last_params = params
        return FakeResult(self.rows)

def test_sobreposicoes_areas_uc():
    async def run_test() -> None:
        rows = [
            SimpleNamespace(
                tipo_area="uc",
                imovel_id="imovel-1",
                codigo_car="CAR001",
                nome_imovel="Fazenda Teste",
                municipio="Campinas",
                estado="SP",
                area_id="area-1",
                area_nome="UC Teste",
                area_imovel_ha=120.5,
                area_intersecao_ha=12.25,
                percentual_sobreposicao=10.15,
                tipo_relacao="parcial",
            )
        ]
        session = FakeSession(rows)

        resultado = await AnalyticsService(session).sobreposicoes_areas(TipoAreaSobreposicao.uc, limite=5)

        assert session.last_params == {"limite": 5}
        assert "FROM rel_imovel_uc" in session.last_sql
        assert resultado.tipo_area == "uc"
        assert resultado.total == 1
        assert resultado.itens[0].area_nome == "UC Teste"
        assert resultado.itens[0].percentual_sobreposicao == 10.15

    asyncio.run(run_test())