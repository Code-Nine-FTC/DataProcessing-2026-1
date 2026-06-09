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
from nlp_processor.pipeline.preprocessor import AdvancedGeoASGPreprocessor, normalizar
from nlp_processor.pipeline.query_builder import executar_consulta
from nlp_processor.pipeline.response_formatter import format_pipeline_response
from models.db_model import Municipio

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.20
FEEDBACK_VALIDADE_MINUTOS = 30

_preprocessor = AdvancedGeoASGPreprocessor()
_MUNICIPIOS_NORMALIZADOS_CACHE: Optional[list[str]] = None

_ESCOPO_AMBIENTAL_TOKENS = frozenset({
    "ambiental", "ambientais", "meio ambiente",
    "queimada", "queimadas", "incendio", "incendios", "foco", "focos", "fogo",
    "queimou", "queimaram", "queimam", "queimando", "incendiou", "incendiaram",
    "desmatamento", "desmatamentos", "desmatado", "desmatada", "supressao",
    "desmatou", "desmatam", "desmata", "desmatar", "desmato", "desmataram",
    "corte de vegetacao", "supressao vegetal", "perda de vegetacao",
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
    "regiao administrativa", "regioes administrativas", "ra de", "ranking",
})

_TOKENS_SUPERLATIVO_RANKING = frozenset({
    "maior", "maiores", "mais", "maximo", "maximos", "maxima", "maximas",
    "top", "ranking", "concentra", "concentram", "concentracao",
    "principal", "principais", "primeiro", "primeiros",
    "lidera", "lideram", "predomina", "predominam",
    "qual municipio", "quais municipios",
    "municipio que mais", "municipios que mais",
    "municipio com mais", "municipios com mais",
})

_TOKENS_ESCOPO_MUNICIPAL = frozenset({
    "municipio", "municipios", "cidade", "cidades",
})

_INTENTS_PROMOVEM_RANKING = frozenset({
    "buscar_queimadas", "buscar_desmatamentos", "buscar_terras_indigenas",
    "buscar_unidades_conservacao", "buscar_quilombolas", "buscar_assentamentos",
    "buscar_queimadas_em_quilombolas",
})

_TOKENS_CAMADA_ESTADUAL_EXPLICITA = frozenset({
    "camada estadual", "camadas estaduais", "datageo", "camada ambiental estadual",
    "camadas ambientais estaduais", "camada de vegetacao", "vegetacao nativa",
})

_INTENTS_SUPRIMIR_CAMADAS_ESTADUAIS = frozenset({
    "buscar_queimadas", "buscar_desmatamentos", "buscar_terras_indigenas",
    "buscar_unidades_conservacao", "buscar_quilombolas", "buscar_assentamentos",
    "buscar_queimadas_em_quilombolas", "buscar_maiores_quantidades",
    "buscar_imoveis_queimada", "buscar_imoveis_desmatamento",
    "buscar_imoveis_quilombo", "buscar_imoveis_ti",
})

_TOKENS_QUILOMBOLA_FOCO = frozenset({
    "quilombola", "quilombolas", "territorio quilombola", "territorios quilombolas",
    "area quilombola", "areas quilombolas",
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
    if not historico or not isinstance(historico, list):
        return {}

    # Varredura reversa segura por índice para evitar travamentos de iteração externa
    ultima_assistente = None
    for i in range(len(historico) - 1, -1, -1):
        msg = historico[i]
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            ultima_assistente = msg
            break

    if not ultima_assistente:
        return {}

    feedback = ultima_assistente.get("feedback")
    if isinstance(feedback, dict):
        feedback = feedback.get("avaliacao")
        
    try:
        feedback_int = int(feedback) if feedback is not None else 0
    except (ValueError, TypeError):
        return {}

    if feedback_int not in (-1, 1):
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

    logger.info("Feedback do turno anterior aplicado: avaliacao=%d.", feedback_int)
    return {"avaliacao": feedback_int}


async def _carregar_municipios_normalizados(session: AsyncSession) -> list[str]:
    global _MUNICIPIOS_NORMALIZADOS_CACHE
    if _MUNICIPIOS_NORMALIZADOS_CACHE is not None:
        return _MUNICIPIOS_NORMALIZADOS_CACHE

    stmt = select(Municipio.nome).where(Municipio.nome.is_not(None))
    result = await session.execute(stmt)
    nomes: set[str] = set()
    for (nome,) in result.all():
        nomes.add(normalizar(nome))
    _MUNICIPIOS_NORMALIZADOS_CACHE = sorted(nomes)
    logger.info("Carregados %d municípios normalizados do banco e salvos no cache.", len(_MUNICIPIOS_NORMALIZADOS_CACHE))
    return _MUNICIPIOS_NORMALIZADOS_CACHE


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

    intents_classificados = {i for i, _ in intencoes_classificadas}

    promocao = _aplicar_promocao_imovel(texto_norm, intencao_principal)
    # Só promove se o alvo ainda não está na lista classificada — evita colapsar multi-intents
    if promocao and promocao not in intents_classificados:
        logger.info("Promoção de intent: %s -> %s.", intencao_principal, promocao)
        return [(promocao, confianca)]

    rebaixamento = _aplicar_rebaixamento(texto_norm, intencao_principal)
    if rebaixamento:
        logger.info("Rebaixamento de intent: %s -> %s.", intencao_principal, rebaixamento)
        return [(rebaixamento, confianca)]

    if intencao_principal == "buscar_queimadas" and _texto_contem(texto_norm, _TOKENS_QUILOMBOLA_FOCO):
        logger.info("Promoção por contexto quilombola: buscar_queimadas -> buscar_queimadas_em_quilombolas.")
        return [("buscar_queimadas_em_quilombolas", confianca)]

    if (
        intencao_principal in _INTENTS_SUPRIMIR_CAMADAS_ESTADUAIS
        and not _texto_contem(texto_norm, _TOKENS_CAMADA_ESTADUAL_EXPLICITA)
    ):
        intencoes_classificadas = [
            (i, c) for i, c in intencoes_classificadas if i != "buscar_camadas_estaduais"
        ]
        if intencoes_classificadas:
            intencao_principal = intencoes_classificadas[0][0]

    if confianca < CONFIDENCE_THRESHOLD:
        inferida = _inferir_intencao_por_vocabulario(texto_norm, entidades)
        logger.info("Confiança baixa (%.2f) — inferindo intent: %s.", confianca, inferida)
        intencao_principal = inferida
        intencoes_classificadas = [(inferida, confianca)]

    if (
        intencao_principal in _INTENTS_PROMOVEM_RANKING
        and _texto_contem(texto_norm, _TOKENS_SUPERLATIVO_RANKING)
        and _texto_contem(texto_norm, _TOKENS_ESCOPO_MUNICIPAL)
    ):
        logger.info("Promoção para buscar_maiores_quantidades por vocabulário de ranking municipal.")
        return [("buscar_maiores_quantidades", confianca), (intencao_principal, confianca)]

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
        logger.error("Modelo de intenções não carregado ou não treinado.")
        return _build_resultado_erro(
            inicio=inicio,
            texto="Ocorreu um erro interno. Tente novamente.",
            mensagem="Modelo de intenções não treinado ou arquivos corrompidos.",
        )

    preprocessed = _preprocessor.process(pergunta)
    texto_norm = preprocessed["text_for_entities_and_rag"].lower()

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

    # Log de diagnóstico para identificar gargalo de consulta lenta SQL/Geométrica
    logger.info("Executando consulta assíncrona no banco de dados para a intent: %s...", intencao_principal)
    try:
        resultado = await executar_consulta(
            session=session,
            intents=intencoes_resolvidas,
            entities=entidades,
            query_embedding=query_embedding,
        )
        logger.info("Consulta executada com sucesso.")
    except Exception:
        logger.exception("Erro ao executar consulta no banco de dados.")
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
        per_intent=resultado.get("per_intent"),
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