import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.main import create_app
from app.models import Base, User


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def sqlite_bundle():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)

    def override_db():
        session = factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield {"client": test_client, "factory": factory}
    engine.dispose()


@pytest.fixture()
def sqlite_client(sqlite_bundle) -> TestClient:
    return sqlite_bundle["client"]


@pytest.fixture()
def auth_client(sqlite_client) -> TestClient:
    register_user(sqlite_client)
    return sqlite_client


@pytest.fixture()
def postgres_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://raremed:raremed@localhost:5432/raremed",
    )


def register_user(
    client: TestClient,
    email: str = "person@example.com",
    password: str = "correcthorse1",
    display_name: str = "Person",
):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )
    assert response.status_code == 201, response.text
    return response


def set_role(factory, email: str, role: str) -> None:
    session = factory()
    user = session.query(User).filter(User.email == email).one()
    user.role = role
    session.commit()
    session.close()
