"""RAG retrieval chain: embed question -> retrieve chunks -> cited Claude answer."""

import logging
import re
import time
from dataclasses import dataclass

import anthropic

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


@dataclass
class RagAnswer:
    """The full result of a RAG question-answering call."""

    answer: str
    sources: list[Source]
    confidence: float
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

    def __init__(
        self,
        vectorstore: VectorStore | None = None,
        client: anthropic.Anthropic | None = None,
    ):
        settings = get_settings()
        self._settings = settings
        self._vectorstore = vectorstore or VectorStore()
        self._client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def count_indexed_chunks(self) -> int:
        """Number of chunks currently stored in the vector store."""
        return self._vectorstore.count()

    def retrieve(self, question: str, top_k: int | None = None) -> list[dict]:
        """Return the top-k most relevant regulatory chunks for `question`."""
        top_k = top_k or self._settings.retrieval_top_k
        return self._vectorstore.query(question, n_results=top_k)

    def answer(self, question: str, top_k: int | None = None) -> RagAnswer:
        """Retrieve context and generate a cited answer to `question` via Claude."""
        start = time.perf_counter()
        chunks = self.retrieve(question, top_k=top_k)

        if not chunks:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return RagAnswer(
                answer="No regulatory context is available to answer this question.",
                sources=[],
                confidence=0.0,
                latency_ms=latency_ms,
            )

        context_block = _build_context_block(chunks)
        answer_language = _detect_answer_language(question)
        user_prompt = (
            f"CONTEXT:\n{context_block}\n\n"
            f"QUESTION: {question}\n\n"
            f"ANSWER LANGUAGE: {answer_language} (write your entire answer in "
            f"{answer_language}, regardless of the language of the context above)"
        )

        response = self._client.messages.create(
            model=self._settings.anthropic_model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        answer_text = next((block.text for block in response.content if block.type == "text"), "")

        sources = [
            Source(
                document=chunk["metadata"]["source"],
                section=chunk["metadata"]["section"],
                text=chunk["text"][:400],
                relevance_score=round(_distance_to_relevance(chunk["distance"]), 4),
            )
            for chunk in chunks
        ]
        confidence = round(sum(s.relevance_score for s in sources) / len(sources), 4)
        latency_ms = int((time.perf_counter() - start) * 1000)

        logger.info("RAG answer generated in %d ms (confidence=%.2f)", latency_ms, confidence)
        return RagAnswer(
            answer=answer_text, sources=sources, confidence=confidence, latency_ms=latency_ms
        )
