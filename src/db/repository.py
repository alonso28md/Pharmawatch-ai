"""CRUD repository for query logs and evaluation runs, backed by SQLite."""

import logging
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Base, EvaluationRun, QueryLog

logger = logging.getLogger(__name__)


class Repository:
    """Owns the SQLAlchemy engine/session and exposes CRUD operations."""

    def __init__(self, db_path: Path | str):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{self._db_path}", future=True)
        self._session_factory: sessionmaker[Session] = sessionmaker(bind=self._engine, future=True)
        Base.metadata.create_all(self._engine)

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
            )
            session.add(record)
            session.commit()
            return record.id

    def list_queries(self, limit: int = 1000) -> list[QueryLog]:
        """Return the most recent `limit` query log rows, newest first."""
        with self._session_factory() as session:
            statement = select(QueryLog).order_by(QueryLog.timestamp.desc()).limit(limit)
            return list(session.scalars(statement))

    def log_evaluation_run(
        self, total_cases: int, passed: int, failed: int, metrics_json: str, report_path: str | None = None
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
