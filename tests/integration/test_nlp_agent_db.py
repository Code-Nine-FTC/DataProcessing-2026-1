from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy import select

from models.db_model import Chat, ConsultaUsuario, IntencaoConsulta, RespostaSistema
from nlp_processor.index import NLPProcessor

pytestmark = pytest.mark.integration

_DEFAULT_AGENT_RESULT = {
    "texto_resposta": "Teste de resposta do agente mockado.",
    "features": [],
    "fontes": [{"nome": "Fonte Teste", "orgao": "Orgão Teste", "url": "https://teste.com"}],
    "status": "sucesso",
    "intencao": "buscar_queimadas",
    "intencao_score": 0.95,
    "entidades_detectadas_json": {
        "municipio": "campinas",
        "data_inicio": None,
        "data_fim": None,
        "codigo_car": None,
        "palavras_chave": ["queimadas"],
    },
    "filtros_detectados_json": {"municipio": "campinas"},
    "sql_executado": "SELECT * FROM queimada_evento WHERE ...",
    "mensagem_erro": None,
    "tempo_resposta_ms": 150,
    "bbox": None,
}


@pytest.fixture
def processor():
    return NLPProcessor()


@patch("nlp_processor.index.run_agent", new_callable=AsyncMock)
class TestNLPProcessorProcess:
    async def test_process_cria_chat_quando_sem_chat_id(
        self, mock_run_agent, db_session, processor
    ):
        mock_run_agent.return_value = dict(_DEFAULT_AGENT_RESULT)

        result = await processor.process(
            session=db_session, pergunta="Queimadas em Campinas?"
        )

        assert result["status"] == "sucesso"
        chat_id = result["chat_id"]
        assert isinstance(chat_id, UUID)

        chat = await db_session.get(Chat, chat_id)
        assert chat is not None
        assert chat.title == "Queimadas em Campinas?"

    async def test_process_reusa_chat_existente(
        self, mock_run_agent, db_session, processor
    ):
        mock_run_agent.return_value = dict(_DEFAULT_AGENT_RESULT)

        chat = Chat()
        db_session.add(chat)
        await db_session.flush()

        result = await processor.process(
            session=db_session,
            pergunta="Mais queimadas?",
            chat_id=chat.id,
        )

        assert result["chat_id"] == chat.id

    async def test_process_persiste_consulta_usuario(
        self, mock_run_agent, db_session, processor
    ):
        mock_run_agent.return_value = dict(_DEFAULT_AGENT_RESULT)

        result = await processor.process(
            session=db_session, pergunta="Queimadas em Jacareí?"
        )

        consulta = await db_session.get(ConsultaUsuario, result["consulta_id"])
        assert consulta is not None
        assert consulta.pergunta == "Queimadas em Jacareí?"
        assert consulta.intencao_detectada == "buscar_queimadas"
        assert consulta.turno == 1

    async def test_process_persiste_resposta_sistema(
        self, mock_run_agent, db_session, processor
    ):
        mock_run_agent.return_value = dict(_DEFAULT_AGENT_RESULT)

        result = await processor.process(
            session=db_session, pergunta="Queimadas em Jacareí?"
        )

        resposta = await db_session.get(RespostaSistema, result["resposta_id"])
        assert resposta is not None
        assert resposta.texto_resposta == _DEFAULT_AGENT_RESULT["texto_resposta"]
        assert resposta.status == "sucesso"
        assert resposta.fontes_utilizadas_json == {"fontes": _DEFAULT_AGENT_RESULT["fontes"]}
        assert resposta.mapa_geojson == {"type": "FeatureCollection", "features": []}

    async def test_process_incrementa_turno(
        self, mock_run_agent, db_session, processor
    ):
        mock_run_agent.return_value = dict(_DEFAULT_AGENT_RESULT)

        chat_id = (await processor.process(
            session=db_session, pergunta="Primeira?"
        ))["chat_id"]

        result2 = await processor.process(
            session=db_session, pergunta="Segunda?", chat_id=chat_id
        )

        consulta2 = await db_session.get(ConsultaUsuario, result2["consulta_id"])
        assert consulta2.turno == 2

    async def test_process_cria_intencao_no_catalogo(
        self, mock_run_agent, db_session, processor
    ):
        mock_run_agent.return_value = dict(_DEFAULT_AGENT_RESULT)

        await processor.process(
            session=db_session, pergunta="Queimadas em Jacareí?"
        )

        stmt = select(IntencaoConsulta).where(IntencaoConsulta.nome == "buscar_queimadas")
        intencao = (await db_session.execute(stmt)).scalar_one_or_none()
        assert intencao is not None
        assert intencao.nome == "buscar_queimadas"

    async def test_process_carrega_historico_no_segundo_turno(
        self, mock_run_agent, db_session, processor
    ):
        mock_run_agent.return_value = dict(_DEFAULT_AGENT_RESULT)

        chat_id = (await processor.process(
            session=db_session, pergunta="Turno 1?"
        ))["chat_id"]

        call_args = []

        async def _side_effect(session, pergunta, historico, municipio=None):
            call_args.append((pergunta, historico))
            return dict(_DEFAULT_AGENT_RESULT)

        mock_run_agent.side_effect = _side_effect

        await processor.process(
            session=db_session, pergunta="Turno 2?", chat_id=chat_id
        )

        _, historico = call_args[0]
        assert len(historico) == 2
        assert historico[0]["role"] == "user"
        assert historico[0]["content"] == "Turno 1?"
        assert historico[1]["role"] == "assistant"

    async def test_process_computa_bbox_quando_nao_fornecido(
        self, mock_run_agent, db_session, processor
    ):
        result_dict = dict(_DEFAULT_AGENT_RESULT)
        result_dict["bbox"] = None
        result_dict["features"] = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-46.0, -23.0], [-45.0, -23.0], [-45.0, -22.0], [-46.0, -22.0], [-46.0, -23.0]]],
                },
                "properties": {},
            }
        ]
        mock_run_agent.return_value = result_dict

        result = await processor.process(
            session=db_session, pergunta="Queimadas?"
        )

        assert result["bbox"] is not None
        assert len(result["bbox"]) == 4
        assert result["bbox"][0] == -46.0
        assert result["bbox"][2] == -45.0

    async def test_process_status_erro_lanca_fallback(
        self, mock_run_agent, db_session, processor
    ):
        from api.utils.exceptions import NLPProcessingError

        result_dict = dict(_DEFAULT_AGENT_RESULT)
        result_dict["status"] = "erro"
        result_dict["mensagem_erro"] = "Erro simulado"
        mock_run_agent.return_value = result_dict

        with pytest.raises(NLPProcessingError):
            await processor.process(
                session=db_session, pergunta="Erro?"
            )

    async def test_process_status_sem_resultado_lanca_fallback(
        self, mock_run_agent, db_session, processor
    ):
        from api.utils.exceptions import DataNotFoundError

        result_dict = dict(_DEFAULT_AGENT_RESULT)
        result_dict["status"] = "sem_resultado"
        mock_run_agent.return_value = result_dict

        with pytest.raises(DataNotFoundError):
            await processor.process(
                session=db_session, pergunta="Sem dados?"
            )
