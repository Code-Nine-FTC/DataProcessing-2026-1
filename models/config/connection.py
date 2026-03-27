import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()


def get_engine():
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "visiona")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")

    os.environ["PGPASSWORD"] = password

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"

    return create_engine(url, pool_pre_ping=True)