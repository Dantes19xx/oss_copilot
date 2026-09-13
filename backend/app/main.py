import os
import uuid
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv(override=True)

from backend.graph.graph import review_app  # noqa: E402
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
    result = await review_app.ainvoke({"user_request": request.message}, config=config)
    return _to_response(thread_id, result)


@app.post("/api/agent/resume", response_model=AgentResponse)
async def resume_agent(request: ResumeRequest) -> AgentResponse:
    config = {"configurable": {"thread_id": request.thread_id}}
    result = await review_app.ainvoke(Command(resume=request.answer), config=config)
    return _to_response(request.thread_id, result)
