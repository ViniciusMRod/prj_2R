"""
Configuração do banco de dados PostgreSQL.
Fornece engine, SessionLocal e Base para os models SQLAlchemy.
"""
import os
import logging
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import QueuePool

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pcmso_user:pcmso_password@localhost:5432/pcmso_alerts")
DB_ECHO = os.getenv("DB_ECHO", "False").lower() == "true"

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=DB_ECHO,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    """Dependency para FastAPI — fornece sessão e fecha automaticamente."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager para uso fora do FastAPI (scripts, celery, etc.)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def test_connection() -> bool:
    """Testa se a conexão com o banco está funcionando."""
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("Conexão com PostgreSQL estabelecida com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Falha na conexão com PostgreSQL: {e}")
        return False
