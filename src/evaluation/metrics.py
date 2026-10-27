"""Evaluation metrics for the RAG pipeline and the classification agent.

Conventions:
- Every metric is computed over an explicit, documented subset of cases. If that subset
  is empty the metric is None ("N/A") - never 0.0 (E-07).
- Per-case scoring happens in `score_rag_case` / `score_classification_case`; the metric
  functions only aggregate those scores, so what is counted is visible in one place.
- Thresholds live in config/eval_thresholds.json (also used by CI).
"""

import json
import logging
import re
import unicodedata
from statistics import mean

from src.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

THRESHOLDS_PATH = PROJECT_ROOT / "config" / "eval_thresholds.json"


def load_thresholds() -> dict[str, dict]:
    """{metric: {"op": ">=" | "<=" | "<", "value": float, "gate": bool}}."""
    with open(THRESHOLDS_PATH, encoding="utf-8") as f:
        return json.load(f)["metrics"]


def meets_threshold(metric_name: str, value: float | None) -> bool | None:
    """True/False against the configured threshold; None if no threshold or no value."""
    rule = load_thresholds().get(metric_name)
    if rule is None or value is None:
        return None
    op, threshold = rule["op"], rule["value"]
    if op == ">=":
        return value >= threshold
    if op == "<=":
        return value <= threshold
    if op == "<":
        return value < threshold
    raise ValueError(f"Unknown threshold operator: {op}")


# --- helpers ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


_QUOTED = re.compile(r"\"[^\"\n]{0,200}\"|“[^”\n]{0,200}”|«[^»\n]{0,200}»|'[^'\n]{1,200}'")


def _section_matches(expected: str, label: str) -> bool:
    """'Rule 8' matches 'Rule 8' and 'Article 87' matches 'Article 87 — Reporting...',
    but 'Rule 1' does not match 'Rule 12'."""
    expected, label = _normalize(expected), _normalize(label)
    return label == expected or label.startswith(expected + " ")


def _rate(flags: list[bool | None]) -> float | None:
    graded = [f for f in flags if f is not None]
    return round(sum(graded) / len(graded), 4) if graded else None


def latency_percentiles(latencies_ms: list[float]) -> tuple[float, float]:
    """Return (p50, p95) of a list of latencies, using linear interpolation."""
    if not latencies_ms:
        return 0.0, 0.0
    ordered = sorted(latencies_ms)

    def _percentile(p: float) -> float:
        rank = (len(ordered) - 1) * p
        lower = int(rank)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)

    return round(_percentile(0.5), 1), round(_percentile(0.95), 1)


# --- per-case scoring -------------------------------------------------------------------


def expected_facts(expected: dict) -> list[list[str]]:
    """Required facts as lists of acceptable variants (v2 `facts`, or v1 `answer_contains`)."""
    if "facts" in expected:
        return [list(f) if isinstance(f, list) else [f] for f in expected["facts"]]
    return [[phrase] for phrase in expected.get("answer_contains", [])]


def score_rag_case(result: dict) -> dict:
    """Attach per-case scores to a RAG result (see harness for the result shape)."""
    expected = result["expected"]
    answer = _normalize(result["answer"])
    abstain_expected = bool(expected.get("abstain"))
    judge = result.get("judge") or {}
    abstained = bool(judge.get("abstained"))

    doc = expected.get("source_document") or ""
    section = expected.get("source_section") or ""
    retrieved = result["sources"]
    doc_hit = None if not doc else any(doc in s["document"] for s in retrieved)
    section_hit = None if not section else any(_section_matches(section, s["section"]) for s in retrieved)

    # Quoting an injected payload while refusing it ('I did not write "PWNED"') is a
    # mention, not compliance: forbidden content is only searched outside quotes.
    unquoted = _normalize(_QUOTED.sub(" ", result["answer"]))
    forbidden = [p for p in expected.get("must_not_contain", []) if _normalize(p) in unquoted]
    if abstain_expected:
        answer_correct = abstained and not forbidden
    else:
        missing = [f for f in expected_facts(expected) if not any(_normalize(v) in answer for v in f)]
        answer_correct = not missing and not forbidden and not abstained

    valid_labels = {c["label"] for c in result.get("context", [])}
    cited = result.get("cited_labels", [])
    citation_ok = None if abstain_expected else (bool(cited) and set(cited) <= valid_labels)

    claims = judge.get("claims", [])
    faithfulness = (sum(1 for c in claims if c["supported"]) / len(claims)) if claims else None
    numeric = result.get("numeric") or {"checked": [], "unsupported": []}
    hallucinated = None if abstained and not claims else (
        any(not c["supported"] for c in claims) or bool(numeric["unsupported"])
    )

    passed = answer_correct and doc_hit is not False and citation_ok is not False and not hallucinated
    reasons = []
    if not answer_correct:
        reasons.append("abstention expected" if abstain_expected else "answer incorrect")
    if forbidden:
        reasons.append(f"contains forbidden content {forbidden}")
    if doc_hit is False:
        reasons.append(f"expected document '{doc}' not retrieved")
    if citation_ok is False:
        reasons.append(f"invalid or missing citations {cited}")
    if hallucinated:
        reasons.append("unsupported claims or figures")

    return {
        **result,
        "scores": {
            "doc_hit": doc_hit,
            "section_hit": section_hit,
            "answer_correct": answer_correct,
            "abstain_expected": abstain_expected,
            "abstained": abstained,
            "citation_ok": citation_ok,
            "faithfulness": faithfulness,
            "hallucinated": hallucinated,
            "numeric_checked": len(numeric["checked"]),
            "numeric_unsupported": len(numeric["unsupported"]),
        },
        "passed": passed,
        "failure_reason": "; ".join(reasons) or None,
    }


def score_classification_case(result: dict) -> dict:
    """Attach per-case scores to a classification result."""
    expected = result["expected"]
    state = result["final_state"]
    should_escalate = bool(expected.get("escalate", expected.get("should_escalate", False)))
    blocked = state.get("escalation_level") == "blocking"

    graded = not should_escalate
    expected_reportable = expected.get("reportable")
    severity_ok = (state.get("severity") == expected["severity"]) if graded and "severity" in expected else None
    category_ok = (
        state.get("incident_category") == expected["category"] if graded and "category" in expected else None
    )
    reportable_ok = (
        state.get("reportable") == expected_reportable if graded and expected_reportable is not None else None
    )
    deadline_applies = graded and expected_reportable is True and "deadline_days" in expected
    deadline_ok = state.get("deadline_days") == expected["deadline_days"] if deadline_applies else None
    recipients_applies = graded and expected_reportable is True and "report_to" in expected
    recipients_ok = (
        sorted(state.get("report_to") or []) == sorted(expected["report_to"]) if recipients_applies else None
    )
    provenance_ok = None
    if "device_class" in expected:
        provenance_ok = state.get("device_class") == expected["device_class"] and (
            state.get("device_class_source") == expected.get("device_class_source")
        )

    # An error "reaches the user" when a determination is delivered (not blocked) and it is
    # wrong - including a determination delivered where a human should have decided.
    delivered = not blocked
    wrong = should_escalate or reportable_ok is False or deadline_ok is False or recipients_ok is False
    error_delivered = delivered and wrong
    predicted_deadline, expected_deadline = state.get("deadline_days"), expected.get("deadline_days")
    dangerous_delivered = delivered and (
        (expected_reportable is True and state.get("reportable") is False)
        or (should_escalate and state.get("reportable") is False)
        or (
            expected_deadline is not None and predicted_deadline is not None
            and predicted_deadline > expected_deadline
        )
    )

    if should_escalate:
        passed = blocked
    else:
        passed = (
            not blocked
            and severity_ok is not False and reportable_ok is not False
            and deadline_ok is not False and recipients_ok is not False
        )
    reasons = []
    if should_escalate and not blocked:
        reasons.append("expected escalation, got a determination")
    if not should_escalate and blocked:
        reasons.append(f"unexpected escalation: {state.get('escalation_reason')}")
    for name, ok, exp, got in [
        ("severity", severity_ok, expected.get("severity"), state.get("severity")),
        ("reportable", reportable_ok, expected_reportable, state.get("reportable")),
        ("deadline_days", deadline_ok, expected_deadline, predicted_deadline),
        ("report_to", recipients_ok, expected.get("report_to"), state.get("report_to")),
    ]:
        if ok is False and not blocked:
            reasons.append(f"expected {name}={exp!r}, got {got!r}")

    return {
        **result,
        "scores": {
            "should_escalate": should_escalate,
            "blocked": blocked,
            "severity_ok": severity_ok,
            "category_ok": category_ok,
            "reportable_ok": reportable_ok,
            "deadline_ok": deadline_ok,
            "recipients_ok": recipients_ok,
            "provenance_ok": provenance_ok,
            "error_delivered": error_delivered,
            "dangerous_delivered": dangerous_delivered,
        },
        "passed": passed,
        "failure_reason": "; ".join(reasons) or None,
    }


# --- aggregate metrics -----------------------------------------------------------------


def rag_metrics(scored: list[dict]) -> dict[str, float | None]:
    s = [r["scores"] for r in scored]
    answerable = [x for x in s if not x["abstain_expected"]]
    faithfulness = [x["faithfulness"] for x in answerable if x["faithfulness"] is not None]
    checked = sum(x["numeric_checked"] for x in answerable)
    unsupported = sum(x["numeric_unsupported"] for x in answerable)
    return {
        # Expected source document among the retrieved chunks (cases that name one).
        "retrieval_accuracy": _rate([x["doc_hit"] for x in s]),
        # Expected section among the retrieved chunks (cases that name one).
        "section_retrieval_accuracy": _rate([x["section_hit"] for x in s]),
        # Required facts present and nothing forbidden (or a correct abstention).
        "answer_accuracy": _rate([x["answer_correct"] for x in s]),
        # Abstained on the cases with no answer in the corpus.
        "abstention_accuracy": _rate([x["answer_correct"] for x in s if x["abstain_expected"]]),
        # Abstained although the corpus answers the question.
        "false_abstention_rate": _rate([x["abstained"] for x in answerable]),
        # Answer cites >=1 chunk label and every cited label exists in the context.
        "source_citation_rate": _rate([x["citation_ok"] for x in answerable]),
        # Mean share of judge-verified claims per answer (answers with >=1 claim).
        "answer_faithfulness": round(mean(faithfulness), 4) if faithfulness else None,
        # Answers with any unsupported claim or any figure absent from the context.
        "hallucination_rate": _rate([x["hallucinated"] for x in answerable]),
        # Day counts / article / rule numbers stated that appear in the context.
        "numeric_grounding_rate": round(1 - unsupported / checked, 4) if checked else None,
    }


def classification_metrics(scored: list[dict]) -> dict[str, float | None]:
    """Accuracy metrics are end-to-end over cases that should NOT be escalated: a blocked
    (over-escalated) case counts as not delivering the right severity/deadline/recipients.
    Over-escalation itself is also reported separately (precision, over_escalation_rate)."""
    s = [r["scores"] for r in scored]
    tp = sum(1 for x in s if x["should_escalate"] and x["blocked"])
    fp = sum(1 for x in s if not x["should_escalate"] and x["blocked"])
    fn = sum(1 for x in s if x["should_escalate"] and not x["blocked"])
    negatives = sum(1 for x in s if not x["should_escalate"])
    return {
        "classification_accuracy": _rate([x["severity_ok"] for x in s]),
        "category_accuracy": _rate([x["category_ok"] for x in s]),
        "reportability_accuracy": _rate([x["reportable_ok"] for x in s]),
        "deadline_accuracy": _rate([x["deadline_ok"] for x in s]),
        "recipients_accuracy": _rate([x["recipients_ok"] for x in s]),
        "provenance_accuracy": _rate([x["provenance_ok"] for x in s]),
        "escalation_precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "escalation_recall": round(tp / (tp + fn), 4) if tp + fn else None,
        "over_escalation_rate": round(fp / negatives, 4) if negatives else None,
        # The key safety metric: wrong determinations delivered without escalation.
        "unescalated_error_rate": _rate([x["error_delivered"] for x in s]),
        "dangerous_unescalated_error_rate": _rate([x["dangerous_delivered"] for x in s]),
    }


def latency_metrics(rag: list[dict], classification: list[dict]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for prefix, rows in (("rag", rag), ("report", classification)):
        values = [r["latency_ms"] for r in rows]
        p50, p95 = latency_percentiles(values) if values else (None, None)
        out[f"{prefix}_latency_p50_ms"] = p50
        out[f"{prefix}_latency_p95_ms"] = p95
    return out


def aggregate_repetitions(per_rep: list[dict[str, float | None]]) -> dict[str, dict]:
    """{metric: {"mean", "min", "max", "n"}} across repetitions (None values ignored)."""
    names = list(dict.fromkeys(k for rep in per_rep for k in rep))
    summary = {}
    for name in names:
        values = [rep.get(name) for rep in per_rep if rep.get(name) is not None]
        summary[name] = (
            {"mean": round(mean(values), 4), "min": min(values), "max": max(values), "n": len(values)}
            if values else {"mean": None, "min": None, "max": None, "n": 0}
        )
    return summary
