import uuid
from datetime import datetime, timezone, date as date_type

from sqlalchemy import text


def get_or_create_fonte_dado(
    conn,
    nome: str,
    orgao_responsavel: str = None,
    url_origem: str = None,
    formato: str = None,
    periodicidade: str = None,
    escopo_geografico: str = None,
    licenca: str = None,
) -> str:
    """Retorna o UUID da fonte_dado existente ou cria uma nova."""
    row = conn.execute(
        text("SELECT id FROM fonte_dado WHERE nome = :nome"),
        {"nome": nome},
    ).fetchone()
    if row:
        return str(row[0])

    new_id = str(uuid.uuid4())
    conn.execute(
        text("""
            INSERT INTO fonte_dado
                (id, nome, orgao_responsavel, url_origem, formato,
                 periodicidade, escopo_geografico, licenca, ativo)
            VALUES
                (:id, :nome, :orgao, :url, :fmt, :period, :escopo, :licenca, true)
        """),
        {
            "id": new_id,
            "nome": nome,
            "orgao": orgao_responsavel,
            "url": url_origem,
            "fmt": formato,
            "period": periodicidade,
            "escopo": escopo_geografico,
            "licenca": licenca,
        },
    )
    print(f"[loader] Fonte criada: {nome}")
    return new_id


def get_or_create_dataset(
    conn,
    fonte_dado_id: str,
    nome: str,
    descricao: str = None,
    versao: str = None,
    data_referencia: date_type = None,
) -> tuple[str, bool]:
    """
    Retorna (dataset_id, is_new).
    Se is_new=False, os dados já foram importados — o ETL deve abortar.
    """
    row = conn.execute(
        text("SELECT id FROM dataset WHERE fonte_dado_id = :fid AND nome = :nome"),
        {"fid": fonte_dado_id, "nome": nome},
    ).fetchone()
    if row:
        print(f"[loader] Dataset '{nome}' já importado — abortando inserção duplicada.")
        return str(row[0]), False

    new_id = str(uuid.uuid4())
    conn.execute(
        text("""
            INSERT INTO dataset
                (id, fonte_dado_id, nome, descricao, versao, data_coleta, data_referencia)
            VALUES
                (:id, :fid, :nome, :descricao, :versao, :coleta, :referencia)
        """),
        {
            "id": new_id,
            "fid": fonte_dado_id,
            "nome": nome,
            "descricao": descricao,
            "versao": versao,
            "coleta": datetime.now(timezone.utc),
            "referencia": data_referencia,
        },
    )
    print(f"[loader] Dataset criado: {nome}")
    return new_id, True
