"""Smoke tests for the retriever. Run with:  pytest tests/rag -s

-s shows the printed chunk listings. These tests embed queries locally (no API calls)
and need the index built first (python -m src.rag.embed_sources). They only check the shape of the
results. Whether the *right* chunks come back is measured in the evals, not here.
"""
import pytest

from src.rag.chunk_retriever import DEFAULT_TOP_K, retrieve

SAMPLE_QUERIES = [
    "What is the restocking fee for opened electronics shipped to California?",
    "How long do I have to return a bookshelf?",
    "Holiday return deadline for electronics",
    "Can I return a doorbuster?",
    "My package says delivered but I never got it",
    "Your website says love it or send it back anytime",
]


def print_chunks(query: str, chunks) -> None:
    print(f"\n=== {query}")
    for rank, c in enumerate(chunks, start=1):
        m = c.metadata
        preview = c.page_content.split("\n", 1)[1][:110].replace("\n", " ")
        print(f"{rank}. {m['doc_id']:7} | {m['section'][:32]:32} | {m['status']:10} {m['authority']:17} "
              f"| dist {m['distance']:.3f}\n     {preview}")


@pytest.mark.parametrize("query", SAMPLE_QUERIES)
def test_retrieves_top_k_chunks(query):
    chunks = retrieve(query)
    print_chunks(query, chunks)

    assert len(chunks) == DEFAULT_TOP_K
    for c in chunks:
        assert c.metadata["doc_id"] in c.page_content.split("\n", 1)[0]  # chunk is prefixed with its source
        assert {"status", "authority", "section", "source"} <= c.metadata.keys()
    distances = [c.metadata["distance"] for c in chunks]
    assert distances == sorted(distances)  # best first


def test_k_is_respected():
    assert len(retrieve("return window", k=2)) == 2


STALE_DOCS = {"ARC-01", "ARC-02", "SUP-01", "SUP-02", "MKT-01"}
STALE_TRAP = ("I'm a Peak member and your returns FAQ says furniture can come back within 60 days. "
              "The bookshelf is too big for the room.")


def test_authoritative_only_leaves_stale_documents_out_of_the_search():
    assert STALE_DOCS & {c.metadata["doc_id"] for c in retrieve(STALE_TRAP)}  # v1 still returns them
    filtered = retrieve(STALE_TRAP, authoritative_only=True)
    assert len(filtered) == DEFAULT_TOP_K
    assert all(c.metadata["status"] == "active" and c.metadata["authority"] == "authoritative" for c in filtered)
    assert not STALE_DOCS & {c.metadata["doc_id"] for c in filtered}


def test_scope_to_the_orders_category_and_state():
    seen_cat, seen_state = set(), set()
    for query in SAMPLE_QUERIES + ["return window", "how much is the fee", STALE_TRAP]:
        for c in retrieve(query, k=12, category="electronics", state="WA"):
            m = c.metadata
            if m["doc_type"] == "category_policy":
                seen_cat.add(m["category"])
            if m["doc_type"] == "state_addendum":
                seen_state.add(m["state"])
    assert seen_cat <= {"electronics", "hygiene_personal_care"}  # CAT-03 stays searchable (swimwear, earbuds)
    assert seen_state <= {"WA", "ALL"}
    assert retrieve("return window", k=12) != retrieve("return window", k=12, category="electronics", state="WA")
