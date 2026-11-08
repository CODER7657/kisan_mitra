# main.py

import mimetypes
import os
import time
import uuid
from collections import defaultdict, deque
from urllib.parse import urlsplit

import openai
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from kisan import answer, config, logs, vision, weather
from kisan.middleware import RequestContext

load_dotenv()
log = logs.setup()
# Read and checked once, now: a bad value stops the app here with the variable's name.
settings = config.get_settings()

app = FastAPI(title="Kisan Mitra AI Backend")

DEV_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]


def allowed_origins(value: str | None) -> list[str]:
    """Local dev servers plus each origin in ALLOWED_ORIGINS (comma separated).

    A browser sends a bare origin (scheme://host[:port]), so a pasted page URL is cut down
    to its origin, and an entry without a scheme is dropped; both are logged, since a CORS
    mismatch otherwise fails silently in the visitor's browser.
    """
    origins = list(DEV_ORIGINS)
    for entry in (o.strip() for o in (value or "").split(",")):
        if not entry:
            continue
        if entry == "*":  # any site; fine for a public API that uses no cookies
            origins.append(entry)
            continue
        parts = urlsplit(entry)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            log.warning("ALLOWED_ORIGINS: ignoring %r, expected e.g. https://example.org", entry)
            continue
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin != entry.rstrip("/"):
            log.warning("ALLOWED_ORIGINS: using %r for %r (an origin has no path)", origin, entry)
        origins.append(origin)
    return list(dict.fromkeys(origins))


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(settings.allowed_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=[logs.REQUEST_ID_HEADER],
)
# Added last, so it wraps CORS: preflights and refusals get a request id too.
app.add_middleware(RequestContext)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_AUDIO_BYTES = 20 * 1024 * 1024


class RateLimiter:
    """At most `limit` requests per client per `window` seconds, in this process.

    On serverless hosts each instance keeps its own count, so this is a speed bump against
    a script draining the free LLM quota, not an exact global limit.
    """

    def __init__(self, limit: int, window: float = 60.0, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self.clock()
        q = self.hits[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        if len(self.hits) > 10_000:  # forget idle clients so memory stays bounded
            for k in [k for k, v in self.hits.items() if not v]:
                del self.hits[k]
        return True


limiter = RateLimiter(settings.rate_limit_per_min)


def client_key(request: Request) -> str:
    """The visitor's IP: the first address in X-Forwarded-For when a proxy (Vercel) sets it."""
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def store(data: bytes, filename: str, content_type: str) -> str | None:
    """Optionally keep uploads in Vercel Blob, under a random path. Off unless STORE_UPLOADS=1."""
    s = config.load()
    if not s.uploads_enabled:
        return None
    from vercel_blob import put

    ext = os.path.splitext(filename)[1].lower()[:8]
    blob = put(
        f"uploads/{uuid.uuid4().hex}{ext}",
        data,
        # 10 s per attempt; the library retries 502/503/504 a bounded number of times.
        options={"token": s.blob_token, "content_type": content_type, "timeout": 10},
    )
    return blob["url"]


@app.get("/")
def read_root():
    """Confirms the server is running, and which parts are configured."""
    p = config.provider()
    return {
        "message": "Welcome to the Kisan Mitra AI Backend!",
        "provider": p.name if p else None,
        "photo_classifier": vision.available(),
    }


@app.get("/health")
def health():
    """Liveness, for the host's health check and uptime pings: cheap, no model calls, nothing secret."""
    return {"status": "ok"}


@app.head("/health")
def health_head():
    """The same check for uptime monitors that send HEAD."""
    return {"status": "ok"}


@app.get("/ready", responses={503: {"description": "A dependency is missing"}})
def ready():
    """Readiness: a model provider is configured and the photo classifier's files are in
    place (or may be fetched). No model calls, no network; names only, never a secret."""
    checks = {
        "model_provider": config.provider() is not None,
        "photo_classifier": vision.available(),
    }
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        return JSONResponse({"status": "not ready", "missing": missing, "checks": checks}, 503)
    return {"status": "ready", "checks": checks}


@app.post("/analyze/")
async def analyze_farm_data(
    request: Request,
    image_file: UploadFile | None = File(None),
    audio_file: UploadFile | None = File(None),
    question: str | None = Form(None),
    language: str | None = Form(None),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
):
    """A spoken or typed question, with an optional crop photo and location, answered and checked."""
    if not limiter.allow(client_key(request)):
        raise HTTPException(
            429, "Too many questions in a minute. Please wait a little and try again."
        )
    p = config.provider()
    if p is None:
        raise HTTPException(
            503, "No model provider configured: set GROQ_API_KEY or OPENAI_API_KEY."
        )

    image = await image_file.read() if image_file else b""
    audio = await audio_file.read() if audio_file else b""
    if len(image) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "The photo is larger than 8 MB.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "The recording is larger than 20 MB.")
    question = (question or "").strip()[:2000]
    if not audio and not question:
        raise HTTPException(400, "Send a voice recording or type a question.")

    image_type = (
        (image_file.content_type if image_file else None)
        or mimetypes.guess_type(image_file.filename if image_file else "")[0]
        or "image/jpeg"
    )
    try:
        transcript = (
            answer.transcribe(p, audio, audio_file.filename or "question.wav", language)
            if audio
            else ""
        )
        full_question = " ".join(x for x in (transcript, question) if x)
        photo = None
        if image:
            try:
                photo = vision.classify(image)
            except Exception as exc:
                log.exception("photo classifier failed")
                raise HTTPException(
                    400, "The photo could not be read. Please send a JPG or PNG."
                ) from exc
        forecast = weather.forecast(lat, lon) if lat is not None and lon is not None else None
        result = answer.answer(
            p,
            full_question,
            language,
            photo,
            bool(image),
            forecast,
            (image, image_type) if image else None,
        )
        image_url = store(image, image_file.filename or "photo.jpg", image_type) if image else None
        audio_url = (
            store(audio, audio_file.filename or "question.wav", "audio/wav") if audio else None
        )
    except HTTPException:
        raise
    except openai.RateLimitError as exc:
        log.warning("model provider rate limit")
        raise HTTPException(
            503, "The advice service is busy right now. Please try again in a minute."
        ) from exc
    except (openai.APITimeoutError, openai.APIConnectionError) as exc:
        log.warning("model provider timeout or connection error")
        raise HTTPException(
            504, "The advice service took too long to answer. Please try again."
        ) from exc
    except Exception as exc:
        log.exception("analysis failed")
        raise HTTPException(500, "Something went wrong while answering. Please try again.") from exc

    return {
        "analysis": result["analysis"],
        "transcript": transcript,
        "question": full_question,
        "language": result["language"],
        "photo": photo,
        "weather": forecast,
        "guard": {
            "lines_removed": len(result["guard"]["removed"]),
            "kvk_added": result["guard"]["kvk_added"],
        },
        "provider": {
            "name": p.name,
            "chat_model": p.chat_model,
            "asr_model": p.asr_model if audio else None,
        },
        "image_url": image_url,
        "audio_url": audio_url,
    }
