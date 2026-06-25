# -*- coding: utf-8 -*-
"""
Orquestrador do pipeline NLP local — sem dependências de LLMs externos.

Fluxo:
  1. Pré-processa o texto
  2. Classifica a intenção (TF-IDF + Logistic Regression)
  3. Extrai entidades (regex + gazetteer)
  4. Gera embedding da pergunta (sentence-transformers, para RAG)
  5. Executa consulta(s) no banco via query_builder
  6. Formata a resposta textual com citação de fontes
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
import logging
from time import perf_counter
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nlp_processor.pipeline.intent_classifier import get_classifier
from nlp_processor.pipeline.entity_extractor import extrair_entidades
from nlp_processor.pipeline.embedder import get_embedder
from nlp_processor.pipeline.preprocessor import corrigir_ortografia, normalizar
from nlp_processor.pipeline.query_builder import executar_consulta
from nlp_processor.pipeline.response_formatter import formatar_resposta
from models.db_model import Municipio

logger = logging.getLogger(__name__)

# Limiar mínimo de confiança para aceitar a intenção detectada.
# Abaixo disso, cai para buscar_documentos (mais genérico).
# Com 9 classes, probabilidades acima de 0.35 já indicam predição confiável.
CONFIDENCE_THRESHOLD = 0.20

# Janela de validade do feedback do turno anterior. Depois disso, descarta —
# o usuário pode ter voltado ao chat dias depois pra perguntar outra coisa,
# e o feedback antigo não reflete a expectativa atual.
FEEDBACK_VALIDADE_MINUTOS = 30

# Intenções de tema que suportam ranking de municípios (mais/menos).
# Mapeia a intenção temática detectada pelo classificador para o `tema`
# entendido pela ferramenta ranking_municipios.
_RANKING_TEMA_POR_INTENCAO: dict[str, str] = {
    "buscar_queimadas": "queimadas",
    "buscar_desmatamentos": "desmatamentos",
    "buscar_unidades_conservacao": "unidades_conservacao",
    "buscar_terras_indigenas": "terras_indigenas",
    "buscar_quilombolas": "quilombolas",
    "buscar_imoveis_rurais": "imoveis_rurais",
    "buscar_assentamentos": "assentamentos",
    "buscar_camadas_estaduais": "camadas_estaduais",
}

_ESCOPO_AMBIENTAL_TOKENS = (
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
)


def _extrair_feedback_contexto(
    historico: list[dict],
    intencao_atual: Optional[str] = None,
    agora: Optional[datetime] = None,
) -> dict[str, int]:
    """Devolve o feedback do turno anterior, mas só se ainda for relevante.

    Regras (RF-02 — evitar reuso de respostas/sinais antigos sem contexto):
      1. Apenas o turno imediatamente anterior é considerado, não "o mais
         recente em qualquer lugar do histórico".
      2. Se a intenção mudou entre o turno anterior e o atual, descarta —
         o feedback foi sobre outro assunto.
      3. Se passou mais que FEEDBACK_VALIDADE_MINUTOS desde o turno anterior,
         descarta — o contexto provavelmente expirou.
    """
    ultima_assistente: Optional[dict] = None
    for mensagem in reversed(historico):
        if mensagem.get("role") == "assistant":
            ultima_assistente = mensagem
            break

    if not ultima_assistente:
        return {}

    feedback = ultima_assistente.get("feedback")
    if isinstance(feedback, dict):
        feedback = feedback.get("avaliacao")
    if feedback not in (-1, 1):
        return {}

    intencao_anterior = ultima_assistente.get("intencao")
    if intencao_atual and intencao_anterior and intencao_atual != intencao_anterior:
        logger.info(
            "Feedback do turno anterior descartado: mudança de intenção "
            "(%s -> %s).",
            intencao_anterior,
            intencao_atual,
        )
        return {}

    data_anterior = ultima_assistente.get("data_hora")
    if isinstance(data_anterior, datetime):
        referencia = agora or datetime.utcnow()
        if referencia - data_anterior > timedelta(minutes=FEEDBACK_VALIDADE_MINUTOS):
            logger.info(
                "Feedback do turno anterior descartado: fora da janela de "
                "%d min (delta=%s).",
                FEEDBACK_VALIDADE_MINUTOS,
                referencia - data_anterior,
            )
            return {}

    logger.info("Feedback do turno anterior aplicado: avaliacao=%s.", feedback)
    return {"avaliacao": int(feedback)}


def _tokens_protegidos(municipios_norm: list[str]) -> set[str]:
    """Tokens (4+ letras) dos nomes de municípios, para blindar nomes próprios
    contra a correção ortográfica (ex.: 'ubatuba', 'piracicaba')."""
    tokens: set[str] = set()
    for nome in municipios_norm:
        for token in nome.split():
            if len(token) >= 4:
                tokens.add(token)
    return tokens


async def _carregar_municipios_normalizados(session: AsyncSession) -> list[str]:
    stmt = select(Municipio.nome).where(Municipio.nome.is_not(None))
    result = await session.execute(stmt)

    nomes: set[str] = set()
    for (nome,) in result.all():
        nomes.add(normalizar(nome))

    logger.info(f"Carregados {len(nomes)} municípios normalizados do banco")
    return sorted(nomes)


def _serializar_entidades(entidades) -> dict[str, Any]:
    return asdict(entidades)


def _serializar_filtros(entidades_json: dict[str, Any]) -> dict[str, Any]:
    return {
        chave: valor
        for chave, valor in entidades_json.items()
        if chave != "palavras_chave" and valor is not None
    }


def _fora_escopo_sem_sinal_geografico(texto_norm: str, entidades) -> bool:
    if (
        entidades.codigo_car
        or entidades.municipio
        or entidades.regiao_administrativa
    ):
        return False
    return not any(token in texto_norm for token in _ESCOPO_AMBIENTAL_TOKENS)


async def run_agent(
    session: AsyncSession,
    pergunta: str,
    historico: list[dict],
    municipio: Optional[str] = None,  # injetado do filtro do frontend
) -> dict[str, Any]:
    """
    Executa o pipeline NLP local.

    Retorna:
        (texto_resposta, features_geojson, fontes, status)
        status: 'sucesso' | 'sem_resultado' | 'fora_escopo' | 'erro'
    """
    inicio = perf_counter()
    classifier = get_classifier()
    embedder = get_embedder()
    # `feedback_contexto` é calculado mais adiante (após a intenção final ser
    # decidida), pra que a regra "descartar feedback em caso de mudança de
    # intenção" possa comparar a intenção do turno anterior com a atual.

    def _finalizar(
        texto_resposta: str,
        features: list[dict],
        fontes: list[dict],
        status: str,
        intencao: str | None,
        intencao_score: float | None,
        entidades_detectadas_json: dict[str, Any],
        filtros_detectados_json: dict[str, Any],
        sql_executado: str | None = None,
        mensagem_erro: str | None = None,
    ) -> dict[str, Any]:
        return {
            "texto_resposta": texto_resposta,
            "features": features,
            "fontes": fontes,
            "status": status,
            "intencao": intencao,
            "intencao_score": intencao_score,
            "entidades_detectadas_json": entidades_detectadas_json,
            "filtros_detectados_json": filtros_detectados_json,
            "sql_executado": sql_executado,
            "mensagem_erro": mensagem_erro,
            "tempo_resposta_ms": int((perf_counter() - inicio) * 1000),
        }

    if not classifier.is_ready():
        logger.error("Modelo de intenções não treinado. Execute nlp_processor.training.train")
        return _finalizar(
            texto_resposta="Ocorreu um erro interno. Tente novamente.",
            features=[],
            fontes=[],
            status="erro",
            intencao=None,
            intencao_score=None,
            entidades_detectadas_json={},
            filtros_detectados_json={},
            mensagem_erro="Modelo de intenções não treinado.",
        )

    # Carrega os municípios antes de tudo: além de alimentar o extrator de
    # entidades, seus nomes protegem nomes próprios da correção ortográfica.
    municipios_extras: list[str] = []
    try:
        municipios_extras = await _carregar_municipios_normalizados(session)
    except Exception:
        logger.warning("Não foi possível carregar municípios do banco; usando gazetteer estático.")

    # Correção ortográfica da pergunta (typos comuns) antes de classificar e
    # extrair entidades. Municípios e jargão de domínio são preservados.
    pergunta_corrigida = corrigir_ortografia(pergunta, _tokens_protegidos(municipios_extras))
    if pergunta_corrigida != pergunta:
        logger.info("Pergunta corrigida: %r -> %r", pergunta, pergunta_corrigida)

    intencao, confianca = classifier.predict(pergunta_corrigida)
    logger.info("Intenção detectada: %s (%.2f)", intencao, confianca)

    entidades = extrair_entidades(pergunta_corrigida, municipios_extras)
    texto_norm = normalizar(pergunta_corrigida)
    fora_escopo_sem_sinal = _fora_escopo_sem_sinal_geografico(texto_norm, entidades)

    # Injeta município do filtro apenas em perguntas abertas. Consultas por CAR
    # devem ser resolvidas pelo identificador do imóvel, sem herdar o filtro visual.
    # Rankings são multi-município ("qual cidade teve mais...") e não devem ser
    # presos a um único município vindo do filtro do mapa.
    if (
        municipio
        and not entidades.municipio
        and not entidades.codigo_car
        and not fora_escopo_sem_sinal
        and not entidades.ranking
    ):
        logger.info("Injetando município do filtro: %s", municipio)
        entidades.municipio = municipio

    entidades_json = _serializar_entidades(entidades)
    filtros_json = _serializar_filtros(entidades_json)

    override_intencao = False
    if fora_escopo_sem_sinal:
        intencao = "fora_escopo"
        override_intencao = True
        logger.info("Pergunta marcada como fora_escopo por ausência de sinais ambientais/geográficos.")

    if entidades.codigo_car and any(
        termo in texto_norm
        for termo in (
            "passivo",
            "passivos",
            "sobreposicao",
            "preservacao",
            "area de preservacao",
            "area protegida",
            "unidade de conservacao",
            "unidades de conservacao",
            "terra indigena",
            "terras indigenas",
            "quilombo",
            "quilombola",
            "desmatamento",
        )
    ):
        intencao = "buscar_passivos_imovel"
        override_intencao = True
        logger.info(
            "Intent override para passivos com CAR detectado (%s).",
            entidades.codigo_car,
        )

    if not override_intencao and entidades.codigo_car and any(
        termo in texto_norm
        for termo in ("foco", "focos", "queimada", "incendio", "incendios")
    ):
        intencao = "buscar_focos_queimada_imovel"
        override_intencao = True
        logger.info(
            "Intent override para CAR detectado (%s) com termo de queimada/incendio.",
            entidades.codigo_car,
        )

    tokens_imovel = (
        "imovel", "imoveis", "fazenda", "fazendas",
        "propriedade", "propriedades", "sitio", "sitios",
    )

    if not override_intencao and any(t in texto_norm for t in tokens_imovel):
        promocoes: list[tuple[tuple[str, ...], str]] = [
            (
                ("queimada", "queimadas", "incendio", "incendios", "foco", "focos"),
                "buscar_imoveis_queimada",
            ),
            (
                (
                    "desmatamento", "desmatamentos", "desmatado", "desmatada",
                    "supressao", "deter", "prodes",
                ),
                "buscar_imoveis_desmatamento",
            ),
            (
                ("quilombo", "quilombos", "quilombola", "quilombolas"),
                "buscar_imoveis_quilombo",
            ),
            (
                ("terra indigena", "terras indigenas", "indigena", "indigenas"),
                "buscar_imoveis_ti",
            ),
        ]
        for tokens, alvo in promocoes:
            if intencao != alvo and any(t in texto_norm for t in tokens):
                logger.info(
                    "Promovendo intent %s -> %s (texto cita imóvel + %s).",
                    intencao, alvo, tokens[0],
                )
                intencao = alvo
                override_intencao = True
                break

    if not override_intencao and entidades.codigo_car and any(
        termo in texto_norm
        for termo in (
            "imovel",
            "imoveis",
            "fazenda",
            "fazendas",
            "propriedade",
            "propriedades",
            "sitio",
            "sitios",
            "sicar",
            "mapa",
            "geografia",
            "geometria",
            "localize",
            "localizar",
            "mostre",
            "mostrar",
            "exibir",
            "exiba",
        )
    ):
        intencao = "buscar_imoveis_rurais"
        override_intencao = True
        logger.info(
            "Intent override para buscar_imoveis_rurais (CAR %s com pedido de localização).",
            entidades.codigo_car,
        )

    if not override_intencao and entidades.codigo_car:
        intencao = "buscar_imoveis_rurais"
        override_intencao = True
        logger.info(
            "Intent override para buscar_imoveis_rurais (CAR %s sem termo específico).",
            entidades.codigo_car,
        )

    if not override_intencao:
        rebaixamentos = {
            "buscar_imoveis_queimada": "buscar_queimadas",
            "buscar_imoveis_desmatamento": "buscar_desmatamentos",
            "buscar_imoveis_quilombo": "buscar_quilombolas",
            "buscar_imoveis_ti": "buscar_terras_indigenas",
        }
        if intencao in rebaixamentos and not any(t in texto_norm for t in tokens_imovel):
            nova = rebaixamentos[intencao]
            logger.info(
                "Rebaixando intent %s -> %s (texto sem token de imóvel/fazenda/propriedade).",
                intencao, nova,
            )
            intencao = nova
            override_intencao = True

    if not override_intencao and confianca < CONFIDENCE_THRESHOLD:
        fallbacks_por_token: list[tuple[tuple[str, ...], str]] = [
            (tokens_imovel, "buscar_imoveis_rurais"),
            (
                ("queimada", "queimadas", "incendio", "incendios", "foco", "focos"),
                "buscar_queimadas",
            ),
            (
                (
                    "desmatamento", "desmatamentos", "desmatado", "desmatada",
                    "supressao", "deter", "prodes",
                ),
                "buscar_desmatamentos",
            ),
            (
                ("quilombo", "quilombos", "quilombola", "quilombolas"),
                "buscar_quilombolas",
            ),
            (
                ("terra indigena", "terras indigenas", "indigena", "indigenas"),
                "buscar_terras_indigenas",
            ),
            (
                (
                    "unidade de conservacao", "unidades de conservacao",
                    "parque", "apa", "resex", "rebio", "estacao ecologica",
                    "flona", "rppn",
                ),
                "buscar_unidades_conservacao",
            ),
        ]

        intent_inferida: str | None = None
        for tokens, alvo in fallbacks_por_token:
            if any(t in texto_norm for t in tokens):
                intent_inferida = alvo
                break

        if intent_inferida:
            logger.info(
                "Confiança baixa (%.2f) — inferindo intent %s pelo vocabulário.",
                confianca, intent_inferida,
            )
            intencao = intent_inferida
        elif entidades.municipio:
            intencao = "buscar_queimadas"
            logger.info(
                "Confiança baixa (%.2f) mas município detectado (%s) — "
                "usando buscar_queimadas.",
                confianca,
                entidades.municipio,
            )
        elif entidades.ano or entidades.data_inicio or entidades.data_fim:
            # Perguntas centradas em ano/data sem tema claro (ex.: "o que houve
            # em 2024?", "dados de 2019 a 2021") caíam em buscar_documentos e
            # não retornavam nada útil. Queimadas é a série temporal mais densa,
            # então é o fallback temporal mais informativo.
            intencao = "buscar_queimadas"
            logger.info(
                "Confiança baixa (%.2f) com sinal temporal (ano=%s, "
                "inicio=%s, fim=%s) — usando buscar_queimadas.",
                confianca,
                entidades.ano,
                entidades.data_inicio,
                entidades.data_fim,
            )
        else:
            intencao = "buscar_documentos"
            logger.info("Confiança baixa — usando buscar_documentos como fallback.")

    # 2.b Ranking de municípios ("qual cidade teve mais/menos <tema>?",
    # "top 5 cidades com mais desmatamento"). O classificador já resolveu o
    # tema (queimadas, desmatamentos, etc.); aqui só trocamos a intenção para a
    # ferramenta de agregação, preservando o tema detectado.
    if entidades.ranking:
        tema = _RANKING_TEMA_POR_INTENCAO.get(intencao)
        if tema:
            entidades.tema_ranking = tema
            intencao = "ranking_municipios"
            logger.info(
                "Ranking de municípios detectado (tema=%s, ordem=%s, limite=%d).",
                tema, entidades.ranking_ordem, entidades.ranking_limite,
            )

    # 3. Embedding para RAG
    query_embedding: list[float] = []
    try:
        query_embedding = embedder.embed(pergunta_corrigida)
    except Exception:
        logger.warning("Não foi possível gerar embedding — RAG desativado.")

    # 4. Consulta ao banco
    try:
        resultado = await executar_consulta(
            session=session,
            intencao=intencao,
            entidades=entidades,
            query_embedding=query_embedding,
        )
    except Exception:
        logger.exception("Erro ao executar consulta no banco.")
        return _finalizar(
            texto_resposta="Ocorreu um erro ao consultar os dados. Tente novamente.",
            features=[],
            fontes=[],
            status="erro",
            intencao=intencao,
            intencao_score=confianca,
            entidades_detectadas_json=entidades_json,
            filtros_detectados_json=filtros_json,
            mensagem_erro="Erro ao executar consulta no banco.",
        )

    features = resultado["features"]
    fontes = resultado["fontes"]
    contexto_documental = resultado["contexto_documental"]

    # 5. Determinar status
    if intencao == "fora_escopo":
        status = "fora_escopo"
    elif intencao != "buscar_documentos" and not features:
        status = "sem_resultado"
    elif not features and not contexto_documental:
        status = "sem_resultado"
    else:
        status = "sucesso"

    # 6. Avaliar se feedback do turno anterior ainda é aplicável.
    # Só fazemos isso aqui porque a intenção final pode diferir da inicial
    # do classifier (vários overrides acima podem ter mudado).
    feedback_contexto = _extrair_feedback_contexto(
        historico, intencao_atual=intencao
    )

    # 7. Formatar resposta
    texto = formatar_resposta(
        intencao=intencao,
        entidades=entidades,
        total_features=len(features),
        fontes=fontes,
        contexto_documental=contexto_documental,
        confianca=confianca,
        descricao_consulta=resultado.get("descricao"),
        feedback_contexto=feedback_contexto or None,
        features=features,
    )

    return {
        "texto_resposta": texto,
        "features": features,
        "bbox": resultado.get("bbox"),
        "fontes": fontes,
        "status": status,
        "intencao": intencao,
        "intencao_score": confianca,
        "entidades_detectadas_json": entidades_json,
        "filtros_detectados_json": filtros_json,
        "sql_executado": resultado.get("sql_executado"),
        "mensagem_erro": resultado.get("mensagem_erro"),
        "tempo_resposta_ms": int((perf_counter() - inicio) * 1000),
    }
