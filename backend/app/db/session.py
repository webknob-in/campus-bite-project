from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


# Fail fast when the database host is unreachable (so /health answers 503 instead of hanging).
CONNECT_TIMEOUT_SECONDS = 10


def build_engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.port == 6543:  # Supabase transaction pooler (Vercel runtime)
        return create_engine(
            url,
            poolclass=NullPool,
            # url carries sslmode=require
            connect_args={"prepare_threshold": None, "connect_timeout": CONNECT_TIMEOUT_SECONDS},
        )
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


engine = build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
