"""FastAPI application entrypoint: wires routers, middleware, and CORS."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.api.deps import get_query_log, limiter
from src.api.middleware import LoggingMiddleware, SecurityHeadersMiddleware, TimingMiddleware
from src.api.routes import ask, config, evaluate, health, metrics, report
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
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(
        status_code=429, content={"detail": "Rate limit exceeded. Please slow down."}
    ),
)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(LoggingMiddleware, sink=get_query_log().add)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TimingMiddleware)
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
app.include_router(evaluate.router)
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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all error handler: never leak stack traces to the client."""
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
