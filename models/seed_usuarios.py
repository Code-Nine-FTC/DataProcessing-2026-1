# -*- coding: utf-8 -*-
"""Cria usuários padrão de desenvolvimento (idempotente)."""
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from api.config.settings import settings
from models.db_model import Usuario

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)

USUARIOS_PADRAO = [
    {
        "email": "admin@codenine.dev",
        "senha": "admin123",
        "nome": "Admin Codenine",
        "role": "admin",
    },
    {
        "email": "user@codenine.dev",
        "senha": "user123",
        "nome": "Usuário Demo",
        "role": "user",
    },
]


def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_usuarios() -> None:
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        for dados in USUARIOS_PADRAO:
            existente = session.scalar(
                select(Usuario).where(Usuario.email == dados["email"])
            )
            if existente:
                print(f"[skip] {dados['email']} já existe")
                continue

            session.add(
                Usuario(
                    email=dados["email"],
                    senha_hash=_hash_senha(dados["senha"]),
                    nome=dados["nome"],
                    role=dados["role"],
                )
            )
            print(f"[ok] {dados['email']} ({dados['role']})")

        session.commit()
    print("Seed de usuários concluído.")


if __name__ == "__main__":
    seed_usuarios()
