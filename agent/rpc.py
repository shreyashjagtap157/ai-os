"""
HTTP RPC for controlling the agent (FastAPI app).
"""
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Any
from starlette.responses import PlainTextResponse

import os

app = FastAPI(title="AI-OS Agent RPC")


class ExecuteRequest(BaseModel):
    command: str
    args: list[str] = []


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.post("/execute")
async def execute(req: ExecuteRequest):
    # handler should be injected by async agent at runtime
    if not hasattr(app.state, "registry"):
        raise HTTPException(status_code=503, detail="Agent not ready")
    # API key auth
    api_key = None
    if hasattr(app.state, "api_key"):
        api_key = app.state.api_key
    # If api_key is set, require header
    if api_key:
        # check Authorization or x-api-key
        auth = req.scope.get("headers")
        headers = {k.decode(): v.decode() for k, v in auth}
        provided = headers.get("authorization") or headers.get("x-api-key")
        if not provided:
            raise HTTPException(status_code=401, detail="Missing API key")
        if provided.lower().startswith("bearer "):
            provided = provided.split(" ", 1)[1]
        if provided != api_key:
            raise HTTPException(status_code=403, detail="Invalid API key")

    registry = app.state.registry
    try:
        result = registry.execute(req.command, req.args)
        return {"ok": bool(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def metrics():
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

        data = generate_latest()
        return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
