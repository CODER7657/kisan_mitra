"""The backend with its model provider stubbed, for load tests (perf/k6-health-analyze.js).

    backend/.venv/bin/python perf/stub_server.py          # http://127.0.0.1:8000
    PORT=8100 python perf/stub_server.py

Everything outside this process is replaced the way the backend tests replace it: the
model client answers instantly with a fixed draft (which still goes through the guard),
the weather lookup returns no forecast and uploads are off, so a load test measures this
server's own work and never calls Groq, OpenAI, Open-Meteo or Vercel Blob, and needs no
key. The per-client rate limit is lifted, since a load test is one client sending far
more than 10 questions a minute. Listens on 127.0.0.1 only.
"""

import os
import sys
import types
from collections.abc import Callable
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"

# A draft with one dose sentence, so every answer exercises the guard's removal path.
REPLY = (
    "**What to do now**\n"
    "- Remove the spotted leaves and keep them away from the field.\n"
    "- Spray mancozeb 2.5 g per litre of water.\n"
    "- Irrigate in the morning so the leaves dry by evening."
)


class FakeClient:
    """The two calls /analyze/ makes on a provider client: chat and transcription."""

    def __init__(self) -> None:
        def chat(**kwargs):
            message = types.SimpleNamespace(content=REPLY)
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

        def transcribe(**kwargs):
            return "my tomato leaves have black patches"

        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=chat))
        self.audio = types.SimpleNamespace(transcriptions=types.SimpleNamespace(create=transcribe))


def configure(
    setenv: Callable[[str, str], None] = os.environ.__setitem__,
    setattr_: Callable[[object, str, object], None] = setattr,
):
    """Stub the app's outside calls and return it. Tests pass pytest's monkeypatch
    functions, so nothing leaks into other tests."""
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    # Set before main loads backend/.env: load_dotenv never overrides a set variable, so a
    # real key in .env is not picked up. The stub key is never sent anywhere.
    setenv("GROQ_API_KEY", "perf-stub-key")
    setenv("LLM_PROVIDER", "groq")
    setenv("OPENAI_API_KEY", "")
    setenv("STORE_UPLOADS", "0")

    import main
    from kisan import config, weather

    config.get_settings.cache_clear()
    fake = FakeClient()
    setattr_(config, "client", lambda provider: fake)
    setattr_(weather, "forecast", lambda *args, **kwargs: None)
    setattr_(main, "store", lambda *args, **kwargs: None)
    setattr_(main.limiter, "allow", lambda key: True)
    return main.app


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(configure(), host="127.0.0.1", port=port, log_level="warning")
