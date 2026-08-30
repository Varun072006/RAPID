"""
Database setup — SQLAlchemy engine + session factory.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from apps.api.config import get_settings
from packages.domain.payments.models import Base


def get_engine():
    settings = get_settings()
    db_url = settings.database_url
    try:
        if db_url.startswith("sqlite"):
            return create_engine(
                db_url,
                connect_args={"check_same_thread": False},
            )
        else:
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
            # Test connection
            with engine.connect() as conn:
                pass
            return engine
    except Exception as exc:
        from loguru import logger
        logger.warning(
            f"PostgreSQL connection failed ({exc}). "
            "Falling back to local SQLite database (rapid.db)."
        )
        return create_engine(
            "sqlite:///./rapid.db",
            connect_args={"check_same_thread": False},
        )


_engine = None
_SessionLocal = None


def init_db() -> None:
    """Create all tables (idempotent)."""
    global _engine, _SessionLocal
    _engine = get_engine()
    Base.metadata.create_all(bind=_engine)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def get_db() -> Session:
    """FastAPI dependency that yields a DB session."""
    if _SessionLocal is None:
        init_db()
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
