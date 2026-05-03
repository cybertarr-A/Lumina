"""
FastAPI Application Entry Point.
Configures middleware, routers, startup/shutdown events, and monitoring.
"""
import time
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.config import settings
from backend.database import create_tables
from backend.routes.auth import router as auth_router
from backend.routes.contracts import router as contracts_router
from backend.routes.api import (
    audit_router,
    compile_router,
    deploy_router,
    ws_router,
)
from backend.utils.logger import RequestLogger, get_logger, setup_logging

# ── Logging setup ─────────────────────────────────────────────────────────────
setup_logging()
logger = get_logger(__name__)

# ── Sentry ────────────────────────────────────────────────────────────────────
if settings.SENTRY_DSN and settings.SENTRY_DSN.strip():
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN.strip(),
        environment=settings.APP_ENV,
        traces_sample_rate=0.2,
    )

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


# ── Application Lifespan ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_starting", version=settings.APP_VERSION, env=settings.APP_ENV)
    await create_tables()
    logger.info("database_ready")
    yield
    logger.info("application_shutdown")


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Lumina API",
    description=(
        "Production-grade platform for generating, compiling, auditing, "
        "and deploying Solidity smart contracts with AI assistance."
    ),
    version=settings.APP_VERSION,
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.is_production:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Request timing middleware ──────────────────────────────────────────────────
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.monotonic()
    response: Response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000

    # Add timing header
    response.headers["X-Process-Time-Ms"] = str(round(duration_ms, 2))

    # Skip health check logging
    if request.url.path != "/health":
        RequestLogger.log_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
    return response


# ── Prometheus metrics ─────────────────────────────────────────────────────────
if settings.PROMETHEUS_ENABLED:
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=["/health", "/metrics"],
    ).instrument(app).expose(app, endpoint="/metrics")


# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = settings.API_PREFIX

app.include_router(auth_router, prefix=PREFIX)
app.include_router(contracts_router, prefix=PREFIX)
app.include_router(compile_router, prefix=PREFIX)
app.include_router(audit_router, prefix=PREFIX)
app.include_router(deploy_router, prefix=PREFIX)
app.include_router(ws_router)  # WebSocket — no versioned prefix


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Lumina API",
        "docs": "/api/docs",
        "version": settings.APP_VERSION,
    }


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "path": str(request.url.path)},
    )
