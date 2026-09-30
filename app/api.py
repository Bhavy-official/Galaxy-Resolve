"""REST API: POST /v1/troubleshoot, GET /health."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional, Union

import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.engine import Engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = Path(__file__).resolve().parent / "static"


class SiisResponse(BaseModel):
    title: str = ""
    content: str = ""


class TroubleshootRequest(BaseModel):
    query: str
    siis_response: Optional[Union[SiisResponse, str]] = None


engine = Engine()


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine.load()  # models, catalog index and cache DB load once at startup
    yield


app = FastAPI(title="GalaxyResolve", version="1.0.0", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def index():
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<h1>Galaxy Resolve API</h1><p>Visit /health or /docs</p>"


@app.get("/health")
def health() -> JSONResponse:

    ok = engine.ready
    body = {
        "status": "ok" if ok else "loading",
        "models": engine.models.ready,
        "catalog": engine.catalog is not None,
        "cache": engine.store is not None,
        "cached_plans": engine.store.n_plans if engine.store else 0,
        "llm": engine.use_llm,
    }
    return JSONResponse(body, status_code=200 if ok else 503)


@app.post("/v1/troubleshoot")
def troubleshoot(req: TroubleshootRequest) -> JSONResponse:
    siis = req.siis_response
    if isinstance(siis, str):
        siis = SiisResponse(content=siis)
    result = engine.troubleshoot(req.query, siis.model_dump() if siis else None)
    return JSONResponse(result)


@app.post("/v1/troubleshoot/stream")
async def troubleshoot_stream(req: TroubleshootRequest):
    async def event_generator():
        yield f"data: {json.dumps({'stage': 'normalize', 'message': 'Normalizing query & extracting slots...'})}\n\n"
        siis = req.siis_response
        if isinstance(siis, str):
            siis = SiisResponse(content=siis)
        
        hit = engine.lookup(req.query) if req.query else None
        if hit:
            yield f"data: {json.dumps({'stage': 'cache_hit', 'message': 'Sub-300ms Cache Hit! Serving cached plan.'})}\n\n"
            plan, sim = hit
            res = engine._respond(plan.plan, 0.0, cache_hit=True, model=plan.model, similarity=sim)
            yield f"data: {json.dumps({'stage': 'completed', 'result': res})}\n\n"
            return

        yield f"data: {json.dumps({'stage': 'llm_enrich', 'message': 'Enriching problem domain & title...'})}\n\n"
        yield f"data: {json.dumps({'stage': 'grounding', 'message': 'Verifying sentence grounding from context...'})}\n\n"
        yield f"data: {json.dumps({'stage': 'deeplink_catalog', 'message': 'Matching target settings to catalog URIs...'})}\n\n"
        
        result = engine.troubleshoot(req.query, siis.model_dump() if siis else None)
        yield f"data: {json.dumps({'stage': 'completed', 'result': result})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

