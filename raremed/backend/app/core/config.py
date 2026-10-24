"""Environment-backed settings.

Development defaults match docker-compose.yml. Real deployments must replace
the development database and Neo4j passwords.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    # backend/app/core/config.py -> repository root in a source checkout.
    return Path(__file__).resolve().parents[3]


def _env_files() -> tuple[str, ...]:
    candidates = (
        Path.cwd() / ".env",
        _repo_root() / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    )
    return tuple(str(path) for path in candidates if path.is_file())


def default_data_root() -> Path:
    """Prefer the repository data directory, then the Docker mount."""
    repo_data = _repo_root() / "data"
    if repo_data.exists():
        return repo_data
    docker_data = Path("/data")
    if docker_data.exists():
        return docker_data
    return repo_data


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    log_json: bool = True

    database_url: str = "postgresql+psycopg://raremed:raremed@localhost:5432/raremed"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "raremed-neo4j"
    neo4j_database: str = "neo4j"
    neo4j_timeout_seconds: float = 2.0

    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = 2.0
    ollama_model: str | None = None
    ollama_think: bool | None = None
    model_temperature: float | None = None
    model_num_ctx: int | None = None
    inference_provider: str | None = None
    openai_base_url: str = ""
    openai_api_key: str = ""
    vllm_base_url: str = ""
    vllm_api_key: str = ""

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    data_root: Path = Field(default_factory=default_data_root)

    session_ttl_seconds: int = 604800
    cookie_secure: bool | None = None
    cookie_samesite: str = "lax"
    admin_email: str = ""
    admin_password: str = ""

    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def session_cookie_secure(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.app_env != "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
