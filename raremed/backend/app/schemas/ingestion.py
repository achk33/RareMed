from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IngestionRunRequest(BaseModel):
    strict: bool = False


class SourceImportRow(BaseModel):
    source: str
    role: str
    file_path: str | None = None
    expected_path: str | None = None
    version: str | None = None
    release_date: str | None = None
    import_status: str
    entity_counts: dict[str, int] = Field(default_factory=dict)
    relationship_counts: dict[str, int] = Field(default_factory=dict)
    validation_warnings: list[str] = Field(default_factory=list)
    last_successful_import: datetime | None = None
    required: bool = False
    schema_name: str | None = None


class IngestionRunSummary(BaseModel):
    run_id: str
    status: str
    trigger: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None
    entity_count: int = 0
    relationship_count: int = 0
    warning_count: int = 0
    missing_required: list[str] = Field(default_factory=list)
    error_message: str | None = None


class IngestionStatus(BaseModel):
    running: bool
    current_run: IngestionRunSummary | None = None
    last_successful_import: datetime | None = None
    missing_required: list[str] = Field(default_factory=list)
    sources: list[SourceImportRow] = Field(default_factory=list)
    history: list[IngestionRunSummary] = Field(default_factory=list)
    counts: dict[str, Any] = Field(default_factory=dict)
    note: str
