"""
marketmate/platform/social_scheduler.py
──────────────────────────────────────────
Background scheduler for the social marketing engine.

Periodically checks for approved posts that are due for publishing
and publishes them to their target platforms.

Also supports scheduled marketing content generation (auto-generate
marketing posts at regular intervals).

NOT signal-driven — this is a MARKETING scheduler, not a signal broadcaster.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from marketmate.core.logger import get_logger
from marketmate.core.config import cfg
from marketmate.platform.social_repo import SocialRepo
from marketmate.platform.social_publishers import get_publisher
from marketmate.platform.social_generator import generate_marketing_post, VALID_POST_TYPES

log = get_logger("platform.social_scheduler")


class SocialScheduler:
    """
    Background scheduler for marketing post publishing and auto-generation.

    Two responsibilities:
      1. Publish approved posts that are due (every CHECK_INTERVAL seconds)
      2. Auto-generate marketing posts on a schedule (every GENERATE_INTERVAL seconds)
    """

    CHECK_INTERVAL = 60       # Check for due posts every 60 seconds
    GENERATE_INTERVAL = 21600 # Auto-generate marketing posts every 6 hours

    def __init__(self) -> None:
        self._repo = SocialRepo()
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._last_generate: Optional[datetime] = None

    async def start(self) -> None:
        """Start the background scheduler tasks."""
        if not cfg.social.enabled:
            log.info("social_scheduler_disabled")
            return

        if self._running:
            log.warning("social_scheduler_already_running")
            return

        self._running = True
        self._tasks = [
            asyncio.create_task(self._publish_loop(), name="social_publish_loop"),
            asyncio.create_task(self._generate_loop(), name="social_generate_loop"),
        ]
        log.info("social_scheduler_started",
                 check_interval=self.CHECK_INTERVAL,
                 generate_interval=self.GENERATE_INTERVAL)

    async def stop(self) -> None:
        """Stop the background scheduler."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        log.info("social_scheduler_stopped")

    # ═══════════════════════════════════════════════════════════════════════════
    # Publishing loop
    # ═══════════════════════════════════════════════════════════════════════════

    async def _publish_loop(self) -> None:
        """Periodically check for due posts and publish them."""
        while self._running:
            try:
                await self._publish_due_posts()
            except Exception as exc:
                log.error("publish_loop_error", error=str(exc))

            await asyncio.sleep(self.CHECK_INTERVAL)

    async def _publish_due_posts(self) -> None:
        """Publish all approved posts that are past their scheduled_for time."""
        due_posts = await self._repo.get_due_posts()
        if not due_posts:
            return

        log.info("publishing_due_posts", count=len(due_posts))

        for post in due_posts:
            content = post.get("content", "")
            platforms = post.get("platforms", [])
            post_id = post.get("post_id", "")
            results = {}

            for platform_name in platforms:
                publisher = get_publisher(platform_name)
                if publisher is None:
                    results[platform_name] = "unknown_platform"
                    continue

                if not publisher.is_configured:
                    results[platform_name] = "not_configured"
                    continue

                try:
                    if platform_name == "instagram":
                        success = await publisher.publish(content, image_url=None)
                    else:
                        success = await publisher.publish(content)
                    results[platform_name] = "published" if success else "failed"
                except Exception as exc:
                    results[platform_name] = f"error: {exc}"
                    log.error("scheduled_publish_error",
                              post_id=post_id, platform=platform_name, error=str(exc))

            # Mark as published if at least one platform succeeded
            if any(v == "published" for v in results.values()):
                await self._repo.mark_published(post_id)
                log.info("post_published_scheduled",
                         post_id=post_id, results=results)
            else:
                log.warning("post_publish_all_failed",
                            post_id=post_id, results=results)

    # ═══════════════════════════════════════════════════════════════════════════
    # Auto-generation loop
    # ═══════════════════════════════════════════════════════════════════════════

    async def _generate_loop(self) -> None:
        """Periodically auto-generate marketing content."""
        if not cfg.social.auto_generate:
            log.info("social_auto_generate_disabled")
            return

        while self._running:
            try:
                await self._auto_generate_post()
            except Exception as exc:
                log.error("generate_loop_error", error=str(exc))

            await asyncio.sleep(self.GENERATE_INTERVAL)

    async def _auto_generate_post(self) -> None:
        """Generate a marketing post and add it to the queue."""
        import random

        post_type = random.choice(VALID_POST_TYPES)
        result = await generate_marketing_post(
            post_type=post_type,
            use_ai=cfg.social.use_ai_generation,
        )

        if not result:
            log.warning("auto_generate_failed", post_type=post_type)
            return

        post_id = await self._repo.create_post(
            post_type=post_type,
            content=result["content"],
            platforms=result["platforms"],
        )

        self._last_generate = datetime.now(timezone.utc)

        if post_id:
            log.info("auto_marketing_post_queued",
                     post_id=post_id, post_type=post_type)
        else:
            log.warning("auto_generate_queue_failed", post_type=post_type)


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton instance
# ═══════════════════════════════════════════════════════════════════════════════

social_scheduler = SocialScheduler()
