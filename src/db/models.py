"""SQLAlchemy ORM models for operational query logging and evaluation history."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all PharmaWatch AI ORM models."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


class QueryLog(Base):
    """One row per API request to /ask, /report, or /evaluate."""

    __tablename__ = "queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(64), nullable=False)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    device_class: Mapped[str | None] = mapped_column(String(8), nullable=True)
    reportable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvaluationRun(Base):
    """One row per evaluation harness run (via script or the /evaluate endpoint)."""

    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[int] = mapped_column(Integer, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    report_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
