"""
RAG endpoints - upload knowledge documents and ask questions grounded in them.

  POST   /api/rag/upload        (multipart file OR {title, text})
  GET    /api/rag/documents     list uploaded docs
  DELETE /api/rag/documents/{id}
  POST   /api/rag/ask           {question} -> answer grounded in documents
"""
import json
from fastapi import APIRouter, Body, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..routers.auth import get_current_user
from ..models.user import User
from ..models.knowledge import KnowledgeDocument
from ..core import rag_service, ai_service

router = APIRouter()


@router.post("/api/rag/upload")
async def upload_document(
    file: UploadFile = File(None),
    title: str = Form(None),
    text: str = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a PDF/text file OR paste raw text to add to the knowledge base."""
    doc_title = title or (file.filename if file else "Untitled")
    filename = file.filename if file else None

    if file is not None:
        raw = await file.read()
        content = rag_service.extract_text(file.filename, raw)
    elif text:
        content = text
    else:
        return {"success": False, "message": "Provide a file or text"}

    if not content.strip():
        return {"success": False, "message": "Could not extract any text from the document"}

    chunks = rag_service.chunk_text(content)
    doc = KnowledgeDocument(
        title=doc_title,
        filename=filename,
        chunks=json.dumps(chunks),
        char_count=len(content),
        chunk_count=len(chunks),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"success": True, "message": f"Document added ({len(chunks)} chunks)",
            "document": {"id": doc.id, "title": doc.title, "chunk_count": doc.chunk_count, "char_count": doc.char_count}}


@router.get("/api/rag/documents")
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = db.query(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).all()
    return {"success": True, "documents": [
        {"id": d.id, "title": d.title, "filename": d.filename,
         "chunk_count": d.chunk_count, "char_count": d.char_count,
         "created_at": d.created_at.isoformat() if d.created_at else None}
        for d in docs
    ]}


@router.delete("/api/rag/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
    if not doc:
        return {"success": False, "message": "Document not found"}
    db.delete(doc)
    db.commit()
    return {"success": True, "message": "Document deleted"}


@router.post("/api/rag/ask")
def rag_ask(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Answer a question using the uploaded knowledge documents (RAG)."""
    question = (payload.get("question") or "").strip()
    if not question:
        return {"success": False, "message": "No question provided"}

    # gather all chunks from all documents
    docs = db.query(KnowledgeDocument).all()
    all_chunks = []
    for d in docs:
        try:
            all_chunks.extend(json.loads(d.chunks or "[]"))
        except Exception:
            pass

    if not all_chunks:
        # no documents -> fall back to normal AI
        result = ai_service.ask_question(question)
        result["grounded"] = False
        result["source"] = "general knowledge (no documents uploaded)"
        return result

    # retrieve relevant chunks
    relevant = rag_service.retrieve(question, all_chunks, top_k=4)
    if not relevant:
        result = ai_service.ask_question(question)
        result["grounded"] = False
        result["source"] = "general knowledge (no relevant document sections found)"
        return result

    context = "\n\n---\n\n".join(relevant)
    prompt = (
        "You are a marine inspection assistant. Answer the question using ONLY the "
        "reference material below when relevant. If the material does not cover it, say so "
        "and then give general guidance.\n\n"
        f"REFERENCE MATERIAL:\n{context}\n\n"
        f"QUESTION: {question}"
    )
    result = ai_service.ask_question(prompt)
    result["grounded"] = True
    result["source"] = f"{len(relevant)} document section(s)"
    return result