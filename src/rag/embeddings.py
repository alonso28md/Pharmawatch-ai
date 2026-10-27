"""Local, free sentence-embedding generation via sentence-transformers."""

import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from src.config import get_settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 384


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load (and cache) the sentence-transformers embedding model."""
    model_name = get_settings().embedding_model
    logger.info("Loading embedding model %s", model_name)
    return SentenceTransformer(model_name)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one 384-dim embedding vector per input text."""
    if not texts:
        return []
    model = get_embedding_model()
    vectors = model.encode(texts, show_progress_bar=False)
    return vectors.tolist()


def embed_text(text: str) -> list[float]:
    """Return the embedding vector for a single text."""
    return embed_texts([text])[0]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
