import csv
from pathlib import Path

# ----------------------------------
# METADADOS DAS 16 REGIÕES ADMINISTRATIVAS
# ----------------------------------

RA_METADATA = [
    {"nome": "RA de São Paulo",              "sigla": "RASP",   "tipo": "RA"},
    {"nome": "RA de Registro",               "sigla": "RAREG",  "tipo": "RA"},
    {"nome": "RA da Baixada Santista",       "sigla": "RABS",   "tipo": "RA"},
    {"nome": "RA de São José dos Campos",    "sigla": "RASJC",  "tipo": "RA"},
    {"nome": "RA de Sorocaba",               "sigla": "RASOR",  "tipo": "RA"},
    {"nome": "RA de Campinas",               "sigla": "RACAM",  "tipo": "RA"},
    {"nome": "RA de Ribeirão Preto",         "sigla": "RARP",   "tipo": "RA"},
    {"nome": "RA Central",                   "sigla": "RACEN",  "tipo": "RA"},
    {"nome": "RA de São José do Rio Preto",  "sigla": "RASJRP", "tipo": "RA"},
    {"nome": "RA de Araçatuba",              "sigla": "RAARA",  "tipo": "RA"},
    {"nome": "RA de Presidente Prudente",    "sigla": "RAPP",   "tipo": "RA"},
    {"nome": "RA de Marília",                "sigla": "RAMAR",  "tipo": "RA"},
    {"nome": "RA de Bauru",                  "sigla": "RABAU",  "tipo": "RA"},
    {"nome": "RA de Franca",                 "sigla": "RAFRA",  "tipo": "RA"},
    {"nome": "RA de Barretos",               "sigla": "RABAR",  "tipo": "RA"},
    {"nome": "RA de Itapeva",                "sigla": "RAITA",  "tipo": "RA"},
]


# ----------------------------------
# MAPA: NOME DE RA NO CSV → NOME CANÔNICO EM RA_METADATA
# ----------------------------------
# O CSV oficial usa formatos como "RA Campinas" (sem "de"),
# "RM  São Paulo" (RMSP é a 16ª RA, equivalente a "RA de São Paulo")
# e "RA Santos" (oficialmente referida como "RA da Baixada Santista").
# A chave é a forma normalizada (lowercase, espaços colapsados) do nome do CSV.

_CSV_RA_TO_CANONICO: dict[str, str] = {
    "ra aracatuba":             "RA de Araçatuba",
    "ra barretos":              "RA de Barretos",
    "ra bauru":                 "RA de Bauru",
    "ra campinas":              "RA de Campinas",
    "ra central":               "RA Central",
    "ra franca":                "RA de Franca",
    "ra itapeva":                "RA de Itapeva",
    "ra marilia":                "RA de Marília",
    "ra presidente prudente":    "RA de Presidente Prudente",
    "ra registro":               "RA de Registro",
    "ra ribeirao preto":         "RA de Ribeirão Preto",
    "ra santos":                 "RA da Baixada Santista",
    "ra sao jose do rio preto":  "RA de São José do Rio Preto",
    "ra sao jose dos campos":    "RA de São José dos Campos",
    "ra sorocaba":               "RA de Sorocaba",
    "rm sao paulo":              "RA de São Paulo",
}


# ----------------------------------
# MAPEAMENTO MUNICÍPIO → RA (populado pelo CSV)
# ----------------------------------
# Chave: nome do município (sem normalização — o script `inserir_regiao_administrativa`
#        normaliza com `models.inserir_estado_municipio.normalizar` para casar com
#        `Municipio.nome` no banco).
# Valor: nome canônico da RA (exatamente como aparece em RA_METADATA).

MUNICIPIO_TO_RA: dict[str, str] = {}


# ----------------------------------
# LOADER DO CSV OFICIAL
# ----------------------------------

CSV_PATH = Path(__file__).resolve().parent / "docs" / "codigos_municipios_regioes.csv"


def _normalizar_chave(texto: str) -> str:
    """Normalização leve para casar chaves do _CSV_RA_TO_CANONICO.

    Lowercase, remove acentos via NFD e colapsa espaços. Mantém o módulo
    independente de `nlp_processor.pipeline.preprocessor` para evitar import
    circular (este módulo é importado pelo loader do banco).
    """
    import unicodedata
    s = texto.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


def _abrir_csv(path: Path):
    """Abre o CSV tentando UTF-8 primeiro e caindo para latin-1.

    O arquivo de origem (SEADE) costuma vir em windows-1252/latin-1, mas
    aceitamos UTF-8 para o caso de o usuário re-exportar.
    """
    try:
        with path.open(encoding="utf-8") as f:
            f.read()
        return path.open(encoding="utf-8")
    except UnicodeDecodeError:
        return path.open(encoding="latin-1")


def _carregar_csv_municipios_ra() -> None:
    if not CSV_PATH.exists():
        print(
            f"⚠️ [regioes_administrativas_sp_data] CSV não encontrado em "
            f"{CSV_PATH}. MUNICIPIO_TO_RA ficará vazio."
        )
        return

    nomes_ra_validos = {meta["nome"] for meta in RA_METADATA}
    ras_desconhecidas: set[str] = set()
    ignorados_sem_ra: list[str] = []
    carregados = 0

    with _abrir_csv(CSV_PATH) as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            municipio = (row.get("municipio") or "").strip()
            ra_csv = (row.get("ra") or "").strip()
            cod_ibge = (row.get("cod_ibge") or "").strip()

            if not municipio or not ra_csv:
                continue
            # Linhas-resumo do CSV (Estado e "Sem especificação de município")
            if cod_ibge in {"35", "3500000"} or ra_csv.lower().startswith("estado"):
                continue
            if ra_csv.lower().startswith("sem especificacao") or "sem especifica" in ra_csv.lower():
                continue

            chave = _normalizar_chave(ra_csv)
            ra_canonica = _CSV_RA_TO_CANONICO.get(chave)

            if ra_canonica is None:
                ras_desconhecidas.add(ra_csv)
                ignorados_sem_ra.append(municipio)
                continue
            if ra_canonica not in nomes_ra_validos:
                # Sanidade: o mapa apontou para um nome que não está em RA_METADATA
                ras_desconhecidas.add(f"{ra_csv} -> {ra_canonica}")
                continue

            MUNICIPIO_TO_RA[municipio] = ra_canonica
            carregados += 1

    if ras_desconhecidas:
        print(
            f"⚠️ [regioes_administrativas_sp_data] {len(ras_desconhecidas)} valores "
            f"da coluna `ra` do CSV não foram reconhecidos e foram ignorados: "
            f"{sorted(ras_desconhecidas)}"
        )
        if ignorados_sem_ra:
            print(
                f"   {len(ignorados_sem_ra)} municípios ficaram sem RA por esse motivo. "
                f"Ex.: {ignorados_sem_ra[:5]}"
            )

    print(
        f"[regioes_administrativas_sp_data] {carregados} municípios carregados "
        f"de {CSV_PATH.name}."
    )


_carregar_csv_municipios_ra()
