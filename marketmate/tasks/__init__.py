"""
marketmate.tasks
────────────────
Celery task queue for MarketMate background processing.
"""

from marketmate.tasks.celery_app import celery_app, celery_available

__all__ = ["celery_app", "celery_available"]
