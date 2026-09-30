from fastapi.testclient import TestClient
from app.api import app

client = TestClient(app)

def test_health():
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code in (200, 503)

def test_troubleshoot_stream():
    with TestClient(app) as client:
        res = client.post("/v1/troubleshoot/stream", json={"query": "Battery draining fast"})
        assert res.status_code == 200
        assert "text/event-stream" in res.headers.get("content-type", "")
        content = res.text
        assert "normalize" in content
        assert "completed" in content

