"""Phase 1: cost/exposure containment - auth modes, /evaluate whitelist, single job, no docs/ writes."""

import asyncio
import json
import threading

import pytest

from src.api.deps import limiter
from src.config import PROJECT_ROOT, get_settings
from src.evaluation.harness import EvaluationRunResult
from src.rag.retriever import RagAnswer, Source

KEY = "s3cret-test-key"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def _stub_retriever(monkeypatch):
    class Stub:
        def answer(self, question, **kwargs):
            return RagAnswer("ok", [Source("D", "S", "t", 0.9)], 0.9, 1)

    monkeypatch.setattr("src.api.routes.ask.get_retriever", lambda: Stub())


def _configure(monkeypatch, api_key: str = "", demo: bool = False) -> None:
    monkeypatch.setenv("API_KEY", api_key)
    monkeypatch.setenv("DEMO_MODE", "true" if demo else "false")
    get_settings.cache_clear()


class _FakeHarness:
    """Stands in for EvaluationHarness: no model calls; optionally blocks until released."""

    release: threading.Event | None = None
    started: threading.Event | None = None

    def __init__(self, dataset_path):
        self.dataset_path = dataset_path

    def run(self, categories=None):
        if self.started:
            self.started.set()
        if self.release:
            self.release.wait(timeout=10)
        return EvaluationRunResult(
            total_cases=1,
            passed=1,
            failed=0,
            metrics={"retrieval_accuracy": 1.0},
            failed_cases=[],
            model="stub",
        )


@pytest.fixture
def fake_harness(monkeypatch):
    _FakeHarness.release = None
    _FakeHarness.started = None
    monkeypatch.setattr("src.api.routes.evaluate.EvaluationHarness", _FakeHarness)
    return _FakeHarness


ASK = {"question": "What is the reporting deadline?"}


# --- auth modes --------------------------------------------------------------------


async def test_ask_disabled_without_api_key_or_demo_mode(api_client, monkeypatch):
    _configure(monkeypatch)
    response = await api_client.post("/ask", json=ASK)
    assert response.status_code == 403
    assert response.json()["code"] == "endpoint_disabled"


async def test_report_disabled_without_api_key_or_demo_mode(api_client, monkeypatch):
    _configure(monkeypatch)
    response = await api_client.post("/report", json={"description": "x" * 30})
    assert response.status_code == 403


async def test_ask_open_in_explicit_demo_mode(api_client, monkeypatch):
    _configure(monkeypatch, demo=True)
    response = await api_client.post("/ask", json=ASK)
    assert response.status_code == 200


@pytest.mark.parametrize("header", [None, "wrong-key", ""])
async def test_ask_requires_matching_key_when_configured(api_client, monkeypatch, header):
    _configure(monkeypatch, api_key=KEY, demo=True)  # demo mode never bypasses a configured key
    headers = {} if header is None else {"X-API-Key": header}
    response = await api_client.post("/ask", json=ASK, headers=headers)
    assert response.status_code == 401
    assert response.json() == {
        "code": "unauthorized",
        "message": "Invalid or missing API key",
        "details": None,
    }


async def test_ask_accepts_matching_key(api_client, monkeypatch):
    _configure(monkeypatch, api_key=KEY)
    response = await api_client.post("/ask", json=ASK, headers={"X-API-Key": KEY})
    assert response.status_code == 200


async def test_evaluate_disabled_even_in_demo_mode_without_api_key(
    api_client, monkeypatch, fake_harness
):
    _configure(monkeypatch, demo=True)
    response = await api_client.post("/evaluate", json={"dataset": "default"})
    assert response.status_code == 403


async def test_evaluate_rejects_missing_key(api_client, monkeypatch, fake_harness):
    _configure(monkeypatch, api_key=KEY)
    response = await api_client.post("/evaluate", json={"dataset": "default"})
    assert response.status_code == 401


# --- /evaluate dataset whitelist -----------------------------------------------------


@pytest.mark.parametrize(
    "dataset",
    ["../data/golden_dataset.json", "C:/Windows/win.ini", "/etc/passwd", "golden_dataset.json"],
)
async def test_evaluate_rejects_paths_as_validation_error(
    api_client, monkeypatch, fake_harness, dataset
):
    _configure(monkeypatch, api_key=KEY)
    response = await api_client.post(
        "/evaluate", json={"dataset": dataset}, headers={"X-API-Key": KEY}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_unknown_dataset_names_get_identical_errors(api_client, monkeypatch, fake_harness):
    """Whether or not a file with that name exists under data/, the answer is the same."""
    _configure(monkeypatch, api_key=KEY)
    headers = {"X-API-Key": KEY}
    existing = await api_client.post(
        "/evaluate", json={"dataset": "classification_rules"}, headers=headers
    )
    missing = await api_client.post(
        "/evaluate", json={"dataset": "does-not-exist"}, headers=headers
    )
    assert existing.status_code == missing.status_code == 422
    assert existing.json() == missing.json()


async def test_evaluate_writes_json_to_artifacts_not_docs(
    api_client, monkeypatch, fake_harness, tmp_path
):
    _configure(monkeypatch, api_key=KEY)
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    docs_before = {p: p.read_bytes() for p in (PROJECT_ROOT / "docs").rglob("*") if p.is_file()}

    response = await api_client.post(
        "/evaluate", json={"dataset": "default"}, headers={"X-API-Key": KEY}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    written = tmp_path / "artifacts" / "evaluations" / body["report_file"]
    assert written.is_file()
    assert json.loads(written.read_text(encoding="utf-8"))["summary"]["total_cases"] == 1
    assert {
        p: p.read_bytes() for p in (PROJECT_ROOT / "docs").rglob("*") if p.is_file()
    } == docs_before


async def test_evaluate_does_not_log_evaluation_runs_to_query_db(
    api_client, monkeypatch, fake_harness
):
    from src.api.deps import get_repository

    _configure(monkeypatch, api_key=KEY)
    await api_client.post("/evaluate", json={"dataset": "default"}, headers={"X-API-Key": KEY})
    assert get_repository().list_evaluation_runs() == []


async def test_second_concurrent_evaluation_gets_409(api_client, monkeypatch, fake_harness):
    _configure(monkeypatch, api_key=KEY)
    fake_harness.release = threading.Event()
    fake_harness.started = threading.Event()
    headers = {"X-API-Key": KEY}

    first = asyncio.create_task(
        api_client.post("/evaluate", json={"dataset": "default"}, headers=headers)
    )
    await asyncio.to_thread(fake_harness.started.wait, 5)
    second = await api_client.post("/evaluate", json={"dataset": "default"}, headers=headers)
    fake_harness.release.set()
    first_response = await first

    assert second.status_code == 409
    assert second.json()["code"] == "evaluation_in_progress"
    assert first_response.status_code == 200

    # The lock is released afterwards: a new run is accepted again.
    fake_harness.release = None
    third = await api_client.post("/evaluate", json={"dataset": "default"}, headers=headers)
    assert third.status_code == 200


# --- uniform error envelope ------------------------------------------------------------


async def test_validation_errors_use_the_uniform_envelope(api_client):
    response = await api_client.post("/ask", json={"question": "short"})
    body = response.json()
    assert response.status_code == 422
    assert set(body) == {"code", "message", "details"}
    assert body["code"] == "validation_error"
    assert all("input" not in d for d in body["details"])
