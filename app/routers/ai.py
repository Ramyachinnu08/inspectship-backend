"""
AI endpoints for InspectShip.

Routes (mounted under /api via main.py or with the /api prefix in paths):
  POST /api/ai/analyze-image   { image, question? }
  POST /api/ai/compare-images  { before, after, context? }
  POST /api/ai/ask             { question, context? }
  GET  /api/ai/status          -> whether AI is configured
"""
from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..routers.auth import get_current_user
from ..models.user import User
from ..core import ai_service

router = APIRouter()


@router.get("/api/ai/status")
def ai_status(user: User = Depends(get_current_user)):
    return {"success": True, "configured": ai_service.is_configured(), "model": ai_service.MODEL}


@router.post("/api/ai/analyze-image")
def analyze_image(payload: dict = Body(...), user: User = Depends(get_current_user)):
    image = payload.get("image") or ""
    question = payload.get("question") or ""
    if not image:
        return {"success": False, "message": "No image provided"}
    return ai_service.analyze_image(image, question)


@router.post("/api/ai/compare-images")
def compare_images(payload: dict = Body(...), user: User = Depends(get_current_user)):
    before = payload.get("before") or ""
    after = payload.get("after") or ""
    context = payload.get("context") or ""
    if not before or not after:
        return {"success": False, "message": "Both before and after images are required"}
    return ai_service.compare_images(before, after, context)


@router.post("/api/ai/ask")
def ask(payload: dict = Body(...), user: User = Depends(get_current_user)):
    question = payload.get("question") or ""
    context = payload.get("context") or ""
    if not question:
        return {"success": False, "message": "No question provided"}
    return ai_service.ask_question(question, context)