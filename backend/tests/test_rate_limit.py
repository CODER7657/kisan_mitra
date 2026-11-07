"""The per-visitor speed bump in front of /analyze/ (it protects the free LLM quota)."""

from types import SimpleNamespace

import main


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_allows_up_to_the_limit_then_refuses():
    lim = main.RateLimiter(3, window=60, clock=Clock())
    assert [lim.allow("a") for _ in range(4)] == [True, True, True, False]


def test_clients_are_counted_separately():
    lim = main.RateLimiter(1, window=60, clock=Clock())
    assert lim.allow("a") and lim.allow("b")
    assert not lim.allow("a")


def test_window_slides():
    clock = Clock()
    lim = main.RateLimiter(2, window=60, clock=clock)
    assert lim.allow("a") and lim.allow("a") and not lim.allow("a")
    clock.t = 60.0
    assert lim.allow("a")


def test_client_key_uses_first_forwarded_address():
    req = SimpleNamespace(headers={"x-forwarded-for": "203.0.113.7, 10.0.0.1"}, client=SimpleNamespace(host="10.0.0.1"))
    assert main.client_key(req) == "203.0.113.7"
    req = SimpleNamespace(headers={}, client=SimpleNamespace(host="198.51.100.2"))
    assert main.client_key(req) == "198.51.100.2"
    assert main.client_key(SimpleNamespace(headers={}, client=None)) == "unknown"


def test_analyze_returns_429_past_the_limit(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(main, "limiter", main.RateLimiter(1, window=60, clock=Clock()))
    monkeypatch.setattr(main.config, "provider", lambda: None)  # first call fails fast with 503
    client = TestClient(main.app)
    assert client.post("/analyze/", data={"question": "hi"}).status_code == 503
    r = client.post("/analyze/", data={"question": "hi"})
    assert r.status_code == 429 and "Too many" in r.json()["detail"]
