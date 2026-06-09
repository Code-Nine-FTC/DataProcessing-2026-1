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

# ---------------------------------------------------------------------------
# Vocabulários de detecção
# ---------------------------------------------------------------------------

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

_TOKENS_SOBREPOSICAO = frozenset({
    "sobreposicao", "sobrepoe", "sobrepoem", "sobreposto", "sobrepostos",
    "sobreposta", "sobrepostas", "sobrepor",
    "intersecao", "interseccao", "intersecoes", "interseccoes",
    "intersecta", "intersectam", "cruzamento", "cruzam",
})

_TOKENS_LOCALIZACAO = frozenset({
    "imovel", "imoveis", "fazenda", "fazendas", "propriedade", "propriedades",
    "sitio", "sitios", "sicar", "mapa", "geografia", "geometria",
    "localize", "localizar", "mostre", "mostrar", "exibir", "exiba",
})

# Mapeamento intent rankeável → tema para buscar_maiores_quantidades
_TEMA_POR_INTENT: dict[str, str] = {
    "buscar_queimadas":           "queimadas",
    "buscar_desmatamentos":       "desmatamentos",
    "buscar_terras_indigenas":    "terras_indigenas",
    "buscar_unidades_conservacao": "unidades_conservacao",
    "buscar_quilombolas":         "quilombolas",
}

# Promoções para sub-intents de imóvel quando código CAR está ausente mas texto menciona imóvel
_PROMOCOES_IMOVEL: list[tuple[frozenset[str], str]] = [
    (frozenset({"queimada", "queimadas", "incendio", "incendios", "foco", "focos"}), "buscar_imoveis_queimada"),
    (frozenset({"desmatamento", "desmatamentos", "desmatado", "desmatada", "supressao", "deter", "prodes"}), "buscar_imoveis_desmatamento"),
    (frozenset({"quilombo", "quilombos", "quilombola", "quilombolas"}), "buscar_imoveis_quilombo"),
    (frozenset({"terra indigena", "terras indigenas", "indigena", "indigenas"}), "buscar_imoveis_ti"),
]

_FALLBACKS_POR_TOKEN: list[tuple[frozenset[str], str]] = [
    (_TOKENS_IMOVEL, "buscar_imoveis_rurais"),
    (frozenset({"queimada", "queimadas", "incendio", "incendios", "foco", "focos"}), "buscar_queimadas"),
    (frozenset({"desmatamento", "desmatamentos", "desmatado", "desmatada", "supressao", "deter", "prodes"}), "buscar_desmatamentos"),
    (frozenset({"quilombo", "quilombos", "quilombola", "quilombolas"}), "buscar_quilombolas"),
    (frozenset({"terra indigena", "terras indigenas", "indigena", "indigenas"}), "buscar_terras_indigenas"),
    (frozenset({"unidade de conservacao", "unidades de conservacao", "parque", "apa", "resex", "rebio", "estacao ecologica", "flona", "rppn"}), "buscar_unidades_conservacao"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _texto_contem(texto: str, tokens: frozenset[str]) -> bool:
    return any(t in texto for t in tokens)


def _fora_escopo(texto_norm: str, entidades: Entidades) -> bool:
    if entidades.codigo_car or entidades.municipio or entidades.regiao_administrativa:
        return False
    return not _texto_contem(texto_norm, _ESCOPO_AMBIENTAL_TOKENS)


def _inferir_intencao_por_vocabulario(texto_norm: str, entidades: Entidades) -> str:
    for tokens, alvo in _FALLBACKS_POR_TOKEN:
        if _texto_contem(texto_norm, tokens):
            return alvo
    if entidades.municipio:
        return "buscar_queimadas"
    return "buscar_documentos"


def _deve_promover_ranking(texto_norm: str) -> bool:
    return (
        _texto_contem(texto_norm, _TOKENS_SUPERLATIVO_RANKING)
        and _texto_contem(texto_norm, _TOKENS_ESCOPO_MUNICIPAL)
    )


def _extrair_feedback_contexto(
    historico: list[dict],
    intencao_atual: Optional[str] = None,
    agora: Optional[datetime] = None,
) -> dict[str, int]:
    if not historico or not isinstance(historico, list):
        return {}

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
    logger.info("Carregados %d municípios normalizados do banco.", len(_MUNICIPIOS_NORMALIZADOS_CACHE))
    return _MUNICIPIOS_NORMALIZADOS_CACHE


def _serializar_entidades(entidades: Entidades) -> dict[str, Any]:
    return asdict(entidades)


def _serializar_filtros(entidades_json: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entidades_json.items() if k != "palavras_chave" and v is not None}


# ---------------------------------------------------------------------------
# Resolução de intenção — lógica de negócio única e limpa
# ---------------------------------------------------------------------------

def _resolver_intencao_final(
    texto_norm: str,
    entidades: Entidades,
    intent_classificado: str,
    confianca: float,
) -> tuple[str, float]:
    """Retorna a intenção final (string única) e sua confiança.

    Ordem de prioridade:
    1. Fora de escopo
    2. Override por código CAR
    3. Sobreposição entre duas camadas territoriais
    4. Promoção para ranking municipal (independente da confiança)
    5. Baixa confiança → fallback por vocabulário
    6. Promoção de imóvel (sem CAR mas texto menciona imóvel)
    7. Intent classificado (aceito sem alteração)
    """

    if _fora_escopo(texto_norm, entidades):
        logger.info("Pergunta marcada como fora_escopo.")
        return "fora_escopo", 1.0

    if entidades.codigo_car:
        if _texto_contem(texto_norm, _TOKENS_PASSIVO):
            override = "buscar_passivos_imovel"
        elif _texto_contem(texto_norm, _TOKENS_QUEIMADA_IMOVEL):
            override = "buscar_focos_queimada_imovel"
        else:
            override = "buscar_imoveis_rurais"
        logger.info("Override por CAR (%s): %s.", entidades.codigo_car, override)
        return override, confianca

    if (
        entidades.tema_sobreposicao_a
        and entidades.tema_sobreposicao_b
        and _texto_contem(texto_norm, _TOKENS_SOBREPOSICAO)
    ):
        logger.info(
            "Sobreposição de áreas: %s x %s.",
            entidades.tema_sobreposicao_a,
            entidades.tema_sobreposicao_b,
        )
        return "buscar_sobreposicao_areas", confianca

    if _deve_promover_ranking(texto_norm):
        if entidades.tema_ranking is None:
            entidades.tema_ranking = _TEMA_POR_INTENT.get(intent_classificado)
        entidades.is_ranking = True
        logger.info("Promoção para buscar_maiores_quantidades (tema=%s).", entidades.tema_ranking)
        return "buscar_maiores_quantidades", confianca

    if confianca < CONFIDENCE_THRESHOLD:
        inferida = _inferir_intencao_por_vocabulario(texto_norm, entidades)
        logger.info("Confiança baixa (%.2f) — intent inferido por vocabulário: %s.", confianca, inferida)
        return inferida, confianca

    if _texto_contem(texto_norm, _TOKENS_IMOVEL):
        for tokens, alvo in _PROMOCOES_IMOVEL:
            if _texto_contem(texto_norm, tokens) and intent_classificado != alvo:
                logger.info("Promoção de intent por contexto de imóvel: %s -> %s.", intent_classificado, alvo)
                return alvo, confianca

    return intent_classificado, confianca


def _determinar_status(intent: str, features: list, contexto_documental: str) -> str:
    if intent == "fora_escopo":
        return "fora_escopo"
    if intent == "buscar_documentos" and contexto_documental:
        return "sucesso"
    if not features:
        return "sem_resultado"
    return "sucesso"


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


# ---------------------------------------------------------------------------
# Ponto de entrada principal
# ---------------------------------------------------------------------------

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

    intent_bruto, confianca_bruta = classifier.predict(preprocessed)
    logger.info("Intent classificado: %s (confiança: %.2f)", intent_bruto, confianca_bruta)

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

    intent_final, confianca_final = _resolver_intencao_final(texto_norm, entidades, intent_bruto, confianca_bruta)
    logger.info("Intent final: %s | contexto_espacial: %s", intent_final, entidades.contexto_espacial)

    query_embedding: list[float] = []
    try:
        query_embedding = embedder.embed(preprocessed)
    except Exception:
        logger.warning("Não foi possível gerar embedding — RAG desativado.")

    logger.info("Executando consulta para intent=%s contexto=%s ...", intent_final, entidades.contexto_espacial)
    try:
        resultado = await executar_consulta(
            session=session,
            intent=intent_final,
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
            intencao=intent_final,
            confianca=confianca_final,
            entidades_json=entidades_json,
            filtros_json=filtros_json,
        )

    features = resultado["features"]
    fontes = resultado["fontes"]
    contexto_documental = resultado["contexto_documental"]
    effective_tool = resultado.get("effective_tool", intent_final)
    status = _determinar_status(intent_final, features, contexto_documental)

    feedback_contexto = _extrair_feedback_contexto(historico, intencao_atual=intent_final)

    texto = format_pipeline_response(
        effective_tool=effective_tool,
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
        "intencao": intent_final,
        "intencao_score": confianca_final,
        "entidades_detectadas_json": entidades_json,
        "filtros_detectados_json": filtros_json,
        "sql_executado": resultado.get("sql_executado"),
        "mensagem_erro": resultado.get("mensagem_erro"),
        "tempo_resposta_ms": int((perf_counter() - inicio) * 1000),
    }
