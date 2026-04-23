"""
main.py — FastAPI Backend Server for AI College Data Assistant

This is the REST API layer that:
  1. Initializes the SQLite database on startup
  2. Exposes a /query endpoint for natural language queries
  3. Routes requests through Context Engine → Decision Engine
  4. Returns structured JSON responses

Run with:  uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import os

import db
import logic

# ---------------------------------------------------------------------------
# FastAPI App Initialization
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI College Data Assistant",
    description="Natural language interface for college data queries, analytics, and policy lookup.",
    version="1.0.0"
)

# Allow Streamlit frontend to make cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # In production, restrict to Streamlit's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
llm_ready = False
llm_initializing = True

async def initialize_llm():
    """Initialize LLM in background to avoid blocking startup."""
    global llm_ready, llm_initializing
    try:
        from llm_router import get_router
        router = get_router()
        
        # Check if Ollama or OpenAI are actually running (async wrapper to prevent blocking)
        ollama_ok = await asyncio.to_thread(router.check_ollama)
        openai_ok = await asyncio.to_thread(router.check_openai)
        
        if ollama_ok:
            llm_ready = True
            print("[OK] LLM Router initialized - Ollama ready")
        elif openai_ok:
            llm_ready = True
            print("[OK] LLM Router initialized - OpenAI ready")
        else:
            llm_ready = False
            print("[WARN] LLM Router initialized but no models available")
    except Exception as e:
        llm_ready = False
        print(f"[ERROR] LLM initialization failed: {e}")
    finally:
        llm_initializing = False

# ---------------------------------------------------------------------------
# Startup Event — Initialize Database & LLM
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Initialize the database and start LLM loading in background."""
    # Initialize database (fast)
    db.init_db()
    print("[OK] Database initialized")
    
    # Start LLM initialization in background (don't wait for it)
    asyncio.create_task(initialize_llm())
    print("[OK] AI College Data Assistant API is ready!")


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """
    Incoming query from the frontend.

    Attributes:
        query:      Natural language question from the user
        role:       User role -- affects context and permissions
        llm_config: Optional LLM router overrides from the UI
    """
    query: str
    role: str = "student"
    llm_config: Optional[dict] = None  # e.g. {"strategy": "always_ollama", ...}


class QueryResponse(BaseModel):
    """
    Structured response returned to the frontend.

    Attributes:
        answer:      Main response text
        explanation: Why this result was generated (explainability)
        query_type:  How the query was classified (data/analytical/knowledge)
        data:        Raw data rows (if applicable)
        model_info:  Metadata about which LLM provider/model was used
        error:       Whether there was an error processing the query
    """
    answer: str
    explanation: str
    query_type: str
    data: Optional[list] = []
    model_info: Optional[dict] = None
    error: bool = False


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Fast health check - doesn't wait for LLM."""
    return {
        "status": "online",
        "service": "AI College Data Assistant",
        "database": "ready",
        "llm": "initializing" if llm_initializing else ("ready" if llm_ready else "error")
    }


@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Main endpoint: Accept a natural language query and return a structured response.
    """
    global llm_initializing, llm_ready
    
    # Wait for LLM if not ready yet
    if llm_initializing:
        # Wait up to 30 seconds for LLM to initialize
        for _ in range(30):
            if not llm_initializing:
                break
            await asyncio.sleep(1)
        
        if llm_initializing:
            return QueryResponse(
                answer="LLM is still initializing. Please try again in a few seconds.",
                explanation="Backend timeout waiting for LLM initialization.",
                query_type="unknown",
                error=True
            )

    # Validate input
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Validate role
    valid_roles = ["student", "teacher", "admin"]
    role = request.role.lower().strip()
    if role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{request.role}'. Must be one of: {valid_roles}"
        )

    try:
        # Process through the full pipeline, passing LLM config from UI
        result = await asyncio.to_thread(
            logic.process_query,
            query=request.query,
            role=role,
            llm_config=request.llm_config,
        )

        return QueryResponse(
            answer=result["answer"],
            explanation=result["explanation"],
            query_type=result["query_type"],
            data=result.get("data", []),
            model_info=result.get("model_info"),
            error=False
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


@app.get("/session-memory")
def get_session_memory():
    """Return the current session memory (last 3 queries) for debugging/display."""
    return {
        "role": logic.context_engine.user_role,
        "memory": logic.context_engine.get_memory_display()
    }


@app.get("/llm-status")
def llm_status():
    """Return LLM status without blocking."""
    if llm_initializing:
        return {
            "status": "initializing",
            "ollama": False,
            "openai": False,
            "message": "LLM is still loading in the background..."
        }
    
    from llm_router import get_router
    router = get_router()
    
    return {
        "status": "ready" if llm_ready else "error",
        "ollama": router.check_ollama(),
        "openai": router.check_openai(),
        "strategy": router.strategy,
        "token_threshold": router.token_threshold,
        # Legacy fields for backward compatibility with older app.py versions
        "ollama_ready": router.check_ollama(),
        "openai_ready": router.check_openai()
    }
