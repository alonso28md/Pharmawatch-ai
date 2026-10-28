"""GET /evaluations/latest — read the most recent stored evaluation result (never runs one)."""

import asyncio
import json
import re
from pathlib import Path

from fastapi import APIRouter, Query

from src.api.errors import ApiError
from src.api.schemas import EvaluationLatest
from src.config import get_settings

router = APIRouter()

# eval_<label>_<YYYYmmddTHHMMSSZ>[_rescored].json, as written by the reporter / rescore script.
_NAME = re.compile(r"^eval_(?P<label>[a-z0-9_-]+?)_(?P<ts>\d{8}T\d{6}Z)(?P<rescored>_rescored)?\.json$")


def _pick_latest(directory: Path, label: str | None) -> Path | None:
    candidates = []
    for path in directory.glob("eval_*.json"):
        match = _NAME.match(path.name)
        if match and (label is None or match["label"] == label):
            # Newest run first; for the same run prefer the re-scored file.
            candidates.append(((match["ts"], bool(match["rescored"])), path))
    return max(candidates)[1] if candidates else None


def _load(label: str | None) -> EvaluationLatest | None:
    directory = get_settings().artifacts_dir_absolute / "evaluations"
    path = _pick_latest(directory, label) if directory.is_dir() else None
    if path is None:
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    return EvaluationLatest(
        file=path.name,
        rescored=path.stem.endswith("_rescored"),
        timestamp=report.get("metadata", {}).get("timestamp") or report.get("timestamp"),
        metadata=report.get("metadata", {}),
        summary=report.get("summary", {}),
        metric_summary=report.get("metric_summary", {}),
        failed_cases=report.get("failed_cases", []),
    )


@router.get("/evaluations/latest", response_model=EvaluationLatest, tags=["evaluation"])
async def latest_evaluation(
    dataset: str | None = Query(None, pattern=r"^[a-z0-9_-]{1,40}$", description="Dataset label, e.g. v2"),
) -> EvaluationLatest:
    """Metrics of the latest stored evaluation run, with thresholds and min/max over repetitions.

    Read-only: it reads JSON files in ARTIFACTS_DIR/evaluations and never calls the model.
    Per-case results are not included.
    """
    result = await asyncio.to_thread(_load, dataset)
    if result is None:
        raise ApiError(404, "not_found", "No stored evaluation results")
    return result
