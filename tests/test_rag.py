"""Tests for the RAG ingestion, vector store, and retriever pipeline."""

import pytest

from src.rag.embeddings import cosine_similarity, embed_text, embed_texts
from src.rag.ingest import chunk_documents, load_documents
from src.rag.retriever import RagRetriever
from tests.conftest import REGULATIONS_DIR


def test_load_documents_finds_all_regulation_files():
    documents = load_documents(REGULATIONS_DIR)
    sources = {doc.source for doc in documents}

    assert sources == {
        "mdr_vigilance_articles.txt",
        "mdr_annex_classification_rules.txt",
        "aemps_vigilancia_guia.txt",
    }
    for doc in documents:
        assert len(doc.text) > 500
        assert doc.display_name


def test_chunk_documents_produces_tagged_chunks(regulatory_chunks):
    assert len(regulatory_chunks) > 10

    for chunk in regulatory_chunks:
        assert chunk["text"].strip()
        assert len(chunk["text"]) <= 800 + 50  # allow slight splitter overshoot
        metadata = chunk["metadata"]
        assert metadata["source"]
        assert metadata["section"]
        assert isinstance(metadata["chunk_id"], int)


def test_chunk_documents_respects_custom_chunk_size():
    documents = load_documents(REGULATIONS_DIR)
    chunks = chunk_documents(documents, chunk_size=300, chunk_overlap=50)
    assert all(len(chunk["text"]) <= 350 for chunk in chunks)


def test_embed_texts_returns_384_dim_vectors():
    vectors = embed_texts(["serious incident", "field safety corrective action"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 384


def test_cosine_similarity_identical_vs_unrelated():
    vec = embed_text("reporting deadline for a serious incident")
    same = cosine_similarity(vec, vec)
    unrelated_vec = embed_text("the weather is sunny today")
    unrelated = cosine_similarity(vec, unrelated_vec)
    assert same > 0.99
    assert unrelated < same


def test_vectorstore_query_retrieves_relevant_mdr_chunk(populated_vectorstore):
    results = populated_vectorstore.query(
        "What is the reporting deadline for a serious incident?", n_results=5
    )
    assert results
    sources = [r["metadata"]["source"] for r in results]
    assert any("MDR 2017/745" in s for s in sources)
    assert any("15 days" in r["text"] for r in results)


def test_vectorstore_query_retrieves_classification_rule(populated_vectorstore):
    results = populated_vectorstore.query(
        "How are breast implants classified under MDR Annex VIII?", n_results=5
    )
    assert results
    sources = [r["metadata"]["source"] for r in results]
    assert any("Annex VIII" in s for s in sources)


@pytest.mark.live
def test_retriever_answer_cites_sources(tmp_path, regulatory_chunks):
    from src.rag.vectorstore import VectorStore

    store = VectorStore(persist_dir=tmp_path / "chroma_db")
    store.add_documents(regulatory_chunks)

    retriever = RagRetriever(vectorstore=store)
    result = retriever.answer("What is the reporting deadline for a serious incident?")

    assert result.answer
    assert result.sources
    assert 0.0 <= result.confidence <= 1.0
    assert result.latency_ms > 0
