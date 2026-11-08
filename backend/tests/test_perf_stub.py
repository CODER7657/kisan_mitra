"""perf/stub_server.py: the load-test server must answer without any key or network."""

import importlib.util
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

STUB = Path(__file__).resolve().parents[2] / "perf" / "stub_server.py"


def _load():
    spec = importlib.util.spec_from_file_location("perf_stub_server", STUB)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("the stub server tried to reach the network")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    app = _load().configure(monkeypatch.setenv, monkeypatch.setattr)
    with TestClient(app) as c:
        yield c


def test_health_and_ready(client):
    assert client.get("/health").json() == {"status": "ok"}
    r = client.get("/ready")
    assert r.status_code == 200 and r.json()["checks"]["model_provider"] is True


def test_analyze_answers_from_the_stub_and_the_guard_removes_the_dose(client):
    for _ in range(15):  # more than the per-minute rate limit, which the stub lifts
        r = client.post("/analyze/", data={"question": "black spots on tomato leaves"})
        assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"]["name"] == "groq"
    assert "mancozeb" not in body["analysis"] and body["guard"]["lines_removed"] == 1
    assert body["image_url"] is None and body["weather"] is None


def test_a_key_already_in_the_environment_is_replaced(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "not-a-real-key-but-could-be")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    _load().configure(monkeypatch.setenv, monkeypatch.setattr)
    from kisan import config

    assert config.get_settings().groq_api_key.get_secret_value() == "perf-stub-key"
    assert config.provider().name == "groq"
