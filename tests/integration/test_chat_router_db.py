from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from models.db_model import Chat, ConsultaUsuario, FeedbackResposta, RespostaSistema

pytestmark = pytest.mark.integration

_AGENT_RESULT = {
    "texto_resposta": "Resposta gerada pelo agente mockado.",
    "features": [],
    "fontes": [{"nome": "Fonte Teste", "orgao": "Orgão Teste", "url": "https://teste.com"}],
    "status": "sucesso",
    "intencao": "buscar_queimadas",
    "intencao_score": 0.95,
    "entidades_detectadas_json": {"municipio": "jacarei"},
    "filtros_detectados_json": {"municipio": "jacarei"},
    "sql_executado": None,
    "mensagem_erro": None,
    "tempo_resposta_ms": 100,
    "bbox": None,
}


@patch("nlp_processor.index.run_agent", new_callable=AsyncMock)
class TestChatRouterDB:
    async def test_post_mensagem_cria_chat(
        self, mock_run_agent, test_client
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        resp = await test_client.post(
            "/chat/mensagem",
            json={"pergunta": "Queimadas em Jacareí?"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sucesso"
        assert isinstance(data["chat_id"], str)
        assert len(data["chat_id"]) == 36

    async def test_post_mensagem_retorna_schema_completo(
        self, mock_run_agent, test_client
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        resp = await test_client.post(
            "/chat/mensagem",
            json={"pergunta": "Queimadas em Jacareí?"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "chat_id" in data
        assert "consulta_id" in data
        assert "resposta_id" in data
        assert "texto_resposta" in data
        assert "fontes_citadas" in data
        assert "mapa" in data
        assert "status" in data

    async def test_post_mensagem_com_chat_id_existente(
        self, mock_run_agent, test_client, db_session
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        chat = Chat()
        db_session.add(chat)
        await db_session.flush()

        resp = await test_client.post(
            "/chat/mensagem",
            json={"pergunta": "Mais queimadas?", "chat_id": str(chat.id)},
        )

        assert resp.status_code == 200
        assert resp.json()["chat_id"] == str(chat.id)

    async def test_post_mensagem_pergunta_muito_curta(
        self, mock_run_agent, test_client
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        resp = await test_client.post(
            "/chat/mensagem",
            json={"pergunta": "ab"},
        )

        assert resp.status_code == 422

    async def test_get_lista_chats(
        self, mock_run_agent, test_client, db_session
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        chat1 = Chat(title="Chat 1")
        chat2 = Chat(title="Chat 2")
        db_session.add_all([chat1, chat2])
        await db_session.flush()

        resp = await test_client.get("/chat/")
        assert resp.status_code == 200
        data = resp.json()
        ids = [c["id"] for c in data]
        assert str(chat1.id) in ids
        assert str(chat2.id) in ids

    async def test_get_historico_chat(
        self, mock_run_agent, test_client, db_session
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        chat = Chat(title="Historico Teste")
        db_session.add(chat)
        await db_session.flush()

        consulta = ConsultaUsuario(
            chat_id=chat.id, pergunta="Pergunta 1?", turno=1
        )
        db_session.add(consulta)
        await db_session.flush()

        resposta = RespostaSistema(
            consulta_usuario_id=consulta.id,
            texto_resposta="Resposta 1",
            status="sucesso",
        )
        db_session.add(resposta)
        await db_session.flush()

        resp = await test_client.get(f"/chat/{chat.id}/historico")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chat_id"] == str(chat.id)
        assert data["title"] == "Historico Teste"
        assert len(data["mensagens"]) == 1
        assert data["mensagens"][0]["pergunta"] == "Pergunta 1?"

    async def test_get_historico_chat_404(
        self, mock_run_agent, test_client
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        fake_id = uuid4()
        resp = await test_client.get(f"/chat/{fake_id}/historico")
        assert resp.status_code == 404

    async def test_delete_chat(
        self, mock_run_agent, test_client, db_session
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        chat = Chat()
        db_session.add(chat)
        await db_session.flush()

        resp = await test_client.delete(f"/chat/{chat.id}")
        assert resp.status_code == 200

        chat_db = await db_session.get(Chat, chat.id)
        assert chat_db.ativo is False

    async def test_delete_chat_404(
        self, mock_run_agent, test_client
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        resp = await test_client.delete(f"/chat/{uuid4()}")
        assert resp.status_code == 404

    async def test_post_feedback(
        self, mock_run_agent, test_client, db_session
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        consulta = ConsultaUsuario(pergunta="Teste?", turno=1)
        db_session.add(consulta)
        await db_session.flush()

        resposta = RespostaSistema(
            consulta_usuario_id=consulta.id,
            texto_resposta="Resposta",
            status="sucesso",
        )
        db_session.add(resposta)
        await db_session.flush()

        resp = await test_client.post(
            "/chat/feedback",
            json={"resposta_sistema_id": str(resposta.id), "avaliacao": 1},
        )
        assert resp.status_code == 201
        assert "sucesso" in resp.json()["mensagem"].lower()

        stmt = select(FeedbackResposta).where(
            FeedbackResposta.resposta_sistema_id == resposta.id
        )
        fb = (await db_session.execute(stmt)).scalar_one()
        assert fb.avaliacao == 1

    async def test_post_feedback_404(
        self, mock_run_agent, test_client
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        resp = await test_client.post(
            "/chat/feedback",
            json={"resposta_sistema_id": str(uuid4()), "avaliacao": -1},
        )
        assert resp.status_code == 404

    async def test_get_geojson_resposta(
        self, mock_run_agent, test_client, db_session
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        geojson = {"type": "FeatureCollection", "features": []}
        consulta = ConsultaUsuario(pergunta="Geo?", turno=1)
        db_session.add(consulta)
        await db_session.flush()

        resposta = RespostaSistema(
            consulta_usuario_id=consulta.id,
            texto_resposta="Com mapa",
            status="sucesso",
            mapa_geojson=geojson,
        )
        db_session.add(resposta)
        await db_session.flush()

        resp = await test_client.get(f"/chat/resposta/{resposta.id}/geojson")
        assert resp.status_code == 200
        assert resp.json() == geojson

    async def test_get_geojson_resposta_404(
        self, mock_run_agent, test_client
    ):
        mock_run_agent.return_value = dict(_AGENT_RESULT)

        resp = await test_client.get(f"/chat/resposta/{uuid4()}/geojson")
        assert resp.status_code == 404
