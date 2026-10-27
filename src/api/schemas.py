"""Pydantic v2 request/response models for the PharmaWatch AI REST API."""

from typing import Literal

from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    """POST /report request body."""

    description: str = Field(
        ..., min_length=20, description="Free-text description of the adverse event"
    )
    device_name: str | None = None
    device_class: Literal["I", "IIa", "IIb", "III"] | None = None


class AskRequest(BaseModel):
    """POST /ask request body."""

    question: str = Field(..., min_length=10)
    language: str | None = "en"


class EvaluateRequest(BaseModel):
    """POST /evaluate request body."""

    dataset: str = "default"
    categories: list[str] | None = None
    verbose: bool = False


class Source(BaseModel):
    """A single cited regulatory source chunk."""

    document: str
    section: str
    text: str
    relevance_score: float | None = None


class ReportResponse(BaseModel):
    """POST /report response body."""

    incident_id: str
    severity: Literal["serious", "non-serious"] | None
    severity_confidence: float | None
    severity_reasoning: str | None
    reportable: bool | None
    report_to: list[str] | None
    deadline_days: int | None
    device_class: str | None
    classification_rule: str | None
    escalated_to_human: bool
    escalation_reason: str | None = None
    rag_sources: list[Source]
    draft_notification: dict | None = None
    processing_time_ms: int


class AskResponse(BaseModel):
    """POST /ask response body."""

    answer: str
    sources: list[Source]
    confidence: float
    processing_time_ms: int


class EvaluationSummary(BaseModel):
    """Summary block of an /evaluate response."""

    total_cases: int
    passed: int
    failed: int
    pass_rate: float


class FailedCase(BaseModel):
    """A single failed case in an /evaluate response."""

    case_id: str
    reason: str | None = None


class EvaluateResponse(BaseModel):
    """POST /evaluate response body."""

    summary: EvaluationSummary
    metrics: dict[str, float]
    failed_cases: list[FailedCase]
    report_path: str
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
    avg_latency_ms: float
    p95_latency_ms: float
    classification_distribution: dict[str, int]
    escalation_rate: float
    top_device_classes: dict[str, int]
    avg_confidence: float
    error_rate: float


class ConfigResponse(BaseModel):
    """GET /config response body: capabilities/limits a future client can rely on."""

    model: str
    rate_limit_per_minute: int
    retrieval_top_k: int
    supported_languages: list[str]
    endpoints: list[str]
