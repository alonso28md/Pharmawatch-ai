"""Serving the built web interface under /app without breaking /static, /docs or the API."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.frontend import frontend_router
from src.api.middleware import SecurityHeadersMiddleware


@pytest.fixture
def dist(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("nope", encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(dist):
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(frontend_router(dist))
    return TestClient(app)


def test_root_redirects_to_trailing_slash(client):
    r = client.get("/app", follow_redirects=False)
    assert r.status_code == 308
    assert r.headers["location"] == "/app/"


def test_index_and_client_routes_serve_the_shell_uncached(client):
    for path in ("/app/", "/app/review", "/app/review/INC-2026-A1B2C301", "/app/settings"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "id=root" in r.text
        assert r.headers["cache-control"] == "no-cache"


def test_hashed_assets_are_immutable(client):
    r = client.get("/app/assets/index-abc123.js")
    assert r.status_code == 200
    assert "immutable" in r.headers["cache-control"]
    assert client.get("/app/favicon.svg").headers["cache-control"] == "no-cache"


def test_missing_assets_are_404_not_the_shell(client):
    assert client.get("/app/assets/missing.js").status_code == 404
    assert client.get("/app/missing.png").status_code == 404


def test_path_traversal_is_refused(client):
    for path in ("/app/../secret.txt", "/app/%2e%2e/secret.txt", "/app/..%2Fsecret.txt"):
        r = client.get(path)
        assert "nope" not in r.text, path


def test_strict_csp_applies_to_the_app(client):
    r = client.get("/app/")
    assert r.headers["content-security-policy"] == "default-src 'self'"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_main_app_keeps_static_docs_and_api():
    from src.api.main import app

    with TestClient(app) as c:
        assert c.get("/docs").status_code == 200
        assert c.get("/static/app.js").status_code == 200
        assert c.get("/health").status_code in (200, 503)
        schema = c.get("/openapi.json").json()
        assert not any(p.startswith("/app") for p in schema["paths"])
