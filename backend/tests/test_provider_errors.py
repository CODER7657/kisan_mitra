"""A busy or slow model provider gives the farmer a clear, retryable message fast, not a vague 500."""

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

import main
from kisan import config


def rate_limit():
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return openai.RateLimitError(
        "rate limited", response=httpx.Response(429, request=req), body=None
    )


def timeout():
    return openai.APITimeoutError(request=httpx.Request("POST", "https://api.groq.com"))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "limiter", main.RateLimiter(1000))
    monkeypatch.setattr(
        main.config,
        "provider",
        lambda: config.Provider("groq", "k", "u", "m", "a", sees_images=False),
    )
    return TestClient(main.app)


@pytest.mark.parametrize(
    "error, status, words", [(rate_limit, 503, "busy"), (timeout, 504, "too long")]
)
def test_provider_failures_map_to_clear_messages(client, monkeypatch, error, status, words):
    def boom(*a, **k):
        raise error()

    monkeypatch.setattr(main.answer, "answer", boom)
    r = client.post("/analyze/", data={"question": "My cotton leaves are yellow"})
    assert r.status_code == status
    assert words in r.json()["detail"]


def test_client_fails_fast_by_default_and_batch_jobs_can_wait(monkeypatch):
    p = config.Provider("groq", "k", "https://api.groq.com/openai/v1", "m", "a", sees_images=False)
    monkeypatch.delenv("KISAN_LLM_TIMEOUT", raising=False)
    monkeypatch.delenv("KISAN_LLM_RETRIES", raising=False)
    c = config.client(p)
    assert c.timeout == 25 and c.max_retries == 1
    monkeypatch.setenv("KISAN_LLM_TIMEOUT", "60")
    monkeypatch.setenv("KISAN_LLM_RETRIES", "4")
    c = config.client(p)
    assert c.timeout == 60 and c.max_retries == 4
