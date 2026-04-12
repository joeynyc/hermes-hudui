"""Hermes HUD Web UI — FastAPI backend."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
)
from .file_watcher import start_watcher, stop_watcher
from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


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
    logger.info("Hermes HUD stopped")


app = FastAPI(
    title="Hermes HUD",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, handle ping/pong
            data = await websocket.receive_text()
            # Echo back for heartbeat/ping
            if data == "ping":
                await websocket.send_text("pong")
    except Exception:
        pass
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

# Serve frontend static files (after API routes so /api takes priority)
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def cli():
    """CLI entry point: hermes-hudui"""
    parser = argparse.ArgumentParser(description="Hermes HUD Web UI")
    parser.add_argument("--port", type=int, default=3001, help="Port (default: 3001)")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument(
        "--dev", action="store_true", help="Development mode (auto-reload)"
    )
    parser.add_argument(
        "--hermes-dir", default=None, help="Hermes data directory (default: ~/.hermes)"
    )
    args = parser.parse_args()

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
