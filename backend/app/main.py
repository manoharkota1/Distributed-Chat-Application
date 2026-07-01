"""
FastAPI application entry point.

Wires together all routers, middleware, and lifecycle hooks.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.redis import close_redis
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.conversations import router as conversations_router
from app.ws.router import router as ws_router
from app.pubsub.redis_bridge import redis_bridge

# ── Logging ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Application Lifecycle ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup/shutdown of background services."""
    # Startup
    logger.info("Starting %s", settings.app_name)
    await redis_bridge.start()
    yield
    # Shutdown
    logger.info("Shutting down %s", settings.app_name)
    await redis_bridge.stop()
    await close_redis()


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
