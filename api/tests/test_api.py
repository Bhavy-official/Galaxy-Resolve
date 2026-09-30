from fastapi.testclient import TestClient

from app.main import app
from app.schema import ContextDeeplinkResponse

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_troubleshoot_is_schema_valid():
    r = client.post("/v1/troubleshoot", json={"query": "screen is black"})
    assert r.status_code == 200
    ContextDeeplinkResponse.model_validate(r.json())


def test_all_modules_import():
    import importlib
    import pkgutil

    import app
    for m in pkgutil.walk_packages(app.__path__, "app."):
        importlib.import_module(m.name)
