"""The documentation checker passes on the repository and catches a wrong figure."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_docs", ROOT / "scripts" / "check_docs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.errors.clear()
    return module


def test_display_rounding_is_half_up_on_decimals():
    checker = _load_checker()
    assert checker._expected(0.5185, latency=False) == 51.9  # float rounding would give 51.8
    assert checker._expected(7996.6667, latency=True) == 8.0
    assert checker._expected(None, latency=False) is None


def test_repository_docs_match_the_stored_results():
    checker = _load_checker()
    import json

    fixture = json.loads(checker.FIXTURE.read_text(encoding="utf-8"))
    assert checker.check_metric_tables(fixture["metric_summary"]) > 0
    checker.check_facts(fixture)
    checker.check_links_and_commands()
    checker.check_secrets_and_paths()
    checker.check_claims()
    assert checker.errors == []


def test_a_wrong_figure_or_claim_is_reported(tmp_path, monkeypatch):
    checker = _load_checker()
    doc = tmp_path / "doc.md"
    doc.write_text(
        "| `deadline_accuracy` | 85.0 % | 51.9 % – 59.3 % | ≥ 85 % | ✅ |\n"
        "This system is production-ready.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(checker, "DOCS", [doc])
    monkeypatch.setattr(checker, "rel", lambda p: p.name)
    import json

    fixture = json.loads(checker.FIXTURE.read_text(encoding="utf-8"))
    checker.check_metric_tables(fixture["metric_summary"])
    checker.check_claims()
    joined = "\n".join(checker.errors)
    assert "mean 85.0" in joined
    assert "misses the threshold" in joined
    assert "production" in joined
