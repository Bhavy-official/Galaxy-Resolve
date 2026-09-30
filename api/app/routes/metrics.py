"""GET /v1/metrics and GET /v1/trace/{id} — observability for the console and eval."""
from fastapi import APIRouter

router = APIRouter()

# TODO(B): wire to app.obs.metrics and app.obs.trace
