"""Plot the indexed policy chunks in 2D so you can see how they cluster.

Run from the repo root:  python -m src.rag.plot_chunks
Writes CHROMA_CHUNK_PLOT_DIR/chunks.html. Open it in a browser; use the dropdown to color by a metadata field
and hover a point to see the doc and section.

Reads the vectors already stored in Chroma (no embedding API calls). Uses t-SNE with cosine distance.
A 2D projection distorts distances: nearby points are similar, but do not read exact gaps from it.
"""
import os
from pathlib import Path

import chromadb
import numpy as np
import plotly.graph_objects as go
from dotenv import load_dotenv
from sklearn.manifold import TSNE

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = str(REPO_ROOT / os.environ["CHROMA_DIR"])
COLLECTION = os.environ["CHROMA_COLLECTION"]
OUT_FILE = REPO_ROOT / os.environ["CHROMA_CHUNK_PLOT_DIR"] / "chunks.html"

COLOR_FIELDS = ["authority", "status", "doc_type", "category", "state"]
UNSET = "(none)"  # category and state exist only on some docs


def load_chunks() -> tuple[np.ndarray, list[dict], list[str]]:
    coll = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(COLLECTION)
    data = coll.get(include=["embeddings", "metadatas", "documents"])
    return np.array(data["embeddings"]), data["metadatas"], data["documents"]


def project_2d(vectors: np.ndarray) -> np.ndarray:
    # random_state fixed so the picture is the same on every run.
    perplexity = min(15, len(vectors) - 1)
    return TSNE(n_components=2, metric="cosine", perplexity=perplexity, random_state=0).fit_transform(vectors)


def hover_text(meta: dict, doc: str) -> str:
    preview = doc.split("\n", 1)[1][:160].replace("\n", " ")
    return (
        f"<b>{meta['doc_id']}</b> | {meta['section']}<br>"
        f"{meta['status']} / {meta['authority']}<br>{preview}..."
    )


def build_figure(xy: np.ndarray, metas: list[dict], docs: list[str]) -> go.Figure:
    hovers = [hover_text(m, d) for m, d in zip(metas, docs)]
    fig = go.Figure()
    trace_field: list[str] = []  # which color field each trace belongs to

    for field in COLOR_FIELDS:
        values = [m.get(field, UNSET) for m in metas]
        for value in sorted(set(values)):
            idx = [i for i, v in enumerate(values) if v == value]
            fig.add_trace(
                go.Scatter(
                    x=xy[idx, 0], y=xy[idx, 1], mode="markers", name=value,
                    text=[hovers[i] for i in idx], hoverinfo="text",
                    marker=dict(size=9, opacity=0.8),
                    visible=(field == COLOR_FIELDS[0]),
                    legendgroup=field,
                )
            )
            trace_field.append(field)

    buttons = [
        dict(label=f"color by {field}", method="update",
             args=[{"visible": [tf == field for tf in trace_field]}])
        for field in COLOR_FIELDS
    ]
    fig.update_layout(
        title="Policy chunks in embedding space (t-SNE, cosine)",
        updatemenus=[dict(buttons=buttons, direction="down", x=0.0, y=1.15, xanchor="left")],
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        height=800, hovermode="closest",
    )
    return fig


def main() -> None:
    vectors, metas, docs = load_chunks()
    fig = build_figure(project_2d(vectors), metas, docs)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(OUT_FILE, include_plotlyjs="cdn")
    print(f"Wrote {len(vectors)} points to {OUT_FILE}")


if __name__ == "__main__":
    main()
