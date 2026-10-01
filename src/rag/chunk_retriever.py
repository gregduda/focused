"""Retrieve the top-k policy chunks for a query from the Chroma index.

Version 1 (the default): no metadata filtering. Whatever is nearest comes back, including stale or
non-authoritative docs (ARC-*, SUP-*, MKT-01). `authoritative_only=True` is the first v2 filter (D-071): only chunks
with status "active" and authority "authoritative" are searched. Status alone is not enough, because SUP-01, SUP-02,
and MKT-01 are active but non-authoritative.

Build the index first:  python -m src.rag.embed_sources
"""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langsmith import traceable

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = str(REPO_ROOT / os.environ["CHROMA_DIR"])
COLLECTION = os.environ["CHROMA_COLLECTION"]
DEFAULT_TOP_K = int(os.environ["RETRIEVER_TOP_K"])


@lru_cache(maxsize=1)
def _vector_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION,
        # No embedding_function: same local default as embed_sources.py (all-MiniLM-L6-v2). Keep them identical.
        persist_directory=CHROMA_DIR,
    )


# CAT-03 (hygiene and personal care) also covers swimwear and in-ear earbuds, whose catalog category is apparel or
# electronics (README, open question 18), so it stays searchable whatever the order's category.
ALWAYS_SEARCHABLE_CATEGORY = "hygiene_personal_care"


def _search_filter(authoritative_only: bool, category: str | None, state: str | None) -> dict | None:
    """The Chroma `where` clause for a search, or None for no filtering (version 1)."""
    clauses = []
    if authoritative_only:
        clauses += [{"status": {"$eq": "active"}}, {"authority": {"$eq": "authoritative"}}]
    if category is not None and state is not None:
        clauses.append({"$or": [
            {"doc_type": {"$nin": ["category_policy", "state_addendum"]}},
            {"$and": [{"doc_type": {"$eq": "category_policy"}},
                      {"category": {"$in": [category, ALWAYS_SEARCHABLE_CATEGORY]}}]},
            {"$and": [{"doc_type": {"$eq": "state_addendum"}}, {"state": {"$in": [state, "ALL"]}}]},
        ]})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


@traceable(run_type="retriever", name="policy_retriever")  # shows the query and chunks as their own trace step
def retrieve(query: str, k: int = DEFAULT_TOP_K, authoritative_only: bool = False, category: str | None = None,
             state: str | None = None) -> list[Document]:
    """Return the k chunks nearest to the query, best first. With authoritative_only, stale and non-authoritative
    documents are left out of the search, so the k slots go to documents that apply. With category and state (the
    order's), category documents other than that category's and state addenda other than that state's are left out
    too (D-072); documents without a category or state are never restricted.

    Each returned Document has the chunk text (starting with "Title (DOC-ID)") and its metadata,
    plus a "distance" entry (Chroma's L2 distance on unit-length vectors; smaller means closer).
    """
    results = _vector_store().similarity_search_with_score(
        query, k=k, filter=_search_filter(authoritative_only, category, state))
    return [Document(page_content=doc.page_content, metadata={**doc.metadata, "distance": score})
            for doc, score in results]


def docs_by_id(doc_ids: list[str]) -> list[Document]:
    """Every chunk of the given documents, fetched by id and not searched for, in the order of `doc_ids` and then
    section order. Used by the retrieval modes that add documents by rule (see forced_docs.py). The distance is 0.0
    because no search was involved."""
    got = _vector_store().get(where={"doc_id": {"$in": list(doc_ids)}})
    chunks = sorted(zip(got["ids"], got["documents"], got["metadatas"]),
                    key=lambda c: (doc_ids.index(c[2]["doc_id"]), int(c[0].split("::")[1])))
    return [Document(page_content=text, metadata={**meta, "distance": 0.0}) for _, text, meta in chunks]
