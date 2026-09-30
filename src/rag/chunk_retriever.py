"""Retrieve the top-k policy chunks for a query from the Chroma index.

Version 1: no metadata filtering. Whatever is nearest comes back, including stale or
non-authoritative docs (ARC-*, SUP-*, MKT-01). Version 2 will add filters here.

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


@traceable(run_type="retriever", name="policy_retriever")  # shows the query and chunks as their own trace step
def retrieve(query: str, k: int = DEFAULT_TOP_K) -> list[Document]:
    """Return the k chunks nearest to the query, best first.

    Each returned Document has the chunk text (starting with "Title (DOC-ID)") and its metadata,
    plus a "distance" entry (Chroma's L2 distance on unit-length vectors; smaller means closer).
    """
    results = _vector_store().similarity_search_with_score(query, k=k)
    return [Document(page_content=doc.page_content, metadata={**doc.metadata, "distance": score})
            for doc, score in results]
