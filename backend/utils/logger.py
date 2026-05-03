"""
Structured JSON logging using structlog.
Provides consistent log format across all services.
"""
import logging
import sys
from typing import Any

import structlog
from structlog.types import FilteringBoundLogger

from backend.config import settings


def setup_logging() -> None:
    """Configure structlog with JSON output for production."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]

    if settings.is_production:
        # JSON output for production (Loki/CloudWatch friendly)
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Colored console output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.DEBUG else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Route standard library logging through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
    )
    for lib in ["uvicorn", "sqlalchemy", "celery"]:
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str) -> FilteringBoundLogger:
    """Get a bound logger for a module."""
    return structlog.get_logger(name)


class RequestLogger:
    """Middleware-friendly request logger."""

    @staticmethod
    def log_request(
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        **extra: Any,
    ) -> None:
        logger = get_logger("http")
        logger.info(
            "http_request",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
            **extra,
        )
