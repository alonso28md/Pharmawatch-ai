"""Shared pytest fixtures for the PharmaWatch AI test suite."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import PROJECT_ROOT  # noqa: E402
from src.rag.ingest import chunk_documents, load_documents  # noqa: E402
from src.rag.vectorstore import VectorStore  # noqa: E402

REGULATIONS_DIR = PROJECT_ROOT / "data" / "regulations"

HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))

requires_api_key = pytest.mark.skipif(
    not HAS_API_KEY, reason="ANTHROPIC_API_KEY is not set; skipping live Claude API test"
)


@pytest.fixture(scope="session")
def regulatory_chunks() -> list[dict]:
    """All regulatory chunks, built once per test session."""
    documents = load_documents(REGULATIONS_DIR)
    return chunk_documents(documents)


@pytest.fixture
def populated_vectorstore(tmp_path, regulatory_chunks) -> VectorStore:
    """A VectorStore in a temp directory, pre-loaded with the regulatory chunks."""
    store = VectorStore(persist_dir=tmp_path / "chroma_db")
    store.add_documents(regulatory_chunks)
    return store


@pytest.fixture
async def api_client():
    """An httpx.AsyncClient wired directly to the FastAPI app (no network)."""
    from httpx import ASGITransport, AsyncClient

    from src.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
