import uuid

import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from sqlalchemy import select

from api.dependencies import DBSession
from api.models.document import Document
from api.schemas.document import DocumentOut
from api.services.ingest import extract_text, index_document, index_document_safely

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

router = APIRouter()


@router.get("", response_model=list[DocumentOut])
async def list_documents(db=DBSession):
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(file: UploadFile, background: BackgroundTasks, db=DBSession):
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    name = file.filename or "unnamed"
    try:
        content = await asyncio.to_thread(extract_text, raw, name, file.content_type)
    except Exception as exc:
        raise HTTPException(422, f"Could not extract text from {name}: {exc}")
    if not content.strip():
        raise HTTPException(422, f"No extractable text in {name} (scanned PDFs need OCR)")

    doc = Document(
        name=name,
        content=content,
        content_type=file.content_type or "text/plain",
        size_bytes=len(raw),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    # Embedding takes a few seconds on CPU; respond now and index after.
    background.add_task(index_document_safely, doc.id)
    return doc


@router.post("/{doc_id}/reindex")
async def reindex_document(doc_id: uuid.UUID, db=DBSession):
    if not await db.get(Document, doc_id):
        raise HTTPException(404, "Document not found")
    return {"id": str(doc_id), "chunks": await index_document(doc_id)}


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(doc_id: uuid.UUID, db=DBSession):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/{doc_id}/content")
async def get_document_content(doc_id: uuid.UUID, db=DBSession):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return {"id": str(doc.id), "name": doc.name, "content": doc.content, "content_type": doc.content_type}


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: uuid.UUID, db=DBSession):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    await db.delete(doc)
    await db.commit()
