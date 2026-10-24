"""Structured logs and request context.

Request bodies are never logged. Probe failures log an exception type only,
so a database URL or password cannot land in the log line.
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from logging import LogRecord

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        error_type = getattr(record, "error_type", None)
        if error_type:
            payload["error_type"] = error_type
        if record.exc_info:
            payload["exception"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_raremed_configured", False):
        return

    settings = get_settings()
    handler = logging.StreamHandler()
    if settings.log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )

    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    setattr(root, "_raremed_configured", True)


class RequestContextMiddleware:
    """Pure ASGI middleware so streamed chat tokens are not buffered."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        incoming = request.headers.get("x-request-id")
        request_id = incoming.strip() if incoming else uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_headers(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["X-RareMed-Role"] = "decision-support"
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            logger = logging.getLogger("raremed.access")
            level = logging.DEBUG if request.url.path == "/health" else logging.INFO
            logger.log(
                level,
                "%s %s %s %.1fms",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )
            request_id_ctx.reset(token)
