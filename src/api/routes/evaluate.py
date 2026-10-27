"""POST /evaluate — run the evaluation harness against a whitelisted golden dataset."""

import asyncio
import logging
import threading

from fastapi import APIRouter, Depends, Request

from src.api.deps import limiter, verify_api_key_strict
from src.api.errors import ApiError
from src.api.schemas import EvaluateRequest, EvaluateResponse, EvaluationSummary, FailedCase
from src.config import get_settings
from src.evaluation.harness import EvaluationHarness
from src.evaluation.reporter import write_json_report

logger = logging.getLogger(__name__)
router = APIRouter()

# One evaluation at a time per process: each run makes many paid model calls.
_evaluation_lock = threading.Lock()


def _run_evaluation(dataset_name: str, categories: list[str] | None):
    settings = get_settings()
    dataset_path = settings.evaluation_dataset_files[dataset_name]
    result = EvaluationHarness(dataset_path).run(categories)
    report_path = write_json_report(result, settings.artifacts_dir_absolute, dataset_name)
    return result, report_path


@router.post(
    "/evaluate",
    response_model=EvaluateResponse,
    tags=["evaluation"],
    dependencies=[Depends(verify_api_key_strict)],
)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def evaluate(request: Request, payload: EvaluateRequest) -> EvaluateResponse:
    """Run the golden-dataset evaluation harness (real model calls; takes minutes).

    Only dataset names from the EVALUATION_DATASETS whitelist are accepted. The
    error for an unknown name is the same whether or not a file by that name exists.
    Results are written as JSON to ARTIFACTS_DIR - never to docs/ or the query DB.
    """
    datasets = get_settings().evaluation_dataset_files
    if payload.dataset not in datasets or not datasets[payload.dataset].is_file():
        raise ApiError(422, "unknown_dataset", "Unknown dataset", {"allowed": sorted(datasets)})

    if not _evaluation_lock.acquire(blocking=False):
        raise ApiError(409, "evaluation_in_progress", "Another evaluation is already running")
    try:
        result, report_path = await asyncio.to_thread(
            _run_evaluation, payload.dataset, payload.categories
        )
    finally:
        _evaluation_lock.release()

    pass_rate = round(result.passed / result.total_cases, 4) if result.total_cases else None
    return EvaluateResponse(
        summary=EvaluationSummary(
            total_cases=result.total_cases, passed=result.passed, failed=result.failed, pass_rate=pass_rate
        ),
        metrics=result.metrics,
        failed_cases=[FailedCase(**fc) for fc in result.failed_cases],
        report_file=report_path.name,
        timestamp=report_path.stem.rsplit("_", 1)[-1],
    )
