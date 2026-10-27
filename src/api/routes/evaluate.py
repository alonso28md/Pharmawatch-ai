"""POST /evaluate — run the evaluation harness against the golden dataset."""

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from src.api.deps import limiter, verify_api_key
from src.api.schemas import EvaluateRequest, EvaluateResponse, EvaluationSummary, FailedCase
from src.config import PROJECT_ROOT, get_settings
from src.evaluation.harness import EvaluationHarness
from src.evaluation.reporter import write_reports

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/evaluate", response_model=EvaluateResponse, tags=["evaluation"], dependencies=[Depends(verify_api_key)]
)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def evaluate(request: Request, payload: EvaluateRequest) -> EvaluateResponse:
    """Run the golden-dataset evaluation harness and write fresh reports.

    This makes real Claude API calls for every case in the dataset and can take
    several minutes; it is not meant to be called at high frequency.
    """
    dataset_path = (
        PROJECT_ROOT / "data" / "golden_dataset.json"
        if payload.dataset == "default"
        else Path(payload.dataset)
    )

    harness = EvaluationHarness(dataset_path)
    result = await asyncio.to_thread(harness.run, payload.categories)

    docs_dir = PROJECT_ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_path = docs_dir / "evaluation_report.md"
    json_path = docs_dir / "evaluation_report.json"
    write_reports(result, report_path, json_path, dataset_label=dataset_path.name)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    pass_rate = round(result.passed / result.total_cases, 4) if result.total_cases else 0.0

    return EvaluateResponse(
        summary=EvaluationSummary(
            total_cases=result.total_cases, passed=result.passed, failed=result.failed, pass_rate=pass_rate
        ),
        metrics=result.metrics,
        failed_cases=[FailedCase(**fc) for fc in result.failed_cases],
        report_path=str(report_path.relative_to(PROJECT_ROOT)),
        timestamp=timestamp,
    )
