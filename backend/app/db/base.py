from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def get_engine():
    if not settings.database_url:
        return None
    return create_engine(settings.database_url, pool_pre_ping=True)


def get_session_factory():
    engine = get_engine()
    if engine is None:
        return None
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


engine = get_engine()
SessionLocal = get_session_factory()


def get_db():
    """FastAPI dependency that yields a SQLAlchemy database session."""
    if SessionLocal is None:
        raise RuntimeError("Database session factory is not configured. Check DATABASE_URL.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

