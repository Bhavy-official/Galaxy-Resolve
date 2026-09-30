"""POST /v1/troubleshoot/stream — SSE per stage for the console (ADR-008). Not scored."""
from fastapi import APIRouter

router = APIRouter()

# TODO(A+C): emit events cache -> enrich -> segment -> extract -> ground -> resolve -> compile -> done
