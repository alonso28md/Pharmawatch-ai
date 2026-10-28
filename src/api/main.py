"""FastAPI application entrypoint: wires routers, middleware, and CORS."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.middleware import SlowAPIMiddleware

from src import __version__
from src.api.deps import get_repository, limiter
from src.api.errors import install_error_handlers
from src.api.middleware import (
    BodySizeLimitMiddleware,
    ObservabilityMiddleware,
    SecurityHeadersMiddleware,
    db_request_log_sink,
)
from src.api.routes import ask, config, evaluate, evaluations, health, metrics, report, reports
from src.config import PROJECT_ROOT, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="PharmaWatch AI",
    description=(
        "AI-powered pharmacovigilance assistant for medical device adverse event "
        "classification and regulatory reporting. Combines a RAG pipeline over real "
        "MDR 2017/745 and AEMPS regulatory text with a LangGraph incident-"
        "classification agent, backed by a reproducible evaluation harness."
    ),
    version=__version__,
)

app.state.limiter = limiter
install_error_handlers(app)

# Middleware runs outermost-last-added: CORS -> SecurityHeaders -> Observability ->
# BodySizeLimit -> SlowAPI -> routes. Observability wraps everything that can fail
# (413, 429, 5xx) so every business request is logged with its real status.
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(BodySizeLimitMiddleware, max_bytes_provider=lambda: get_settings().max_request_bytes)
app.add_middleware(
    ObservabilityMiddleware,
    sink=db_request_log_sink(get_repository, store_input_text=lambda: get_settings().store_input_text),
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ask.router)
app.include_router(report.router)
app.include_router(reports.router)
app.include_router(evaluate.router)
app.include_router(evaluations.router)
app.include_router(metrics.router)
app.include_router(config.router)

static_dir = PROJECT_ROOT / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir), html=True), name="static")


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to the static demo page if present, else to the API docs."""
    from fastapi.responses import RedirectResponse

    if static_dir.exists():
        return RedirectResponse(url="/static/index.html")
    return RedirectResponse(url="/docs")
