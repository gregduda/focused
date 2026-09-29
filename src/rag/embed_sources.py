"""Embed the refund policy docs into a local Chroma database.

Run from the repo root:  python -m src.rag.embed_sources

Each doc is split by "##" section. Every chunk is prefixed with the doc title and doc_id so the
source survives retrieval, and carries the doc's front matter as metadata (status, authority, ...).
The index is rebuilt from scratch on every run.
"""
import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = (REPO_ROOT / os.environ["POLICY_DOCS_DIR"]).resolve()
CHROMA_DIR = str(REPO_ROOT / os.environ["CHROMA_DIR"])
COLLECTION = os.environ["CHROMA_COLLECTION"]

# Front matter fields stored as chunk metadata. Missing fields are skipped (Chroma rejects None).
METADATA_FIELDS = ["doc_id", "title", "doc_type", "status", "authority", "category", "state"]


def find_policy_files() -> list[Path]:
    """Every policy doc under DOCS_DIR, minus the corpus README (documentation, not policy)."""
    files = sorted(p for p in DOCS_DIR.rglob("*.md") if p.name != "README.md")
    return files


def split_front_matter(text: str) -> tuple[dict, str]:
    _, front, body = text.split("---", 2)
    return yaml.safe_load(front), body.strip()


def chunk_doc(path: Path) -> list[Document]:
    meta, body = split_front_matter(path.read_text(encoding="utf-8"))
    base_meta = {k: str(meta[k]) for k in METADATA_FIELDS if meta.get(k) is not None}
    base_meta["source"] = str(path.relative_to(REPO_ROOT))
    prefix = f"{meta['title']} ({meta['doc_id']})"

    # Split before each "## " heading. Anything before the first one is the H1 plus any preamble.
    parts = re.split(r"^(?=## )", body, flags=re.MULTILINE)
    chunks = []
    for part in parts:
        part = part.strip()
        if part.startswith("# "):  # preamble: drop the H1 title line, keep any text under it
            part = part.split("\n", 1)[1].strip() if "\n" in part else ""
            section = "Overview"
        else:
            section = part.split("\n", 1)[0].removeprefix("## ").strip()
        if not part:
            continue
        chunks.append(
            Document(
                page_content=f"{prefix}\n{part}",
                metadata={**base_meta, "section": section},
            )
        )
    return chunks


def main() -> None:
    docs = [chunk for path in find_policy_files() for chunk in chunk_doc(path)]
    # Ids are doc_id::n with n restarting per doc, so they stay stable when other docs change.
    counts: dict[str, int] = {}
    ids = []
    for d in docs:
        n = counts.get(d.metadata["doc_id"], 0)
        ids.append(f"{d.metadata['doc_id']}::{n}")
        counts[d.metadata["doc_id"]] = n + 1

    store = Chroma(
        collection_name=COLLECTION,
        embedding_function=OpenAIEmbeddings(), #By default, Chroma uses all-MiniLM-L6-v2 embeddings locally
        persist_directory=CHROMA_DIR,
    )
    store.reset_collection()  # rebuild from scratch so removed docs don't linger
    store.add_documents(docs, ids=ids)
    print(f"Indexed {len(docs)} chunks from {len(counts)} docs into '{COLLECTION}' at {CHROMA_DIR}")


if __name__ == "__main__":
    main()
