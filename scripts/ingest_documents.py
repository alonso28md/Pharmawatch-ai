#!/usr/bin/env python
"""Ingest the regulatory documents in data/regulations/ into the Chroma vector store."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import PROJECT_ROOT, get_settings  # noqa: E402
from src.rag.ingest import chunk_documents, load_documents  # noqa: E402
from src.rag.vectorstore import VectorStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    regulations_dir = PROJECT_ROOT / "data" / "regulations"

    documents = load_documents(regulations_dir)
    if not documents:
        logger.warning("No .txt documents found in %s", regulations_dir)
        return

    chunks = chunk_documents(
        documents, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
    )
    logger.info(
        "Produced %d chunk(s) (chunk_size=%d, overlap=%d)",
        len(chunks),
        settings.chunk_size,
        settings.chunk_overlap,
    )

    store = VectorStore()
    store.reset()
    store.add_documents(chunks)
    logger.info(
        "Vector store ready: %d chunk(s) in collection 'regulations' at %s",
        store.count(),
        settings.chroma_persist_dir_absolute,
    )


if __name__ == "__main__":
    main()
