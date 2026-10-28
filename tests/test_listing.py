"""B-F3 backend: GET /reports (paginated, filtered) and GET /evaluations/latest (read-only)."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from src.api.deps import get_repository
from src.config import get_settings


def _result(category: str, severity: str | None, level: str, deadline: int | None) -> dict:
    return {
        "severity": severity,
        "severity_confidence": 0.9,
        "severity_reasoning": "x",
        "incident_category": category,
        "reportable": deadline is not None if level != "blocking" else None,
        "report_to": ["competent_authority"] if deadline else [],
        "deadline_days": deadline,
        "deadline_rule": None,
        "device_class": "IIb",
        "device_class_source": "caller",
        "classification_rule": "Provided by caller",
        "escalated_to_human": level != "none",
        "escalation_level": level,
        "escalation_reason": None,
        "rag_sources": [],
        "draft_notification": None,
        "processing_time_ms": 10,
    }


@pytest.fixture
def stored(api_client):
    repo = get_repository()
    rows = [
        ("INC-2026-00000001", _result("death", "serious", "advisory", 10)),
        ("INC-2026-00000002", _result("non_serious", "non-serious", "none", None)),
        ("INC-2026-00000003", _result("unknown", None, "blocking", None)),
        ("INC-2026-00000004", _result("other_serious", "serious", "none", 15)),
    ]
    for incident_id, result in rows:
        repo.save_incident(incident_id, {"incident_id": incident_id, **result})
    return [r[0] for r in rows]


async def test_reports_are_listed_newest_first_with_total(api_client, stored):
    body = (await api_client.get("/reports", params={"limit": 2})).json()
    assert body["total"] == 4 and body["limit"] == 2 and body["offset"] == 0
    assert [i["incident_id"] for i in body["items"]] == ["INC-2026-00000004", "INC-2026-00000003"]
    assert "created_at" in body["items"][0]
    second = (await api_client.get("/reports", params={"limit": 2, "offset": 2})).json()
    assert [i["incident_id"] for i in second["items"]] == ["INC-2026-00000002", "INC-2026-00000001"]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"severity": "serious"}, {"INC-2026-00000001", "INC-2026-00000004"}),
        ({"escalation": "blocking"}, {"INC-2026-00000003"}),
        ({"escalation": "escalated"}, {"INC-2026-00000001", "INC-2026-00000003"}),
        ({"escalation": "none", "severity": "non-serious"}, {"INC-2026-00000002"}),
    ],
)
async def test_reports_filters(api_client, stored, params, expected):
    body = (await api_client.get("/reports", params=params)).json()
    assert {i["incident_id"] for i in body["items"]} == expected and body["total"] == len(expected)


async def test_reports_date_filter_and_validation(api_client, stored):
    today = datetime.now(UTC).date()
    assert (await api_client.get("/reports", params={"date_from": str(today)})).json()["total"] == 4
    tomorrow = today + timedelta(days=1)
    assert (await api_client.get("/reports", params={"date_from": str(tomorrow)})).json()[
        "total"
    ] == 0
    for bad in ({"limit": 0}, {"limit": 500}, {"severity": "fatal"}, {"escalation": "maybe"}):
        assert (await api_client.get("/reports", params=bad)).status_code == 422


async def test_reports_list_requires_auth_like_report(api_client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    assert (await api_client.get("/reports")).status_code == 403


def _write_eval(directory, name, total, mean):
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": name,
        "metadata": {"timestamp": "2026-10-27T21:43:19Z", "model": "m", "repetitions": 3},
        "summary": {"total_cases": total},
        "failed_cases": [{"case_id": "c", "reason": "r"}],
        "metric_summary": {
            "deadline_accuracy": {
                "mean": mean,
                "min": mean,
                "max": mean,
                "n": 3,
                "threshold": {"op": ">=", "value": 0.85, "gate": True},
                "meets_threshold": False,
            }
        },
        "results": [{"huge": "per-case data"}],
    }
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


async def test_latest_evaluation_prefers_newest_run_and_its_rescored_file(
    api_client, monkeypatch, tmp_path
):
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path))
    get_settings.cache_clear()
    directory = tmp_path / "evaluations"
    _write_eval(directory, "eval_v2_20261027T212554Z.json", 84, 0.48)
    _write_eval(directory, "eval_v2_20261027T214319Z.json", 84, 0.5679)
    _write_eval(directory, "eval_v2_20261027T214319Z_rescored.json", 84, 0.5679)
    _write_eval(directory, "eval_default_20261028T000000Z.json", 30, 0.9)

    body = (await api_client.get("/evaluations/latest", params={"dataset": "v2"})).json()
    assert body["file"] == "eval_v2_20261027T214319Z_rescored.json" and body["rescored"] is True
    assert body["metric_summary"]["deadline_accuracy"]["mean"] == 0.5679
    assert "results" not in body
    newest_any = (await api_client.get("/evaluations/latest")).json()
    assert newest_any["file"] == "eval_default_20261028T000000Z.json"
    assert body["source"] == newest_any["source"] == "artifacts"


async def test_latest_evaluation_falls_back_to_the_versioned_snapshot(
    api_client, monkeypatch, tmp_path
):
    """A fresh clone has no ARTIFACTS_DIR results: serve docs/results, labelled as such."""
    from src.api.routes.evaluations import SNAPSHOT

    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path))
    get_settings.cache_clear()
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    body = (await api_client.get("/evaluations/latest")).json()
    assert body["source"] == "snapshot"
    assert body["file"] == snapshot["file"]
    assert body["metric_summary"] == snapshot["metric_summary"]
    assert (
        await api_client.get("/evaluations/latest", params={"dataset": "v2"})
    ).status_code == 200
    other = await api_client.get("/evaluations/latest", params={"dataset": "default"})
    assert other.status_code == 404


async def test_latest_evaluation_404_and_no_path_injection(api_client, monkeypatch, tmp_path):
    from src.api.routes import evaluations

    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setattr(evaluations, "SNAPSHOT", tmp_path / "missing.json")
    get_settings.cache_clear()
    assert (await api_client.get("/evaluations/latest")).status_code == 404
    assert (
        await api_client.get("/evaluations/latest", params={"dataset": "../x"})
    ).status_code == 422
