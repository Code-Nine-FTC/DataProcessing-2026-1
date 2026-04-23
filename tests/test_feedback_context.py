from nlp_processor.agent import run_agent
from nlp_processor.pipeline.entity_extractor import Entidades


class _ClassifierStub:
    def is_ready(self) -> bool:
        return True

    def predict(self, pergunta: str) -> tuple[str, float]:
        return "buscar_queimadas", 0.92


class _EmbedderStub:
    def embed(self, pergunta: str) -> list[float]:
        return [0.1, 0.2]


async def _run_agent_with_feedback(monkeypatch, historico):
    async def fake_carregar_municipios(session):
        return []

    async def fake_executar_consulta(session, intencao, entidades, query_embedding):
        return {
            "features": [{"type": "Feature", "geometry": None, "properties": {}}],
            "fontes": [{"nome": "INPE", "orgao": "INPE"}],
            "contexto_documental": "",
            "sql_executado": "SELECT 1",
            "mensagem_erro": None,
        }

    monkeypatch.setattr("nlp_processor.agent.get_classifier", lambda: _ClassifierStub())
    monkeypatch.setattr("nlp_processor.agent.get_embedder", lambda: _EmbedderStub())
    monkeypatch.setattr("nlp_processor.agent._carregar_municipios_normalizados", fake_carregar_municipios)
    monkeypatch.setattr(
        "nlp_processor.agent.extrair_entidades",
        lambda pergunta, municipios_extras: Entidades(municipio="Campinas"),
    )
    monkeypatch.setattr("nlp_processor.agent.executar_consulta", fake_executar_consulta)

    return await run_agent(
        session=None,
        pergunta="queimadas em campinas",
        historico=historico,
    )


async def test_run_agent_considera_feedback_negativo(monkeypatch):
    resultado = await _run_agent_with_feedback(
        monkeypatch,
        [
            {"role": "user", "content": "pergunta anterior"},
            {
                "role": "assistant",
                "content": "resposta anterior",
                "feedback": -1,
            },
        ],
    )

    assert "feedback anterior foi negativo" in resultado["texto_resposta"]


async def test_run_agent_considera_feedback_positivo(monkeypatch):
    resultado = await _run_agent_with_feedback(
        monkeypatch,
        [
            {"role": "user", "content": "pergunta anterior"},
            {
                "role": "assistant",
                "content": "resposta anterior",
                "feedback": 1,
            },
        ],
    )

    assert "feedback anterior foi positivo" in resultado["texto_resposta"]