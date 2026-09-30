"""GalaxyResolve API entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import device, metrics, stream, troubleshoot

app = FastAPI(title="GalaxyResolve", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict:
    # TODO(B): return 503 until Screen Graph, indexes, lookup table and LLM clients are loaded.
    return {"status": "ok"}


app.include_router(troubleshoot.router)
app.include_router(stream.router)
app.include_router(device.router)
app.include_router(metrics.router)
