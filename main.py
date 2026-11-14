"""Local synthetic-data demo API. Roles describe response style, not permissions."""

import asyncio
import hmac
import ipaddress
import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

import db
import logic
from llm_router import get_router


async def require_access(request: Request):
    expected = os.getenv("CAMPUS_API_TOKEN", "")
    if expected:
        supplied = request.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied.encode(), f"Bearer {expected}".encode()):
            raise HTTPException(status_code=401, detail="API access token required")
    else:
        try:
            local = ipaddress.ip_address(request.client.host).is_loopback
        except (ValueError, AttributeError):
            local = False
        if not local:
            raise HTTPException(status_code=403, detail="Remote access requires CAMPUS_API_TOKEN")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="CampusOracle AI — synthetic-data demo",
    description="Local prototype: SQL queries, rule-based analytics, and ranked policy search.",
    version="1.1.0", lifespan=lifespan, dependencies=[Depends(require_access)],
    # The Streamlit server calls this API directly; browser CORS is unnecessary.
    docs_url=None, redoc_url=None, openapi_url=None,
)


class HistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(max_length=4000)
    response: str = Field(max_length=2000)


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ollama_model: str | None = Field(default=None, max_length=200)
    strategy: Literal["offline", "auto", "always_ollama", "always_openai", "always_gemini"] | None = None
    allow_cloud: bool = False


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=4000)
    # This is presentation context. There is no institutional RBAC implementation.
    role: Literal["student", "teacher", "admin"] = "student"
    llm_config: LLMConfig | None = None
    history: list[HistoryItem] = Field(default_factory=list, max_length=3)


class PolicySource(BaseModel):
    number: int
    document: str
    section: str
    start_line: int
    end_line: int
    excerpt: str


class QueryResponse(BaseModel):
    answer: str
    explanation: str
    query_type: str
    data: list = Field(default_factory=list)
    sources: list[PolicySource] = Field(default_factory=list)
    model_info: dict | None = None
    error: bool = False


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Default validation errors echo input, which could include private query text.
    return JSONResponse(status_code=422, content={"detail": "Invalid request fields or values"})


@app.get("/health")
def health_check():
    return {"status": "online", "service": "CampusOracle AI", "data": "synthetic demo"}


@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    try:
        result = await asyncio.to_thread(
            logic.process_query, query=request.query, role=request.role,
            llm_config=request.llm_config.model_dump(exclude_none=True) if request.llm_config else None,
            history=[item.model_dump() for item in request.history],
        )
        return QueryResponse(**result)
    except Exception:
        # Do not return exception text or log prompts, keys, or student data.
        raise HTTPException(status_code=500, detail="Unable to process query") from None


@app.get("/llm-status")
def llm_status():
    # No probe of remote APIs and no credentials in this response.
    return {**get_router().get_status(),
            "cloud_enabled_by_operator": os.getenv("ALLOW_CLOUD_LLM", "false").lower() == "true"}
