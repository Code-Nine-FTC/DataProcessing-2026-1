# -*- coding: utf-8 -*-
"""
Extrator de entidades para o pipeline NLP ambiental.
Extrai: MUNICIPIO, DATA_INICIO, DATA_FIM, CATEGORIA_UC, FASE_TI, SENSOR.
Não depende de modelos treinados — usa regex + gazetteer de municípios de SP.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from nlp_processor.pipeline.preprocessor import normalizar

# ---------------------------------------------------------------------------
# Gazetteer de municípios do estado de São Paulo (nomes normalizados)
# ---------------------------------------------------------------------------
# Lista reduzida com os principais; o loader completo vem do banco em runtime.
MUNICIPIOS_SP_BASE: list[str] = [
    "sao paulo", "campinas", "sao jose dos campos", "ribeirao preto",
    "sorocaba", "maua", "sao jose do rio preto", "santos", "mogi das cruzes",
    "osasco", "piracicaba", "bauru", "jundiai", "carapicuiba", "limeira",
    "guarulhos", "santo andre", "sao bernardo do campo", "sao caetano do sul",
    "diadema", "barueri", "cotia", "itapevi", "taboao da serra", "embu das artes",
    "suzano", "itaquaquecetuba", "mogi guacu", "botucatu", "marilia",
    "presidente prudente", "franca", "araras", "americana", "araraquara",
    "sao carlos", "taubate", "volta redonda", "indaiatuba", "itu",
    "aracatuba", "assis", "catanduva", "jaboticabal",
    "cacapava", "lins", "ourinhos", "registro", "sao joao da boa vista",
    "ilhabela", "ubatuba", "caraguatatuba", "sao sebastiao",
    "bertioga", "guaruja", "praia grande", "mongagua", "itanhaem",
    "peruibe", "iguape", "pariquera-acu", "cananeia", "miracatu",
    "jacupiranga", "eldorado", "itapirapua paulista", "barra do chapeu",
    "apiai", "capao bonito", "itapetininga", "tatuapua",
    "pontal", "terra roxa", "altinopolis", "batatais", "bebedouro",
    "taquaritinga", "mirassol", "votuporanga", "fernandopolis",
    "andradina", "penapolis", "birigui", "baurinia",
    "piraju", "avare", "itai", "manduri", "cerqueira cesar",
    "itapeva", "buri", "itarare", "itaporanga", "fartura",
    "sao miguel arcanjo", "paranapanema", "sarutaia",
]


# ---------------------------------------------------------------------------
# Padrões de datas
# ---------------------------------------------------------------------------
_DATE_PATTERNS = [
    # dd/mm/yyyy ou dd-mm-yyyy
    (r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b", "%d/%m/%Y"),
    # yyyy-mm-dd
    (r"\b(\d{4})[/\-](\d{2})[/\-](\d{2})\b", "%Y-%m-%d"),
]

_MONTH_MAP = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}

_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")

# ---------------------------------------------------------------------------
# Categorias de UC e padrões
# ---------------------------------------------------------------------------
_CATEGORIAS_UC = {
    r"\bparque\s+nacional\b": "Parque Nacional",
    r"\bparque\s+estadual\b": "Parque Estadual",
    r"\bparque\s+municipal\b": "Parque Municipal",
    r"\bparque\b": "Parque",
    r"\bapa\b|area de protecao ambiental": "APA",
    r"\bresex\b|reserva\s+extrativista": "RESEX",
    r"\brebio\b|reserva\s+biologica": "REBIO",
    r"\bestacao\s+ecologica\b": "Estação Ecológica",
    r"\bflona\b|floresta\s+nacional": "FLONA",
    r"\brppn\b": "RPPN",
    r"\bapa\s+estadual\b": "APA Estadual",
}

# ---------------------------------------------------------------------------
# Fases de TI
# ---------------------------------------------------------------------------
_FASES_TI = {
    r"\bhomologada\b": "Homologada",
    r"\bdelimitada\b": "Delimitada",
    r"\bdeclarada\b": "Declarada",
    r"\bem\s+estudo\b": "Em Estudo",
    r"\bencaminhada\s+ri\b": "Encaminhada RI",
}

# ---------------------------------------------------------------------------
# Sensores de queimada
# ---------------------------------------------------------------------------
_SENSORES = [
    "aqua", "terra", "npp-375", "modis", "viirs", "goes-16",
    "msg-3", "noaa-20",
]


# ---------------------------------------------------------------------------
# Resultado da extração
# ---------------------------------------------------------------------------
@dataclass
class Entidades:
    municipio: Optional[str] = None
    data_inicio: Optional[str] = None      # YYYY-MM-DD
    data_fim: Optional[str] = None         # YYYY-MM-DD
    ano: Optional[int] = None
    categoria_uc: Optional[str] = None
    fase_ti: Optional[str] = None
    sensor: Optional[str] = None
    grupo_snuc: Optional[str] = None       # 'PI' ou 'US'
    palavras_chave: list[str] = field(default_factory=list)
    codigo_car: Optional[str] = None


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def _extrair_datas(texto_norm: str) -> tuple[Optional[str], Optional[str]]:
    """Tenta encontrar até duas datas no texto e retorna (inicio, fim)."""
    encontradas: list[str] = []

    # Padrão dd/mm/yyyy ou dd-mm-yyyy
    for match in re.finditer(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b", texto_norm):
        d, m, y = match.group(1), match.group(2), match.group(3)
        encontradas.append(f"{y}-{m.zfill(2)}-{d.zfill(2)}")

    # Padrão yyyy-mm-dd
    for match in re.finditer(r"\b(\d{4})[/\-](\d{2})[/\-](\d{2})\b", texto_norm):
        y, m, d = match.group(1), match.group(2), match.group(3)
        iso = f"{y}-{m}-{d}"
        if iso not in encontradas:
            encontradas.append(iso)

    # Padrão "janeiro de 2024" / "em marco 2025"
    for nome_mes, num_mes in _MONTH_MAP.items():
        for match in re.finditer(
            rf"\b{nome_mes}\s+(?:de\s+)?(\d{{4}})\b", texto_norm
        ):
            ano = match.group(1)
            iso = f"{ano}-{str(num_mes).zfill(2)}-01"
            if iso not in encontradas:
                encontradas.append(iso)

    encontradas = sorted(set(encontradas))
    inicio = encontradas[0] if encontradas else None
    fim = encontradas[-1] if len(encontradas) > 1 else None
    return inicio, fim


def _extrair_periodo_relativo(texto_norm: str) -> tuple[Optional[str], Optional[str]]:
    hoje = datetime.utcnow().date()
    if re.search(r"\bultim[oa]s?\s+semana(s)?\b", texto_norm) or re.search(
        r"\bultim[oa]s?\s+7\s+dias\b", texto_norm
    ):
        inicio = hoje - timedelta(days=7)
        return inicio.isoformat(), hoje.isoformat()

    if re.search(r"\bultim[oa]s?\s+mes(es)?\b", texto_norm) or re.search(
        r"\bultim[oa]s?\s+30\s+dias\b", texto_norm
    ):
        inicio = hoje - timedelta(days=30)
        return inicio.isoformat(), hoje.isoformat()

    if re.search(r"\bultim[oa]s?\s+ano(s)?\b", texto_norm) or re.search(
        r"\bultim[oa]s?\s+12\s+meses\b", texto_norm
    ):
        inicio = hoje - timedelta(days=365)
        return inicio.isoformat(), hoje.isoformat()

    return None, None


def _extrair_ano(texto_norm: str) -> Optional[int]:
    match = _YEAR_PATTERN.search(texto_norm)
    return int(match.group(1)) if match else None


def _extrair_municipio(
    texto_norm: str,
    municipios_extras: Optional[list[str]] = None,
) -> Optional[str]:
    gazetteer = MUNICIPIOS_SP_BASE + (municipios_extras or [])
    # Ordena do maior para menor para evitar match parcial
    for municipio in sorted(gazetteer, key=len, reverse=True):
        if municipio in texto_norm:
            return municipio.title()
    return None


def _extrair_categoria_uc(texto_norm: str) -> Optional[str]:
    for pattern, categoria in _CATEGORIAS_UC.items():
        if re.search(pattern, texto_norm):
            return categoria
    return None


def _extrair_fase_ti(texto_norm: str) -> Optional[str]:
    for pattern, fase in _FASES_TI.items():
        if re.search(pattern, texto_norm):
            return fase
    return None


def _extrair_sensor(texto_norm: str) -> Optional[str]:
    for sensor in _SENSORES:
        if sensor in texto_norm:
            return sensor.upper()
    return None


def _extrair_grupo_snuc(texto_norm: str) -> Optional[str]:
    if re.search(r"protecao\s+integral\b", texto_norm):
        return "Proteção Integral"
    if re.search(r"uso\s+sustentavel\b", texto_norm):
        return "Uso Sustentável"
    return None


# ---------------------------------------------------------------------------
# Extrator principal
# ---------------------------------------------------------------------------

def extrair_entidades(
    texto: str,
    municipios_extras: Optional[list[str]] = None,
) -> Entidades:
    """
    Extrai entidades de uma pergunta em linguagem natural.

    Args:
        texto: Pergunta original do usuário.
        municipios_extras: Lista de municípios adicionais (ex: carregados do banco).
    """
    texto_norm = normalizar(texto)

    data_inicio, data_fim = _extrair_datas(texto_norm)
    ano = _extrair_ano(texto_norm)

    # Se só encontrou ano sem data completa, cria intervalo anual
    if ano and not data_inicio:
        data_inicio = f"{ano}-01-01"
        data_fim = f"{ano}-12-31"

    if not data_inicio and not data_fim:
        periodo_inicio, periodo_fim = _extrair_periodo_relativo(texto_norm)
        if periodo_inicio and periodo_fim:
            data_inicio = periodo_inicio
            data_fim = periodo_fim

    return Entidades(
        municipio=_extrair_municipio(texto_norm, municipios_extras),
        data_inicio=data_inicio,
        data_fim=data_fim,
        ano=ano,
        categoria_uc=_extrair_categoria_uc(texto_norm),
        fase_ti=_extrair_fase_ti(texto_norm),
        sensor=_extrair_sensor(texto_norm),
        grupo_snuc=_extrair_grupo_snuc(texto_norm),
        palavras_chave=[w for w in texto_norm.split() if len(w) > 4],
        codigo_car=_extrair_codigo_car(texto_norm),
    )


# ---------------------------------------------------------------------------
# Extrair código CAR simples
# Padrões suportados:
# - "código car SP000123456" ou "codigo car: SP000123456"
# - "CAR SP000123456"
# - qualquer token alfanumérico com prefixo de 2 letras seguido por 6+ dígitos
# ---------------------------------------------------------------------------
def _extrair_codigo_car(texto_norm: str) -> Optional[str]:
    def _valid(code: str) -> bool:
        return len(code) >= 6 and any(ch.isdigit() for ch in code)

    # Ex: SP-3500105-268208B9F3A84F508B9C79474EA557EC
    m = re.search(r"\b([A-Za-z]{2}-\d{6,}-[A-Za-z0-9]+)\b", texto_norm)
    if m and _valid(m.group(1)):
        return m.group(1).upper()

    m = re.search(r"codigo\s+car[:\s]*([A-Za-z0-9\-]+)", texto_norm)
    if m and _valid(m.group(1)):
        return m.group(1).upper()

    m = re.search(r"\bcar[:\s]*([A-Za-z0-9\-]+)\b", texto_norm)
    if m and _valid(m.group(1)):
        return m.group(1).upper()

    # fallback: token like BR01231SP or SP12345678
    m = re.search(r"\b([A-Za-z]{2}\d{4,12}[A-Za-z]{0,2})\b", texto_norm)
    if m and _valid(m.group(1)):
        return m.group(1).upper()
    return None
