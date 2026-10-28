"""Pydantic v2 request/response models for the PharmaWatch AI REST API."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

MAX_TEXT_LENGTH = 4000

# Whitespace is stripped BEFORE the length limits apply, so "          " is rejected (B-13).
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=20, max_length=MAX_TEXT_LENGTH)
]
Question = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=10, max_length=MAX_TEXT_LENGTH)
]
DeviceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
DeviceClass = Literal["I", "IIa", "IIb", "III"]


class ReportRequest(BaseModel):
    """POST /report request body."""

    description: Description = Field(..., description="Free-text description of the adverse event")
    device_name: DeviceName | None = None
    device_class: DeviceClass | None = None


class AskRequest(BaseModel):
    """POST /ask request body. `language` forces the answer language; omitted = auto-detect."""

    question: Question
    language: Literal["en", "es"] | None = None


class EvaluateRequest(BaseModel):
    """POST /evaluate request body. `dataset` is a whitelisted name, never a path."""

    dataset: str = Field(default="default", pattern=r"^[a-z0-9_-]{1,40}$")
    categories: list[Literal["rag", "classification"]] | None = None


class Source(BaseModel):
    """A single cited regulatory source chunk."""

    document: str
    section: str
    text: str
    relevance_score: float | None = None
    chunk_id: str | None = None


class ContextChunk(BaseModel):
    """One retrieved chunk as given to the model, with its citation label."""

    label: str
    chunk_id: str
    document: str
    section: str
    text: str


class ReportResponse(BaseModel):
    """POST /report response body."""

    incident_id: str
    severity: Literal["serious", "non-serious"] | None
    severity_confidence: float | None
    severity_reasoning: str | None
    incident_category: str | None
    reportable: bool | None
    report_to: list[str] | None
    deadline_days: int | None
    deadline_rule: str | None
    device_class: str | None
    device_class_source: Literal["caller", "extracted", "rule"] | None
    classification_rule: str | None
    escalated_to_human: bool
    escalation_level: Literal["none", "advisory", "blocking"]
    escalation_reason: str | None = None
    rag_sources: list[Source]
    draft_notification: dict | None = None
    processing_time_ms: int


class IncidentSummary(ReportResponse):
    """A stored incident result with its creation time."""

    created_at: datetime


class IncidentPage(BaseModel):
    """GET /reports response: newest first."""

    items: list[IncidentSummary]
    total: int
    limit: int
    offset: int


class MetricStat(BaseModel):
    mean: float | None
    min: float | None
    max: float | None
    n: int
    threshold: dict | None = None
    meets_threshold: bool | None = None


class EvaluationLatest(BaseModel):
    """GET /evaluations/latest: a stored evaluation result (read-only, never runs one)."""

    file: str
    rescored: bool
    # "artifacts": a result file in ARTIFACTS_DIR; "snapshot": the summary versioned in
    # docs/results/ (served when this installation has no stored results of its own).
    source: Literal["artifacts", "snapshot"] = "artifacts"
    timestamp: str | None
    metadata: dict
    summary: dict
    metric_summary: dict[str, MetricStat]
    failed_cases: list[dict]


class AskResponse(BaseModel):
    """POST /ask response body."""

    answer: str
    sources: list[Source]
    # Mean similarity of the retrieved chunks to the question. It measures retrieval,
    # not whether the answer is correct (an abstention can still score ~0.6).
    retrieval_score: float
    processing_time_ms: int
    # The labelled chunks the model saw ([C1]..[Ck]), full text, so a client can show the
    # exact cited fragment; and the labels the answer actually cites.
    context: list[ContextChunk] = []
    cited_labels: list[str] = []
    # False when the answer cites nothing: the model is instructed to cite every claim and
    # to cite nothing when the corpus does not contain the answer (abstention signal).
    answered_from_context: bool = True


class EvaluationSummary(BaseModel):
    """Summary block of an /evaluate response."""

    total_cases: int
    passed: int
    failed: int
    pass_rate: float | None


class FailedCase(BaseModel):
    """A single failed case in an /evaluate response."""

    case_id: str
    reason: str | None = None


class EvaluateResponse(BaseModel):
    """POST /evaluate response body. `report_file` lives in ARTIFACTS_DIR/evaluations/."""

    summary: EvaluationSummary
    metrics: dict[str, float | None]
    failed_cases: list[FailedCase]
    report_file: str
    timestamp: str


class HealthResponse(BaseModel):
    """GET /health response body."""

    status: Literal["healthy", "degraded"]
    version: str
    vectorstore: Literal["connected", "unavailable"]
    vectorstore_documents: int
    database: Literal["connected", "unavailable"]
    model: str
    uptime_seconds: float


class OperationalMetricsResponse(BaseModel):
    """GET /metrics response body."""

    total_queries: int
    queries_last_24h: int
    include_demo: bool
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    latency_samples: int
    classification_distribution: dict[str, int]
    escalation_rate: float
    blocking_escalation_rate: float
    top_device_classes: dict[str, int]
    avg_confidence: float
    error_rate: float  # share of requests that ended in 5xx
    client_error_rate: float  # share that ended in 4xx (validation, auth, 413, 429)


class ConfigResponse(BaseModel):
    """GET /config response body: capabilities/limits a future client can rely on."""

    model: str
    rate_limit_per_minute: int
    retrieval_top_k: int
    supported_languages: list[str]
    endpoints: list[str]
