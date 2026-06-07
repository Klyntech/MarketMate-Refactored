"""
marketmate/core/logger.py
──────────────────────────
Structured logging with structlog.
Outputs JSON in production, coloured text in dev.

Migrated from ``utils/logger.py`` — import path updated to
``marketmate.core.config``.
"""

import logging
import sys
import structlog
from marketmate.core.config import cfg


def _configure_logging() -> None:
    log_level = getattr(logging, cfg.app.log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if cfg.app.env == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)


_configure_logging()


def get_logger(name: str = "marketmate") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
