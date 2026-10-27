"""GET /config — capability/configuration endpoint for client integrations."""

from fastapi import APIRouter

from src.api.schemas import ConfigResponse
from src.config import get_settings

router = APIRouter()


@router.get("/config", response_model=ConfigResponse, tags=["observability"])
async def config() -> ConfigResponse:
    """Expose non-secret capabilities/limits so a future client can configure itself."""
    settings = get_settings()
    return ConfigResponse(
        model=settings.anthropic_model,
        rate_limit_per_minute=settings.rate_limit_per_minute,
        retrieval_top_k=settings.retrieval_top_k,
        supported_languages=["en", "es"],
        endpoints=["/health", "/ask", "/report", "/reports/{incident_id}", "/evaluate", "/metrics", "/config"],
    )
