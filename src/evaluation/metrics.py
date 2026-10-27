"""Evaluation metrics for the RAG pipeline and the classification agent.

Thresholds mirror the project spec's metric table.
"""

import logging
import re

logger = logging.getLogger(__name__)

HALLUCINATION_FAITHFULNESS_CUTOFF = 0.5
# Calibrated empirically (see docs/evaluation_report.md Notes): all-MiniLM-L6-v2
# cosine similarity between a short paraphrased claim and a long regulatory
# paragraph runs much lower than for same-domain-length text pairs. A manually
# verified, directly-grounded claim ("no later than 15 days...") scored 0.53
# against its exact source paragraph, a wrong-fact claim ("45 days") scored 0.44,
# and an unrelated claim scored ~0.0. 0.7 (a threshold more appropriate for
# comparing same-length passages) scored every real answer as unsupported,
# which inspection showed to be false - the answers were directly quoting
# correct figures and article numbers from the retrieved context.
CLAIM_SUPPORT_SIMILARITY_THRESHOLD = 0.4

METRIC_THRESHOLDS: dict[str, tuple[str, float]] = {
    "retrieval_accuracy": (">=", 0.85),
    "answer_faithfulness": (">=", 0.90),
    "hallucination_rate": ("<=", 0.10),
    "classification_accuracy": (">=", 0.80),
    "reportability_accuracy": (">=", 0.85),
    "escalation_appropriateness": (">=", 0.75),
    "latency_p50_ms": ("<", 5000),
    "latency_p95_ms": ("<", 15000),
    "source_citation_rate": (">=", 0.95),
}


def meets_threshold(metric_name: str, value: float) -> bool:
    """Check whether `value` satisfies the spec's threshold for `metric_name`."""
    if metric_name not in METRIC_THRESHOLDS:
        return True
    operator, threshold = METRIC_THRESHOLDS[metric_name]
    if operator == ">=":
        return value >= threshold
    if operator == "<=":
        return value <= threshold
    if operator == "<":
        return value < threshold
    raise ValueError(f"Unknown threshold operator: {operator}")


def retrieval_accuracy(rag_results: list[dict]) -> float:
    """% of RAG cases where the expected source document is among the retrieved chunks."""
    if not rag_results:
        return 0.0
    hits = 0
    for result in rag_results:
        expected_doc = result["expected"].get("source_document", "")
        retrieved_docs = [source["document"] for source in result["sources"]]
        if expected_doc and any(expected_doc in doc or doc in expected_doc for doc in retrieved_docs):
            hits += 1
    return round(hits / len(rag_results), 4)


_MARKDOWN_NOISE_PATTERN = re.compile(r"^[\s|\-:]+$")


def _split_into_claims(text: str) -> list[str]:
    """Split an answer into claim-like fragments, tolerant of Markdown formatting."""
    # Normalize Markdown table rows into plain text and drop separator/rule lines
    # (e.g. "|---|---|") before sentence-splitting, so a table cell isn't scored
    # as its own disconnected "claim".
    lines = []
    for line in text.split("\n"):
        if _MARKDOWN_NOISE_PATTERN.match(line):
            continue
        cleaned = line.replace("|", " ").replace("**", "").replace("*", "")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            lines.append(cleaned)
    normalized = " ".join(lines)

    sentences = re.split(r"(?<=[.!?])\s+", normalized.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 8]


def answer_faithfulness_and_hallucination(rag_results: list[dict]) -> tuple[float, float]:
    """Embedding-based faithfulness: % of answer claims supported by retrieved chunks.

    hallucination_rate is the complementary per-answer rate: the fraction of answers
    whose faithfulness falls below HALLUCINATION_FAITHFULNESS_CUTOFF.
    """
    from src.rag.embeddings import cosine_similarity, embed_texts

    per_answer_faithfulness = []
    hallucinated_count = 0

    for result in rag_results:
        claims = _split_into_claims(result["answer"])
        context_texts = [source["text"] for source in result["sources"] if source["text"]]
        if not claims or not context_texts:
            continue

        claim_vectors = embed_texts(claims)
        context_vectors = embed_texts(context_texts)

        supported = 0
        for claim_vector in claim_vectors:
            max_similarity = max(
                cosine_similarity(claim_vector, context_vector) for context_vector in context_vectors
            )
            if max_similarity >= CLAIM_SUPPORT_SIMILARITY_THRESHOLD:
                supported += 1

        faithfulness = supported / len(claims)
        per_answer_faithfulness.append(faithfulness)
        if faithfulness < HALLUCINATION_FAITHFULNESS_CUTOFF:
            hallucinated_count += 1

    if not per_answer_faithfulness:
        return 0.0, 0.0

    avg_faithfulness = sum(per_answer_faithfulness) / len(per_answer_faithfulness)
    hallucination_rate = hallucinated_count / len(per_answer_faithfulness)
    return round(avg_faithfulness, 4), round(hallucination_rate, 4)


def source_citation_rate(rag_results: list[dict]) -> float:
    """% of RAG answers that include at least one verifiable citation."""
    if not rag_results:
        return 0.0
    cited = sum(1 for result in rag_results if result["sources"])
    return round(cited / len(rag_results), 4)


def classification_accuracy(classification_results: list[dict]) -> float:
    """% of graded classification cases where predicted severity == expected severity."""
    graded = [r for r in classification_results if "severity" in r["expected"]]
    if not graded:
        return 0.0
    correct = sum(1 for r in graded if r["predicted_severity"] == r["expected"]["severity"])
    return round(correct / len(graded), 4)


def reportability_accuracy(classification_results: list[dict]) -> float:
    """% of graded classification cases where predicted reportable == expected reportable."""
    graded = [r for r in classification_results if "reportable" in r["expected"]]
    if not graded:
        return 0.0
    correct = sum(1 for r in graded if r["predicted_reportable"] == r["expected"]["reportable"])
    return round(correct / len(graded), 4)


def escalation_appropriateness(classification_results: list[dict]) -> float:
    """% of ambiguous cases (expected.should_escalate) that the agent correctly escalated."""
    ambiguous = [r for r in classification_results if r["expected"].get("should_escalate") is True]
    if not ambiguous:
        return 0.0
    correct = sum(1 for r in ambiguous if r["escalated_to_human"] is True)
    return round(correct / len(ambiguous), 4)


def latency_percentiles(latencies_ms: list[float]) -> tuple[float, float]:
    """Return (p50, p95) of a list of latencies, using linear interpolation."""
    if not latencies_ms:
        return 0.0, 0.0
    sorted_latencies = sorted(latencies_ms)

    def _percentile(p: float) -> float:
        rank = (len(sorted_latencies) - 1) * p
        lower = int(rank)
        upper = min(lower + 1, len(sorted_latencies) - 1)
        if lower == upper:
            return sorted_latencies[lower]
        return sorted_latencies[lower] + (sorted_latencies[upper] - sorted_latencies[lower]) * (rank - lower)

    return round(_percentile(0.5), 1), round(_percentile(0.95), 1)
