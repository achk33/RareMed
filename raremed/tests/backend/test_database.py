from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.database import check_database, driver_connect_args
from app.models import Base


def test_database_probe_runs_select_one():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    check_database(engine)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
    engine.dispose()


def test_postgres_connect_timeout_is_bounded():
    assert driver_connect_args("postgresql+psycopg://raremed:raremed@localhost:5432/raremed") == {
        "connect_timeout": 3
    }
    assert driver_connect_args("sqlite+pysqlite:///:memory:") == {}


def test_metadata_registers_workspace_tables():
    tables = Base.metadata.tables
    assert "conversations" in tables
    assert "messages" in tables
    assert "conversation_id" in tables["messages"].c


def test_postgres_connectivity(postgres_url):
    if not postgres_url.startswith("postgresql"):
        raise AssertionError("DATABASE_URL must use the PostgreSQL driver.")

    engine = create_engine(
        postgres_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )
    try:
        check_database(engine)
    except OperationalError as exc:
        engine.dispose()
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if sqlstate in {"28P01", "28000"}:
            raise
        import pytest

        pytest.skip("PostgreSQL is not reachable. Start it with docker compose up.")
    else:
        engine.dispose()
