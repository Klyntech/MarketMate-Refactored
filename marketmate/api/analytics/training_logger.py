"""
marketmate.analytics.training_logger
─────────────────────────────────────
SHIM — DO NOT EDIT

This file exists only so old imports like:
    from marketmate.analytics.training_logger import training_logger
continue to work without changes.

The real implementation is in marketmate.db.repositories.training.
Migrate callers to:
    from marketmate.db.repositories.training import training_logger
then delete this file.
"""

from marketmate.db.repositories.training import training_logger  # noqa: F401

__all__ = ["training_logger"]
