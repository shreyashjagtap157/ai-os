import json
import pytest
from fastapi.testclient import TestClient
from agent import rpc
from agent.config import load_config
from pathlib import Path


client = TestClient(rpc.app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_execute_without_registry():
    # Ensure returns 503 when registry not set
    r = client.post("/execute", json={"command": "echo", "args": ["x"]})
    assert r.status_code == 503


@pytest.fixture
def setup_registry(monkeypatch):
    class DummyRegistry:
        def execute(self, cmd, args):
            if cmd == 'echo':
                print('echo ' + ' '.join(args))
                return True
            return True

    rpc.app.state.registry = DummyRegistry()
    yield
    del rpc.app.state.registry


def test_execute_with_registry_no_auth(setup_registry):
    # ensure works without api_key configured
    r = client.post("/execute", json={"command": "echo", "args": ["hi"]})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_execute_with_api_key(monkeypatch, setup_registry):
    # attach api_key to app.state and ensure auth required
    rpc.app.state.api_key = 'secret123'
    # missing header
    r = client.post("/execute", json={"command": "echo", "args": ["hi"]})
    assert r.status_code == 401
    # with header
    r = client.post("/execute", json={"command": "echo", "args": ["hi"]}, headers={"x-api-key": "secret123"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    del rpc.app.state.api_key
*** End Patch