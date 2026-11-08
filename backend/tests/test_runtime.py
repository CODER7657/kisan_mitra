"""Runtime hardening (roadmap §2.4): settings checked at startup, request ids, JSON access
logs that hold no personal data, /ready, and safe response headers.

cd backend && pytest tests/test_runtime.py
"""

import importlib
import io
import json
import logging
import warnings

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_analyze import PNG, post
from test_analyze import app as app  # noqa: F401  (the /analyze/ fixture with a fake provider)

import main
from kisan import config, logs, vision
from kisan.middleware import RequestContext

KEYS = ("GROQ_API_KEY", "OPENAI_API_KEY", "LLM_PROVIDER")


@pytest.fixture
def no_keys(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def logged():
    """Every line the app logs while the test runs, rendered by the real JSON formatter."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logs.formatter())
    logger = logging.getLogger(logs.LOGGER)
    logger.addHandler(handler)

    def lines():
        return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]

    lines.text = stream.getvalue
    yield lines
    logger.removeHandler(handler)


# --- Settings -------------------------------------------------------------------------


def test_defaults_match_the_old_environment_reading(monkeypatch, no_keys):
    for k in ("KISAN_LLM_TIMEOUT", "KISAN_LLM_RETRIES", "RATE_LIMIT_PER_MIN", "STORE_UPLOADS"):
        monkeypatch.delenv(k, raising=False)
    s = config.load()
    assert (s.kisan_llm_timeout, s.kisan_llm_retries, s.rate_limit_per_min) == (25.0, 1, 12)
    assert s.groq_chat_model == "qwen/qwen3.8-27b" and s.groq_asr_model == "whisper-large-v3"
    assert s.openai_chat_model == "gpt-4o" and not s.uploads_enabled
    assert config.provider() is None


def test_good_environment_is_read_with_types(monkeypatch):
    monkeypatch.setenv("KISAN_LLM_TIMEOUT", "60.5")
    monkeypatch.setenv("KISAN_LLM_RETRIES", "10")
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "1")
    s = config.load()
    assert (s.kisan_llm_timeout, s.kisan_llm_retries, s.rate_limit_per_min) == (60.5, 10, 1)


def test_provider_choice_is_unchanged(monkeypatch, no_keys):
    monkeypatch.setenv("GROQ_API_KEY", "  test-groq  ")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    assert config.provider().name == "groq" and config.provider().api_key == "test-groq"
    monkeypatch.setenv("LLM_PROVIDER", " OpenAI ")
    p = config.provider()
    assert (p.name, p.chat_model, p.asr_model, p.sees_images) == (
        "openai",
        "gpt-4o",
        "whisper-1",
        True,
    )


@pytest.mark.parametrize(
    "name, value",
    [
        ("KISAN_LLM_TIMEOUT", "0"),
        ("KISAN_LLM_TIMEOUT", "-5"),
        ("KISAN_LLM_TIMEOUT", "soon"),
        ("KISAN_LLM_RETRIES", "-1"),
        ("KISAN_LLM_RETRIES", "11"),
        ("RATE_LIMIT_PER_MIN", "0"),
        ("RATE_LIMIT_PER_MIN", "lots"),
    ],
)
def test_bad_values_are_refused_with_the_variable_name(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(config.ConfigError) as err:
        config.load()
    assert str(err.value).startswith("Invalid configuration: ") and name in str(err.value)


def test_bad_value_stops_the_app_at_startup(monkeypatch):
    monkeypatch.setenv("KISAN_LLM_RETRIES", "50")
    try:
        with pytest.raises(config.ConfigError, match="KISAN_LLM_RETRIES"):
            importlib.reload(main)
    finally:
        monkeypatch.undo()
        config.get_settings.cache_clear()
        importlib.reload(main)


def test_error_message_never_echoes_the_value(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "sk-looks-like-a-key")
    with pytest.raises(config.ConfigError) as err:
        config.load()
    assert "sk-looks-like-a-key" not in str(err.value)


def test_secrets_are_not_in_any_repr(monkeypatch, no_keys):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-secret")
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "test-blob-secret")
    monkeypatch.setenv("STORE_UPLOADS", "1")
    s = config.load()
    for text in (repr(s), str(s), repr(config.provider()), str(s.model_dump())):
        assert "test-groq-secret" not in text and "test-blob-secret" not in text
    assert s.uploads_enabled and s.blob_token == "test-blob-secret"


def test_settings_are_cached_until_cleared(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "5")
    first = config.get_settings()
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "7")
    assert config.get_settings() is first
    config.get_settings.cache_clear()
    assert config.get_settings().rate_limit_per_min == 7


# --- Request id -----------------------------------------------------------------------


def test_request_id_is_generated():
    r = TestClient(main.app).get("/health")
    rid = r.headers["x-request-id"]
    assert len(rid) == 32 and int(rid, 16) >= 0


def test_safe_incoming_request_id_is_kept():
    r = TestClient(main.app).get("/health", headers={"X-Request-ID": "abc-123_XYZ"})
    assert r.headers["x-request-id"] == "abc-123_XYZ"


@pytest.mark.parametrize(
    "bad", ["x" * 65, "has space", "line\\nbreak", "a;b", "é".encode(), "<script>", "../etc"]
)
def test_unsafe_incoming_request_id_is_replaced(bad):
    r = TestClient(main.app).get("/health", headers={"X-Request-ID": bad})
    assert r.headers["x-request-id"] != bad and len(r.headers["x-request-id"]) == 32


def test_request_id_helper_bounds():
    assert logs.request_id("a" * 64) == "a" * 64
    assert logs.request_id("a" * 65) != "a" * 65
    assert len(logs.request_id(None)) == len(logs.request_id("")) == 32


def test_request_id_on_4xx_and_5xx_errors(app, monkeypatch):
    client = app["client"]
    assert "x-request-id" in client.get("/no-such-page").headers  # 404
    r = post(app, question="hello")  # no provider: 503
    assert r.status_code == 503 and "x-request-id" in r.headers
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    r = post(app)  # neither audio nor question: 400
    assert r.status_code == 400 and "x-request-id" in r.headers

    def boom(*a, **k):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(main.answer, "answer", boom)
    r = post(app, question="hello")
    assert r.status_code == 500 and "x-request-id" in r.headers


def test_unhandled_exception_still_gets_a_request_id(logged):
    app = FastAPI()
    app.add_middleware(RequestContext)

    @app.get("/crash")
    def crash():
        raise RuntimeError("bug")

    r = TestClient(app, raise_server_exceptions=False).get("/crash")
    assert r.status_code == 500 and r.json() == {"detail": "Internal Server Error"}
    assert r.headers["x-request-id"] and r.headers["x-content-type-options"] == "nosniff"
    access = [line for line in logged() if line["event"] == "request"]
    assert access[-1]["status"] == 500 and access[-1]["request_id"] == r.headers["x-request-id"]


def test_non_http_scopes_pass_through():
    seen = []

    async def inner(scope, receive, send):
        seen.append(scope["type"])

    import asyncio

    asyncio.run(RequestContext(inner)({"type": "lifespan"}, None, None))
    assert seen == ["lifespan"]


def test_request_id_is_exposed_to_the_browser(monkeypatch):
    origin = "http://localhost:5173"
    r = TestClient(main.app).get("/health", headers={"Origin": origin})
    assert r.headers["access-control-allow-origin"] == origin
    assert "x-request-id" in r.headers["access-control-expose-headers"].lower()


def test_backend_sends_safe_headers_but_not_hsts():
    r = TestClient(main.app).get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "strict-transport-security" not in r.headers  # Vercel adds it on its domains


# --- Logs -----------------------------------------------------------------------------


def test_one_json_access_line_per_request(logged):
    r = TestClient(main.app).get("/health?visitor=ramesh", headers={"X-Request-ID": "req-1"})
    access = [line for line in logged() if line["event"] == "request"]
    assert len(access) == 1
    line = access[0]
    assert {"method", "path", "status", "duration_ms", "request_id", "level", "timestamp"} <= set(
        line
    )
    assert (line["method"], line["path"], line["status"]) == ("GET", "/health", 200)
    assert line["request_id"] == r.headers["x-request-id"] == "req-1"
    assert isinstance(line["duration_ms"], float) and line["duration_ms"] >= 0
    assert "ramesh" not in logged.text()  # no query string


def test_analyze_logs_no_question_answer_transcript_filename_or_ip(app, logged, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    question = "Ramesh Patel ni kapas na paan pila"
    files = {
        "image_file": ("ramesh-farm-leaf.png", PNG, "image/png"),
        "audio_file": ("ramesh-voice-note.wav", b"RIFF0000WAVE", "audio/wav"),
    }
    r = app["client"].post(
        "/analyze/",
        files=files,
        data={"question": question, "language": "en"},
        headers={"X-Forwarded-For": "203.0.113.7", "X-Request-ID": "analyze-1"},
    )
    assert r.status_code == 200
    text = logged.text()
    for private in (
        question,
        "Ramesh",
        "ramesh-farm-leaf",
        "ramesh-voice-note",
        "black patches",  # the transcript
        "Remove the spotted leaves",  # the answer
        "203.0.113.7",
        "testclient",  # the client host
    ):
        assert private not in text, private
    access = [line for line in logged() if line["event"] == "request"]
    assert access == [
        {
            **access[0],
            "method": "POST",
            "path": "/analyze/",
            "status": 200,
            "request_id": "analyze-1",
        }
    ]


def test_stdlib_warnings_carry_the_request_id(app, logged, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    def unreadable(data):
        raise ValueError("not an image")

    monkeypatch.setattr(vision, "classify", unreadable)
    r = app["client"].post(
        "/analyze/",
        files={"image_file": ("secret-name.png", b"junk", "image/png")},
        data={"question": "what is wrong with my leaf"},
        headers={"X-Request-ID": "photo-1"},
    )
    assert r.status_code == 400
    failure = next(line for line in logged() if line["event"] == "photo classifier failed")
    assert failure["request_id"] == "photo-1" and failure["level"] == "error"
    assert "ValueError" in failure["exception"]
    assert "secret-name" not in logged.text() and "what is wrong" not in logged.text()


def test_setup_is_idempotent():
    logger = logs.setup()
    count = len(logger.handlers)
    assert logs.setup() is logger and len(logger.handlers) == count


# --- /ready and the schema --------------------------------------------------------------


def test_ready_when_provider_and_classifier_are_there(monkeypatch, no_keys):
    monkeypatch.setenv("GROQ_API_KEY", "test-not-real")
    monkeypatch.setattr(vision, "available", lambda: True)
    r = TestClient(main.app).get("/ready")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ready",
        "checks": {"model_provider": True, "photo_classifier": True},
    }
    assert "test-not-real" not in r.text and "groq" not in r.text


@pytest.mark.parametrize(
    "key, classifier, missing",
    [
        (None, True, ["model_provider"]),
        ("test-not-real", False, ["photo_classifier"]),
        (None, False, ["model_provider", "photo_classifier"]),
    ],
)
def test_not_ready_names_what_is_missing(monkeypatch, no_keys, key, classifier, missing):
    if key:
        monkeypatch.setenv("GROQ_API_KEY", key)
    monkeypatch.setattr(vision, "available", lambda: classifier)
    r = TestClient(main.app).get("/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "not ready" and r.json()["missing"] == missing
    assert "test-not-real" not in r.text


def test_ready_with_the_real_bundled_classifier_files(monkeypatch, no_keys):
    if not (vision.MODEL_DIR / vision.BACKBONE_FILE).exists():
        pytest.skip("backbone not downloaded (scripts/get_model.py)")
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-real")
    assert TestClient(main.app).get("/ready").status_code == 200


def test_schema_has_no_duplicate_operation_ids():
    main.app.openapi_schema = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        schema = main.app.openapi()
    assert not [w for w in caught if "Duplicate Operation ID" in str(w.message)]
    ids = [op["operationId"] for item in schema["paths"].values() for op in item.values()]
    assert len(ids) == len(set(ids))
    assert {"get", "head"} <= set(schema["paths"]["/health"]) and "get" in schema["paths"]["/ready"]
