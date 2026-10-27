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
    assert 0.0 <= result.retrieval_score <= 1.0
    assert result.latency_ms > 0


# --- section labelling (B-08) ---------------------------------------------------------


def test_every_annex_rule_gets_its_own_section_label(regulatory_chunks):
    annex = [c for c in regulatory_chunks if c["metadata"]["source_file"] == "mdr_annex_classification_rules.txt"]
    labels = {c["metadata"]["section"] for c in annex}
    assert {f"Rule {n}" for n in range(1, 23)} <= labels


def test_wrapped_body_lines_do_not_become_sections(regulatory_chunks):
    labels = {c["metadata"]["section"] for c in regulatory_chunks}
    bogus = [
        label for label in labels
        if label.startswith(("Article 87(1)", "Article 92,", "Article 84.", "Rule 3.5"))
    ]
    assert bogus == []
    vigilance = {
        c["metadata"]["section"] for c in regulatory_chunks
        if c["metadata"]["source_file"] == "mdr_vigilance_articles.txt"
    }
    assert {label.split(" —")[0] for label in vigilance} == {
        "Header", "Article 2", "Article 87", "Article 88", "Article 89", "Article 92",
    }


def test_retriever_answer_with_scripted_llm(populated_vectorstore):
    """The full answer() path without network: labelled context in, parsed citations out."""
    from tests.fakes import ScriptedLLM

    llm = ScriptedLLM(text="Within 15 days [C1][C2], see also [C9].")
    retriever = RagRetriever(vectorstore=populated_vectorstore, llm=llm)
    result = retriever.answer("What is the reporting deadline for a serious incident?", language="es")

    _, system, user = llm.calls[0]
    assert "[C1]" in user and "ANSWER LANGUAGE: Spanish" in user
    assert "untrusted user input" in system
    assert [c["label"] for c in result.context] == [f"C{i}" for i in range(1, len(result.context) + 1)]
    assert result.cited_labels == ["C1", "C2", "C9"]
    assert all(len(c["text"]) > 400 or c["text"] for c in result.context)
    assert 0.0 <= result.retrieval_score <= 1.0


# --- multilingual retrieval (B-21) ------------------------------------------------------


def test_index_built_with_another_embedding_model_is_refused(tmp_path):
    """A legacy (all-MiniLM) index must not be silently queried with a different model."""
    import chromadb

    from src.rag.vectorstore import COLLECTION_NAME, EmbeddingModelMismatchError, VectorStore

    client = chromadb.PersistentClient(path=str(tmp_path))
    legacy = client.get_or_create_collection(name=COLLECTION_NAME)  # no model recorded
    legacy.add(ids=["a"], documents=["text"], embeddings=[[0.1] * 384])
    del client

    with pytest.raises(EmbeddingModelMismatchError, match="re-run scripts/ingest_documents.py"):
        VectorStore(persist_dir=tmp_path)


@pytest.mark.parametrize(
    ("question", "expected_document"),
    [
        ("¿Cuál es el plazo máximo para notificar un incidente grave según el MDR?",
         "MDR 2017/745 (Articles 87-92, Vigilance)"),
        ("¿Cómo se clasifica un desfibrilador externo automático?",
         "MDR 2017/745 Annex VIII (Classification Rules)"),
        ("Through which channel are incidents reported to the Spanish agency?",
         "AEMPS - Guía de vigilancia de productos sanitarios"),
    ],
)
def test_cross_language_retrieval(populated_vectorstore, question, expected_document):
    sources = [r["metadata"]["source"] for r in populated_vectorstore.query(question, n_results=5)]
    assert expected_document in sources


def test_reindex_mode_replaces_a_legacy_index(tmp_path):
    import chromadb

    from src.rag.vectorstore import COLLECTION_NAME, VectorStore

    client = chromadb.PersistentClient(path=str(tmp_path))
    client.get_or_create_collection(name=COLLECTION_NAME).add(
        ids=["a"], documents=["text"], embeddings=[[0.1] * 384]
    )
    del client

    store = VectorStore(persist_dir=tmp_path, for_reindex=True)
    assert store.count() == 0
    store.add_documents([{"id": "x", "text": "Article 87 deadline 15 days", "metadata": {"source": "s", "section": "Article 87"}}])
    assert VectorStore(persist_dir=tmp_path).count() == 1  # now opens without complaint
