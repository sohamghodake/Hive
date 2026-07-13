import uuid

from fastapi import APIRouter, HTTPException, UploadFile
from sqlalchemy import select

from api.dependencies import DBSession
from api.models.document import Document
from api.schemas.document import DocumentOut

router = APIRouter()


@router.get("", response_model=list[DocumentOut])
async def list_documents(db=DBSession):
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(file: UploadFile, db=DBSession):
    raw = await file.read()
    content = raw.decode("utf-8", errors="replace")
    doc = Document(
        name=file.filename or "unnamed",
        content=content,
        content_type=file.content_type or "text/plain",
        size_bytes=len(raw),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


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
