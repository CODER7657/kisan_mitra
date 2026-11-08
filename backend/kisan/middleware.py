"""Request id, one access log line, and safe default headers on every response.

A pure ASGI middleware (no BaseHTTPMiddleware), so the request id is bound in the same
context the route runs in and is still there when the route logs a warning.
"""

import time

import structlog

from kisan import logs

# Headers worth sending on a JSON API. HSTS is added by Vercel on its domains, so it is not
# repeated here; a CSP or frame policy means little for responses that are never rendered.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


class RequestContext:
    def __init__(self, app):
        self.app = app
        self.log = logs.get_logger()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                incoming = value.decode("latin-1")
                break
        rid = logs.request_id(incoming)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=rid)
        start = time.perf_counter()
        # status stays None if no response was ever started (e.g. the client went away).
        state = {"status": None, "started": False, "error": False}

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                state["status"], state["started"] = message["status"], True
                headers = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", rid.encode()))
                present = {k.lower() for k, _ in headers}
                for k, v in SECURITY_HEADERS.items():
                    if k.lower().encode() not in present:
                        headers.append((k.lower().encode(), v.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            # Unhandled: answer 500 ourselves so the reply still carries the request id,
            # then re-raise so the server logs the traceback. If headers already went out,
            # the logged status is what the client got, flagged as an error.
            state["error"] = True
            if not state["started"]:
                await send_with_headers(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send(
                    {"type": "http.response.body", "body": b'{"detail":"Internal Server Error"}'}
                )
            raise
        finally:
            self.log.info(
                "request",
                method=scope.get("method"),
                path=scope.get("path"),
                status=state["status"],
                duration_ms=round((time.perf_counter() - start) * 1000, 1),
                **({"error": True} if state["error"] else {}),
            )
            structlog.contextvars.clear_contextvars()
