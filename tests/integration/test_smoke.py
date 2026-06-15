import pytest
from fastapi.routing import APIRoute

pytestmark = pytest.mark.smoke


@pytest.fixture(scope="module")
def app():
    from api.main import app
    return app


class TestSmokeRoutes:
    """Verifica que todos os routers foram registrados sem erros de import.

    Estes testes NÃO exigem banco de dados — apenas importam o app FastAPI
    e inspecionam as rotas registradas. São o primeiro filtro de deploy.
    """

    _EXPECTED_PATHS: set[str] = {
        # Auth
        "/auth/register",
        "/auth/login",
        "/auth/me",
        # Admin / ETL
        "/admin/etl/status",
        "/admin/etl/atualizar",
        # Analytics — Imoveis
        "/analytics/imoveis/area-por-estado",
        "/analytics/imoveis/area-por-municipio",
        "/analytics/imoveis/status-car",
        # Analytics — Desmatamento
        "/analytics/desmatamento/area-por-estado",
        "/analytics/desmatamento/area-por-mes",
        "/analytics/desmatamento/alertas-por-tipo",
        "/analytics/desmatamento/area-em-imoveis-por-estado",
        "/analytics/desmatamento/buffer-imoveis",
        "/analytics/desmatamento/distancia-alertas-imoveis",
        # Analytics — Queimadas
        "/analytics/queimadas/distancia-imoveis",
        "/analytics/queimadas/focos-por-estado",
        "/analytics/queimadas/focos-por-municipio",
        "/analytics/queimadas/focos-por-mes",
        "/analytics/queimadas/focos-por-bioma",
        "/analytics/queimadas/intensidade-por-bioma",
        "/analytics/queimadas/dias-sem-chuva-por-estado",
        "/analytics/queimadas/risco-medio-por-estado",
        "/analytics/queimadas/dentro-fora-imoveis",
        "/analytics/queimadas/ultimo-incendio-por-estado",
        # Analytics — Areas Protegidas
        "/analytics/unidades-conservacao/por-grupo-snuc",
        "/analytics/unidades-conservacao/por-esfera",
        "/analytics/terras-indigenas/por-fase",
        "/analytics/assentamentos/por-modalidade",
        "/analytics/assentamentos/familias-por-estado",
        # Analytics — Sobreposicoes
        "/analytics/sobreposicoes/areas",
        "/analytics/sobreposicoes/resumo",
        # Analytics — Score Ambiental
        "/analytics/score-ambiental/imoveis",
        "/analytics/score-ambiental/imoveis/{imovel_id}",
        "/analytics/score-ambiental/assentamentos",
        "/analytics/score-ambiental/assentamentos/{assentamento_id}",
        "/analytics/score-ambiental/resumo",
        "/analytics/imoveis/{imovel_id}/resumo-ambiental",
        # Chat
        "/chat/",
        "/chat/mensagem",
        "/chat/feedback",
        "/chat/{chat_id}/historico",
        "/chat/{chat_id}/resumo",
        "/chat/{chat_id}",
        "/chat/resposta/{resposta_id}/geojson",
        # Dashboard
        "/dashboard/sp",
        # GeoJSON Layers
        "/municipal/geojson/layers/",
        "/municipal/geojson/layers/{layer_name}",
        # Municipal
        "/municipal/",
        "/municipal/search",
        "/municipal/{municipio_id}",
        "/municipal/intersections",
        # Health / Spatial
        "/health/spatial/",
    }

    @pytest.fixture(scope="module")
    def registered_paths(self, app):
        routes = [
            r.path for r in app.routes
            if isinstance(r, APIRoute) and not getattr(r, "include_in_schema", True)
        ]
        routes += [
            r.path for r in app.routes
            if isinstance(r, APIRoute)
        ]
        return set(routes)

    def test_numero_de_rotas(self, registered_paths):
        assert len(registered_paths) >= 42, (
            f"Esperadas pelo menos 42 rotas, encontradas {len(registered_paths)}"
        )

    def test_todas_as_rotas_esperadas(self, registered_paths):
        nao_encontradas = self._EXPECTED_PATHS - registered_paths
        assert not nao_encontradas, (
            f"Rotas esperadas mas nao registradas ({len(nao_encontradas)}):\n"
            + "\n".join(f"  - {p}" for p in sorted(nao_encontradas))
        )

    def test_sem_rotas_extras_inesperadas(self, app, registered_paths):
        ignoradas = {"/", "/openapi.json", "/openapi.json/", "/docs", "/docs/", "/redoc", "/redoc/"}
        extras = registered_paths - self._EXPECTED_PATHS - ignoradas
        assert not extras, (
            f"Rotas registradas mas nao esperadas ({len(extras)}):\n"
            + "\n".join(f"  - {p}" for p in sorted(extras))
        )

    def test_cada_router_tem_ao_menos_uma_rota(self, app):
        prefixes = {
            "/auth", "/admin", "/analytics", "/chat",
            "/dashboard", "/municipal", "/health",
        }
        paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
        for prefix in prefixes:
            assert any(p.startswith(prefix) for p in paths), (
                f"Nenhuma rota registrada com prefixo {prefix}"
            )


class TestSmokeDocs:
    """Verifica que a documentacao da API esta acessivel."""

    async def test_swagger_ui_redireciona(self, app):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/", follow_redirects=False)
            assert resp.status_code in (200, 302, 307)
