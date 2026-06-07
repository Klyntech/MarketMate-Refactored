"""
marketmate.analytics.audit_logger
──────────────────────────────────
SHIM — DO NOT EDIT

This file exists only so old imports like:
    from marketmate.analytics.audit_logger import audit_logger
continue to work without changes.

The real implementation is in marketmate.db.repositories.audit.
Migrate callers to:
    from marketmate.db.repositories.audit import audit_logger
then delete this file.
"""

from marketmate.db.repositories.audit import AuditRepository

# Backward-compatible singleton — the old code used a module-level
# `audit_logger` instance.  Provide one that delegates to the new
# AuditRepository class so existing call sites keep working.
audit_logger = AuditRepository()

__all__ = ["audit_logger"]
