"""Hermes HUD Web UI — FastAPI backend."""

from __future__ import annotations

import argparse
import ipaddress
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

# Suppress macOS MallocStackLogging warnings triggered by frequent subprocess spawning
if sys.platform == "darwin":
    os.environ.setdefault("MallocStackLogging", "0")
    os.environ.setdefault("MallocLogFile", "/dev/null")

# Ensure dirs that commonly hold the hermes CLI are on PATH even when the
# server is launched with a minimal environment (systemd, cron, launchd).
# Appended, so an existing PATH ordering is never overridden.
_path_parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
_extra_dirs = [
    d for d in (os.path.expanduser("~/.local/bin"), "/usr/local/bin")
    if d not in _path_parts
]
os.environ["PATH"] = os.pathsep.join(_path_parts + _extra_dirs)

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocketDisconnect

from .api import (
    state,
    memory,
    sessions,
    skills,
    cron,
    projects,
    health,
    profiles,
    patterns,
    corrections,
    agents,
    timeline,
    snapshots,
    dashboard,
    token_costs,
    cache,
    chat,
    sudo,
    providers,
    gateway,
    model_info,
    plugins,
    replay,
)
from .file_watcher import start_watcher, stop_watcher
from .chat.engine import chat_engine
from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
_ALLOW_REMOTE_ENV = "_HERMES_HUD_ALLOW_REMOTE"
_ALLOWED_ORIGINS_ENV = "_HERMES_HUD_ALLOWED_ORIGINS"
_CORS_METHODS = "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT"


def _is_loopback_host(host: str) -> bool:
    """Return whether a CLI bind host is limited to this machine."""
    hostname = host.strip().strip("[]").lower().rstrip(".")
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _normalise_origin(origin: str) -> str | None:
    """Return a canonical HTTP(S) origin or ``None`` for invalid input."""
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if (
        parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        return None
    hostname = parsed.hostname.lower().rstrip(".")
    host = f"[{hostname}]" if ":" in hostname else hostname
    try:
        port = parsed.port
    except ValueError:
        return None
    default_port = 80 if parsed.scheme == "http" else 443
    port_suffix = f":{port}" if port and port != default_port else ""
    return f"{parsed.scheme}://{host}{port_suffix}"


def _configured_origins() -> set[str]:
    origins: set[str] = set()
    for value in os.environ.get(_ALLOWED_ORIGINS_ENV, "").split(","):
        if normalised := _normalise_origin(value.strip()):
            origins.add(normalised)
    return origins


def _remote_access_enabled() -> bool:
    return os.environ.get(_ALLOW_REMOTE_ENV, "").lower() in {"1", "true", "yes"}


def _request_host_is_loopback(request_host: str) -> bool:
    """Return whether an HTTP Host header points at a loopback interface."""
    host = request_host.strip()
    if not host:
        return False
    if host.startswith("["):
        closing = host.find("]")
        hostname = host[1:closing] if closing > 0 else host
    else:
        hostname = host.rsplit(":", 1)[0] if ":" in host else host
    return _is_loopback_host(hostname)


def _origin_allowed(origin: str, request_host: str) -> bool:
    """Validate browser origins for the local control API.

    Localhost origins are always accepted so production and Vite development
    work on arbitrary local ports. Remote access is opt-in and same-origin by
    default; additional origins must be supplied explicitly by the CLI.
    """
    normalised = _normalise_origin(origin)
    if normalised is None:
        return False

    parsed = urlsplit(normalised)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if _is_loopback_host(hostname):
        return True
    if normalised in _configured_origins():
        return True

    if not _remote_access_enabled():
        return False
    return parsed.netloc.lower() == request_host.strip().lower()


class LocalOriginMiddleware:
    """Block cross-site browser access to the local API.

    CORS headers alone do not prevent simple cross-site POST requests from
    executing. This middleware rejects untrusted browser requests before route
    handlers run, while continuing to allow local CLI clients that send no
    browser Origin headers.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api"):
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        origin = headers.get("origin", "")
        request_host = headers.get("host", "")
        trusted_origin = bool(origin) and _origin_allowed(origin, request_host)
        cross_site = headers.get("sec-fetch-site", "").lower() == "cross-site"

        if not _remote_access_enabled() and not _request_host_is_loopback(request_host):
            response = JSONResponse(
                {
                    "detail": (
                        "Remote access to the Hermes HUD API is disabled. "
                        "Start the CLI with --unsafe-allow-remote only on a trusted network."
                    )
                },
                status_code=403,
            )
            await response(scope, receive, send)
            return

        if (origin and not trusted_origin) or (not origin and cross_site):
            response = JSONResponse(
                {"detail": "Cross-origin access to the Hermes HUD API is denied."},
                status_code=403,
            )
            await response(scope, receive, send)
            return

        if (
            scope.get("method") == "OPTIONS"
            and headers.get("access-control-request-method")
        ):
            if not trusted_origin:
                response = JSONResponse(
                    {"detail": "CORS preflight requires a trusted Origin."},
                    status_code=403,
                )
            else:
                response = Response(
                    status_code=204,
                    headers=self._cors_headers(
                        origin,
                        headers.get("access-control-request-headers", ""),
                    ),
                )
            await response(scope, receive, send)
            return

        if not trusted_origin:
            await self.app(scope, receive, send)
            return

        async def send_with_cors(message):
            if message["type"] == "http.response.start":
                cors_headers = self._cors_headers(origin)
                message.setdefault("headers", []).extend(
                    (key.lower().encode("latin-1"), value.encode("latin-1"))
                    for key, value in cors_headers.items()
                )
            await send(message)

        await self.app(scope, receive, send_with_cors)

    @staticmethod
    def _cors_headers(origin: str, requested_headers: str = "") -> dict[str, str]:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": _CORS_METHODS,
            "Access-Control-Max-Age": "600",
            "Vary": "Origin",
        }
        if requested_headers:
            headers["Access-Control-Allow-Headers"] = requested_headers
        return headers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: start/stop file watcher."""
    # Startup
    hermes_dir = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    await start_watcher(hermes_dir)
    logger.info(f"Hermes HUD started, watching {hermes_dir}")

    yield

    # Shutdown
    await stop_watcher()
    chat_engine.cleanup_all()
    logger.info("Hermes HUD stopped")


app = FastAPI(
    title="Hermes HUD",
    version="0.10.0",
    lifespan=lifespan,
)

app.add_middleware(LocalOriginMiddleware)


async def _static_http_only(scope, receive, send):
    """ASGI wrapper: forward only HTTP scopes to StaticFiles.

    StaticFiles asserts scope["type"] == "http" and crashes on WebSocket
    scopes that leak to the catch-all mount on client disconnect.
    """
    if scope["type"] != "http":
        return
    await _static_app(scope, receive, send)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    origin = websocket.headers.get("origin", "")
    request_host = websocket.headers.get("host", "")
    cross_site = websocket.headers.get("sec-fetch-site", "").lower() == "cross-site"
    if (
        not _remote_access_enabled()
        and not _request_host_is_loopback(request_host)
    ) or (origin and not _origin_allowed(origin, request_host)) or (
        not origin and cross_site
    ):
        await websocket.close(code=1008, reason="Cross-origin WebSocket denied")
        return

    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("WebSocket error", exc_info=True)
    finally:
        await ws_manager.disconnect(websocket)


# API routes
app.include_router(state.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
app.include_router(cron.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(profiles.router, prefix="/api")
app.include_router(patterns.router, prefix="/api")
app.include_router(corrections.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(timeline.router, prefix="/api")
app.include_router(snapshots.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(token_costs.router, prefix="/api")
app.include_router(cache.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(sudo.router, prefix="/api")
app.include_router(providers.router, prefix="/api")
app.include_router(gateway.router, prefix="/api")
app.include_router(model_info.router, prefix="/api")
app.include_router(plugins.router, prefix="/api")
app.include_router(replay.router, prefix="/api")

# Serve frontend static files (after API routes so /api takes priority)
if STATIC_DIR.exists():
    _static_app = StaticFiles(directory=str(STATIC_DIR), html=True)
    app.mount("/", _static_http_only, name="static")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hermes HUD Web UI")
    parser.add_argument("--port", type=int, default=3001, help="Port (default: 3001)")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument(
        "--dev", action="store_true", help="Development mode (auto-reload)"
    )
    parser.add_argument(
        "--hermes-dir", default=None, help="Hermes data directory (default: ~/.hermes)"
    )
    parser.add_argument(
        "--unsafe-allow-remote",
        action="store_true",
        help="Allow binding to a non-loopback host without authentication",
    )
    parser.add_argument(
        "--allowed-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help="Additional trusted browser origin (repeatable; remote mode only)",
    )
    return parser


def cli():
    """CLI entry point: hermes-hudui"""
    parser = _build_parser()
    args = parser.parse_args()

    if not _is_loopback_host(args.host) and not args.unsafe_allow_remote:
        parser.error(
            "Refusing to expose unauthenticated control endpoints on a non-loopback "
            "host. Add --unsafe-allow-remote only on a trusted network."
        )
    if args.unsafe_allow_remote:
        os.environ[_ALLOW_REMOTE_ENV] = "1"
        logger.warning(
            "Remote access enabled without authentication; use only on a trusted network"
        )
    if args.allowed_origin:
        normalised_origins = []
        for origin in args.allowed_origin:
            normalised = _normalise_origin(origin)
            if normalised is None:
                parser.error(f"Invalid --allowed-origin value: {origin!r}")
            normalised_origins.append(normalised)
        os.environ[_ALLOWED_ORIGINS_ENV] = ",".join(normalised_origins)

    if args.hermes_dir:
        os.environ["HERMES_HOME"] = args.hermes_dir

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=args.dev,
    )


if __name__ == "__main__":
    cli()
