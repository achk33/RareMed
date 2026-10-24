from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="cli")
    strict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)
    imports_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)
    previous_run_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relationship_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_required: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    source_summaries: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    counts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    warnings: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
