"""POST /v1/troubleshoot — the scored endpoint. Always 200 with a schema-valid body."""
import time

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.config import settings
from app.schema import ContextDeeplinkResponse

router = APIRouter()


class TroubleshootRequest(BaseModel):
    query: str
    siis_response: dict | str | None = None


@router.post("/v1/troubleshoot")
def troubleshoot(req: TroubleshootRequest, response: Response) -> dict:
    start = time.perf_counter()
    # TODO(A): call app.pipeline.run.run(req.query, req.siis_response)
    result = ContextDeeplinkResponse(contexts=[])
    latency_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Latency-Ms"] = str(latency_ms)
    response.headers["X-Cache-Hit"] = "false"
    body = result.model_dump(mode="json")
    if settings.include_meta:
        body["meta"] = {"latency_ms": latency_ms, "cache_hit": False, "cost_usd": 0.0,
                        "fallback": "no_siis_context" if req.siis_response is None else "no_match"}
    return body
