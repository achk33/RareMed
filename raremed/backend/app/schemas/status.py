from pydantic import BaseModel, Field

from app.schemas.common import DependencyStatus


class OllamaStatus(BaseModel):
    status: str
    base_url: str
    detail: str | None = None
    models: list[str] = Field(default_factory=list)
    configured_model: str = ""
    model_ready: bool = False
    think: bool = False


class DatasetSummary(BaseModel):
    readable: bool
    total_files: int
    sources_with_files: list[str]


class StatusResponse(BaseModel):
    service: str
    version: str
    api_version: str
    environment: str
    decision_support_notice: str
    database: DependencyStatus
    neo4j: DependencyStatus
    ollama: OllamaStatus
    datasets: DatasetSummary
    clinical_reasoning_enabled: bool = False
