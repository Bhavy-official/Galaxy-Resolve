"""REST API: POST /v1/troubleshoot, GET /health."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional, Union

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.engine import Engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


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
