from fastapi import APIRouter, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from app.company_support.service import execute_company_support_rag
from app.company_support.vectorstore import ingest_company_knowledge

router = APIRouter(
    prefix="/api/v1/company-support",
    tags=["Company Support Chatbot"],
)

class ChatRequest(BaseModel):
    message: str = Field(..., description="The user query or message for the support assistant.")
    history: Optional[List[dict]] = Field(default=None, description="Optional chat history list of dicts with role and content.")

class ChatResponse(BaseModel):
    query: str
    response: str
    sources: List[str]
    status: str

@router.post("/chat", response_model=ChatResponse)
def company_support_chat(payload: ChatRequest):
    """
    POST endpoint to interact with the isolated General Company Support Chatbot.
    Uses RAG based on the files in backend/knowledge_base/.
    """
    res = execute_company_support_rag(payload.message, payload.history)
    return res

@router.post("/ingest")
def trigger_knowledge_ingestion(
    background_tasks: BackgroundTasks,
    force: bool = Query(default=False, description="Whether to clear existing collection before inserting.")
):
    """
    POST endpoint to rebuild the company support vector store from raw files.
    Runs asynchronously as a background task.
    """
    background_tasks.add_task(ingest_company_knowledge, force=force)
    return {
        "status": "accepted",
        "message": "Company knowledge base ingestion has been triggered in the background."
    }

@router.get("/health")
def company_support_health():
    """
    Simple health check for the company support module.
    """
    return {
        "status": "healthy",
        "module": "company_support"
    }
