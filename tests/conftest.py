"""Shared pytest fixtures for the PharmaWatch AI test suite."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import PROJECT_ROOT  # noqa: E402
from src.rag.ingest import chunk_documents, load_documents  # noqa: E402

REGULATIONS_DIR = PROJECT_ROOT / "data" / "regulations"

HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))

requires_api_key = pytest.mark.skipif(
    not HAS_API_KEY, reason="ANTHROPIC_API_KEY is not set; skipping live Claude API test"
)


@pytest.fixture(scope="session", autouse=True)
def _isolated_data_paths(tmp_path_factory):
    """Point every storage path at a throwaway directory for the whole session.

    Opening (even just querying) a Chroma PersistentClient rewrites its files, and
    the API logs every request to SQLite, so no test may ever resolve the real
    data/ directory. The session vector store is built from the regulatory corpus.
    """
    from src.config import get_settings
    from src.rag.vectorstore import VectorStore

    root = tmp_path_factory.mktemp("pharmawatch_data")
    overrides = {
        "DB_PATH": str(root / "session.db"),
        "CHROMA_PERSIST_DIR": str(root / "chroma_db"),
        "ARTIFACTS_DIR": str(root / "artifacts"),
    }
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    get_settings.cache_clear()

    VectorStore(persist_dir=overrides["CHROMA_PERSIST_DIR"]).add_documents(
        chunk_documents(load_documents(REGULATIONS_DIR))
    )
    yield root

    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def regulatory_chunks() -> list[dict]:
    """All regulatory chunks, built once per test session."""
    documents = load_documents(REGULATIONS_DIR)
    return chunk_documents(documents)


@pytest.fixture
def populated_vectorstore(tmp_path, regulatory_chunks):
    """A VectorStore in a temp directory, pre-loaded with the regulatory chunks."""
    from src.rag.vectorstore import VectorStore

    store = VectorStore(persist_dir=tmp_path / "chroma_db")
    store.add_documents(regulatory_chunks)
    return store


@pytest.fixture
async def api_client(tmp_path, monkeypatch):
    """An httpx.AsyncClient wired to the FastAPI app, backed by an isolated test DB."""
    from src.api import deps
    from src.config import get_settings

    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    get_settings.cache_clear()
    deps.get_repository.cache_clear()

    from httpx import ASGITransport, AsyncClient

    from src.api.main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    deps.get_repository.cache_clear()
    get_settings.cache_clear()
