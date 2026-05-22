from __future__ import annotations

"""Vector Store + RAG pipeline â€” ChromaDB with sentence-transformers embeddings.

Provides semantic search over:
- Medical literature / clinical guidelines
- Payer policy documents
- Historical PA decisions (case precedents)
- Patient clinical notes for evidence retrieval
"""

import os
import uuid
import structlog
from typing import Any

from app.config import get_settings

logger = structlog.get_logger()

_chroma_client = None
_embedding_fn = None
_rag_available = False


def _init_rag():
    global _chroma_client, _embedding_fn, _rag_available
    if _chroma_client is not None:
        return _rag_available

    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        settings = get_settings()
        persist_dir = settings.CHROMA_PERSIST_DIR
        os.makedirs(persist_dir, exist_ok=True)

        _chroma_client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # Use sentence-transformers for local embeddings
        try:
            from chromadb.utils import embedding_functions
            _embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.EMBEDDING_MODEL
            )
        except Exception as exc:
            logger.warning("rag.sentence_transformers_unavailable", error=str(exc))
            _embedding_fn = None  # ChromaDB will use default embeddings

        _rag_available = True
        logger.info("rag.initialized", persist_dir=persist_dir, model=settings.EMBEDDING_MODEL)
    except Exception as exc:
        _rag_available = False
        logger.warning("rag.unavailable", error=str(exc))

    return _rag_available


def _get_collection(name: str):
    """Get or create a ChromaDB collection."""
    _init_rag()
    if not _rag_available:
        return None
    kwargs = {"name": name}
    if _embedding_fn:
        kwargs["embedding_function"] = _embedding_fn
    return _chroma_client.get_or_create_collection(**kwargs)


# â”€â”€ Collections â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

COLLECTION_POLICIES = "payer_policies"
COLLECTION_LITERATURE = "medical_literature"
COLLECTION_PRECEDENTS = "pa_precedents"
COLLECTION_CLINICAL = "clinical_notes"


# â”€â”€ Ingest Functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def ingest_policy_document(
    policy_id: str,
    payer_id: str,
    cpt_code: str,
    policy_text: str,
    metadata: dict | None = None,
) -> bool:
    """Index a payer policy document for semantic retrieval."""
    collection = _get_collection(COLLECTION_POLICIES)
    if not collection:
        return False

    # Chunk long documents
    chunks = _chunk_text(policy_text, chunk_size=500, overlap=50)

    ids = [f"{policy_id}_chunk_{i}" for i in range(len(chunks))]
    documents = chunks
    metadatas = [
        {
            "policy_id": policy_id,
            "payer_id": payer_id,
            "cpt_code": cpt_code,
            "chunk_index": i,
            **(metadata or {}),
        }
        for i in range(len(chunks))
    ]

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    logger.info("rag.policy_ingested", policy_id=policy_id, chunks=len(chunks))
    return True


def ingest_medical_literature(
    doc_id: str,
    title: str,
    text: str,
    source: str = "pubmed",
    metadata: dict | None = None,
) -> bool:
    """Index medical literature for appeal evidence retrieval."""
    collection = _get_collection(COLLECTION_LITERATURE)
    if not collection:
        return False

    chunks = _chunk_text(text, chunk_size=500, overlap=50)
    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {"doc_id": doc_id, "title": title, "source": source, "chunk_index": i, **(metadata or {})}
        for i in range(len(chunks))
    ]

    collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
    logger.info("rag.literature_ingested", doc_id=doc_id, title=title, chunks=len(chunks))
    return True


def ingest_pa_precedent(
    pa_id: str,
    payer_id: str,
    cpt_code: str,
    outcome: str,
    clinical_summary: str,
    appeal_letter: str | None = None,
) -> bool:
    """Index a historical PA decision as a case precedent."""
    collection = _get_collection(COLLECTION_PRECEDENTS)
    if not collection:
        return False

    text = f"Outcome: {outcome}. Clinical Summary: {clinical_summary}"
    if appeal_letter:
        text += f" Appeal: {appeal_letter[:1000]}"

    collection.upsert(
        ids=[pa_id],
        documents=[text],
        metadatas=[{"pa_id": pa_id, "payer_id": payer_id, "cpt_code": cpt_code, "outcome": outcome}],
    )
    logger.info("rag.precedent_ingested", pa_id=pa_id, outcome=outcome)
    return True


def ingest_clinical_notes(
    patient_id: str,
    note_id: str,
    note_text: str,
    note_type: str = "progress_note",
    date: str | None = None,
) -> bool:
    """Index patient clinical notes for evidence retrieval."""
    collection = _get_collection(COLLECTION_CLINICAL)
    if not collection:
        return False

    chunks = _chunk_text(note_text, chunk_size=400, overlap=40)
    ids = [f"{note_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {"patient_id": patient_id, "note_id": note_id, "note_type": note_type, "date": date or "", "chunk_index": i}
        for i in range(len(chunks))
    ]

    collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
    return True


# â”€â”€ Search / Retrieval Functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def search_policies(
    query: str,
    payer_id: str | None = None,
    cpt_code: str | None = None,
    n_results: int = 5,
) -> list[dict]:
    """Search payer policy documents semantically."""
    collection = _get_collection(COLLECTION_POLICIES)
    if not collection:
        return []

    where_filter = {}
    if payer_id:
        where_filter["payer_id"] = payer_id
    if cpt_code:
        where_filter["cpt_code"] = cpt_code

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where_filter if where_filter else None,
    )

    return _format_results(results)


def search_literature(
    query: str,
    n_results: int = 5,
) -> list[dict]:
    """Search medical literature for supporting evidence."""
    collection = _get_collection(COLLECTION_LITERATURE)
    if not collection:
        return []

    results = collection.query(query_texts=[query], n_results=n_results)
    return _format_results(results)


def search_precedents(
    query: str,
    payer_id: str | None = None,
    cpt_code: str | None = None,
    outcome: str | None = None,
    n_results: int = 5,
) -> list[dict]:
    """Search historical PA precedents for similar cases."""
    collection = _get_collection(COLLECTION_PRECEDENTS)
    if not collection:
        return []

    where_filter = {}
    if payer_id:
        where_filter["payer_id"] = payer_id
    if cpt_code:
        where_filter["cpt_code"] = cpt_code
    if outcome:
        where_filter["outcome"] = outcome

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where_filter if where_filter else None,
    )

    return _format_results(results)


def search_clinical_notes(
    query: str,
    patient_id: str,
    n_results: int = 10,
) -> list[dict]:
    """Search a patient's clinical notes for specific evidence."""
    collection = _get_collection(COLLECTION_CLINICAL)
    if not collection:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where={"patient_id": patient_id},
    )

    return _format_results(results)


# â”€â”€ RAG Pipeline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def retrieve_context_for_evidence(
    clinical_query: str,
    payer_id: str,
    cpt_code: str,
    patient_id: str | None = None,
    max_chunks: int = 10,
) -> dict:
    """
    Full RAG retrieval: gather relevant context from all sources
    for the clinical evidence extraction LLM call.
    """
    context = {
        "policy_context": [],
        "literature_context": [],
        "precedent_context": [],
        "clinical_notes_context": [],
    }

    # Policy context
    context["policy_context"] = search_policies(
        clinical_query, payer_id=payer_id, cpt_code=cpt_code, n_results=3
    )

    # Medical literature
    context["literature_context"] = search_literature(clinical_query, n_results=3)

    # Similar precedents
    context["precedent_context"] = search_precedents(
        clinical_query, payer_id=payer_id, cpt_code=cpt_code, n_results=3
    )

    # Patient-specific notes
    if patient_id:
        context["clinical_notes_context"] = search_clinical_notes(
            clinical_query, patient_id=patient_id, n_results=max_chunks
        )

    return context


def retrieve_context_for_appeal(
    denial_reason: str,
    payer_id: str,
    cpt_code: str,
) -> dict:
    """Retrieve RAG context specifically for appeal letter generation."""
    context = {
        "successful_appeals": [],
        "policy_references": [],
        "supporting_literature": [],
    }

    # Find successful appeals for similar cases
    context["successful_appeals"] = search_precedents(
        denial_reason, payer_id=payer_id, cpt_code=cpt_code, outcome="approved", n_results=3
    )

    # Policy text relevant to denial
    context["policy_references"] = search_policies(
        denial_reason, payer_id=payer_id, cpt_code=cpt_code, n_results=3
    )

    # Medical literature supporting the procedure
    context["supporting_literature"] = search_literature(
        f"medical necessity {cpt_code} {denial_reason}", n_results=5
    )

    return context


# â”€â”€ Utilities â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks for embedding."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        # Try to break at sentence boundary
        if end < len(text):
            last_period = text[start:end].rfind(". ")
            if last_period > chunk_size // 2:
                end = start + last_period + 2
        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if c]


def _format_results(results: dict) -> list[dict]:
    """Format ChromaDB query results into clean dicts."""
    formatted = []
    if not results or not results.get("documents"):
        return formatted

    docs = results["documents"][0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i, doc in enumerate(docs):
        entry = {
            "text": doc,
            "metadata": metas[i] if i < len(metas) else {},
            "score": 1.0 - (distances[i] if i < len(distances) else 0),
        }
        formatted.append(entry)

    return formatted


def is_rag_available() -> bool:
    return _init_rag()
