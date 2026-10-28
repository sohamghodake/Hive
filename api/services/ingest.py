"""Document ingestion: text extraction, chunking, embedding, and storage."""
from __future__ import annotations

import asyncio
import io
import logging
import uuid

from sqlalchemy import delete, select

from api.models.document import Document, Embedding
from db.session import _session_factory
from rag.embeddings import chunk_text, embed_passages

logger = logging.getLogger(__name__)

# Embedding is CPU-bound; running every upload at once would starve the event
# loop's threads, so ingestion is serialised.
_ingest_lock = asyncio.Lock()
INGEST_SLICE = 64


def extract_text(raw: bytes, filename: str, content_type: str | None) -> str:
    """Return the document's text. PDFs are parsed; everything else is decoded.

    Decoding a PDF as UTF-8 (the previous behaviour) stores binary noise, which
    then embeds as noise and can never be retrieved.
    """
    is_pdf = (content_type or "").lower() == "application/pdf" or filename.lower().endswith(".pdf")
    if not is_pdf:
        return raw.decode("utf-8", errors="replace")

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(p for p in pages if p)


async def index_document(document_id: uuid.UUID) -> int:
    """(Re)build a document's embeddings. Returns the number of chunks stored."""
    async with _ingest_lock, _session_factory() as db:
        doc = await db.get(Document, document_id)
        if doc is None:
            return 0
        chunks = chunk_text(doc.content)
        await db.execute(delete(Embedding).where(Embedding.document_id == document_id))

        # Embed in slices so peak memory is bounded by the slice, not the
        # document, and the event loop gets control back between slices.
        for start in range(0, len(chunks), INGEST_SLICE):
            part = chunks[start:start + INGEST_SLICE]
            vectors = await asyncio.to_thread(embed_passages, part)
            db.add_all(
                Embedding(document_id=document_id, chunk_index=start + i, chunk_text=text, embedding=vec)
                for i, (text, vec) in enumerate(zip(part, vectors, strict=True))
            )
            await db.flush()
        doc.embedded = bool(chunks)
        await db.commit()

    logger.info("indexed document %s: %d chunks", document_id, len(chunks))
    return len(chunks)


async def index_document_safely(document_id: uuid.UUID) -> None:
    """Background-task wrapper: a failed index must not crash the worker."""
    try:
        await index_document(document_id)
    except Exception:
        logger.exception("indexing failed for document %s", document_id)


async def backfill_unindexed() -> None:
    """Index every document not yet embedded — e.g. after migration 002 resets them."""
    async with _session_factory() as db:
        ids = (await db.execute(select(Document.id).where(Document.embedded.is_(False)))).scalars().all()
    for doc_id in ids:
        await index_document_safely(doc_id)
    if ids:
        logger.info("backfilled embeddings for %d document(s)", len(ids))
