# -*- coding: utf-8 -*-
import uuid
from time import time
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from api.schemas.chat import ChatMensagemRequest
from api.services.chat_service import ChatService
from api.utils.exceptions import NLPProcessingError, DatabaseConnectionError, DataNotFoundError


@pytest.fixture
def service():
    return ChatService()


@pytest.fixture
def req():
    return ChatMensagemRequest(
        pergunta="pergunta de teste",
        chat_id=None,
    )


@pytest.fixture
def mock_session():
    return AsyncMock()


class TestBuildFallbackResponse:
    def test_retorna_chat_mensagem_response(self, service, req):
        start = time()
        response = service._build_fallback_response(
            tipo="nlp_fallback",
            req=req,
            mensagem="mensagem de fallback",
            sugestoes=["sugestao 1"],
            start_time=start,
        )

        assert response.texto_resposta == "mensagem de fallback"
        assert response.status == "erro"
        assert response.fontes_citadas == []
        assert response.fallback_info is not None
        assert response.fallback_info.tipo_fallback == "nlp_fallback"
        assert response.fallback_info.sugestoes == ["sugestao 1"]

    def test_contem_ids_validos(self, service, req):
        start = time()
        response = service._build_fallback_response(
            tipo="data_fallback",
            req=req,
            mensagem="sem dados",
            sugestoes=[],
            start_time=start,
        )

        assert isinstance(response.chat_id, uuid.UUID)
        assert isinstance(response.consulta_id, uuid.UUID)
        assert isinstance(response.resposta_id, uuid.UUID)

    def test_usa_chat_id_existente(self, service, mock_session):
        chat_id = uuid.uuid4()
        req = ChatMensagemRequest(pergunta="teste", chat_id=chat_id)
        start = time()

        response = service._build_fallback_response(
            tipo="generic_fallback",
            req=req,
            mensagem="erro generico",
            sugestoes=[],
            start_time=start,
        )

        assert response.chat_id == chat_id

    def test_mapa_vazio(self, service, req):
        start = time()
        response = service._build_fallback_response(
            tipo="nlp_fallback",
            req=req,
            mensagem="fallback",
            sugestoes=[],
            start_time=start,
        )

        assert response.mapa.type == "FeatureCollection"
        assert response.mapa.features == []

    def test_fallback_info_completo(self, service, req):
        start = time()
        response = service._build_fallback_response(
            tipo="connection_fallback",
            req=req,
            mensagem="erro de conexao",
            sugestoes=["tentar mais tarde"],
            start_time=start,
        )

        fi = response.fallback_info
        assert fi.tipo_fallback == "connection_fallback"
        assert fi.mensagem_usuario == "erro de conexao"
        assert fi.sugestoes == ["tentar mais tarde"]
        assert fi.retry_count == 0
        assert fi.timestamp is not None


class TestHandleFallbacks:
    @pytest.mark.asyncio
    async def test_handle_nlp_fallback_mensagem_e_sugestoes(self, service, req):
        start = time()
        response = await service._handle_nlp_fallback(
            req=req,
            e=NLPProcessingError("falha nlp"),
            start_time=start,
        )

        assert "Não consegui entender" in response.texto_resposta
        assert "Queimadas em [município]" in response.fallback_info.sugestoes
        assert "Risco ambiental de [propriedade]" in response.fallback_info.sugestoes

    @pytest.mark.asyncio
    async def test_handle_data_fallback_mensagem_e_sugestoes(self, service, req):
        start = time()
        response = await service._handle_data_fallback(
            req=req,
            e=DataNotFoundError("dados nao encontrados"),
            start_time=start,
        )

        assert "não encontrei informações" in response.texto_resposta
        assert "Deseja pesquisar sobre outro tema?" in response.fallback_info.sugestoes
        assert "Listar propriedades com risco" in response.fallback_info.sugestoes
        assert "Exibir alertas recentes" in response.fallback_info.sugestoes

    @pytest.mark.asyncio
    async def test_handle_database_fallback_mensagem(self, service, req):
        start = time()
        response = await service._handle_database_fallback(
            req=req,
            e=DatabaseConnectionError("conexao falhou"),
            start_time=start,
        )

        assert "dificuldade de acessar os dados" in response.texto_resposta
        assert response.fallback_info.sugestoes == []

    @pytest.mark.asyncio
    async def test_handle_generic_fallback_mensagem(self, service, req):
        start = time()
        response = await service._handle_generic_fallback(
            req=req,
            e=Exception("erro inesperado"),
            start_time=start,
        )

        assert "erro inesperado" in response.texto_resposta
        assert "Tentar novamente" in response.fallback_info.sugestoes

    @pytest.mark.asyncio
    async def test_handle_database_fallback_tambem_trata_sqlalchemy_error(self, service, req):
        start = time()
        response = await service._handle_database_fallback(
            req=req,
            e=SQLAlchemyError("deadlock detected"),
            start_time=start,
        )

        assert "dificuldade de acessar os dados" in response.texto_resposta


class TestEnviarMensagemComFallback:
    @pytest.mark.asyncio
    async def test_sucesso_sem_fallback(self, service, mock_session):
        service._process_with_fallback = AsyncMock(return_value={
            "chat_id": uuid.uuid4(),
            "consulta_id": uuid.uuid4(),
            "resposta_id": uuid.uuid4(),
            "texto_resposta": "resposta normal",
            "fontes_citadas": [{"nome": "INPE", "orgao": "INPE", "url": None}],
            "mapa": {"type": "FeatureCollection", "features": []},
            "bbox": None,
            "status": "sucesso",
        })

        response = await service.enviar_mensagem(
            req=ChatMensagemRequest(pergunta="queimadas em campinas"),
            session=mock_session,
        )

        assert response.texto_resposta == "resposta normal"
        assert response.status == "sucesso"
        assert response.fallback_info is None
        assert len(response.fontes_citadas) == 1

    @pytest.mark.asyncio
    async def test_fallback_quando_nlp_processing_error(self, service, mock_session):
        service._process_with_fallback = AsyncMock(
            side_effect=NLPProcessingError("falha nlp")
        )

        response = await service.enviar_mensagem(
            req=ChatMensagemRequest(pergunta="pergunta invalida"),
            session=mock_session,
        )

        assert response.status == "erro"
        assert response.fallback_info is not None
        assert response.fallback_info.tipo_fallback == "nlp_fallback"

    @pytest.mark.asyncio
    async def test_fallback_quando_data_not_found(self, service, mock_session):
        service._process_with_fallback = AsyncMock(
            side_effect=DataNotFoundError("dados inexistentes")
        )

        response = await service.enviar_mensagem(
            req=ChatMensagemRequest(pergunta="dados que nao existem"),
            session=mock_session,
        )

        assert response.status == "erro"
        assert response.fallback_info.tipo_fallback == "data_fallback"

    @pytest.mark.asyncio
    async def test_fallback_quando_database_connection_error(self, service, mock_session):
        service._process_with_fallback = AsyncMock(
            side_effect=DatabaseConnectionError("banco offline")
        )

        response = await service.enviar_mensagem(
            req=ChatMensagemRequest(pergunta="teste"),
            session=mock_session,
        )

        assert response.fallback_info.tipo_fallback == "connection_fallback"

    @pytest.mark.asyncio
    async def test_fallback_quando_sqlalchemy_error(self, service, mock_session):
        service._process_with_fallback = AsyncMock(
            side_effect=SQLAlchemyError("deadlock")
        )

        response = await service.enviar_mensagem(
            req=ChatMensagemRequest(pergunta="teste"),
            session=mock_session,
        )

        assert response.fallback_info.tipo_fallback == "connection_fallback"

    @pytest.mark.asyncio
    async def test_fallback_quando_exception_generica(self, service, mock_session):
        service._process_with_fallback = AsyncMock(
            side_effect=Exception("erro totalmente inesperado")
        )

        response = await service.enviar_mensagem(
            req=ChatMensagemRequest(pergunta="teste"),
            session=mock_session,
        )

        assert response.fallback_info.tipo_fallback == "generic_fallback"

    @pytest.mark.asyncio
    async def test_build_success_response_sem_fallback_info(self, service):
        result = {
            "chat_id": uuid.uuid4(),
            "consulta_id": uuid.uuid4(),
            "resposta_id": uuid.uuid4(),
            "texto_resposta": "sucesso",
            "fontes_citadas": [],
            "mapa": {"type": "FeatureCollection", "features": []},
            "bbox": None,
            "status": "sucesso",
        }

        response = service._build_success_response(result)

        assert response.fallback_info is None
        assert response.status == "sucesso"

    @pytest.mark.asyncio
    async def test_exception_no_process_with_fallback_propaga(self, service, mock_session):
        with patch.object(service, '_process_with_fallback',
                          AsyncMock(side_effect=NLPProcessingError("erro"))):
            with patch.object(service, '_handle_nlp_fallback',
                              AsyncMock(return_value="handled")) as mock_handler:
                result = await service.enviar_mensagem(
                    req=ChatMensagemRequest(pergunta="teste"),
                    session=mock_session,
                )
                mock_handler.assert_called_once()


class TestFallbackLogger:
    def test_logger_recebe_parametros(self):
        from unittest.mock import MagicMock
        from api.utils.fallback_logger import FallbackLogger
        logger = FallbackLogger()
        logger.logger = MagicMock()

        logger.log_fallback_event(
            tipo_fallback="nlp_fallback",
            pergunta_original="teste",
            resposta_fallback="mensagem de fallback",
            sugestoes_providas=["sugestao"],
            tempo_resposta=0.5,
            chat_id="abc-123",
        )

        logger.logger.warning.assert_called_once()
        log_msg = logger.logger.warning.call_args[0][0]
        assert "nlp_fallback" in log_msg
        assert "teste" in log_msg


class TestFallbackMetrics:
    def test_registrar_fallback_incrementa_total(self):
        from api.utils.fallback_metrics import FallbackMetrics
        metrics = FallbackMetrics()

        metrics.registrar_fallback("nlp_fallback", 0.5)
        assert metrics.metrics["total_fallbacks"] == 1
        assert metrics.metrics["por_tipo"]["nlp_fallback"] == 1

    def test_registrar_fallback_calcula_media(self):
        from api.utils.fallback_metrics import FallbackMetrics
        metrics = FallbackMetrics()

        metrics.registrar_fallback("nlp_fallback", 1.0)
        metrics.registrar_fallback("nlp_fallback", 3.0)

        assert metrics.metrics["total_fallbacks"] == 2
        assert metrics.metrics["tempo_medio"] == 2.0

    def test_registrar_fallback_multiplos_tipos(self):
        from api.utils.fallback_metrics import FallbackMetrics
        metrics = FallbackMetrics()

        metrics.registrar_fallback("nlp_fallback", 0.3)
        metrics.registrar_fallback("data_fallback", 0.5)
        metrics.registrar_fallback("connection_fallback", 1.0)
        metrics.registrar_fallback("generic_fallback", 0.2)

        assert metrics.metrics["total_fallbacks"] == 4
        assert metrics.metrics["por_tipo"]["nlp_fallback"] == 1
        assert metrics.metrics["por_tipo"]["data_fallback"] == 1
        assert metrics.metrics["por_tipo"]["connection_fallback"] == 1
        assert metrics.metrics["por_tipo"]["generic_fallback"] == 1

    def test_registrar_fallback_tipo_desconhecido(self):
        from api.utils.fallback_metrics import FallbackMetrics
        metrics = FallbackMetrics()

        metrics.registrar_fallback("tipo_desconhecido", 0.5)

        assert metrics.metrics["total_fallbacks"] == 1
        assert "tipo_desconhecido" not in metrics.metrics["por_tipo"]

    def test_obter_metricas(self):
        from api.utils.fallback_metrics import FallbackMetrics
        metrics = FallbackMetrics()

        metrics.registrar_fallback("nlp_fallback", 1.0)
        metrics.registrar_fallback("data_fallback", 2.0)

        assert metrics.metrics["total_fallbacks"] == 2
        assert metrics.metrics["tempo_medio"] == 1.5


class TestExceptions:
    def test_nlp_processing_error(self):
        with pytest.raises(NLPProcessingError):
            raise NLPProcessingError("falha no processamento nlp")

    def test_database_connection_error(self):
        with pytest.raises(DatabaseConnectionError):
            raise DatabaseConnectionError("falha de conexao com banco")

    def test_data_not_found_error(self):
        with pytest.raises(DataNotFoundError):
            raise DataNotFoundError("dados nao encontrados no banco")

    def test_exceptions_sao_exception_subclass(self):
        assert issubclass(NLPProcessingError, Exception)
        assert issubclass(DatabaseConnectionError, Exception)
        assert issubclass(DataNotFoundError, Exception)
