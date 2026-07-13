"""
FastAPI application entry point.

Wires together all routers, middleware, and lifecycle hooks.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.users import router as users_router
from app.core.config import settings
from app.core.database import close_mongodb, connect_mongodb
from app.core.redis import close_redis, get_redis
from app.pubsub.redis_bridge import redis_bridge
from app.ws.router import router as ws_router

# ── Logging ──────────────────────────────────────────────────────

class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"timestamp": self.formatTime(record), "level": record.levelname, "logger": record.name, "message": record.getMessage()})


handler = logging.StreamHandler()
handler.setFormatter(StructuredFormatter())
logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO, handlers=[handler], force=True)
logger = logging.getLogger(__name__)


# ── Application Lifecycle ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup/shutdown of background services."""
    # Startup
    settings.validate_runtime_settings()
    await connect_mongodb()
    await get_redis()
    await redis_bridge.start()
    logger.info("application_started", extra={"app": settings.app_name})
    yield
    # Shutdown
    logger.info("Shutting down %s", settings.app_name)
    await redis_bridge.stop()
    await close_redis()
    await close_mongodb()


# ── FastAPI App ──────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    description="A horizontally scalable, real-time messaging platform",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS Middleware ──────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(conversations_router)
app.include_router(ws_router)


# ── Health Check ─────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Simple health check endpoint for load balancer probes."""
    return {"status": "healthy", "service": settings.app_name}
