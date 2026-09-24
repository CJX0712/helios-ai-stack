# 作者：晨星
"""FastAPI 应用：/query、/health、/diagnostics（ARCH §7 / T12）。"""

from __future__ import annotations

import os

from typing import Any

from pydantic import BaseModel

from ..core import codes
from ..core.config import ProfileConfig
from ..core.errors import raise_for
from ..pipeline import Pipeline
from .error_handler import register_error_handlers


class QueryRequest(BaseModel):
    """/query 请求体。"""

    question: str
    top_k: int | None = None


class IngestRequest(BaseModel):
    """/ingest 请求体。"""

    text: str
    source: str = ""


class QueryResponse(BaseModel):
    """/query 响应体。"""

    query: str
    text: str
    citations: list[dict]
    timings: dict
    profile: str


def create_app(profile: str | None = None) -> Any:
    """构造 FastAPI 应用；profile 由环境变量或参数决定。"""
    from fastapi import FastAPI

    selected = profile or os.environ.get("HELIOS_PROFILE", "offline")
    cfg = ProfileConfig.from_env({"HELIOS_PROFILE": selected})
    pipe = Pipeline(cfg)

    app = FastAPI(title="helios-ai-stack", version="1.0.0")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "profile": cfg.profile, "docs": pipe.document_count, "chunks": pipe.chunk_count}

    @app.get("/diagnostics")
    def diagnostics() -> dict:
        return {
            "profile": cfg.profile,
            "embedder": pipe.embedder.diagnostics(),
            "reranker": pipe.reranker.diagnostics(),
            "llm": pipe.llm.diagnostics(),
        }

    @app.post("/ingest", response_model=dict)
    def ingest(req: IngestRequest) -> dict:
        doc = pipe.add_document(req.text, req.source)
        if doc is None:
            return {"ingested": False, "doc_id": None, "docs": pipe.document_count}
        return {"ingested": True, "doc_id": doc.doc_id, "docs": pipe.document_count}

    @app.post("/query", response_model=QueryResponse)
    def query(req: QueryRequest) -> QueryResponse:
        if not req.question or not req.question.strip():
            raise raise_for(codes.E_API_BAD_REQUEST, message="空问题")
        ans = pipe.query(req.question, top_k=req.top_k)
        return QueryResponse(
            query=ans.query,
            text=ans.text,
            citations=[c.to_dict() for c in ans.citations],
            timings=ans.timings,
            profile=ans.profile,
        )

    register_error_handlers(app)
    return app


def run_server(profile: str | None = None, host: str = "127.0.0.1", port: int = 8000) -> None:
    """以 uvicorn 拉起服务。"""
    import uvicorn

    app = create_app(profile)
    uvicorn.run(app, host=host, port=port, log_level="info")
