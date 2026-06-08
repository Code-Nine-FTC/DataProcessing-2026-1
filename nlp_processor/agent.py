# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any, Optional

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nlp_processor.pipeline.intent_classifier import get_classifier
from nlp_processor.pipeline.entity_extractor import Entidades, extrair_entidades
from nlp_processor.pipeline.embedder import get_embedder
from nlp_processor.pipeline.preprocessor import AdvancedGeoASGPreprocessor
from nlp_processor.pipeline.query_builder import executar_consulta
from nlp_processor.pipeline.response_formatter import format_pipeline_response
from models.db_model import Municipio

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.20
FEEDBACK_VALIDADE_MINUTOS = 30

_preprocessor = AdvancedGeoASGPreprocessor()

_ESCOPO_AMBIENTAL_TOKENS = frozenset({
    "ambiental", "ambientais", "meio ambiente",
    "queimada", "queimadas", "incendio", "incendios", "foco", "focos", "fogo",
    "desmatamento", "desmatamentos", "desmatado", "desmatada", "supressao",
    "prodes", "deter",
    "sicar", "car", "imovel", "imoveis", "propriedade", "propriedades",
    "fazenda", "fazendas", "sitio", "sitios", "rural", "rurais",
    "mapa", "geografia", "geometria", "coordenada", "localizacao",
    "quilombo", "quilombos", "quilombola", "quilombolas",
    "terra indigena", "terras indigenas", "indigena", "indigenas",
    "unidade de conservacao", "unidades de conservacao", "uc", "ucs",
    "parque", "apa", "resex", "rebio", "estacao ecologica", "flona", "rppn",
    "assentamento", "assentamentos", "bacia", "risco", "camada", "camadas",
    "municipio", "municipios", "cidade", "estado de sao paulo", "sao paulo",
})

_TOKENS_IMOVEL = frozenset({
    "imovel", "imoveis", "fazenda", "fazendas",
    "propriedade", "propriedades", "sitio", "sitios",
})

_TOKENS_PASSIVO = frozenset({
    "passivo", "passivos", "sobreposicao", "preservacao",
    "area de preservacao", "area protegida",
    "unidade de conservacao", "unidades de conservacao",
    "terra indigena", "terras indigenas",
    "quilombo", "quilombola", "desmatamento",
})

_TOKENS_QUEIMADA_IMOVEL = frozenset({
    "foco", "focos", "queimada", "incendio", "incendios",
})

_TOKENS_LOCALIZACAO = frozenset({
    "imovel", "imoveis", "fazenda", "fazendas", "propriedade", "propriedades",
    "sitio", "sitios", "sicar", "mapa", "geografia", "geometria",
    "localize", "localizar", "mostre", "mostrar", "exibir", "exiba",
})

_PROMOCOES_IMOVEL: list[tuple[frozenset[str], str]] = [
    (frozenset({"queimada", "queimadas", "incendio", "incendios", "foco", "focos"}), "buscar_imoveis_queimada"),
    (frozenset({"desmatamento", "desmatamentos", "desmatado", "desmatada", "supressao", "deter", "prodes"}), "buscar_imoveis_desmatamento"),
    (frozenset({"quilombo", "quilombos", "quilombola", "quilombolas"}), "buscar_imoveis_quilombo"),
    (frozenset({"terra indigena", "terras indigenas", "indigena", "indigenas"}), "buscar_imoveis_ti"),
]

_REBAIXAMENTOS: dict[str, str] = {
    "buscar_imoveis_queimada": "buscar_queimadas",
    "buscar_imoveis_desmatamento": "buscar_desmatamentos",
    "buscar_imoveis_quilombo": "buscar_quilombolas",
    "buscar_imoveis_ti": "buscar_terras_indigenas",
}

_FALLBACKS_POR_TOKEN: list[tuple[frozenset[str], str]] = [
    (_TOKENS_IMOVEL, "buscar_imoveis_rurais"),
    (frozenset({"queimada", "queimadas", "incendio", "incendios", "foco", "focos"}), "buscar_queimadas"),
    (frozenset({"desmatamento", "desmatamentos", "desmatado", "desmatada", "supressao", "deter", "prodes"}), "buscar_desmatamentos"),
    (frozenset({"quilombo", "quilombos", "quilombola", "quilombolas"}), "buscar_quilombolas"),
    (frozenset({"terra indigena", "terras indigenas", "indigena", "indigenas"}), "buscar_terras_indigenas"),
    (frozenset({"unidade de conservacao", "unidades de conservacao", "parque", "apa", "resex", "rebio", "estacao ecologica", "flona", "rppn"}), "buscar_unidades_conservacao"),
]


def _texto_contem(texto: str, tokens: frozenset[str]) -> bool:
    return any(t in texto for t in tokens)


def _extrair_feedback_contexto(
    historico: list[dict],
    intencao_atual: Optional[str] = None,
    agora: Optional[datetime] = None,
) -> dict[str, int]:
    ultima_assistente = next(
        (m for m in reversed(historico) if m.get("role") == "assistant"), None
    )
    if not ultima_assistente:
        return {}

    feedback = ultima_assistente.get("feedback")
    if isinstance(feedback, dict):
        feedback = feedback.get("avaliacao")
    if feedback not in (-1, 1):
        return {}

    intencao_anterior = ultima_assistente.get("intencao")
    if intencao_atual and intencao_anterior and intencao_atual != intencao_anterior:
        logger.info("Feedback descartado: mudança de intenção (%s -> %s).", intencao_anterior, intencao_atual)
        return {}

    data_anterior = ultima_assistente.get("data_hora")
    if isinstance(data_anterior, datetime):
        referencia = agora or datetime.utcnow()
        if referencia - data_anterior > timedelta(minutes=FEEDBACK_VALIDADE_MINUTOS):
            logger.info("Feedback descartado: fora da janela de %d min.", FEEDBACK_VALIDADE_MINUTOS)
            return {}

    logger.info("Feedback do turno anterior aplicado: avaliacao=%s.", feedback)
    return {"avaliacao": int(feedback)}


async def _carregar_municipios_normalizados(session: AsyncSession) -> list[str]:
    stmt = select(Municipio.nome).where(Municipio.nome.is_not(None))
    result = await session.execute(stmt)
    nomes: set[str] = set()
    for (nome,) in result.all():
        processed = _preprocessor.process(nome)
        nomes.add(processed["text_for_entities_and_rag"])
    logger.info("Carregados %d municípios normalizados do banco.", len(nomes))
    return sorted(nomes)


def _serializar_entidades(entidades: Entidades) -> dict[str, Any]:
    return asdict(entidades)


def _serializar_filtros(entidades_json: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entidades_json.items() if k != "palavras_chave" and v is not None}


def _fora_escopo(texto_norm: str, entidades: Entidades) -> bool:
    if entidades.codigo_car or entidades.municipio or entidades.regiao_administrativa:
        return False
    return not _texto_contem(texto_norm, _ESCOPO_AMBIENTAL_TOKENS)


def _resolver_intencao_por_car(texto_norm: str, entidades: Entidades, intencao_principal: str) -> Optional[str]:
    if not entidades.codigo_car:
        return None
    if _texto_contem(texto_norm, _TOKENS_PASSIVO):
        return "buscar_passivos_imovel"
    if _texto_contem(texto_norm, _TOKENS_QUEIMADA_IMOVEL):
        return "buscar_focos_queimada_imovel"
    if _texto_contem(texto_norm, _TOKENS_LOCALIZACAO):
        return "buscar_imoveis_rurais"
    return "buscar_imoveis_rurais"


def _aplicar_promocao_imovel(texto_norm: str, intencao: str) -> Optional[str]:
    if not _texto_contem(texto_norm, _TOKENS_IMOVEL):
        return None
    for tokens, alvo in _PROMOCOES_IMOVEL:
        if intencao != alvo and _texto_contem(texto_norm, tokens):
            return alvo
    return None


def _aplicar_rebaixamento(texto_norm: str, intencao: str) -> Optional[str]:
    if intencao in _REBAIXAMENTOS and not _texto_contem(texto_norm, _TOKENS_IMOVEL):
        return _REBAIXAMENTOS[intencao]
    return None


def _inferir_intencao_por_vocabulario(texto_norm: str, entidades: Entidades) -> str:
    for tokens, alvo in _FALLBACKS_POR_TOKEN:
        if _texto_contem(texto_norm, tokens):
            return alvo
    if entidades.municipio:
        return "buscar_queimadas"
    return "buscar_documentos"


def _resolver_intencao_final(
    texto_norm: str,
    entidades: Entidades,
    intencoes_classificadas: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    intencao_principal, confianca = intencoes_classificadas[0]

    if _fora_escopo(texto_norm, entidades):
        logger.info("Pergunta marcada como fora_escopo.")
        return [("fora_escopo", 1.0)]

    override_car = _resolver_intencao_por_car(texto_norm, entidades, intencao_principal)
    if override_car:
        logger.info("Intent override por CAR (%s): %s.", entidades.codigo_car, override_car)
        return [(override_car, confianca)]

    promocao = _aplicar_promocao_imovel(texto_norm, intencao_principal)
    if promocao:
        logger.info("Promoção de intent: %s -> %s.", intencao_principal, promocao)
        return [(promocao, confianca)]

    rebaixamento = _aplicar_rebaixamento(texto_norm, intencao_principal)
    if rebaixamento:
        logger.info("Rebaixamento de intent: %s -> %s.", intencao_principal, rebaixamento)
        return [(rebaixamento, confianca)]

    if confianca < CONFIDENCE_THRESHOLD:
        inferida = _inferir_intencao_por_vocabulario(texto_norm, entidades)
        logger.info("Confiança baixa (%.2f) — inferindo intent: %s.", confianca, inferida)
        return [(inferida, confianca)]

    return intencoes_classificadas


def _build_resultado_erro(
    inicio: float,
    texto: str,
    mensagem: str,
    intencao: Optional[str] = None,
    confianca: Optional[float] = None,
    entidades_json: Optional[dict] = None,
    filtros_json: Optional[dict] = None,
) -> dict[str, Any]:
    return {
        "texto_resposta": texto,
        "features": [],
        "fontes": [],
        "status": "erro",
        "intencao": intencao,
        "intencao_score": confianca,
        "entidades_detectadas_json": entidades_json or {},
        "filtros_detectados_json": filtros_json or {},
        "sql_executado": None,
        "mensagem_erro": mensagem,
        "tempo_resposta_ms": int((perf_counter() - inicio) * 1000),
    }


def _determinar_status(intencoes: list[tuple[str, float]], features: list, contexto_documental: str) -> str:
    intencao_principal = intencoes[0][0] if intencoes else "fora_escopo"
    if intencao_principal == "fora_escopo":
        return "fora_escopo"
    if intencao_principal != "buscar_documentos" and not features:
        return "sem_resultado"
    if not features and not contexto_documental:
        return "sem_resultado"
    return "sucesso"


async def run_agent(
    session: AsyncSession,
    pergunta: str,
    historico: list[dict],
    municipio: Optional[str] = None,
) -> dict[str, Any]:
    inicio = perf_counter()
    classifier = get_classifier()
    embedder = get_embedder()

    if not classifier.is_ready():
        logger.error("Modelo de intenções não treinado.")
        return _build_resultado_erro(
            inicio=inicio,
            texto="Ocorreu um erro interno. Tente novamente.",
            mensagem="Modelo de intenções não treinado.",
        )

    preprocessed = _preprocessor.process(pergunta)
    texto_norm = preprocessed["text_for_entities_and_rag"]

    intencoes_classificadas = classifier.predict_multiple(preprocessed)
    logger.info("Intenções detectadas: %s", intencoes_classificadas)

    municipios_extras: list[str] = []
    try:
        municipios_extras = await _carregar_municipios_normalizados(session)
    except Exception:
        logger.warning("Não foi possível carregar municípios do banco; usando gazetteer estático.")

    entidades = extrair_entidades(preprocessed, municipios_extras)

    if municipio and not entidades.municipio and not entidades.codigo_car and not _fora_escopo(texto_norm, entidades):
        logger.info("Injetando município do filtro: %s", municipio)
        entidades.municipio = municipio

    entidades_json = _serializar_entidades(entidades)
    filtros_json = _serializar_filtros(entidades_json)

    intencoes_resolvidas = _resolver_intencao_final(texto_norm, entidades, intencoes_classificadas)
    intencao_principal, confianca_principal = intencoes_resolvidas[0]

    query_embedding: list[float] = []
    try:
        query_embedding = embedder.embed(preprocessed)
    except Exception:
        logger.warning("Não foi possível gerar embedding — RAG desativado.")

    try:
        resultado = await executar_consulta(
            session=session,
            intents=intencoes_resolvidas,
            entities=entidades,
            query_embedding=query_embedding,
        )
    except Exception:
        logger.exception("Erro ao executar consulta no banco.")
        return _build_resultado_erro(
            inicio=inicio,
            texto="Ocorreu um erro ao consultar os dados. Tente novamente.",
            mensagem="Erro ao executar consulta no banco.",
            intencao=intencao_principal,
            confianca=confianca_principal,
            entidades_json=entidades_json,
            filtros_json=filtros_json,
        )

    features = resultado["features"]
    fontes = resultado["fontes"]
    contexto_documental = resultado["contexto_documental"]
    status = _determinar_status(intencoes_resolvidas, features, contexto_documental)

    feedback_contexto = _extrair_feedback_contexto(historico, intencao_atual=intencao_principal)

    texto = format_pipeline_response(
        intents=intencoes_resolvidas,
        entities=entidades,
        total_features=len(features),
        sources=fontes,
        document_context=contexto_documental,
        query_description=resultado.get("descricao"),
        feedback_context=feedback_contexto or None,
        features=features,
    )

    return {
        "texto_resposta": texto,
        "features": features,
        "bbox": resultado.get("bbox"),
        "fontes": fontes,
        "status": status,
        "intencao": intencao_principal,
        "intencao_score": confianca_principal,
        "entidades_detectadas_json": entidades_json,
        "filtros_detectados_json": filtros_json,
        "sql_executado": resultado.get("sql_executado"),
        "mensagem_erro": resultado.get("mensagem_erro"),
        "tempo_resposta_ms": int((perf_counter() - inicio) * 1000),
    }