# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Union

from nlp_processor.pipeline.preprocessor import AdvancedGeoASGPreprocessor
from models.regioes_administrativas_sp_data import RA_METADATA

_PREPROCESSOR_INSTANCE = AdvancedGeoASGPreprocessor()

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

_MUNICIPIO_DISPLAY: dict[str, str] = {
    "sao paulo": "São Paulo",
    "sao jose dos campos": "São José dos Campos",
    "ribeirao preto": "Ribeirão Preto",
    "sao jose do rio preto": "São José do Rio Preto",
    "mogi das cruzes": "Mogi das Cruzes",
    "jundiai": "Jundiaí",
    "carapicuiba": "Carapicuíba",
    "taboao da serra": "Taboão da Serra",
    "embu das artes": "Embu das Artes",
    "itaquaquecetuba": "Itaquaquecetuba",
    "mogi guacu": "Mogi Guaçu",
    "marilia": "Marília",
    "presidente prudente": "Presidente Prudente",
    "araras": "Araras",
    "araraquara": "Araraquara",
    "sao carlos": "São Carlos",
    "taubate": "Taubaté",
    "indaiatuba": "Indaiatuba",
    "aracatuba": "Araçatuba",
    "jaboticabal": "Jaboticabal",
    "cacapava": "Caçapava",
    "sao joao da boa vista": "São João da Boa Vista",
    "caraguatatuba": "Caraguatatuba",
    "sao sebastiao": "São Sebastião",
    "guaruja": "Guarujá",
    "mongagua": "Mongaguá",
    "itanhaem": "Itanhaém",
    "peruibe": "Peruíbe",
    "pariquera-acu": "Pariquera-Açu",
    "cananeia": "Cananéia",
    "itapirapua paulista": "Itapirapuã Paulista",
    "barra do chapeu": "Barra do Chapéu",
    "apiai": "Apiaí",
    "capao bonito": "Capão Bonito",
    "itapetininga": "Itapetininga",
    "altinopolis": "Altinópolis",
    "votuporanga": "Votuporanga",
    "fernandopolis": "Fernandópolis",
    "penapolis": "Penápolis",
    "avare": "Avaré",
    "cerqueira cesar": "Cerqueira César",
    "itarare": "Itararé",
    "itaporanga": "Itaporanga",
    "sao miguel arcanjo": "São Miguel Arcanjo",
}

_MONTH_MAP = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}

_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")

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

_FASES_TI = {
    r"\bhomologada\b": "Homologada",
    r"\bdelimitada\b": "Delimitada",
    r"\bdeclarada\b": "Declarada",
    r"\bem\s+estudo\b": "Em Estudo",
    r"\bencaminhada\s+ri\b": "Encaminhada RI",
}

_SENSORES = ["aqua", "terra", "npp-375", "modis", "viirs", "goes-16", "msg-3", "noaa-20"]

_TIPOS_ALERTA = [
    (r"\bprodes\s+mata\s+atlantica\b", "PRODES Mata Atlântica"),
    (r"\bprodes\s+cerrado\b", "PRODES Cerrado"),
    (r"\bprodes\b", "PRODES"),
    (r"\bdeter\b", "DETER"),
]

_ESFERAS_UC = [
    (r"\bfederal(?:is)?\b", "Federal"),
    (r"\bestadual(?:is)?\b", "Estadual"),
    (r"\bmunicipal(?:is)?\b", "Municipal"),
]

_BIOMAS_SP = [
    (r"\bmata\s+atlantica\b", "Mata Atlântica"),
    (r"\bcerrado\b", "Cerrado"),
    (r"\bcaatinga\b", "Caatinga"),
]

# Preposição espacial seguida de tipo de área protegida.
# A ordem importa: padrões mais específicos primeiro.
_PADROES_CONTEXTO_ESPACIAL: list[tuple[str, str]] = [
    (
        r"\b(?:dentro\s+d[aeo]s?\s+|n[aeo]s?\s+|em\s+|sobre\s+|"
        r"sobrepost[ao]s?\s+(?:[àa]s?\s+)?|que\s+intersect[ae]m?\s+|"
        r"dentro\s+(?:d[aeo]s?\s+)?(?:áreas?\s+de\s+)?)"
        r"(?:unidades?\s+de\s+conserva[cç][aã]o|ucs?\b|"
        r"parques?\s+(?:nacionais?|estaduais?|municipais?)|"
        r"parques?\b|apa\b|resex\b|rebio\b|flona\b|rppn\b|"
        r"estac[oõ]es?\s+ecol[oó]gicas?|"
        r"áreas?\s+protegidas?|reservas?\s+biol[oó]gicas?|"
        r"reservas?\s+extrativistas?|florestas?\s+nacionais?)",
        "unidade_conservacao",
    ),
    (
        r"\b(?:dentro\s+d[aeo]s?\s+|n[aeo]s?\s+|em\s+|sobre\s+|"
        r"sobrepost[ao]s?\s+(?:[àa]s?\s+)?|que\s+intersect[ae]m?\s+)"
        r"(?:terras?\s+ind[íi]genas?|tis?\b|"
        r"reservas?\s+ind[íi]genas?|áreas?\s+ind[íi]genas?|"
        r"demarca[cç][oõ]es?\s+ind[íi]genas?|territórios?\s+ind[íi]genas?)",
        "terra_indigena",
    ),
    (
        r"\b(?:dentro\s+d[aeo]s?\s+|n[oa]s?\s+|em\s+|sobre\s+|"
        r"sobrepost[ao]s?\s+(?:[àa]s?\s+)?|que\s+intersect[ae]m?\s+)"
        r"(?:territ[oó]rios?\s+quilombolas?|quilombos?\b|"
        r"comunidades?\s+quilombolas?|áreas?\s+quilombolas?)",
        "quilombola",
    ),
    (
        r"\b(?:dentro\s+d[aeo]s?\s+|n[oa]s?\s+|em\s+|sobre\s+|"
        r"sobrepost[ao]s?\s+(?:[àa]s?\s+)?|que\s+intersect[ae]m?\s+)"
        r"(?:assentamentos?\s+(?:rurais?)?|"
        r"projetos?\s+de\s+assentamento|áreas?\s+de\s+assentamento)",
        "assentamento",
    ),
]

# Temas para o ranking municipal (buscar_maiores_quantidades).
_TEMAS_RANKING: list[tuple[list[str], str]] = [
    (["queimada", "queimadas", "incendio", "incendios", "foco", "focos", "fogo", "calor"], "queimadas"),
    (["desmatamento", "desmatamentos", "supressao", "prodes", "deter", "corte raso", "supressao vegetal"], "desmatamentos"),
    (["unidade de conservacao", "unidades de conservacao", "uc", "ucs", "parque", "apa", "resex", "rebio", "flona", "rppn", "area protegida"], "unidades_conservacao"),
    (["terra indigena", "terras indigenas", "ti", "tis", "indigena", "indigenas"], "terras_indigenas"),
    (["quilombola", "quilombolas", "quilombo", "quilombos"], "quilombolas"),
    (["imovel", "imoveis", "fazenda", "fazendas", "propriedade", "propriedades", "car", "sicar"], "imoveis_rurais"),
    (["assentamento", "assentamentos", "reforma agraria"], "assentamentos"),
]

# Camadas territoriais elegíveis para análise de sobreposição (geometria de polígono).
_TEMAS_SOBREPOSICAO: list[tuple[list[str], str]] = [
    (["unidade de conservacao", "unidades de conservacao", "parque", "apa", "resex", "rebio", "flona", "rppn", "area protegida"], "unidades_conservacao"),
    (["terra indigena", "terras indigenas", "indigena", "indigenas"], "terras_indigenas"),
    (["quilombola", "quilombolas", "quilombo", "quilombos"], "quilombolas"),
    (["assentamento", "assentamentos", "reforma agraria"], "assentamentos"),
    (["imovel", "imoveis", "fazenda", "fazendas", "propriedade", "propriedades", "sicar"], "imoveis_rurais"),
]


@dataclass
class Entidades:
    municipio: Optional[str] = None
    regiao_administrativa: Optional[str] = None
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    ano: Optional[int] = None
    categoria_uc: Optional[str] = None
    fase_ti: Optional[str] = None
    sensor: Optional[str] = None
    grupo_snuc: Optional[str] = None
    palavras_chave: list[str] = field(default_factory=list)
    codigo_car: Optional[str] = None
    limite: Optional[int] = 3
    is_ranking: bool = False
    tipo_alerta: Optional[str] = None
    esfera_uc: Optional[str] = None
    bioma: Optional[str] = None
    # Contexto espacial: área protegida dentro da qual se busca o fenômeno.
    # Valores: "unidade_conservacao" | "terra_indigena" | "quilombola" | "assentamento" | None
    contexto_espacial: Optional[str] = None
    # Tema do ranking para buscar_maiores_quantidades.
    # Valores: "queimadas" | "desmatamentos" | "unidades_conservacao" | "terras_indigenas" |
    #          "quilombolas" | "imoveis_rurais" | "assentamentos" | None (todos)
    tema_ranking: Optional[str] = None
    tema_sobreposicao_a: Optional[str] = None
    tema_sobreposicao_b: Optional[str] = None


# ---------------------------------------------------------------------------
# Extratores de data
# ---------------------------------------------------------------------------

def _extrair_datas(texto_norm: str) -> tuple[Optional[str], Optional[str]]:
    encontradas: list[str] = []
    for match in re.finditer(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b", texto_norm):
        d, m, y = match.group(1), match.group(2), match.group(3)
        encontradas.append(f"{y}-{m.zfill(2)}-{d.zfill(2)}")

    for match in re.finditer(r"\b(\d{4})[/\-](\d{2})[/\-](\d{2})\b", texto_norm):
        y, m, d = match.group(1), match.group(2), match.group(3)
        iso = f"{y}-{m}-{d}"
        if iso not in encontradas:
            encontradas.append(iso)

    for nome_mes, num_mes in _MONTH_MAP.items():
        for match in re.finditer(rf"\b{nome_mes}\s+(?:de\s+)?(\d{{4}})\b", texto_norm):
            ano = match.group(1)
            iso = f"{ano}-{str(num_mes).zfill(2)}-01"
            if iso not in encontradas:
                encontradas.append(iso)

    encontradas = sorted(set(encontradas))
    return (encontradas[0] if encontradas else None, encontradas[-1] if len(encontradas) > 1 else None)


def _extrair_periodo_relativo(texto_norm: str) -> tuple[Optional[str], Optional[str]]:
    hoje = datetime.utcnow().date()
    if re.search(r"\bultim[oa]s?\s+semana(s)?\b", texto_norm) or re.search(r"\bultim[oa]s?\s+7\s+dias\b", texto_norm):
        return (hoje - timedelta(days=7)).isoformat(), hoje.isoformat()
    if re.search(r"\bultim[oa]s?\s+mes(es)?\b", texto_norm) or re.search(r"\bultim[oa]s?\s+30\s+dias\b", texto_norm):
        return (hoje - timedelta(days=30)).isoformat(), hoje.isoformat()
    if re.search(r"\bultim[oa]s?\s+ano(s)?\b", texto_norm) or re.search(r"\bultim[oa]s?\s+12\s+meses\b", texto_norm):
        return (hoje - timedelta(days=365)).isoformat(), hoje.isoformat()
    return None, None


def _extrair_ano(texto_norm: str) -> Optional[int]:
    match = _YEAR_PATTERN.search(texto_norm)
    return int(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# Extratores de localização
# ---------------------------------------------------------------------------

_RM_ALIASES_SIGLA: dict[str, str] = {
    "rmsp": "RA de São Paulo", "rmbs": "RA da Baixada Santista", "rmc": "RA de Campinas",
    "rmrp": "RA de Ribeirão Preto", "rmvp": "RA de São José dos Campos",
    "rmvplm": "RA de São José dos Campos", "rmvpln": "RA de São José dos Campos",
}


def _ra_cidade_normalizada(ra_nome: str) -> str:
    base = ra_nome
    for prefixo in ("RA de ", "RA da ", "RA do ", "RA dos ", "RA das ", "RA "):
        if base.startswith(prefixo):
            base = base[len(prefixo):]
            break
    return _PREPROCESSOR_INSTANCE.process(base)["text_for_entities_and_rag"]


_RA_CIDADE_TO_NOME: list[tuple[str, str]] = sorted(
    [(_ra_cidade_normalizada(meta["nome"]), meta["nome"]) for meta in RA_METADATA],
    key=lambda item: len(item[0]), reverse=True,
)

_RA_SIGLAS: dict[str, str] = {
    **{_PREPROCESSOR_INSTANCE.process(meta["sigla"])["text_for_entities_and_rag"]: meta["nome"] for meta in RA_METADATA},
    **_RM_ALIASES_SIGLA,
}


def _extrair_regiao_administrativa(texto_norm: str) -> tuple[Optional[str], str]:
    for sigla_norm, ra_nome in _RA_SIGLAS.items():
        padrao = rf"\b{re.escape(sigla_norm)}\b"
        if re.search(padrao, texto_norm):
            return ra_nome, re.sub(padrao, " ", texto_norm)

    prefixos = (
        r"regiao\s+administrativa\s+(?:de\s+|da\s+|do\s+|dos\s+|das\s+)?",
        r"ra\s+(?:de\s+|da\s+|do\s+|dos\s+|das\s+)?",
        r"regiao\s+(?:de\s+|da\s+|do\s+|dos\s+|das\s+)?",
    )
    for cidade_norm, ra_nome in _RA_CIDADE_TO_NOME:
        for prefixo in prefixos:
            padrao = rf"\b{prefixo}{re.escape(cidade_norm)}\b"
            if re.search(padrao, texto_norm):
                return ra_nome, re.sub(padrao, " ", texto_norm)
    return None, texto_norm


def _extrair_municipio(texto_norm: str, municipios_extras: Optional[list[str]] = None) -> Optional[str]:
    texto_lower = texto_norm.lower()
    gazetteer = MUNICIPIOS_SP_BASE + (municipios_extras or [])
    for municipio in sorted(gazetteer, key=len, reverse=True):
        if municipio == "sao paulo" and re.search(
            r"\b(estado|uf)\s+(?:de\s+)?sao\s+paulo\b|\bsao\s+paulo\s+(?:estado|uf)\b", texto_lower
        ):
            continue
        if municipio in texto_lower:
            return _MUNICIPIO_DISPLAY.get(municipio, municipio.title())
    return None


# ---------------------------------------------------------------------------
# Extratores de atributos de domínio
# ---------------------------------------------------------------------------

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


def _extrair_codigo_car(texto_norm: str) -> Optional[str]:
    def _valid(code: str) -> bool:
        return len(code) >= 6 and any(ch.isdigit() for ch in code)

    m = re.search(r"\b([A-Za-z]{2}-\d{5,7}-[A-Za-z0-9]{6,})\b", texto_norm)
    if m and _valid(m.group(1)):
        return m.group(1).upper()

    m = re.search(r"\b([A-Za-z]{2}\d{5,7}[A-Fa-f0-9]{20,})\b", texto_norm)
    if m and _valid(m.group(1)):
        return m.group(1).upper()

    m = re.search(r"codigo\s+car[:\s]*([A-Za-z0-9\-]+)", texto_norm)
    if m and _valid(m.group(1)):
        return m.group(1).upper()

    m = re.search(r"\bcar[:\s]*([A-Za-z0-9\-]+)\b", texto_norm)
    if m and _valid(m.group(1)):
        return m.group(1).upper()

    m = re.search(r"\b([A-Za-z]{2}\d{6,12})\b", texto_norm)
    if m and _valid(m.group(1)):
        return m.group(1).upper()

    return None


def _extrair_tipo_alerta(texto_norm: str) -> Optional[str]:
    for pattern, valor in _TIPOS_ALERTA:
        if re.search(pattern, texto_norm):
            return valor
    return None


def _extrair_esfera_uc(texto_norm: str) -> Optional[str]:
    for pattern, valor in _ESFERAS_UC:
        if re.search(pattern, texto_norm):
            return valor
    return None


def _extrair_bioma(texto_norm: str) -> Optional[str]:
    for pattern, valor in _BIOMAS_SP:
        if re.search(pattern, texto_norm):
            return valor
    return None


def _extrair_limite(texto_norm: str) -> Optional[int]:
    m = re.search(
        r"\b(?:top|mais|maior|maiores|maxim[os|as]|máxim[os|as]|primeir[os|as])\s*[- ]*(\d+)\b",
        texto_norm,
    )
    if m:
        return int(m.group(1))
    return 3


def _extrair_is_ranking(texto_norm: str) -> bool:
    termos = ["ranking", "lista", "posicao", "colocacao", "classificacao", "ordenado", "top", "maiores", "piores"]
    return any(termo in texto_norm for termo in termos)


def _extrair_contexto_espacial(texto_norm: str) -> Optional[str]:
    """Detecta se a pergunta especifica um contexto espacial de área protegida.

    Usa preposições espaciais ('dentro de', 'em', 'nas') seguidas de palavras-chave
    de área protegida para distinguir filtros espaciais de filtros geográficos
    comuns (como nomes de municípios).
    """
    for padrao, contexto in _PADROES_CONTEXTO_ESPACIAL:
        if re.search(padrao, texto_norm):
            return contexto
    return None


def _extrair_tema_ranking(texto_norm: str) -> Optional[str]:
    """Identifica o tema de dados para o ranking municipal.

    Retorna None quando nenhum tema específico é mencionado,
    indicando que todos os temas devem ser agregados.
    """
    for tokens, tema in _TEMAS_RANKING:
        if any(token in texto_norm for token in tokens):
            return tema
    return None


def _extrair_temas_sobreposicao(texto_norm: str) -> tuple[Optional[str], Optional[str]]:
    encontrados: list[str] = []
    for tokens, tema in _TEMAS_SOBREPOSICAO:
        if tema not in encontrados and any(token in texto_norm for token in tokens):
            encontrados.append(tema)
    if len(encontrados) >= 2:
        return encontrados[0], encontrados[1]
    return None, None


# ---------------------------------------------------------------------------
# Ponto de entrada público
# ---------------------------------------------------------------------------

def extrair_entidades(
    texto: Union[str, Dict[str, Any]],
    municipios_extras: Optional[list[str]] = None,
) -> Entidades:
    if isinstance(texto, dict):
        texto_norm = texto.get("text_for_entities_and_rag", "")
        if not texto_norm:
            texto_norm = texto.get("normalized_text", "")
    else:
        res_nlp = _PREPROCESSOR_INSTANCE.process(texto)
        texto_norm = res_nlp["text_for_entities_and_rag"]

    if not texto_norm or not str(texto_norm).strip():
        return Entidades()

    texto_norm = texto_norm.lower()

    data_inicio, data_fim = _extrair_datas(texto_norm)
    ano = _extrair_ano(texto_norm)

    if ano and not data_inicio:
        data_inicio = f"{ano}-01-01"
        data_fim = f"{ano}-12-31"

    if not data_inicio and not data_fim:
        periodo_inicio, periodo_fim = _extrair_periodo_relativo(texto_norm)
        if periodo_inicio and periodo_fim:
            data_inicio = periodo_inicio
            data_fim = periodo_fim

    regiao_administrativa, texto_sem_ra = _extrair_regiao_administrativa(texto_norm)

    tema_sobreposicao_a, tema_sobreposicao_b = _extrair_temas_sobreposicao(texto_norm)

    return Entidades(
        municipio=_extrair_municipio(texto_sem_ra, municipios_extras),
        regiao_administrativa=regiao_administrativa,
        data_inicio=data_inicio,
        data_fim=data_fim,
        ano=ano,
        categoria_uc=_extrair_categoria_uc(texto_norm),
        fase_ti=_extrair_fase_ti(texto_norm),
        sensor=_extrair_sensor(texto_norm),
        grupo_snuc=_extrair_grupo_snuc(texto_norm),
        palavras_chave=[w for w in texto_norm.split() if len(w) > 4],
        codigo_car=_extrair_codigo_car(texto_norm),
        limite=_extrair_limite(texto_norm),
        is_ranking=_extrair_is_ranking(texto_norm),
        tipo_alerta=_extrair_tipo_alerta(texto_norm),
        esfera_uc=_extrair_esfera_uc(texto_norm),
        bioma=_extrair_bioma(texto_norm),
        contexto_espacial=_extrair_contexto_espacial(texto_norm),
        tema_ranking=_extrair_tema_ranking(texto_norm),
        tema_sobreposicao_a=tema_sobreposicao_a,
        tema_sobreposicao_b=tema_sobreposicao_b,
    )
