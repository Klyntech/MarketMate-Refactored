"""
marketmate/platform/social_publishers.py
──────────────────────────────────────────
Platform-specific social media publishers.

Supported platforms:
  - Twitter/X   (OAuth 1.0a via tweepy)
  - Facebook    (Graph API — Page posts)
  - Instagram   (Graph API — Content Publishing API via Facebook Page)
  - Telegram    (Bot API — channel broadcasts)

Each publisher exposes a single async method:  publish(content: str) -> bool
Returns True on success, False on any failure. All errors are logged, never raised.
"""

from __future__ import annotations

import httpx
from marketmate.core.logger import get_logger
from marketmate.core.config import cfg

log = get_logger("platform.social_publishers")


# ═══════════════════════════════════════════════════════════════════════════════
# Twitter / X  (OAuth 1.0a via tweepy)
# ═══════════════════════════════════════════════════════════════════════════════

class TwitterPublisher:
    """Publish tweets via the Twitter/X API v2 using OAuth 1.0a."""

    def __init__(self) -> None:
        self._api_key = cfg.social.twitter_api_key
        self._api_secret = cfg.social.twitter_api_secret
        self._access_token = cfg.social.twitter_access_token
        self._access_secret = cfg.social.twitter_access_secret
        self._client = None

    @property
    def is_configured(self) -> bool:
        return bool(
            self._api_key and self._api_secret
            and self._access_token and self._access_secret
        )

    async def publish(self, content: str) -> bool:
        if not self.is_configured:
            log.warning("twitter_not_configured")
            return False

        try:
            import tweepy

            client = tweepy.Client(
                consumer_key=self._api_key,
                consumer_secret=self._api_secret,
                access_token=self._access_token,
                access_token_secret=self._access_secret,
            )
            response = client.create_tweet(text=content)
            tweet_id = response.data.get("id") if response.data else None
            log.info("twitter_published", tweet_id=tweet_id)
            return True

        except ImportError:
            log.warning("tweepy_not_installed")
            return False
        except Exception as exc:
            log.error("twitter_publish_failed", error=str(exc))
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# Facebook  (Graph API — Page posts)
# ═══════════════════════════════════════════════════════════════════════════════

class FacebookPublisher:
    """Publish posts to a Facebook Page via the Graph API."""

    GRAPH_URL = "https://graph.facebook.com/v19.0"

    def __init__(self) -> None:
        self._page_id = cfg.social.fb_page_id
        self._access_token = cfg.social.fb_access_token

    @property
    def is_configured(self) -> bool:
        return bool(self._page_id and self._access_token)

    async def publish(self, content: str) -> bool:
        if not self.is_configured:
            log.warning("facebook_not_configured")
            return False

        try:
            url = f"{self.GRAPH_URL}/{self._page_id}/feed"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, data={
                    "message": content,
                    "access_token": self._access_token,
                })

            if resp.status_code == 200:
                post_id = resp.json().get("id", "")
                log.info("facebook_published", post_id=post_id)
                return True
            else:
                log.error("facebook_publish_failed",
                          status=resp.status_code, body=resp.text[:300])
                return False

        except Exception as exc:
            log.error("facebook_publish_error", error=str(exc))
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# Instagram  (Graph API — Content Publishing via Facebook Page)
# ═══════════════════════════════════════════════════════════════════════════════

class InstagramPublisher:
    """
    Publish content to Instagram via the Content Publishing API.

    Instagram Business accounts publish through the Facebook Graph API:
      1. Create a media container (POST /{ig-user-id}/media)
      2. Publish the container (POST /{ig-user-id}/media_publish)

    NOTE: Instagram requires an image_url for posts. For text-only marketing
    content, we generate a branded image URL. If no image is available,
    the post is skipped with a warning.
    """

    GRAPH_URL = "https://graph.facebook.com/v19.0"

    def __init__(self) -> None:
        self._ig_account_id = cfg.social.ig_account_id
        self._access_token = cfg.social.ig_access_token

    @property
    def is_configured(self) -> bool:
        return bool(self._ig_account_id and self._access_token)

    async def publish(self, content: str, image_url: str | None = None) -> bool:
        if not self.is_configured:
            log.warning("instagram_not_configured")
            return False

        # Instagram requires an image — skip text-only posts
        if not image_url:
            log.warning("instagram_skipped_no_image",
                        reason="Instagram requires an image URL for posts")
            return False

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Step 1: Create media container
                create_url = f"{self.GRAPH_URL}/{self._ig_account_id}/media"
                create_resp = await client.post(create_url, data={
                    "image_url": image_url,
                    "caption": content,
                    "access_token": self._access_token,
                })

                if create_resp.status_code not in (200, 201):
                    log.error("instagram_container_failed",
                              status=create_resp.status_code,
                              body=create_resp.text[:300])
                    return False

                container_id = create_resp.json().get("id", "")

                # Step 2: Wait for media processing (brief poll)
                import asyncio
                await asyncio.sleep(3)

                # Step 3: Publish the container
                publish_url = f"{self.GRAPH_URL}/{self._ig_account_id}/media_publish"
                pub_resp = await client.post(publish_url, data={
                    "creation_id": container_id,
                    "access_token": self._access_token,
                })

                if pub_resp.status_code == 200:
                    media_id = pub_resp.json().get("id", "")
                    log.info("instagram_published", media_id=media_id)
                    return True
                else:
                    log.error("instagram_publish_failed",
                              status=pub_resp.status_code,
                              body=pub_resp.text[:300])
                    return False

        except Exception as exc:
            log.error("instagram_publish_error", error=str(exc))
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# Telegram  (Bot API — channel broadcasts)
# ═══════════════════════════════════════════════════════════════════════════════

class TelegramPublisher:
    """Broadcast messages to a Telegram channel via Bot API."""

    API_BASE = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self) -> None:
        self._bot_token = cfg.telegram.bot_token
        self._chat_id = cfg.social.telegram_channel_id or cfg.telegram.chat_id

    @property
    def is_configured(self) -> bool:
        return bool(self._bot_token and self._chat_id)

    async def publish(self, content: str) -> bool:
        if not self.is_configured:
            log.warning("telegram_social_not_configured")
            return False

        try:
            url = self.API_BASE.format(token=self._bot_token)
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json={
                    "chat_id": self._chat_id,
                    "text": content,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                })

            if resp.status_code == 200:
                msg_id = resp.json().get("result", {}).get("message_id")
                log.info("telegram_social_published", message_id=msg_id)
                return True
            else:
                log.error("telegram_social_failed",
                          status=resp.status_code, body=resp.text[:300])
                return False

        except Exception as exc:
            log.error("telegram_social_error", error=str(exc))
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# Publisher registry
# ═══════════════════════════════════════════════════════════════════════════════

PUBLISHERS: dict[str, object] = {
    "twitter": TwitterPublisher,
    "facebook": FacebookPublisher,
    "instagram": InstagramPublisher,
    "telegram": TelegramPublisher,
}


def get_publisher(platform: str):
    """Return a publisher instance for the given platform name."""
    cls = PUBLISHERS.get(platform.lower())
    if cls is None:
        log.warning("unknown_publisher_platform", platform=platform)
        return None
    return cls()


def get_configured_platforms() -> list[str]:
    """Return a list of platform names that have valid credentials."""
    configured = []
    for name, cls in PUBLISHERS.items():
        try:
            instance = cls()
            if instance.is_configured:
                configured.append(name)
        except Exception:
            pass
    return configured
