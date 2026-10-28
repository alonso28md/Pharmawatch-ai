"""Phase 5: version, error envelope everywhere, CSP for docs, contracts and packaging hygiene."""

import re
from pathlib import Path

import pytest

from src import __version__
from tests.conftest import PROJECT_ROOT


async def test_single_version_everywhere(api_client):
    health = (await api_client.get("/health")).json()
    openapi = (await api_client.get("/openapi.json")).json()
    assert health["version"] == openapi["info"]["version"] == __version__
    assert 'attr = "src.__version__"' in (PROJECT_ROOT / "pyproject.toml").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("method", "path", "status", "code"),
    [
        ("get", "/does-not-exist", 404, "not_found"),
        ("get", "/ask", 405, "method_not_allowed"),
        ("post", "/ask", 422, "validation_error"),
    ],
)
async def test_every_error_uses_the_envelope(api_client, method, path, status, code):
    response = await getattr(api_client, method)(path)
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"code", "message", "details"} and body["code"] == code


async def test_docs_pages_get_a_csp_that_allows_their_assets(api_client):
    docs = await api_client.get("/docs")
    assert "https://cdn.jsdelivr.net" in docs.headers["content-security-policy"]
    api = await api_client.get("/config")
    assert api.headers["content-security-policy"] == "default-src 'self'"
    assert api.headers["x-frame-options"] == "DENY"


def test_routes_do_not_use_implicit_request_state():
    """Routes talk to the middleware only through the typed RequestLog dependency."""
    offenders = [
        p.name
        for p in (PROJECT_ROOT / "src" / "api" / "routes").glob("*.py")
        if re.search(r"request\.state\.", p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_one_anthropic_client_construction_site():
    """Only src/agent/llm.py may construct an Anthropic SDK client."""
    sites = [
        str(p.relative_to(PROJECT_ROOT))
        for p in (PROJECT_ROOT / "src").rglob("*.py")
        if "anthropic.Anthropic(" in p.read_text(encoding="utf-8")
    ]
    assert sites == [str(Path("src/agent/llm.py"))]


def test_requirements_have_no_unused_direct_dependencies():
    text = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
    for unused in ("langchain-anthropic", "langchain-core", "numpy"):
        assert unused not in text
    lock = (PROJECT_ROOT / "requirements.lock").read_text(encoding="utf-8")
    pinned = {
        line.split("==")[0].lower().replace("_", "-") for line in lock.splitlines() if "==" in line
    }
    for line in text.splitlines():
        name = re.split(r"[<>=\[ #]", line.strip())[0].lower().replace("_", "-")
        if name:
            assert name in pinned, f"{name} is not pinned in requirements.lock"


def test_dockerfile_runs_as_non_root_without_compilers_in_final_stage():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    final_stage = dockerfile.split("FROM python:3.14-slim\n")[-1]
    assert "USER app" in final_stage
    assert "build-essential" not in final_stage
    assert "COPY config/ config/" in dockerfile
