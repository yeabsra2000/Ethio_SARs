"""AI / RAG explanation endpoints."""

from fastapi import APIRouter

from app.schemas import AnalyzeChangeRequest, AnalyzeChangeResponse
from app.services.rag_engine import get_engine_status, rag_engine

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post(
    "/analyze-change",
    response_model=AnalyzeChangeResponse,
    summary="Explain a SAR change with Gemini + RAG",
)
def analyze_change(request: AnalyzeChangeRequest) -> AnalyzeChangeResponse:
    """Explain radar backscatter changes between two curated scenes."""

    return rag_engine.analyze_change(request)


@router.get(
    "/status",
    summary="RAG engine diagnostics",
)
def ai_status() -> dict:
    """Return knowledge-base and Gemini configuration status."""

    return get_engine_status()
