"""RAG retrieval chain: embed question -> retrieve chunks -> cited Claude answer."""

import logging
import re
import threading
import time
from dataclasses import dataclass
from functools import lru_cache

from src.agent.llm import LLMClient, get_llm_client
from src.config import get_settings
from src.rag.vectorstore import VectorStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a medical device regulatory assistant specializing in \
EU MDR 2017/745 vigilance requirements and Spanish AEMPS pharmacovigilance procedures.
Answer ONLY based on the provided context.
Always cite the source document and section for every claim you make.
If the context does not contain enough information to answer, say so explicitly \
instead of guessing.
The context chunks may be in English or Spanish regardless of the question's \
language. You MUST write your entire answer in the language stated in the \
ANSWER LANGUAGE instruction given with each question, translating any cited \
figures or terms as needed - never switch language because the source chunk \
happened to be in a different one."""

_SPANISH_MARKERS = re.compile(
    r"[áéíóúñ¿¡]|(?:\b(qué|cómo|cuál|cuáles|dónde|cuándo|quién|notificación|"
    r"plazo|vigilancia|incidente|grave|producto sanitario)\b)",
    re.IGNORECASE,
)


def _detect_answer_language(question: str) -> str:
    """Best-effort English/Spanish detection, used to force an explicit answer language.

    Relying on the model to infer "respond in the question's language" was found
    (via live testing) to be unreliable on its own - the model sometimes answered
    in Spanish for a plainly English question even with all-English retrieved
    context. Making the target language an explicit instruction fixes this.
    """
    return "Spanish" if _SPANISH_MARKERS.search(question) else "English"


@dataclass
class Source:
    """A single cited chunk backing a RAG answer."""

    document: str
    section: str
    text: str
    relevance_score: float
    chunk_id: str = ""


@dataclass
class RagAnswer:
    """The full result of a RAG question-answering call."""

    answer: str
    sources: list[Source]
    retrieval_score: float  # mean similarity of the retrieved chunks - NOT answer correctness
    latency_ms: int


def _build_context_block(chunks: list[dict]) -> str:
    blocks = []
    for chunk in chunks:
        metadata = chunk["metadata"]
        blocks.append(
            f"[Source: {metadata['source']}, Section: {metadata['section']}]\n{chunk['text']}"
        )
    return "\n\n".join(blocks)


def _distance_to_relevance(distance: float) -> float:
    """Chroma's sentence-transformer collections use cosine distance in [0, 2]."""
    return max(0.0, min(1.0, 1.0 - distance / 2.0))


class RagRetriever:
    """Retrieves regulatory context and asks Claude to answer with citations."""

    def __init__(self, vectorstore: VectorStore | None = None, llm: LLMClient | None = None):
        settings = get_settings()
        self._settings = settings
        self._vectorstore = vectorstore or VectorStore()
        self._llm = llm
        self._context_lock = threading.Lock()
        self._regulatory_context: list[dict] | None = None

    @property
    def llm(self) -> LLMClient:
        return self._llm or get_llm_client()

    def count_indexed_chunks(self) -> int:
        """Number of chunks currently stored in the vector store."""
        return self._vectorstore.count()

    def retrieve(self, question: str, top_k: int | None = None) -> list[dict]:
        """Return the top-k most relevant regulatory chunks for `question`."""
        top_k = top_k or self._settings.retrieval_top_k
        return self._vectorstore.query(question, n_results=top_k)

    def answer(self, question: str, top_k: int | None = None, language: str | None = None) -> RagAnswer:
        """Retrieve context and generate a cited answer to `question` via Claude."""
        start = time.perf_counter()
        chunks = self.retrieve(question, top_k=top_k)

        if not chunks:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return RagAnswer(
                answer="No regulatory context is available to answer this question.",
                sources=[],
                retrieval_score=0.0,
                latency_ms=latency_ms,
            )

        context_block = _build_context_block(chunks)
        answer_language = {"en": "English", "es": "Spanish"}.get(language or "") or _detect_answer_language(question)
        user_prompt = (
            f"CONTEXT:\n{context_block}\n\n"
            f"QUESTION: {question}\n\n"
            f"ANSWER LANGUAGE: {answer_language} (write your entire answer in "
            f"{answer_language}, regardless of the language of the context above)"
        )

        answer_text = self.llm.complete_text(SYSTEM_PROMPT, user_prompt)

        sources = [
            Source(
                document=chunk["metadata"]["source"],
                section=chunk["metadata"]["section"],
                text=chunk["text"][:400],
                relevance_score=round(_distance_to_relevance(chunk["distance"]), 4),
                chunk_id=chunk["id"],
            )
            for chunk in chunks
        ]
        retrieval_score = round(sum(s.relevance_score for s in sources) / len(sources), 4)
        latency_ms = int((time.perf_counter() - start) * 1000)

        logger.info("RAG answer generated in %d ms (retrieval_score=%.2f)", latency_ms, retrieval_score)
        return RagAnswer(
            answer=answer_text, sources=sources, retrieval_score=retrieval_score, latency_ms=latency_ms
        )

    def regulatory_context(self) -> list[dict]:
        """Fixed MDR context for severity assessment: retrieval only, computed once.

        The questions are constant, so asking the LLM to answer them on every incident
        (as before) cost one model call (~5 s) per /report for an identical result.
        """
        with self._context_lock:
            if self._regulatory_context is None:
                seen: dict[str, dict] = {}
                for query in REGULATORY_CONTEXT_QUERIES:
                    for chunk in self.retrieve(query, top_k=4):
                        seen.setdefault(chunk["id"], chunk)
                self._regulatory_context = [
                    {
                        "chunk_id": c["id"],
                        "document": c["metadata"]["source"],
                        "section": c["metadata"]["section"],
                        "text": c["text"],
                    }
                    for c in seen.values()
                ]
            return self._regulatory_context


REGULATORY_CONTEXT_QUERIES = (
    "What qualifies as a serious incident under MDR Article 2(65)?",
    "Reporting deadlines for serious incidents under Article 87: death, unanticipated "
    "serious deterioration, serious public health threat",
)


@lru_cache(maxsize=1)
def get_retriever() -> RagRetriever:
    """Process-wide RagRetriever (one vector-store connection, one LLM client)."""
    return RagRetriever()
