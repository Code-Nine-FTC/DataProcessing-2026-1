# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any, Callable, Optional

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nlp_processor.pipeline.intent_classifier import get_classifier
from nlp_processor.pipeline.entity_extractor import Entidades, extrair_entidades
from nlp_processor.pipeline.embedder import get_embedder
from nlp_processor.pipeline.preprocessor import AdvancedGeoASGPreprocessor, normalizar
from nlp_processor.pipeline.query_builder import executar_plano
from nlp_processor.pipeline.response_formatter import compor_resposta
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

# Intenções resolvidas de forma holística: a pergunta inteira vira uma única tarefa.
_INTENTS_HOLISTICOS: frozenset[str] = frozenset({
    "buscar_sobreposicao_areas",
    "buscar_maiores_quantidades",
    "buscar_passivos_imovel",
    "buscar_focos_queimada_imovel",
    "fora_escopo",
})

_CONECTORES_RE = re.compile(
    r"\s+e\s+|\s*;\s*|\s+tambem\s+|\s+alem\s+de\s+|\s+bem\s+como\s+|\s+assim\s+como\s+"
)

# Estados, regiões e gentílicos fora de São Paulo: o sistema cobre apenas SP.
_FORA_SP_RE = re.compile(
    r"\b("
    r"bahia|baiano|baiana|ceara|pernambuco|pernambucano|maranhao|piaui|paraiba|"
    r"sergipe|alagoas|rio grande do norte|rio grande do sul|gaucho|"
    r"santa catarina|catarinense|parana|paranaense|minas gerais|mineiro|"
    r"rio de janeiro|carioca|fluminense|espirito santo|mato grosso|"
    r"mato grosso do sul|goias|goiano|tocantins|rondonia|roraima|amapa|"
    r"amazonas|amazonia|paraense|pantanal|distrito federal|brasilia"
    r")\b"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _texto_contem(texto: str, tokens: frozenset[str]) -> bool:
    return any(t in texto for t in tokens)


def _fora_escopo(texto_norm: str, entidades: Entidades) -> bool:
    if entidades.codigo_car or entidades.municipio or entidades.regiao_administrativa:
        return False
    if _FORA_SP_RE.search(texto_norm):
        return True
    return not _texto_contem(texto_norm, _ESCOPO_AMBIENTAL_TOKENS)


def _inferir_intencao_por_vocabulario(texto_norm: str) -> Optional[str]:
    for tokens, alvo in _FALLBACKS_POR_TOKEN:
        if _texto_contem(texto_norm, tokens):
            return alvo
    return None


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
        inferida = _inferir_intencao_por_vocabulario(texto_norm)
        if inferida is None:
            inferida = intent_classificado if entidades.municipio else "fora_escopo"
        logger.info("Confiança baixa (%.2f) — intent resolvido: %s.", confianca, inferida)
        return inferida, confianca

    if _texto_contem(texto_norm, _TOKENS_IMOVEL):
        for tokens, alvo in _PROMOCOES_IMOVEL:
            if _texto_contem(texto_norm, tokens) and intent_classificado != alvo:
                logger.info("Promoção de intent por contexto de imóvel: %s -> %s.", intent_classificado, alvo)
                return alvo, confianca

    return intent_classificado, confianca


def _ms(inicio: float) -> int:
    return int((perf_counter() - inicio) * 1000)


def _session_factory() -> Optional[Callable[[], AsyncSession]]:
    try:
        from models.database import Database
        return lambda: Database().session
    except Exception:
        logger.warning("Fábrica de sessões indisponível; tarefas serão executadas sequencialmente.")
        return None


def _segmentar(texto_norm: str) -> list[str]:
    partes = _CONECTORES_RE.split(texto_norm)
    return [parte.strip() for parte in partes if parte and parte.strip()]


def _herdar_escopo(segmento: Entidades, completo: Entidades) -> None:
    if not segmento.municipio and not segmento.regiao_administrativa:
        segmento.municipio = completo.municipio
        segmento.regiao_administrativa = completo.regiao_administrativa
    if not segmento.data_inicio and not segmento.data_fim and not segmento.ano:
        segmento.data_inicio = completo.data_inicio
        segmento.data_fim = completo.data_fim
        segmento.ano = completo.ano


def _montar_plano(
    preprocessed: dict[str, Any],
    texto_norm: str,
    municipios_extras: list[str],
    municipio_filtro: Optional[str],
) -> tuple[list[tuple[str, Entidades]], Entidades, float]:
    classifier = get_classifier()
    entidades = extrair_entidades(preprocessed, municipios_extras)

    if (
        municipio_filtro
        and not entidades.municipio
        and not entidades.codigo_car
        and not _fora_escopo(texto_norm, entidades)
    ):
        entidades.municipio = municipio_filtro

    intent_geral, confianca = _resolver_intencao_final(
        texto_norm, entidades, *classifier.predict(preprocessed)
    )

    holistico = (
        intent_geral in _INTENTS_HOLISTICOS
        or bool(entidades.codigo_car)
        or _CONECTORES_RE.search(texto_norm) is None
    )
    if holistico:
        return [(intent_geral, entidades)], entidades, confianca

    tarefas: list[tuple[str, Entidades]] = []
    vistos: set[tuple] = set()
    for segmento in _segmentar(texto_norm):
        entrada = {"text_for_entities_and_rag": segmento}
        entidades_seg = extrair_entidades(entrada, municipios_extras)
        _herdar_escopo(entidades_seg, entidades)
        intent_seg, _ = _resolver_intencao_final(
            segmento, entidades_seg, *classifier.predict(entrada)
        )
        if intent_seg == "fora_escopo":
            continue
        chave = (intent_seg, entidades_seg.municipio, entidades_seg.contexto_espacial)
        if chave in vistos:
            continue
        vistos.add(chave)
        tarefas.append((intent_seg, entidades_seg))

    if not tarefas:
        return [(intent_geral, entidades)], entidades, confianca
    return tarefas, entidades, confianca


def _unir_features(blocos: list[dict]) -> list[dict]:
    features: list[dict] = []
    for bloco in blocos:
        features.extend(bloco.get("features") or [])
    return features


def _unir_fontes(blocos: list[dict]) -> list[dict]:
    visto: dict[str, dict] = {}
    for bloco in blocos:
        for fonte in bloco.get("sources", []):
            nome = fonte.get("nome")
            if nome and nome not in visto:
                visto[nome] = fonte
    return list(visto.values())


def _unir_bbox(blocos: list[dict]) -> Optional[list[float]]:
    caixas = [bloco["bbox"] for bloco in blocos if bloco.get("bbox")]
    if not caixas:
        return None
    return [
        min(caixa[0] for caixa in caixas),
        min(caixa[1] for caixa in caixas),
        max(caixa[2] for caixa in caixas),
        max(caixa[3] for caixa in caixas),
    ]


def _status_do_plano(blocos: list[dict], document_context: str) -> str:
    if not blocos or all(bloco["effective_tool"] == "fora_escopo" for bloco in blocos):
        return "fora_escopo"
    if any(bloco.get("features") for bloco in blocos):
        return "sucesso"
    if document_context:
        return "sucesso"
    return "sem_resultado"


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
    marcos: dict[str, int] = {}
    classifier = get_classifier()

    if not classifier.is_ready():
        logger.error("Modelo de intenções não carregado ou não treinado.")
        return _build_resultado_erro(
            inicio=inicio,
            texto="Ocorreu um erro interno. Tente novamente.",
            mensagem="Modelo de intenções não treinado ou arquivos corrompidos.",
        )

    marco = perf_counter()
    preprocessed = _preprocessor.process(pergunta)
    texto_norm = preprocessed["text_for_entities_and_rag"].lower()
    marcos["preprocess_ms"] = _ms(marco)

    municipios_extras: list[str] = []
    try:
        municipios_extras = await _carregar_municipios_normalizados(session)
    except Exception:
        logger.warning("Não foi possível carregar municípios do banco; usando gazetteer estático.")

    marco = perf_counter()
    tarefas, entidades, confianca = _montar_plano(preprocessed, texto_norm, municipios_extras, municipio)
    marcos["plano_ms"] = _ms(marco)

    intents = [intent for intent, _ in tarefas]
    intencao = "+".join(intents)
    logger.info("Plano de execução (%d tarefa(s)): %s", len(tarefas), intents)

    entidades_json = _serializar_entidades(entidades)
    filtros_json = _serializar_filtros(entidades_json)

    needs_rag = False
    query_embedding: list[float] = []
    if needs_rag:
        marco = perf_counter()
        try:
            query_embedding = get_embedder().embed(preprocessed)
        except Exception:
            logger.warning("Não foi possível gerar embedding — RAG desativado.")
        marcos["embedding_ms"] = _ms(marco)

    marco = perf_counter()
    try:
        plano = await executar_plano(
            session=session,
            tarefas=tarefas,
            query_embedding=query_embedding,
            needs_rag=needs_rag,
            session_factory=_session_factory(),
        )
    except Exception:
        logger.exception("Erro ao executar plano de consultas.")
        return _build_resultado_erro(
            inicio=inicio,
            texto="Ocorreu um erro ao consultar os dados. Tente novamente.",
            mensagem="Erro ao executar consulta no banco.",
            intencao=intencao,
            confianca=confianca,
            entidades_json=entidades_json,
            filtros_json=filtros_json,
        )
    marcos["consultas_ms"] = _ms(marco)

    blocos = plano["blocos"]
    document_context = plano["document_context"]

    feedback_contexto = _extrair_feedback_contexto(historico, intencao_atual=intencao)
    texto = compor_resposta(blocos, feedback_context=feedback_contexto or None)

    marcos["total_ms"] = _ms(inicio)
    logger.info("Tempos NLP (ms): %s", marcos)

    return {
        "texto_resposta": texto,
        "features": _unir_features(blocos),
        "bbox": _unir_bbox(blocos),
        "fontes": _unir_fontes(blocos),
        "status": _status_do_plano(blocos, document_context),
        "intencao": intencao,
        "intencao_score": confianca,
        "entidades_detectadas_json": entidades_json,
        "filtros_detectados_json": filtros_json,
        "sql_executado": plano.get("sql_executado"),
        "mensagem_erro": None,
        "tempo_resposta_ms": marcos["total_ms"],
    }
