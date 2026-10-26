"""ChromaDB-backed vector store for the regulations collection."""

import logging
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from src.config import get_settings
from src.rag.embeddings import MODEL_NAME

logger = logging.getLogger(__name__)

COLLECTION_NAME = "regulations"


class VectorStore:
    """Thin wrapper around a persisted ChromaDB collection of regulatory chunks."""

    def __init__(self, persist_dir: str | Path | None = None):
        settings = get_settings()
        self._persist_dir = Path(persist_dir) if persist_dir else settings.chroma_persist_dir_absolute
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(self._persist_dir))
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=MODEL_NAME
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME, embedding_function=self._embedding_fn
        )

    def reset(self) -> None:
        """Drop and recreate the collection (used before re-ingesting)."""
        try:
            self._client.delete_collection(COLLECTION_NAME)
        except Exception:
            logger.debug("Collection %s did not exist yet; nothing to delete", COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME, embedding_function=self._embedding_fn
        )

    def add_documents(self, chunks: list[dict]) -> None:
        """Add pre-built chunks (each with id/text/metadata) to the collection."""
        if not chunks:
            return
        self._collection.add(
            ids=[chunk["id"] for chunk in chunks],
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[chunk["metadata"] for chunk in chunks],
        )
        logger.info("Added %d chunk(s) to collection '%s'", len(chunks), COLLECTION_NAME)

    def count(self) -> int:
        """Number of chunks currently stored."""
        return self._collection.count()

    def query(self, query_text: str, n_results: int = 5) -> list[dict]:
        """Return the top-n most similar chunks to `query_text`."""
        n_results = min(n_results, max(self.count(), 1))
        results = self._collection.query(query_texts=[query_text], n_results=n_results)

        ids = results["ids"][0]
        docs = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        return [
            {
                "id": ids[i],
                "text": docs[i],
                "metadata": metadatas[i],
                "distance": distances[i],
            }
            for i in range(len(ids))
        ]
