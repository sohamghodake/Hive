"""Chunking and embeddings shared by ingestion (api) and retrieval (mcp-db).

Both sides must use the same model: a query embedded with one model and passages
embedded with another produce similarity scores that mean nothing. Keeping the
model id here, imported by both images, is what guarantees that.

Embeddings run locally via fastembed (ONNX, CPU) — no API key, no per-call cost.
"""
from __future__ import annotations

import os
import re
import threading

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIM = 384  # must match the vector(...) column in migration 002

CHUNK_CHARS = 1000   # ~250 tokens; bge-small truncates input at 512 tokens
CHUNK_OVERLAP = 150  # carries context across a boundary so a clause is not split blind

# Memory scales with batch size × sequence length × threads. Unbounded, a
# 400 KB document went to ONNX in one batch on every core and the kernel OOM
# killer took the API down — then the startup backfill retried it, crash-looping.
EMBED_BATCH = int(os.getenv("EMBED_BATCH_SIZE", "16"))
EMBED_THREADS = int(os.getenv("EMBED_THREADS", "2"))

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from fastembed import TextEmbedding

                _model = TextEmbedding(
                    MODEL_NAME,
                    cache_dir=os.getenv("FASTEMBED_CACHE_PATH"),
                    threads=EMBED_THREADS,
                )
    return _model


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph then sentence breaks.

    A hard character cut can land mid-sentence; breaking on structure first keeps
    each chunk readable when it is shown back to the model as evidence.
    """
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []

    pieces: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= size:
            pieces.append(para)
            continue
        # Oversized paragraph: fall back to sentences, then to a hard split.
        for sent in re.split(r"(?<=[.!?])\s+", para):
            while len(sent) > size:
                pieces.append(sent[:size])
                sent = sent[size - overlap:]
            if sent:
                pieces.append(sent)

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + 1 + len(piece) > size:
            chunks.append(current)
            tail = current[-overlap:].split(" ", 1)[-1] if overlap else ""
            current = f"{tail} {piece}" if tail else piece
        else:
            current = f"{current}\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed document chunks. CPU-bound: call through asyncio.to_thread."""
    return [v.tolist() for v in _get_model().passage_embed(texts, batch_size=EMBED_BATCH)]


def embed_query(text: str) -> list[float]:
    """Embed a search query. bge models use a different prefix for queries than
    passages; fastembed's query_embed applies it."""
    return next(iter(_get_model().query_embed(text))).tolist()


def to_pgvector(vec: list[float]) -> str:
    """Serialise for a `$1::vector` parameter."""
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"
