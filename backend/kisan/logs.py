"""One JSON object per log line, each carrying the request id of the request it belongs to.

The standard `logging` calls in the app (log.warning, log.exception) and structlog calls
both end up in the same JSON formatter. The request id lives in a context variable that
the request middleware binds, so every line written while a request runs carries it.

What is logged is deliberately small: method, path (no query string), status, duration
and request id. Never the question, transcript, answer, file names or the visitor's IP.
"""

import logging
import re
import sys
import uuid

import structlog

LOGGER = "kisan_mitra"
REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")

_SHARED = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
]


def request_id(incoming: str | None) -> str:
    """The caller's id when it is a short, plain token (so it can't inject into logs or
    headers); a fresh uuid4 hex otherwise."""
    if incoming and _SAFE_ID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


def formatter() -> logging.Formatter:
    """Renders standard-library and structlog records alike as one JSON line."""
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_SHARED,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )


def setup(stream=None) -> logging.Logger:
    """Attach the JSON handler to the app's logger once; safe to call again (e.g. on reload)."""
    structlog.configure(
        processors=[*_SHARED, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    log = logging.getLogger(LOGGER)
    log.setLevel(logging.INFO)
    # JSON only: a host that installs a root handler would otherwise print every line twice.
    log.propagate = False
    if not any(getattr(h, "_kisan_json", False) for h in log.handlers):
        handler = logging.StreamHandler(stream or sys.stdout)
        handler.setFormatter(formatter())
        handler._kisan_json = True
        log.addHandler(handler)
    return log


def get_logger():
    return structlog.get_logger(LOGGER)
