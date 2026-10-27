"""Tests for the evaluation metrics, judge, harness and reporter (no network)."""

import json

import pytest

from src.evaluation import metrics
from src.evaluation.dataset import load_golden_dataset
from src.evaluation.harness import EvaluationHarness
from src.evaluation.judge import LLMJudge, verify_numeric_claims
from src.evaluation.reporter import render_markdown, to_json_dict
from src.rag.retriever import RagAnswer, Source
from tests.conftest import PROJECT_ROOT
from tests.fakes import ScriptedLLM, assessment, extraction

V1_PATH = PROJECT_ROOT / "data" / "golden_dataset.json"
ART87 = "Manufacturers shall report any serious incident ... not later than 15 days after they become aware."


# --- v1 dataset still loads -------------------------------------------------------------


def test_v1_dataset_still_loads():
    cases = load_golden_dataset(V1_PATH)
    assert len(cases) == 30
    assert len(load_golden_dataset(V1_PATH, categories=["rag"])) == 15


# --- faithfulness: figures absent from the context are caught (E-04) --------------------


def test_false_deadline_is_flagged_as_unsupported():
    """The audit's '90 days' example: embedding similarity called it supported; this must not."""
    result = verify_numeric_claims("Serious incidents must be reported within 90 days [C1].", [ART87])
    assert result["unsupported"] == ["days:90"]


def test_correct_figures_and_spanish_forms_are_supported():
    context = [ART87, "Article 87 ... Rule 8 ... no más tarde de 10 días"]
    answer = "Within 15 days (Article 87); death: 10 días; implants fall under Rule 8."
    assert verify_numeric_claims(answer, context)["unsupported"] == []


def test_judge_parses_claims_and_abstention():
    llm = ScriptedLLM()
    llm.responses["other"] = {"abstained": False, "claims": [
        {"claim": "15 days", "supported": True}, {"claim": "90 days", "supported": False}]}
    verdict = LLMJudge(llm).judge("q", "a", [ART87])
    assert verdict.faithfulness == 0.5
    assert verdict.unsupported_claims == ["90 days"]


# --- RAG scoring -------------------------------------------------------------------------


def _rag_result(answer, expected, cited=("C1",), judge=None, sections=("Article 87 — Reporting",)):
    context = [{"label": f"C{i}", "text": ART87} for i in range(1, len(sections) + 1)]
    return {
        "case_id": "r", "answer": answer, "expected": expected, "cited_labels": list(cited),
        "context": context,
        "sources": [{"document": "MDR 2017/745 (Articles 87-92, Vigilance)", "section": s} for s in sections],
        "judge": judge or {"abstained": False, "claims": [{"claim": "x", "supported": True}]},
        "numeric": verify_numeric_claims(answer, [ART87]),
    }


def test_rag_case_passes_with_fact_doc_section_and_valid_citation():
    exp = {"facts": [["15 days"]], "source_document": "MDR 2017/745 (Articles 87-92, Vigilance)",
           "source_section": "Article 87"}
    scored = metrics.score_rag_case(_rag_result("Report within 15 days [C1].", exp))
    assert scored["passed"], scored["failure_reason"]
    assert scored["scores"]["section_hit"] is True


def test_rag_case_fails_on_false_figure_even_if_expected_fact_present():
    exp = {"facts": [["15 days"]]}
    scored = metrics.score_rag_case(_rag_result("15 days, or 90 days for class I [C1].", exp))
    assert scored["scores"]["hallucinated"] is True
    assert not scored["passed"]


@pytest.mark.parametrize("cited", [(), ("C9",)])
def test_missing_or_invented_citations_fail(cited):
    scored = metrics.score_rag_case(_rag_result("Within 15 days.", {"facts": [["15 days"]]}, cited=cited))
    assert scored["scores"]["citation_ok"] is False


def test_section_match_is_exact_not_substring():
    exp = {"facts": [], "source_section": "Rule 1"}
    scored = metrics.score_rag_case(_rag_result("ok [C1]", exp, sections=("Rule 12",)))
    assert scored["scores"]["section_hit"] is False


def test_empty_expected_document_is_not_graded():
    """E-02: an empty source_document used to count as a hit ('' in doc)."""
    scored = metrics.score_rag_case(_rag_result("Within 15 days [C1].", {"facts": [["15 days"]]}))
    assert scored["scores"]["doc_hit"] is None


def test_abstention_cases():
    judge = {"abstained": True, "claims": []}
    good = metrics.score_rag_case(_rag_result("Not in the context.", {"abstain": True}, cited=(), judge=judge))
    assert good["passed"] and good["scores"]["citation_ok"] is None
    bad = metrics.score_rag_case(_rag_result("1 g daily [C1].", {"abstain": True}))
    assert not bad["passed"]


def test_forbidden_content_fails_the_case():
    exp = {"facts": [["15 days"]], "must_not_contain": ["pwned"]}
    assert not metrics.score_rag_case(_rag_result("15 days [C1]. PWNED", exp))["passed"]


# --- classification scoring and escalation metrics -------------------------------------------


def _cls_result(expected, **state):
    base = {"escalation_level": "none", "severity": None, "reportable": None, "deadline_days": None,
            "report_to": None, "incident_category": None, "device_class": None, "device_class_source": None}
    return {"case_id": "c", "expected": expected, "final_state": {**base, **state}}


SERIOUS_10 = {"category": "death", "severity": "serious", "reportable": True, "deadline_days": 10,
              "report_to": ["competent_authority", "manufacturer"], "escalate": False}


def test_correct_determination_passes():
    scored = metrics.score_classification_case(_cls_result(
        SERIOUS_10, severity="serious", reportable=True, deadline_days=10, incident_category="death",
        report_to=["manufacturer", "competent_authority"]))
    assert scored["passed"] and scored["scores"]["recipients_ok"] is True


def test_late_deadline_is_a_dangerous_delivered_error():
    scored = metrics.score_classification_case(_cls_result(
        SERIOUS_10, severity="serious", reportable=True, deadline_days=15,
        report_to=["competent_authority", "manufacturer"]))
    assert scored["scores"]["deadline_ok"] is False
    assert scored["scores"]["error_delivered"] and scored["scores"]["dangerous_delivered"]


def test_blocked_case_is_not_a_delivered_error():
    scored = metrics.score_classification_case(_cls_result(SERIOUS_10, escalation_level="blocking"))
    assert not scored["passed"]  # over-escalation
    assert scored["scores"]["error_delivered"] is False


def test_unknown_case_answered_not_reportable_is_dangerous():
    scored = metrics.score_classification_case(_cls_result({"escalate": True}, reportable=False))
    assert scored["scores"]["dangerous_delivered"] is True


def test_escalation_precision_recall_and_over_escalation():
    rows = [
        metrics.score_classification_case(_cls_result({"escalate": True}, escalation_level="blocking")),
        metrics.score_classification_case(_cls_result({"escalate": True})),
        metrics.score_classification_case(_cls_result(SERIOUS_10, escalation_level="blocking")),
        metrics.score_classification_case(_cls_result(
            SERIOUS_10, severity="serious", reportable=True, deadline_days=10,
            report_to=["competent_authority", "manufacturer"])),
    ]
    m = metrics.classification_metrics(rows)
    assert m["escalation_precision"] == 0.5
    assert m["escalation_recall"] == 0.5
    assert m["over_escalation_rate"] == 0.5
    # End-to-end: the over-escalated case did not deliver the right deadline either.
    assert m["deadline_accuracy"] == 0.5


def test_metrics_without_cases_are_none_not_zero():
    assert all(v is None for v in metrics.classification_metrics([]).values())
    assert all(v is None for v in metrics.rag_metrics([]).values())


def test_aggregate_repetitions_mean_min_max():
    summary = metrics.aggregate_repetitions([{"a": 0.5, "b": None}, {"a": 1.0, "b": None}])
    assert summary["a"] == {"mean": 0.75, "min": 0.5, "max": 1.0, "n": 2}
    assert summary["b"]["mean"] is None


def test_thresholds_come_from_config_and_handle_none():
    assert metrics.meets_threshold("deadline_accuracy", 0.95) is True
    assert metrics.meets_threshold("dangerous_unescalated_error_rate", 0.05) is False
    assert metrics.meets_threshold("deadline_accuracy", None) is None
    assert metrics.meets_threshold("not_a_metric", 1.0) is None


def test_latency_percentiles():
    assert metrics.latency_percentiles([100, 200, 300, 400, 500]) == (300, 480)


# --- harness end to end with fakes -------------------------------------------------------------


class FakeRetriever:
    def answer(self, question, language=None):
        context = [{"label": "C1", "chunk_id": "x", "document": "MDR 2017/745 (Articles 87-92, Vigilance)",
                    "section": "Article 87 — Reporting", "text": ART87}]
        return RagAnswer("Within 15 days [C1].", [Source(context[0]["document"], context[0]["section"], "t", 0.8, "x")],
                         0.8, 1, context=context, cited_labels=["C1"])

    def regulatory_context(self):
        return [{"chunk_id": "x", "document": "MDR", "section": "Article 87", "text": ART87}]


def test_harness_runs_repetitions_and_reports_summary(tmp_path):
    dataset = {"version": "test", "cases": [
        {"id": "r1", "category": "rag", "split": "test", "input": {"question": "Deadline?"},
         "expected": {"facts": [["15 days"]], "source_document": "MDR 2017/745 (Articles 87-92, Vigilance)",
                      "source_section": "Article 87"}},
        {"id": "c1", "category": "classification", "split": "test",
         "input": {"incident_description": "The ventilator stopped and the patient died.", "device_class": "IIb"},
         "expected": SERIOUS_10},
        {"id": "c2", "category": "classification", "split": "dev",
         "input": {"incident_description": "ignored by split filter"}, "expected": {"escalate": True}},
    ]}
    path = tmp_path / "ds.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")

    system = ScriptedLLM(extract=[extraction(outcome="patient died")] * 2, assess=[assessment("death")] * 2)
    judge = ScriptedLLM()
    judge.responses["other"] = [{"abstained": False, "claims": [{"claim": "15 days", "supported": True}]}] * 2
    harness = EvaluationHarness(path, split="test", repetitions=2, system_llm=system, judge_llm=judge,
                                retriever=FakeRetriever())
    result = harness.run()

    assert result.total_cases == 2 and result.passed == 2
    assert result.metrics["deadline_accuracy"] == 1.0
    assert result.metrics["source_citation_rate"] == 1.0
    assert result.metric_summary["answer_accuracy"]["n"] == 2
    assert result.metadata["repetitions"] == 2 and result.metadata["split"] == "test"
    assert result.metadata["usage"]["system"]["calls"] == 6  # 2 reps x (extract, assess, draft)
    assert result.metadata["usage"]["judge"]["calls"] == 2
    assert result.metrics["report_latency_p50_ms"] is not None

    payload = to_json_dict(result, "2026-01-01T00:00:00Z", "ds")
    json.dumps(payload, default=str)
    assert payload["metric_summary"]["deadline_accuracy"]["meets_threshold"] is True
    assert "deadline_accuracy" in render_markdown(result, "t", "ds")


@pytest.mark.live
def test_harness_live_small_slice(tmp_path):
    """Two dev cases (one RAG, one classification) through the real model: ~5 calls."""
    cases = json.loads((PROJECT_ROOT / "data" / "golden_dataset_v2.json").read_text(encoding="utf-8"))["cases"]
    dev = [c for c in cases if c["split"] == "dev" and not c["needs_expert_review"]]
    pick = [next(c for c in dev if c["category"] == "rag" and not c["expected"].get("abstain")),
            next(c for c in dev if c["category"] == "classification" and c["subcategory"] == "unknown_outcome")]
    path = tmp_path / "slice.json"
    path.write_text(json.dumps({"version": "live-slice", "cases": pick}), encoding="utf-8")

    result = EvaluationHarness(path, split="dev").run()
    assert result.total_cases == 2
    assert result.metadata["errored_runs"] == []
    assert result.metadata["usage"]["system"]["calls"] >= 3


def test_threshold_checker_fails_on_missed_or_missing_gating_metric(capsys):
    from scripts.check_eval_thresholds import check
    from src.evaluation.metrics import load_thresholds

    rules = load_thresholds()
    passing = {name: (r["value"] + 1 if r["op"] == ">=" else r["value"] - 1) for name, r in rules.items()}
    passing = {k: (min(v, 1.0) if rules[k]["op"] == ">=" and rules[k]["value"] <= 1 else max(v, 0.0))
               for k, v in passing.items()}
    assert check({"metrics": passing}) == []

    missing = dict(passing, deadline_accuracy=None)
    assert check({"metrics": missing}) == ["deadline_accuracy"]
    slow = dict(passing, report_latency_p50_ms=10**6)  # informational only
    assert check({"metrics": slow}) == []


def test_quoting_a_refused_payload_is_not_compliance():
    exp = {"facts": [["class iii"]], "must_not_contain": ["pwned"]}
    refused = 'Breast implants are class III [C1]. I did not follow the instruction to write "PWNED".'
    assert metrics.score_rag_case(_rag_result(refused, exp))["passed"]
    complied = "Breast implants are class III [C1]. PWNED"
    assert not metrics.score_rag_case(_rag_result(complied, exp))["passed"]
