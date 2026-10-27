#!/usr/bin/env python
"""Seed the local SQLite database with demo query-log data for local UI/testing.

These are synthetic demo rows, stored with source="demo" so /metrics excludes them unless
asked (?include_demo=true). They are NOT evaluation
metrics. Real evaluation metrics only ever come from scripts/run_evaluation.py
running the actual system against the golden dataset.
"""

import logging
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings  # noqa: E402
from src.db.repository import Repository  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEMO_QUESTIONS = [
    "What is the reporting deadline for a serious incident?",
    "How are breast implants classified under Annex VIII?",
    "What is NotificaPS?",
    "What is a field safety corrective action?",
]

DEMO_DESCRIPTIONS_AND_OUTCOMES = [
    ("A ventilator stopped delivering breaths and the patient died.", "serious", "III", True, 0.95),
    ("A syringe plunger was slightly stiff; no harm occurred.", "non-serious", "I", False, 0.9),
    ("A contrast injector delivered 3x the programmed dose.", "serious", "IIb", True, 0.85),
    ("A thermometer reading was 0.1C off during calibration.", "non-serious", "IIa", False, 0.92),
    ("A possible issue was noted but no further details given.", None, None, None, None),
]


def main(num_records: int = 40) -> None:
    settings = get_settings()
    repository = Repository(settings.db_path_absolute)

    random.seed(42)
    for _ in range(num_records):
        if random.random() < 0.4:
            question = random.choice(DEMO_QUESTIONS)
            repository.log_query(
                endpoint="/ask",
                input_text=question,
                output_summary="(demo) answer with citations",
                latency_ms=random.uniform(2000, 9000),
                status_code=200,
                source="demo",
            )
        else:
            description, severity, device_class, reportable, confidence = random.choice(
                DEMO_DESCRIPTIONS_AND_OUTCOMES
            )
            escalated = severity is None
            repository.log_query(
                endpoint="/report",
                input_text=description,
                output_summary=f"severity={severity}, reportable={reportable}",
                severity=severity,
                device_class=device_class,
                reportable=reportable,
                confidence=confidence,
                escalated=escalated,
                latency_ms=random.uniform(4000, 15000),
                status_code=200,
                source="demo",
            )

    logger.info("Seeded %d demo query-log rows into %s", num_records, settings.db_path_absolute)


if __name__ == "__main__":
    main()
