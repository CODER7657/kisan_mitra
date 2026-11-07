"""Contract fuzzing: no route may answer 500 (roadmap §2.3 item 3).

Schemathesis reads the app's OpenAPI schema and generates requests for every
operation: valid forms, boundary values, wrong types, missing fields, odd
uploads. The check allows any 4xx (refusing bad input is the API's job) and the
deliberate 503/504 "advice service busy / too slow" answers, and nothing else in
the 5xx range. `/analyze/` ends in a catch-all `except Exception -> 500`, so a
500 here means generated input reached a path nobody handled.

Run in two worlds:

* **provider up**: the model client answers with a valid draft, so input reaches
  the guard, language handling and response building.
* **provider down**: every model call raises (rate limit, timeout, connection,
  and an unexpected error), which must surface as 503/504, never 500.

No network: the model client is a fake, uploads are off, and any non-loopback
socket or DNS call raises, so the weather lookup takes its "no forecast" path. Examples per
operation default to 25; set `FUZZ_EXAMPLES` to go deeper.
"""

import os
import socket
import types

import httpx
import openai
import pytest
import schemathesis
from hypothesis import HealthCheck, settings

import main
from kisan import config, vision

FUZZ_EXAMPLES = int(os.environ.get("FUZZ_EXAMPLES", "25"))
GUESSES = {"guesses": [{"label": "Tomato___Late_blight", "crop": "Tomato", "condition": "Late blight",
                        "probability": 0.81}], "confident": True, "threshold": 0.5, "crops_covered": ["Tomato"]}
REPLY = "**What to do now**\n- Remove the spotted leaves and keep them away from the field."


_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_REAL_CONNECT = socket.socket.connect
_REAL_GETADDRINFO = socket.getaddrinfo


def _refuse(target) -> None:
    raise OSError(f"network is disabled in the contract fuzz tests ({target!r})")


def _connect(sock, address):
    # Loopback stays open: asyncio's event loop on Windows talks to itself over a
    # local socket pair, and the in-process test client runs on that loop.
    host = address[0] if isinstance(address, tuple) else address
    if host in _LOOPBACK:
        return _REAL_CONNECT(sock, address)
    _refuse(address)


def _getaddrinfo(host, *args, **kwargs):
    if host in _LOOPBACK:
        return _REAL_GETADDRINFO(host, *args, **kwargs)
    _refuse(host)


def _create_connection(address, *args, **kwargs):
    _refuse(address)


class _Client:
    """The two calls /analyze/ makes on a provider client: chat and transcription."""

    def __init__(self, chat, transcribe):
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=chat))
        self.audio = types.SimpleNamespace(transcriptions=types.SimpleNamespace(create=transcribe))


def _ok_chat(**kwargs):
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=REPLY))])


def _ok_transcribe(**kwargs):
    return "my cotton leaves are turning yellow"


_REQUEST = httpx.Request("POST", "https://api.example/v1/chat/completions")
_FAILURES = [
    openai.RateLimitError("rate limited", response=httpx.Response(429, request=_REQUEST), body=None),
    openai.APITimeoutError(request=_REQUEST),
    openai.APIConnectionError(request=_REQUEST),
]


def _isolate(mp: pytest.MonkeyPatch) -> None:
    mp.setenv("GROQ_API_KEY", "fuzz-stub-key")  # a provider exists; its client is faked
    mp.delenv("OPENAI_API_KEY", raising=False)
    mp.delenv("LLM_PROVIDER", raising=False)
    mp.delenv("STORE_UPLOADS", raising=False)
    mp.setattr(main.limiter, "allow", lambda key: True)
    mp.setattr(vision, "classify", lambda data: GUESSES)
    mp.setattr(socket.socket, "connect", _connect)
    mp.setattr(socket, "getaddrinfo", _getaddrinfo)
    mp.setattr(socket, "create_connection", _create_connection)


@pytest.fixture
def provider_up():
    with pytest.MonkeyPatch.context() as mp:
        _isolate(mp)
        mp.setattr(config, "client", lambda p: _Client(_ok_chat, _ok_transcribe))
        yield


@pytest.fixture
def provider_down():
    calls = {"n": 0}

    def failing(**kwargs):
        calls["n"] += 1
        raise _FAILURES[calls["n"] % len(_FAILURES)]

    with pytest.MonkeyPatch.context() as mp:
        _isolate(mp)
        mp.setattr(config, "client", lambda p: _Client(failing, failing))
        yield


@schemathesis.check
def no_unhandled_server_error(ctx, response, case):
    """5xx fails except 503/504, the deliberate provider-unavailable answers (§2.4)."""
    if response.status_code >= 500 and response.status_code not in (503, 504):
        raise AssertionError(
            f"{response.status_code} from {case.method} {case.formatted_path}: {response.text[:200]}"
        )


schema = schemathesis.openapi.from_asgi("/openapi.json", main.app)

_FUZZ_SETTINGS = settings(
    max_examples=FUZZ_EXAMPLES,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much, HealthCheck.function_scoped_fixture],
)


@schema.parametrize()
@_FUZZ_SETTINGS
def test_no_route_returns_500_when_the_provider_answers(provider_up, case):
    case.call_and_validate(checks=[no_unhandled_server_error])


@schema.parametrize()
@_FUZZ_SETTINGS
def test_no_route_returns_500_when_the_provider_fails(provider_down, case):
    case.call_and_validate(checks=[no_unhandled_server_error])


def test_the_schema_covers_every_route():
    """Fuzzing an empty schema would pass vacuously."""
    documented = {(path, method.upper()) for path, item in main.app.openapi()["paths"].items() for method in item}
    assert {("/", "GET"), ("/health", "GET"), ("/analyze/", "POST")} <= documented


# --- Deep fuzz of /analyze/ ---------------------------------------------------
# Schema-generated requests mostly stop at validation (file fields need real
# uploads, an empty question is a 400), so few reach the answer pipeline. This
# strategy always builds a well-formed request, so every example gets past
# validation and into transcription, the guard and response building.

from fastapi.testclient import TestClient  # noqa: E402
from hypothesis import given  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c63f8cf0c0000040101005a1c0f4d0000000049454e44ae426082"
)

forms = st.fixed_dictionaries(
    {"question": st.text(min_size=1, max_size=2500)},
    optional={
        "language": st.one_of(st.sampled_from(["gu", "hi", "en", "", "xx"]), st.text(max_size=8)),
        "lat": st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
        "lon": st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
    },
)
uploads = st.fixed_dictionaries(
    {},
    optional={
        "image_file": st.one_of(st.just(PNG), st.binary(max_size=512)),
        "audio_file": st.binary(min_size=1, max_size=512),
    },
)


def _post(client, form, files):
    named = {k: (f"{k}.bin", v, "application/octet-stream") for k, v in files.items()}
    data = {k: str(v) for k, v in form.items()}
    return client.post("/analyze/", data=data, files=named or None)


@settings(max_examples=max(FUZZ_EXAMPLES, 100), deadline=None, derandomize=True,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
@given(form=forms, files=uploads)
def test_well_formed_requests_never_500_when_the_provider_answers(provider_up, form, files):
    r = _post(TestClient(main.app), form, files)
    assert r.status_code < 500, r.text[:300]


@settings(max_examples=max(FUZZ_EXAMPLES, 100), deadline=None, derandomize=True,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
@given(form=forms, files=uploads)
def test_well_formed_requests_get_503_or_504_when_the_provider_fails(provider_down, form, files):
    r = _post(TestClient(main.app), form, files)
    assert r.status_code < 500 or r.status_code in (503, 504), r.text[:300]
