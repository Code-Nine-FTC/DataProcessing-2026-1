from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from api.schemas.chat import ChatMensagemRequest, FeedbackRequest
from api.services.chat_service import ChatService
from api.utils.exceptions import NLPProcessingError, DataNotFoundError
from models.db_model import Chat, ConsultaUsuario, FeedbackResposta, RespostaSistema

pytestmark = pytest.mark.integration

_NLP_RESULT = {
    "chat_id": uuid4(),
    "consulta_id": uuid4(),
    "resposta_id": uuid4(),
    "texto_resposta": "Resposta do NLP mockada para teste.",
    "fontes_citadas": [{"nome": "Fonte Teste", "orgao": "Orgão Teste", "url": "https://teste.com"}],
    "mapa": {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-45.9, -23.2]},
                "properties": {"nome": "Ponto Teste"},
            }
        ],
    },
    "bbox": [-46.0, -23.3, -45.8, -23.1],
    "status": "sucesso",
    "qgis": None,
    "fallback_info": None,
}


@pytest.fixture
def service():
    return ChatService()


class TestChatServiceDB:
    async def test_enviar_mensagem_sucesso(
        self, service, db_session
    ):
        req = ChatMensagemRequest(pergunta="Queimadas em Jacareí?")

        with patch.object(service, "_process_with_fallback", new=AsyncMock(return_value=dict(_NLP_RESULT))):
            resp = await service.enviar_mensagem(req, db_session)

        assert resp.status == "sucesso"
        assert resp.texto_resposta == _NLP_RESULT["texto_resposta"]
        assert isinstance(resp.chat_id, UUID)
        assert resp.fallback_info is None
        assert len(resp.fontes_citadas) == 1
        assert resp.mapa.type == "FeatureCollection"
        assert resp.bbox == _NLP_RESULT["bbox"]

    async def test_enviar_mensagem_retorna_chat_id(
        self, service, db_session
    ):
        req = ChatMensagemRequest(pergunta="Teste?")

        with patch.object(service, "_process_with_fallback", new=AsyncMock(return_value=dict(_NLP_RESULT))):
            resp = await service.enviar_mensagem(req, db_session)

        assert isinstance(resp.chat_id, UUID)

    async def test_enviar_mensagem_nlp_error_retorna_fallback(
        self, service, db_session
    ):
        req = ChatMensagemRequest(pergunta="Falha no NLP")

        with patch.object(service, "_process_with_fallback", new=AsyncMock(side_effect=NLPProcessingError("erro simulado"))):
            resp = await service.enviar_mensagem(req, db_session)

        assert resp.status == "erro"
        assert resp.fallback_info is not None
        assert resp.fallback_info.tipo_fallback == "nlp_fallback"
        assert "reformular" in resp.fallback_info.mensagem_usuario.lower()

    async def test_enviar_mensagem_data_not_found_retorna_fallback(
        self, service, db_session
    ):
        req = ChatMensagemRequest(pergunta="Dados nao encontrados")

        with patch.object(service, "_process_with_fallback", new=AsyncMock(side_effect=DataNotFoundError("sem dados"))):
            resp = await service.enviar_mensagem(req, db_session)

        assert resp.status == "erro"
        assert resp.fallback_info is not None
        assert resp.fallback_info.tipo_fallback == "data_fallback"

    async def test_listar_chats_retorna_somente_ativos(
        self, service, db_session
    ):
        chat1 = Chat()
        chat2 = Chat()
        chat3 = Chat()
        chat3.ativo = False
        db_session.add_all([chat1, chat2, chat3])
        await db_session.flush()

        chats = await service.listar_chats(db_session)

        ids = {c.id for c in chats}
        assert chat1.id in ids
        assert chat2.id in ids
        assert chat3.id not in ids

    async def test_historico_chat_retorna_mensagens(
        self, service, db_session
    ):
        from models.db_model import ConsultaUsuario, RespostaSistema

        chat = Chat()
        chat.title = "Chat Teste"
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

        historico = await service.historico_chat(chat.id, db_session)

        assert historico.chat_id == chat.id
        assert historico.title == "Chat Teste"
        assert len(historico.mensagens) == 1
        assert historico.mensagens[0].pergunta == "Pergunta 1?"
        assert historico.mensagens[0].resposta == "Resposta 1"
        assert historico.mensagens[0].turno == 1

    async def test_historico_chat_404_se_chat_inexistente(
        self, service, db_session
    ):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await service.historico_chat(uuid4(), db_session)
        assert exc.value.status_code == 404

    async def test_registrar_feedback(
        self, service, db_session
    ):
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

        result = await service.registrar_feedback(
            FeedbackRequest(resposta_sistema_id=resposta.id, avaliacao=1),
            db_session,
        )

        assert "sucesso" in result["mensagem"].lower()

        stmt = select(FeedbackResposta).where(
            FeedbackResposta.resposta_sistema_id == resposta.id
        )
        fb = (await db_session.execute(stmt)).scalar_one()
        assert fb.avaliacao == 1

    async def test_registrar_feedback_404_se_resposta_inexistente(
        self, service, db_session
    ):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await service.registrar_feedback(
                FeedbackRequest(resposta_sistema_id=uuid4(), avaliacao=-1),
                db_session,
            )
        assert exc.value.status_code == 404

    async def test_desativar_chat(
        self, service, db_session
    ):
        chat = Chat()
        db_session.add(chat)
        await db_session.flush()

        result = await service.desativar_chat(chat.id, db_session)
        assert "sucesso" in result["mensagem"].lower()

        chat_db = await db_session.get(Chat, chat.id)
        assert chat_db.ativo is False

    async def test_desativar_chat_404_se_inexistente(
        self, service, db_session
    ):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await service.desativar_chat(uuid4(), db_session)
        assert exc.value.status_code == 404

    async def test_geojson_por_resposta(
        self, service, db_session
    ):
        consulta = ConsultaUsuario(pergunta="Teste?", turno=1)
        db_session.add(consulta)
        await db_session.flush()

        geojson = {"type": "FeatureCollection", "features": []}
        resposta = RespostaSistema(
            consulta_usuario_id=consulta.id,
            texto_resposta="Resposta",
            status="sucesso",
            mapa_geojson=geojson,
        )
        db_session.add(resposta)
        await db_session.flush()

        result = await service.geojson_por_resposta(resposta.id, db_session)
        assert result == geojson
