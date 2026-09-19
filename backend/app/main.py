import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv(override=True)

from backend.graph.graph import review_app  # noqa: E402
from backend.rag.document_ingest import SUPPORTED_SUFFIXES, ingest_document  # noqa: E402
from langgraph.types import Command  # noqa: E402

app = FastAPI(title="OSS Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class StartRequest(BaseModel):
    message: str
    language: Literal["ru", "en"] = "en"


class ResumeRequest(BaseModel):
    thread_id: str
    answer: str


class AgentResponse(BaseModel):
    """Mirrors the interrupt/resume loop backend/graph/run_agent.py already drives over
    the CLI — the frontend runs the same loop over HTTP instead of stdin/stdout."""

    status: Literal["interrupt", "done"]
    thread_id: str
    payload: dict[str, Any] | None = None
    summary: str | None = None


def _to_response(thread_id: str, result: dict) -> AgentResponse:
    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        return AgentResponse(status="interrupt", thread_id=thread_id, payload=payload)
    return AgentResponse(status="done", thread_id=thread_id, summary=result.get("summary", "(no summary produced)"))


@app.post("/api/agent/start", response_model=AgentResponse)
async def start_agent(request: StartRequest) -> AgentResponse:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    result = await review_app.ainvoke(
        {"user_request": request.message, "language": request.language}, config=config
    )
    return _to_response(thread_id, result)


@app.post("/api/agent/resume", response_model=AgentResponse)
async def resume_agent(request: ResumeRequest) -> AgentResponse:
    config = {"configurable": {"thread_id": request.thread_id}}
    result = await review_app.ainvoke(Command(resume=request.answer), config=config)
    return _to_response(request.thread_id, result)


class StyleGuideUploadResponse(BaseModel):
    repo: str
    source: str
    chunks: int


MAX_STYLE_GUIDE_BYTES = 10 * 1024 * 1024
# A coding-standards document is text, not media — 10 MB is generous headroom, not a
# real limit for the intended use, while still bounding an unauthenticated upload.


@app.post("/api/style-guide/upload", response_model=StyleGuideUploadResponse)
async def upload_style_guide(
    owner: str = Form(...), repo: str = Form(...), file: UploadFile = File(...)
) -> StyleGuideUploadResponse:
    # .name (not the raw filename) so a crafted "../../etc/passwd"-style filename can't
    # escape the temp directory below — it also becomes the "source" stored in Qdrant,
    # so keeping the real filename (unlike a NamedTemporaryFile's random name) matters
    # for anyone inspecting the collection later, not just for safety.
    original_name = Path(file.filename or "").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(400, f"Unsupported file type {suffix!r} — expected .pdf or .docx")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / original_name
        size = 0
        with tmp_path.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_STYLE_GUIDE_BYTES:
                    raise HTTPException(413, f"File too large (max {MAX_STYLE_GUIDE_BYTES // (1024 * 1024)} MB)")
                f.write(chunk)

        # Same ingest_document() the CLI (backend/rag/document_ingest.py) calls — one
        # parsing/chunking/embedding path, not a duplicate reimplementation for the API.
        result = await ingest_document(owner, repo, tmp_path)
    return StyleGuideUploadResponse(**result)
