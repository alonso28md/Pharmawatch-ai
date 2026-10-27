"""SQLAlchemy ORM models for operational query logging, incidents and evaluation history."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all PharmaWatch AI ORM models."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


class QueryLog(Base):
    """One row per business API request (/ask, /report, /evaluate), including failures."""

    __tablename__ = "queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(64), nullable=False)
    method: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "live" for real traffic; "demo" for scripts/seed_db.py rows (excluded from /metrics).
    source: Mapped[str] = mapped_column(String(8), default="live", nullable=False)
    # The submitted text is only kept when STORE_INPUT_TEXT=true; otherwise just its
    # length and SHA-256 (enough to spot duplicates without retaining patient narratives).
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    device_class: Mapped[str | None] = mapped_column(String(8), nullable=True)
    reportable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalation_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Incident(Base):
    """Minimal persistent record of each classified incident (no free-text narrative stored)."""

    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    incident_category: Mapped[str | None] = mapped_column(String(48), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reportable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    deadline_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadline_rule: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_to_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_level: Mapped[str] = mapped_column(String(16), nullable=False)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    device_class: Mapped[str | None] = mapped_column(String(8), nullable=True)
    device_class_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)


class EvaluationRun(Base):
    """Legacy table: evaluation runs are now written as JSON to ARTIFACTS_DIR instead."""

    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[int] = mapped_column(Integer, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    report_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
