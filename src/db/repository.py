"""CRUD repository for query logs, incidents and evaluation runs, backed by SQLite."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Base, EvaluationRun, Incident, QueryLog

logger = logging.getLogger(__name__)

# Columns added after the first release. Existing databases get them via an additive
# ALTER TABLE (no data is rewritten); legacy rows default to source='live'.
_ADDED_QUERY_COLUMNS = {
    "method": "VARCHAR(8)",
    "status_code": "INTEGER",
    "source": "VARCHAR(8) NOT NULL DEFAULT 'live'",
    "escalation_level": "VARCHAR(16)",
    "input_length": "INTEGER",
    "input_sha256": "VARCHAR(64)",
}


class Repository:
    """Owns the SQLAlchemy engine/session and exposes CRUD operations."""

    def __init__(self, db_path: Path | str):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{self._db_path}", future=True)
        self._session_factory: sessionmaker[Session] = sessionmaker(
            bind=self._engine, future=True, expire_on_commit=False
        )
        Base.metadata.create_all(self._engine)
        self._add_missing_columns()

    def _add_missing_columns(self) -> None:
        existing = {c["name"] for c in inspect(self._engine).get_columns("queries")}
        missing = {name: ddl for name, ddl in _ADDED_QUERY_COLUMNS.items() if name not in existing}
        if not missing:
            return
        with self._engine.begin() as conn:
            for name, ddl in missing.items():
                conn.execute(text(f"ALTER TABLE queries ADD COLUMN {name} {ddl}"))
            if "status_code" in missing:
                # One-off, only when upgrading a pre-v2 database: before v2 a middleware bug
                # (B-05) left latency_ms NULL for every real request, so the only /ask and
                # /report rows carrying a latency are the synthetic rows written by
                # scripts/seed_db.py. Mark them as demo so /metrics excludes them.
                marked = conn.execute(
                    text(
                        "UPDATE queries SET source = 'demo' WHERE status_code IS NULL "
                        "AND latency_ms IS NOT NULL AND endpoint IN ('/ask', '/report')"
                    )
                ).rowcount
                logger.info("Marked %d legacy seed row(s) as source='demo'", marked)
        logger.info("Added column(s) %s to existing queries table", sorted(missing))

    # --- query log ------------------------------------------------------------------

    def log_query(
        self,
        endpoint: str,
        input_text: str | None = None,
        output_summary: str | None = None,
        severity: str | None = None,
        device_class: str | None = None,
        reportable: bool | None = None,
        confidence: float | None = None,
        escalated: bool = False,
        latency_ms: float | None = None,
        error: str | None = None,
        method: str | None = None,
        status_code: int | None = None,
        source: str = "live",
        escalation_level: str | None = None,
        input_length: int | None = None,
        input_sha256: str | None = None,
    ) -> int:
        """Insert one query log row and return its id."""
        with self._session_factory() as session:
            record = QueryLog(
                endpoint=endpoint,
                input_text=input_text,
                output_summary=output_summary,
                severity=severity,
                device_class=device_class,
                reportable=reportable,
                confidence=confidence,
                escalated=escalated,
                latency_ms=latency_ms,
                error=error,
                method=method,
                status_code=status_code,
                source=source,
                escalation_level=escalation_level,
                input_length=input_length,
                input_sha256=input_sha256,
            )
            session.add(record)
            session.commit()
            return record.id

    def list_queries(
        self, limit: int | None = 1000, include_demo: bool = True, since: datetime | None = None
    ) -> list[QueryLog]:
        """Return query log rows, newest first."""
        with self._session_factory() as session:
            statement = select(QueryLog).order_by(QueryLog.timestamp.desc(), QueryLog.id.desc())
            if not include_demo:
                statement = statement.where(QueryLog.source != "demo")
            if since is not None:
                statement = statement.where(
                    QueryLog.timestamp >= since.astimezone(UTC).replace(tzinfo=None)
                )
            if limit is not None:
                statement = statement.limit(limit)
            return list(session.scalars(statement))

    # --- incidents --------------------------------------------------------------------

    def save_incident(self, incident_id: str, result: dict) -> None:
        """Persist the classification result (the free-text description is not stored)."""
        with self._session_factory() as session:
            session.add(
                Incident(
                    incident_id=incident_id,
                    incident_category=result.get("incident_category"),
                    severity=result.get("severity"),
                    reportable=result.get("reportable"),
                    deadline_days=result.get("deadline_days"),
                    deadline_rule=result.get("deadline_rule"),
                    report_to_json=json.dumps(result.get("report_to")),
                    escalation_level=result.get("escalation_level", "none"),
                    escalation_reason=result.get("escalation_reason"),
                    device_class=result.get("device_class"),
                    device_class_source=result.get("device_class_source"),
                    result_json=json.dumps(result, default=str),
                )
            )
            session.commit()

    def list_incidents(
        self,
        limit: int = 20,
        offset: int = 0,
        severity: str | None = None,
        escalation: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[list[dict], int]:
        """Newest-first page of stored incident results plus the total matching count.

        `escalation`: "none", "advisory", "blocking" or "escalated" (advisory or blocking).
        """
        conditions = []
        if severity:
            conditions.append(Incident.severity == severity)
        if escalation == "escalated":
            conditions.append(Incident.escalation_level.in_(("advisory", "blocking")))
        elif escalation:
            conditions.append(Incident.escalation_level == escalation)
        if since:
            conditions.append(Incident.created_at >= since.astimezone(UTC).replace(tzinfo=None))
        if until:
            conditions.append(Incident.created_at < until.astimezone(UTC).replace(tzinfo=None))
        with self._session_factory() as session:
            total = (
                session.scalar(select(func.count()).select_from(Incident).where(*conditions)) or 0
            )
            rows = session.scalars(
                select(Incident)
                .where(*conditions)
                .order_by(Incident.created_at.desc(), Incident.incident_id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            items = [
                {**json.loads(r.result_json), "created_at": r.created_at.replace(tzinfo=UTC)}
                for r in rows
            ]
        return items, total

    def get_incident(self, incident_id: str) -> dict | None:
        with self._session_factory() as session:
            row = session.get(Incident, incident_id)
            return None if row is None else json.loads(row.result_json)

    # --- evaluation runs (legacy) ---------------------------------------------------------

    def log_evaluation_run(
        self,
        total_cases: int,
        passed: int,
        failed: int,
        metrics_json: str,
        report_path: str | None = None,
    ) -> int:
        """Insert one evaluation-run row and return its id."""
        with self._session_factory() as session:
            record = EvaluationRun(
                total_cases=total_cases,
                passed=passed,
                failed=failed,
                metrics_json=metrics_json,
                report_path=report_path,
            )
            session.add(record)
            session.commit()
            return record.id

    def list_evaluation_runs(self, limit: int = 50) -> list[EvaluationRun]:
        """Return the most recent `limit` evaluation runs, newest first."""
        with self._session_factory() as session:
            statement = select(EvaluationRun).order_by(EvaluationRun.timestamp.desc()).limit(limit)
            return list(session.scalars(statement))
