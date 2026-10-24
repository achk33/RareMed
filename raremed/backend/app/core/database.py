"""PostgreSQL access through SQLAlchemy.

The pooled engine is created on first use so importing the app, and the
liveness probe, do not require a running database.
"""

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            connect_args=driver_connect_args(settings.database_url),
            future=True,
        )
        _session_factory = sessionmaker(
            bind=_engine,
            autoflush=False,
            expire_on_commit=False,
            class_=Session,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def driver_connect_args(database_url: str) -> dict[str, int]:
    """Bound PostgreSQL TCP connect time so a stopped database fails quickly."""
    if database_url.startswith("postgresql"):
        return {"connect_timeout": 3}
    return {}


def check_database(engine: Engine) -> None:
    """Run a connectivity probe. Raises if the database cannot answer."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
