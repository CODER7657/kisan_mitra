"""What a hosted deploy relies on: the health route, and CORS read from ALLOWED_ORIGINS.

    cd backend && pytest tests/test_deploy.py
"""

import importlib

import pytest
from fastapi.testclient import TestClient

import main

SITE = "https://kisan-mitra-gilt.vercel.app"


def preflight(client, origin):
    return client.options("/analyze/", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})


@pytest.fixture
def hosted(monkeypatch):
    """main rebuilt as the host would start it, with ALLOWED_ORIGINS set; restored afterwards."""
    monkeypatch.setenv("ALLOWED_ORIGINS", f" {SITE}/ , https://other.example.org,,")
    yield TestClient(importlib.reload(main).app)
    monkeypatch.undo()  # put the environment back first, so main is rebuilt from it
    importlib.reload(main)


def test_health_is_ok_without_any_keys(monkeypatch):
    for k in ("GROQ_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    client = TestClient(main.app)
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert client.head("/health").status_code == 200


def test_health_does_not_leak_configuration(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-not-real")
    body = TestClient(main.app).get("/health").text
    assert "test-not-real" not in body and "groq" not in body


@pytest.mark.parametrize("value, expected", [
    (None, main.DEV_ORIGINS),
    ("", main.DEV_ORIGINS),
    (" , ,", main.DEV_ORIGINS),
    (f"{SITE}/", main.DEV_ORIGINS + [SITE]),
    (f"{SITE}, https://b.example.org ,{SITE}", main.DEV_ORIGINS + [SITE, "https://b.example.org"]),
    ("http://localhost:5173", main.DEV_ORIGINS),
    (f"{SITE}/some/page?x=1", main.DEV_ORIGINS + [SITE]),
    ("kisan-mitra-gilt.vercel.app", main.DEV_ORIGINS),
    ("ftp://files.example.org", main.DEV_ORIGINS),
    ("*", main.DEV_ORIGINS + ["*"]),
])
def test_allowed_origins_parsing(value, expected):
    assert main.allowed_origins(value) == expected


def test_bad_origin_entries_are_logged(caplog):
    main.allowed_origins(f"kisan-mitra-gilt.vercel.app, {SITE}/app")
    assert "ignoring 'kisan-mitra-gilt.vercel.app'" in caplog.text
    assert f"using '{SITE}'" in caplog.text


def test_configured_site_passes_preflight(hosted):
    for origin in (SITE, "https://other.example.org"):
        r = preflight(hosted, origin)
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == origin


def test_unlisted_site_is_refused(hosted):
    r = preflight(hosted, "https://evil.example.com")
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers
    # A plain request still runs, but the browser gets no CORS header and hides the reply.
    assert "access-control-allow-origin" not in hosted.get("/health", headers={"Origin": "https://evil.example.com"}).headers


def test_lookalike_origin_is_refused(hosted):
    assert preflight(hosted, SITE + ".evil.example.com").status_code == 400
    assert preflight(hosted, SITE.replace("https", "http")).status_code == 400


def test_dev_server_allowed_by_default():
    r = preflight(TestClient(main.app), "http://localhost:5173")
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
