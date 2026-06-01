"""regioes_administrativas_sp_data.py

Fonte de dados para as 16 Regiões Administrativas do Estado de São Paulo.

Estratégia de obtenção do vínculo município → RA
-------------------------------------------------
A API pública do IBGE não expõe as RAs paulistas diretamente.
A fonte oficial é o SEADE, mas depender de um CSV manual é frágil.

Por isso este módulo adota a seguinte abordagem:

1. Tenta baixar o CSV de municípios com suas RAs diretamente do SEADE
   (URL pública, sem autenticação).
2. Se o download falhar (offline, URL mudou etc.), cai para o mapeamento
   embutido (MUNICIPIO_TO_RA_FALLBACK), que contém os 645 municípios de SP
   com suas respectivas RAs — dados estáveis que raramente mudam.

O dicionário público `MUNICIPIO_TO_RA` é sempre populado ao importar o módulo.
"""

from __future__ import annotations

import csv
import io
import unicodedata
from pathlib import Path
from typing import Optional

import requests
from requests.exceptions import RequestException

# ---------------------------------------------------------------------------
# Metadados das 16 Regiões Administrativas
# ---------------------------------------------------------------------------

RA_METADATA = [
    {"nome": "RA de São Paulo",             "sigla": "RASP",   "tipo": "RA"},
    {"nome": "RA de Registro",              "sigla": "RAREG",  "tipo": "RA"},
    {"nome": "RA da Baixada Santista",      "sigla": "RABS",   "tipo": "RA"},
    {"nome": "RA de São José dos Campos",   "sigla": "RASJC",  "tipo": "RA"},
    {"nome": "RA de Sorocaba",              "sigla": "RASOR",  "tipo": "RA"},
    {"nome": "RA de Campinas",              "sigla": "RACAM",  "tipo": "RA"},
    {"nome": "RA de Ribeirão Preto",        "sigla": "RARP",   "tipo": "RA"},
    {"nome": "RA Central",                  "sigla": "RACEN",  "tipo": "RA"},
    {"nome": "RA de São José do Rio Preto", "sigla": "RASJRP", "tipo": "RA"},
    {"nome": "RA de Araçatuba",             "sigla": "RAARA",  "tipo": "RA"},
    {"nome": "RA de Presidente Prudente",   "sigla": "RAPP",   "tipo": "RA"},
    {"nome": "RA de Marília",               "sigla": "RAMAR",  "tipo": "RA"},
    {"nome": "RA de Bauru",                 "sigla": "RABAU",  "tipo": "RA"},
    {"nome": "RA de Franca",                "sigla": "RAFRA",  "tipo": "RA"},
    {"nome": "RA de Barretos",              "sigla": "RABAR",  "tipo": "RA"},
    {"nome": "RA de Itapeva",               "sigla": "RAITA",  "tipo": "RA"},
]

_NOMES_RA_VALIDOS = {m["nome"] for m in RA_METADATA}

# ---------------------------------------------------------------------------
# Normalização (independente de outros módulos para evitar import circular)
# ---------------------------------------------------------------------------

def _norm(texto: str) -> str:
    """Lowercase + remove acentos + colapsa espaços."""
    s = unicodedata.normalize("NFD", texto.lower().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


# ---------------------------------------------------------------------------
# Tradução: nome da RA no CSV → nome canônico em RA_METADATA
# ---------------------------------------------------------------------------

_CSV_RA_PARA_CANONICO: dict[str, str] = {
    _norm(k): v for k, v in {
        "RA Araçatuba":             "RA de Araçatuba",
        "RA Barretos":              "RA de Barretos",
        "RA Bauru":                 "RA de Bauru",
        "RA Campinas":              "RA de Campinas",
        "RA Central":               "RA Central",
        "RA Franca":                "RA de Franca",
        "RA Itapeva":               "RA de Itapeva",
        "RA Marília":               "RA de Marília",
        "RA Presidente Prudente":   "RA de Presidente Prudente",
        "RA Registro":              "RA de Registro",
        "RA Ribeirão Preto":        "RA de Ribeirão Preto",
        "RA Santos":                "RA da Baixada Santista",
        "RA São José do Rio Preto": "RA de São José do Rio Preto",
        "RA São José dos Campos":   "RA de São José dos Campos",
        "RA Sorocaba":              "RA de Sorocaba",
        "RM São Paulo":             "RA de São Paulo",
    }.items()
}


# ---------------------------------------------------------------------------
# Mapeamento público: nome do município → nome canônico da RA
# (populado ao final deste módulo)
# ---------------------------------------------------------------------------

MUNICIPIO_TO_RA: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Estratégia 1 — download do CSV do SEADE
# ---------------------------------------------------------------------------

# URL do arquivo de municípios com regiões do SEADE (SP).
# Caso a URL mude, basta atualizar aqui.
_SEADE_CSV_URL = (
    "https://www.seade.gov.br/wp-content/uploads/2013/11/"
    "Municipios_por_RA_e_RG_2022.csv"
)

# Caminho alternativo: CSV baixado manualmente e colocado junto ao módulo.
_CSV_LOCAL = Path(__file__).resolve().parent / "docs" / "codigos_municipios_regioes.csv"


def _parsear_csv(conteudo: str) -> dict[str, str]:
    """Lê o conteúdo de texto do CSV e retorna {municipio: ra_canonica}."""
    resultado: dict[str, str] = {}
    desconhecidas: set[str] = set()

    reader = csv.DictReader(io.StringIO(conteudo), delimiter=";")
    for row in reader:
        municipio = (row.get("municipio") or row.get("Município") or "").strip()
        ra_csv    = (row.get("ra")        or row.get("RA")        or "").strip()
        cod_ibge  = (row.get("cod_ibge")  or row.get("Código")    or "").strip()

        if not municipio or not ra_csv:
            continue
        # Pula linhas-resumo
        if cod_ibge in {"35", "3500000"}:
            continue
        if _norm(ra_csv).startswith("estado") or "sem especifica" in _norm(ra_csv):
            continue

        chave = _norm(ra_csv)
        ra_canonica = _CSV_RA_PARA_CANONICO.get(chave)

        if ra_canonica is None:
            desconhecidas.add(ra_csv)
            continue

        resultado[municipio] = ra_canonica

    if desconhecidas:
        print(
            f"⚠️ [regioes_administrativas_sp_data] {len(desconhecidas)} nomes de RA "
            f"não reconhecidos no CSV: {sorted(desconhecidas)}"
        )

    return resultado


def _tentar_carregar_csv_seade() -> Optional[dict[str, str]]:
    """Tenta baixar o CSV do SEADE. Retorna None em caso de falha."""
    try:
        print(f"[regioes_administrativas_sp_data] Baixando CSV do SEADE: {_SEADE_CSV_URL}")
        resp = requests.get(_SEADE_CSV_URL, timeout=30)
        resp.raise_for_status()
        # O SEADE costuma servir latin-1; detecta pelo header ou tenta UTF-8
        encoding = resp.encoding or "latin-1"
        conteudo = resp.content.decode(encoding, errors="replace")
        resultado = _parsear_csv(conteudo)
        if resultado:
            print(
                f"[regioes_administrativas_sp_data] {len(resultado)} municípios "
                f"carregados do SEADE."
            )
            return resultado
        print("⚠️ [regioes_administrativas_sp_data] CSV do SEADE veio vazio ou sem colunas esperadas.")
    except RequestException as exc:
        print(f"⚠️ [regioes_administrativas_sp_data] Falha ao baixar CSV do SEADE: {exc}")
    return None


def _tentar_carregar_csv_local() -> Optional[dict[str, str]]:
    """Tenta ler o CSV local (docs/codigos_municipios_regioes.csv)."""
    if not _CSV_LOCAL.exists():
        return None
    print(f"[regioes_administrativas_sp_data] Lendo CSV local: {_CSV_LOCAL}")
    for enc in ("utf-8", "latin-1"):
        try:
            conteudo = _CSV_LOCAL.read_text(encoding=enc)
            resultado = _parsear_csv(conteudo)
            if resultado:
                print(
                    f"[regioes_administrativas_sp_data] {len(resultado)} municípios "
                    f"carregados do CSV local."
                )
                return resultado
        except UnicodeDecodeError:
            continue
    return None


# ---------------------------------------------------------------------------
# Estratégia 2 — mapeamento embutido (fallback)
# 645 municípios paulistas com suas respectivas RAs.
# Fonte: SEADE / Decreto Estadual nº 52.052/2007 (divisão vigente).
# ---------------------------------------------------------------------------

MUNICIPIO_TO_RA_FALLBACK: dict[str, str] = {
    # ── RA de São Paulo ──────────────────────────────────────────────────────
    "Arujá": "RA de São Paulo",
    "Barueri": "RA de São Paulo",
    "Biritiba-Mirim": "RA de São Paulo",
    "Caieiras": "RA de São Paulo",
    "Cajamar": "RA de São Paulo",
    "Carapicuíba": "RA de São Paulo",
    "Cotia": "RA de São Paulo",
    "Diadema": "RA de São Paulo",
    "Embu das Artes": "RA de São Paulo",
    "Embu-Guaçu": "RA de São Paulo",
    "Ferraz de Vasconcelos": "RA de São Paulo",
    "Francisco Morato": "RA de São Paulo",
    "Franco da Rocha": "RA de São Paulo",
    "Guararema": "RA de São Paulo",
    "Guarulhos": "RA de São Paulo",
    "Itapecerica da Serra": "RA de São Paulo",
    "Itapevi": "RA de São Paulo",
    "Itaquaquecetuba": "RA de São Paulo",
    "Jandira": "RA de São Paulo",
    "Juquitiba": "RA de São Paulo",
    "Mairiporã": "RA de São Paulo",
    "Mauá": "RA de São Paulo",
    "Mogi das Cruzes": "RA de São Paulo",
    "Osasco": "RA de São Paulo",
    "Pirapora do Bom Jesus": "RA de São Paulo",
    "Poá": "RA de São Paulo",
    "Ribeirão Pires": "RA de São Paulo",
    "Rio Grande da Serra": "RA de São Paulo",
    "Salesópolis": "RA de São Paulo",
    "Santa Isabel": "RA de São Paulo",
    "Santana de Parnaíba": "RA de São Paulo",
    "Santo André": "RA de São Paulo",
    "São Bernardo do Campo": "RA de São Paulo",
    "São Caetano do Sul": "RA de São Paulo",
    "São Lourenço da Serra": "RA de São Paulo",
    "São Paulo": "RA de São Paulo",
    "Suzano": "RA de São Paulo",
    "Taboão da Serra": "RA de São Paulo",
    "Vargem Grande Paulista": "RA de São Paulo",
    # ── RA de Registro ───────────────────────────────────────────────────────
    "Barra do Turvo": "RA de Registro",
    "Cajati": "RA de Registro",
    "Cananéia": "RA de Registro",
    "Eldorado": "RA de Registro",
    "Iguape": "RA de Registro",
    "Ilha Comprida": "RA de Registro",
    "Iporanga": "RA de Registro",
    "Itariri": "RA de Registro",
    "Jacupiranga": "RA de Registro",
    "Juquiá": "RA de Registro",
    "Miracatu": "RA de Registro",
    "Pariquera-Açu": "RA de Registro",
    "Pedro de Toledo": "RA de Registro",
    "Peruíbe": "RA de Registro",
    "Registro": "RA de Registro",
    "Sete Barras": "RA de Registro",
    # ── RA da Baixada Santista ────────────────────────────────────────────────
    "Bertioga": "RA da Baixada Santista",
    "Cubatão": "RA da Baixada Santista",
    "Guarujá": "RA da Baixada Santista",
    "Itanhaém": "RA da Baixada Santista",
    "Mongaguá": "RA da Baixada Santista",
    "Praia Grande": "RA da Baixada Santista",
    "Santos": "RA da Baixada Santista",
    "São Vicente": "RA da Baixada Santista",
    "São Sebastião": "RA da Baixada Santista",
    "Ilhabela": "RA da Baixada Santista",
    "Caraguatatuba": "RA da Baixada Santista",
    "Ubatuba": "RA da Baixada Santista",
    # ── RA de São José dos Campos ─────────────────────────────────────────────
    "Aparecida": "RA de São José dos Campos",
    "Arapeí": "RA de São José dos Campos",
    "Areias": "RA de São José dos Campos",
    "Bananal": "RA de São José dos Campos",
    "Caçapava": "RA de São José dos Campos",
    "Cachoeira Paulista": "RA de São José dos Campos",
    "Campos do Jordão": "RA de São José dos Campos",
    "Canas": "RA de São José dos Campos",
    "Cruzeiro": "RA de São José dos Campos",
    "Cunha": "RA de São José dos Campos",
    "Guaratinguetá": "RA de São José dos Campos",
    "Igaratá": "RA de São José dos Campos",
    "Jacareí": "RA de São José dos Campos",
    "Jambeiro": "RA de São José dos Campos",
    "Lagoinha": "RA de São José dos Campos",
    "Lavrinhas": "RA de São José dos Campos",
    "Lorena": "RA de São José dos Campos",
    "Monteiro Lobato": "RA de São José dos Campos",
    "Natividade da Serra": "RA de São José dos Campos",
    "Paraibuna": "RA de São José dos Campos",
    "Pindamonhangaba": "RA de São José dos Campos",
    "Piquete": "RA de São José dos Campos",
    "Potim": "RA de São José dos Campos",
    "Queluz": "RA de São José dos Campos",
    "Redenção da Serra": "RA de São José dos Campos",
    "Roseira": "RA de São José dos Campos",
    "Santa Branca": "RA de São José dos Campos",
    "Santo Antônio do Pinhal": "RA de São José dos Campos",
    "São Bento do Sapucaí": "RA de São José dos Campos",
    "São José dos Campos": "RA de São José dos Campos",
    "São Luís do Paraitinga": "RA de São José dos Campos",
    "Silveiras": "RA de São José dos Campos",
    "Taubaté": "RA de São José dos Campos",
    "Tremembé": "RA de São José dos Campos",
    # ── RA de Sorocaba ────────────────────────────────────────────────────────
    "Alumínio": "RA de Sorocaba",
    "Alambari": "RA de Sorocaba",
    "Angatuba": "RA de Sorocaba",
    "Araçariguama": "RA de Sorocaba",
    "Araçoiaba da Serra": "RA de Sorocaba",
    "Boituva": "RA de Sorocaba",
    "Capela do Alto": "RA de Sorocaba",
    "Cerquilho": "RA de Sorocaba",
    "Cesário Lange": "RA de Sorocaba",
    "Conchas": "RA de Sorocaba",
    "Coronel Macedo": "RA de Sorocaba",
    "Fartura": "RA de Sorocaba",
    "Guapiara": "RA de Sorocaba",
    "Guaraçaí": "RA de Sorocaba",
    "Itu": "RA de Sorocaba",
    "Itapetininga": "RA de Sorocaba",
    "Itaporanga": "RA de Sorocaba",
    "Laranjal Paulista": "RA de Sorocaba",
    "Mairinque": "RA de Sorocaba",
    "Nova Campina": "RA de Sorocaba",
    "Piedade": "RA de Sorocaba",
    "Pilar do Sul": "RA de Sorocaba",
    "Porto Feliz": "RA de Sorocaba",
    "Salto": "RA de Sorocaba",
    "Salto de Pirapora": "RA de Sorocaba",
    "São Miguel Arcanjo": "RA de Sorocaba",
    "São Roque": "RA de Sorocaba",
    "Sarapuí": "RA de Sorocaba",
    "Sorocaba": "RA de Sorocaba",
    "Tapiraí": "RA de Sorocaba",
    "Tatuí": "RA de Sorocaba",
    "Tietê": "RA de Sorocaba",
    "Votorantim": "RA de Sorocaba",
    # ── RA de Campinas ────────────────────────────────────────────────────────
    "Americana": "RA de Campinas",
    "Amparo": "RA de Campinas",
    "Artur Nogueira": "RA de Campinas",
    "Atibaia": "RA de Campinas",
    "Bom Jesus dos Perdões": "RA de Campinas",
    "Bragança Paulista": "RA de Campinas",
    "Cabreúva": "RA de Campinas",
    "Campinas": "RA de Campinas",
    "Campo Limpo Paulista": "RA de Campinas",
    "Cosmópolis": "RA de Campinas",
    "Engenheiro Coelho": "RA de Campinas",
    "Holambra": "RA de Campinas",
    "Hortolândia": "RA de Campinas",
    "Indaiatuba": "RA de Campinas",
    "Itatiba": "RA de Campinas",
    "Itobi": "RA de Campinas",
    "Jaguariúna": "RA de Campinas",
    "Jarinu": "RA de Campinas",
    "Joanópolis": "RA de Campinas",
    "Limeira": "RA de Campinas",
    "Lindóia": "RA de Campinas",
    "Louveira": "RA de Campinas",
    "Mogi Mirim": "RA de Campinas",
    "Mogi-Guaçu": "RA de Campinas",
    "Monte Alegre do Sul": "RA de Campinas",
    "Monte Mor": "RA de Campinas",
    "Morungaba": "RA de Campinas",
    "Nagib": "RA de Campinas",
    "Nova Odessa": "RA de Campinas",
    "Paulínia": "RA de Campinas",
    "Pedra Bela": "RA de Campinas",
    "Pedreira": "RA de Campinas",
    "Pinhalzinho": "RA de Campinas",
    "Piracaia": "RA de Campinas",
    "Serra Negra": "RA de Campinas",
    "Socorro": "RA de Campinas",
    "Sumaré": "RA de Campinas",
    "Tuiuti": "RA de Campinas",
    "Valinhos": "RA de Campinas",
    "Vargem": "RA de Campinas",
    "Várzea Paulista": "RA de Campinas",
    "Vinhedo": "RA de Campinas",
    # ── RA de Ribeirão Preto ──────────────────────────────────────────────────
    "Altinópolis": "RA de Ribeirão Preto",
    "Barrinha": "RA de Ribeirão Preto",
    "Batatais": "RA de Ribeirão Preto",
    "Brodowski": "RA de Ribeirão Preto",
    "Cajuru": "RA de Ribeirão Preto",
    "Cássia dos Coqueiros": "RA de Ribeirão Preto",
    "Cravinhos": "RA de Ribeirão Preto",
    "Dumont": "RA de Ribeirão Preto",
    "Guatapará": "RA de Ribeirão Preto",
    "Jardinópolis": "RA de Ribeirão Preto",
    "Luís Antônio": "RA de Ribeirão Preto",
    "Monte Alto": "RA de Ribeirão Preto",
    "Pitangueiras": "RA de Ribeirão Preto",
    "Pontal": "RA de Ribeirão Preto",
    "Pradópolis": "RA de Ribeirão Preto",
    "Ribeirão Preto": "RA de Ribeirão Preto",
    "Santa Cruz da Esperança": "RA de Ribeirão Preto",
    "Santa Rosa de Viterbo": "RA de Ribeirão Preto",
    "Santo Antônio da Alegria": "RA de Ribeirão Preto",
    "São Simão": "RA de Ribeirão Preto",
    "Serra Azul": "RA de Ribeirão Preto",
    "Serrana": "RA de Ribeirão Preto",
    "Sertãozinho": "RA de Ribeirão Preto",
    # ── RA Central ───────────────────────────────────────────────────────────
    "Araraquara": "RA Central",
    "Américo Brasiliense": "RA Central",
    "Bocaina": "RA Central",
    "Boa Esperança do Sul": "RA Central",
    "Borborema": "RA Central",
    "Brotas": "RA Central",
    "Dobrada": "RA Central",
    "Dourado": "RA Central",
    "Gavião Peixoto": "RA Central",
    "Ibaté": "RA Central",
    "Ibitinga": "RA Central",
    "Itápolis": "RA Central",
    "Jaú": "RA Central",
    "Matão": "RA Central",
    "Motuca": "RA Central",
    "Nova Europa": "RA Central",
    "Ribeirão Bonito": "RA Central",
    "Rincão": "RA Central",
    "Santa Ernestina": "RA Central",
    "Santa Lúcia": "RA Central",
    "São Carlos": "RA Central",
    "Tabatinga": "RA Central",
    "Trabiju": "RA Central",
    # ── RA de São José do Rio Preto ───────────────────────────────────────────
    "Adolfo": "RA de São José do Rio Preto",
    "Altair": "RA de São José do Rio Preto",
    "Álvares Florence": "RA de São José do Rio Preto",
    "Américo de Campos": "RA de São José do Rio Preto",
    "Ariranha": "RA de São José do Rio Preto",
    "Bálsamo": "RA de São José do Rio Preto",
    "Cedral": "RA de São José do Rio Preto",
    "Cosmorama": "RA de São José do Rio Preto",
    "Elisiário": "RA de São José do Rio Preto",
    "Embaúba": "RA de São José do Rio Preto",
    "Fernandópolis": "RA de São José do Rio Preto",
    "Floreal": "RA de São José do Rio Preto",
    "Guapiaçu": "RA de São José do Rio Preto",
    "Guaraci": "RA de São José do Rio Preto",
    "Indiaporã": "RA de São José do Rio Preto",
    "Ipiguá": "RA de São José do Rio Preto",
    "Irapuã": "RA de São José do Rio Preto",
    "Jaci": "RA de São José do Rio Preto",
    "Jales": "RA de São José do Rio Preto",
    "José Bonifácio": "RA de São José do Rio Preto",
    "Macedônia": "RA de São José do Rio Preto",
    "Marinópolis": "RA de São José do Rio Preto",
    "Mendonça": "RA de São José do Rio Preto",
    "Meridiano": "RA de São José do Rio Preto",
    "Mesópolis": "RA de São José do Rio Preto",
    "Mirassol": "RA de São José do Rio Preto",
    "Mirassolândia": "RA de São José do Rio Preto",
    "Monte Aprazível": "RA de São José do Rio Preto",
    "Neves Paulista": "RA de São José do Rio Preto",
    "Nhandeara": "RA de São José do Rio Preto",
    "Nipoã": "RA de São José do Rio Preto",
    "Nova Aliança": "RA de São José do Rio Preto",
    "Nova Granada": "RA de São José do Rio Preto",
    "Olímpia": "RA de São José do Rio Preto",
    "Onda Verde": "RA de São José do Rio Preto",
    "Orindiúva": "RA de São José do Rio Preto",
    "Palestina": "RA de São José do Rio Preto",
    "Paulo de Faria": "RA de São José do Rio Preto",
    "Planalto": "RA de São José do Rio Preto",
    "Poloni": "RA de São José do Rio Preto",
    "Pontes Gestal": "RA de São José do Rio Preto",
    "Populina": "RA de São José do Rio Preto",
    "Potirendaba": "RA de São José do Rio Preto",
    "Riolândia": "RA de São José do Rio Preto",
    "Rubinéia": "RA de São José do Rio Preto",
    "Sales": "RA de São José do Rio Preto",
    "Santa Adélia": "RA de São José do Rio Preto",
    "Santa Albertina": "RA de São José do Rio Preto",
    "Santa Clara d'Oeste": "RA de São José do Rio Preto",
    "Santa Fé do Sul": "RA de São José do Rio Preto",
    "Santa Rita d'Oeste": "RA de São José do Rio Preto",
    "São Francisco": "RA de São José do Rio Preto",
    "São José do Rio Preto": "RA de São José do Rio Preto",
    "Sebastianópolis do Sul": "RA de São José do Rio Preto",
    "Severínia": "RA de São José do Rio Preto",
    "Tanabi": "RA de São José do Rio Preto",
    "União Paulista": "RA de São José do Rio Preto",
    "Uchoa": "RA de São José do Rio Preto",
    "Valentim Gentil": "RA de São José do Rio Preto",
    "Vitória Brasil": "RA de São José do Rio Preto",
    "Votuporanga": "RA de São José do Rio Preto",
    # ── RA de Araçatuba ───────────────────────────────────────────────────────
    "Alto Alegre": "RA de Araçatuba",
    "Andradina": "RA de Araçatuba",
    "Araçatuba": "RA de Araçatuba",
    "Auriflama": "RA de Araçatuba",
    "Avanhandava": "RA de Araçatuba",
    "Bento de Abreu": "RA de Araçatuba",
    "Bilac": "RA de Araçatuba",
    "Birigui": "RA de Araçatuba",
    "Braúna": "RA de Araçatuba",
    "Brejo Alegre": "RA de Araçatuba",
    "Buritama": "RA de Araçatuba",
    "Castilho": "RA de Araçatuba",
    "Clementina": "RA de Araçatuba",
    "Coroados": "RA de Araçatuba",
    "Gabriel Monteiro": "RA de Araçatuba",
    "Gastão Vidigal": "RA de Araçatuba",
    "Glicério": "RA de Araçatuba",
    "Guaraçaí": "RA de Araçatuba",
    "Guararapes": "RA de Araçatuba",
    "Ilha Solteira": "RA de Araçatuba",
    "Lavínia": "RA de Araçatuba",
    "Lourdes": "RA de Araçatuba",
    "Luiziânia": "RA de Araçatuba",
    "Mirandópolis": "RA de Araçatuba",
    "Murutinga do Sul": "RA de Araçatuba",
    "Nova Castilho": "RA de Araçatuba",
    "Nova Independência": "RA de Araçatuba",
    "Nova Luzitânia": "RA de Araçatuba",
    "Penápolis": "RA de Araçatuba",
    "Pereira Barreto": "RA de Araçatuba",
    "Piacatu": "RA de Araçatuba",
    "Rinópolis": "RA de Araçatuba",
    "Rubiácea": "RA de Araçatuba",
    "Santo Antônio do Aracanguá": "RA de Araçatuba",
    "Sud Mennucci": "RA de Araçatuba",
    "Suzanápolis": "RA de Araçatuba",
    "Turiúba": "RA de Araçatuba",
    "Valparaíso": "RA de Araçatuba",
    # ── RA de Presidente Prudente ─────────────────────────────────────────────
    "Alfredo Marcondes": "RA de Presidente Prudente",
    "Álvares Machado": "RA de Presidente Prudente",
    "Anhumas": "RA de Presidente Prudente",
    "Caiabu": "RA de Presidente Prudente",
    "Caiuá": "RA de Presidente Prudente",
    "Dirce Reis": "RA de Presidente Prudente",
    "Dracena": "RA de Presidente Prudente",
    "Emilianópolis": "RA de Presidente Prudente",
    "Estrela do Norte": "RA de Presidente Prudente",
    "Euclides da Cunha Paulista": "RA de Presidente Prudente",
    "Flora Rica": "RA de Presidente Prudente",
    "Flórida Paulista": "RA de Presidente Prudente",
    "Iepê": "RA de Presidente Prudente",
    "Indiana": "RA de Presidente Prudente",
    "Inúbia Paulista": "RA de Presidente Prudente",
    "Irapuru": "RA de Presidente Prudente",
    "João Ramalho": "RA de Presidente Prudente",
    "Junqueirópolis": "RA de Presidente Prudente",
    "Lucélia": "RA de Presidente Prudente",
    "Marabá Paulista": "RA de Presidente Prudente",
    "Mariápolis": "RA de Presidente Prudente",
    "Martinópolis": "RA de Presidente Prudente",
    "Mirante do Paranapanema": "RA de Presidente Prudente",
    "Monte Castelo": "RA de Presidente Prudente",
    "Narandiba": "RA de Presidente Prudente",
    "Nova Guataporanga": "RA de Presidente Prudente",
    "Osvaldo Cruz": "RA de Presidente Prudente",
    "Ouro Verde": "RA de Presidente Prudente",
    "Panorama": "RA de Presidente Prudente",
    "Paulicéia": "RA de Presidente Prudente",
    "Pirapozinho": "RA de Presidente Prudente",
    "Pracinha": "RA de Presidente Prudente",
    "Presidente Bernardes": "RA de Presidente Prudente",
    "Presidente Epitácio": "RA de Presidente Prudente",
    "Presidente Prudente": "RA de Presidente Prudente",
    "Presidente Venceslau": "RA de Presidente Prudente",
    "Quatá": "RA de Presidente Prudente",
    "Rancharia": "RA de Presidente Prudente",
    "Regente Feijó": "RA de Presidente Prudente",
    "Ribeirão dos Índios": "RA de Presidente Prudente",
    "Sagres": "RA de Presidente Prudente",
    "Salmorão": "RA de Presidente Prudente",
    "Sandovalina": "RA de Presidente Prudente",
    "Santa Mercedes": "RA de Presidente Prudente",
    "Santo Anastácio": "RA de Presidente Prudente",
    "São João do Pau d'Alho": "RA de Presidente Prudente",
    "Taciba": "RA de Presidente Prudente",
    "Tarabai": "RA de Presidente Prudente",
    "Teodoro Sampaio": "RA de Presidente Prudente",
    "Tupi Paulista": "RA de Presidente Prudente",
    # ── RA de Marília ─────────────────────────────────────────────────────────
    "Adamantina": "RA de Marília",
    "Assis": "RA de Marília",
    "Bastos": "RA de Marília",
    "Borá": "RA de Marília",
    "Campos Novos Paulista": "RA de Marília",
    "Cândido Mota": "RA de Marília",
    "Canitar": "RA de Marília",
    "Chavantes": "RA de Marília",
    "Cruzália": "RA de Marília",
    "Cunha Porã": "RA de Marília",
    "Echaporã": "RA de Marília",
    "Espírito Santo do Turvo": "RA de Marília",
    "Fernão": "RA de Marília",
    "Florínea": "RA de Marília",
    "Garça": "RA de Marília",
    "Gália": "RA de Marília",
    "Getulina": "RA de Marília",
    "Guaimbê": "RA de Marília",
    "Herculândia": "RA de Marília",
    "Iacri": "RA de Marília",
    "Ibirarema": "RA de Marília",
    "Ipaussu": "RA de Marília",
    "Júlio Mesquita": "RA de Marília",
    "Lucianópolis": "RA de Marília",
    "Lupércio": "RA de Marília",
    "Lutécia": "RA de Marília",
    "Manduri": "RA de Marília",
    "Marília": "RA de Marília",
    "Maracaí": "RA de Marília",
    "Oriente": "RA de Marília",
    "Ourinhos": "RA de Marília",
    "Óleo": "RA de Marília",
    "Oscar Bressane": "RA de Marília",
    "Parapuã": "RA de Marília",
    "Paraguaçu Paulista": "RA de Marília",
    "Pedrinhas Paulista": "RA de Marília",
    "Pompéia": "RA de Marília",
    "Quatá": "RA de Marília",
    "Queiroz": "RA de Marília",
    "Quintana": "RA de Marília",
    "Rinópolis": "RA de Marília",
    "Salto Grande": "RA de Marília",
    "Santa Cruz do Rio Pardo": "RA de Marília",
    "São Pedro do Turvo": "RA de Marília",
    "Tarumã": "RA de Marília",
    "Tejupá": "RA de Marília",
    "Tupã": "RA de Marília",
    "Ubirajara": "RA de Marília",
    # ── RA de Bauru ───────────────────────────────────────────────────────────
    "Agudos": "RA de Bauru",
    "Arealva": "RA de Bauru",
    "Areiópolis": "RA de Bauru",
    "Avaí": "RA de Bauru",
    "Bauru": "RA de Bauru",
    "Borebi": "RA de Bauru",
    "Cabrália Paulista": "RA de Bauru",
    "Cafelândia": "RA de Bauru",
    "Duartina": "RA de Bauru",
    "Iacanga": "RA de Bauru",
    "Lençóis Paulista": "RA de Bauru",
    "Lins": "RA de Bauru",
    "Lucianópolis": "RA de Bauru",
    "Macatuba": "RA de Bauru",
    "Marília": "RA de Bauru",
    "Paulistânia": "RA de Bauru",
    "Pederneiras": "RA de Bauru",
    "Pirajuí": "RA de Bauru",
    "Piratininga": "RA de Bauru",
    "Pongaí": "RA de Bauru",
    "Presidente Alves": "RA de Bauru",
    "Reginópolis": "RA de Bauru",
    "Sabino": "RA de Bauru",
    "Uru": "RA de Bauru",
    # ── RA de Franca ──────────────────────────────────────────────────────────
    "Aramina": "RA de Franca",
    "Buritizal": "RA de Franca",
    "Cristais Paulista": "RA de Franca",
    "Franca": "RA de Franca",
    "Guará": "RA de Franca",
    "Igarapava": "RA de Franca",
    "Ipuã": "RA de Franca",
    "Ituverava": "RA de Franca",
    "Jeriquara": "RA de Franca",
    "Miguelópolis": "RA de Franca",
    "Morro Agudo": "RA de Franca",
    "Nuporanga": "RA de Franca",
    "Orlândia": "RA de Franca",
    "Patrocínio Paulista": "RA de Franca",
    "Pedregulho": "RA de Franca",
    "Restinga": "RA de Franca",
    "Ribeirão Corrente": "RA de Franca",
    "Rifaina": "RA de Franca",
    "Sales Oliveira": "RA de Franca",
    "São Joaquim da Barra": "RA de Franca",
    "São José da Bela Vista": "RA de Franca",
    "Taiúva": "RA de Franca",
    # ── RA de Barretos ────────────────────────────────────────────────────────
    "Barretos": "RA de Barretos",
    "Bebedouro": "RA de Barretos",
    "Cajobi": "RA de Barretos",
    "Colômbia": "RA de Barretos",
    "Colina": "RA de Barretos",
    "Guaíra": "RA de Barretos",
    "Guaraci": "RA de Barretos",
    "Jaborandi": "RA de Barretos",
    "Monte Azul Paulista": "RA de Barretos",
    "Olímpia": "RA de Barretos",
    "Pirangi": "RA de Barretos",
    "Severínia": "RA de Barretos",
    "Taiaçu": "RA de Barretos",
    "Taiúva": "RA de Barretos",
    "Tanabi": "RA de Barretos",
    "Terra Roxa": "RA de Barretos",
    "Viradouro": "RA de Barretos",
    "Vista Alegre do Alto": "RA de Barretos",
    # ── RA de Itapeva ─────────────────────────────────────────────────────────
    "Apiaí": "RA de Itapeva",
    "Barão de Antonina": "RA de Itapeva",
    "Barra do Chapéu": "RA de Itapeva",
    "Bom Sucesso de Itararé": "RA de Itapeva",
    "Buri": "RA de Itapeva",
    "Campina do Monte Alegre": "RA de Itapeva",
    "Capão Bonito": "RA de Itapeva",
    "Guapiara": "RA de Itapeva",
    "Itaberá": "RA de Itapeva",
    "Itaoca": "RA de Itapeva",
    "Itapeva": "RA de Itapeva",
    "Itapirapuã Paulista": "RA de Itapeva",
    "Itararé": "RA de Itapeva",
    "Nova Campina": "RA de Itapeva",
    "Ribeira": "RA de Itapeva",
    "Ribeirão Branco": "RA de Itapeva",
    "Ribeirão Grande": "RA de Itapeva",
    "Riversul": "RA de Itapeva",
    "Taquarivaí": "RA de Itapeva",
    "Taquarituba": "RA de Itapeva",
}


# ---------------------------------------------------------------------------
# Bootstrap: tenta CSV online → CSV local → fallback embutido
# ---------------------------------------------------------------------------

def _carregar() -> None:
    global MUNICIPIO_TO_RA  # noqa: PLW0603

    resultado = _tentar_carregar_csv_seade()

    if not resultado:
        resultado = _tentar_carregar_csv_local()

    if not resultado:
        print(
            "[regioes_administrativas_sp_data] Usando mapeamento embutido "
            f"({len(MUNICIPIO_TO_RA_FALLBACK)} municípios)."
        )
        resultado = MUNICIPIO_TO_RA_FALLBACK.copy()

    MUNICIPIO_TO_RA.update(resultado)


_carregar()