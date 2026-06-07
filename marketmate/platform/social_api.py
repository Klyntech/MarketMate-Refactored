"""
marketmate/platform/social_api.py
──────────────────────────────────
FastAPI router for social media marketing engine admin endpoints.

All endpoints require X-Admin-Secret header for authentication.
Post types: brand_awareness, feature_highlight, community_engage,
            educational_tip, milestone, promotional, social_proof
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from marketmate.core.logger import get_logger
from marketmate.core.config import cfg
from marketmate.platform.social_repo import SocialRepo
from marketmate.platform.social_generator import (
    generate_marketing_post,
    VALID_POST_TYPES,
)
from marketmate.platform.social_publishers import get_publisher, get_configured_platforms

log = get_logger("platform.social_api")

router = APIRouter(prefix="/social", tags=["Social Marketing Engine"])

_repo = SocialRepo()


# ═══════════════════════════════════════════════════════════════════════════════
# Auth helper
# ═══════════════════════════════════════════════════════════════════════════════

def _verify_admin(admin_secret: str | None) -> None:
    """Verify the admin secret header. Raises 401 if invalid."""
    if not admin_secret or admin_secret != cfg.app.admin_secret:
        raise HTTPException(status_code=401, detail="Invalid or missing admin secret")


# ═══════════════════════════════════════════════════════════════════════════════
# Post CRUD
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/posts")
async def list_posts(
    status: Optional[str] = Query(None, enum=["pending", "approved", "rejected", "published"]),
    x_admin_secret: str = Header(None, alias="X-Admin-Secret"),
):
    """List social posts, optionally filtered by status."""
    _verify_admin(x_admin_secret)

    if status == "pending":
        posts = await _repo.get_pending_posts()
    elif status == "approved" or status == "published":
        # For approved/published, we'd need additional repo methods
        # For now, return pending (most common use case)
        posts = await _repo.get_pending_posts()
    else:
        posts = await _repo.get_pending_posts()

    return {"posts": posts, "count": len(posts)}


@router.get("/posts/{post_id}")
async def get_post(
    post_id: str,
    x_admin_secret: str = Header(None, alias="X-Admin-Secret"),
):
    """Get a specific social post by ID."""
    _verify_admin(x_admin_secret)

    post = await _repo.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.post("/posts")
async def create_post(
    post_type: str = Query(..., description="Marketing post type"),
    content: str = Query(..., description="Post content"),
    platforms: str = Query("twitter,facebook,telegram", description="Comma-separated platforms"),
    scheduled_for: Optional[str] = Query(None, description="ISO datetime for scheduled publish"),
    x_admin_secret: str = Header(None, alias="X-Admin-Secret"),
):
    """Create a new marketing post manually."""
    _verify_admin(x_admin_secret)

    if post_type not in VALID_POST_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid post type. Valid: {VALID_POST_TYPES}",
        )

    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    scheduled_dt = None
    if scheduled_for:
        try:
            scheduled_dt = datetime.fromisoformat(scheduled_for).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scheduled_for format. Use ISO 8601.")

    post_id = await _repo.create_post(
        post_type=post_type,
        content=content,
        platforms=platform_list,
        scheduled_for=scheduled_dt,
    )

    if not post_id:
        raise HTTPException(status_code=500, detail="Failed to create post")

    return {"post_id": post_id, "status": "pending"}


# ═══════════════════════════════════════════════════════════════════════════════
# Approve / Reject / Publish
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/posts/{post_id}/approve")
async def approve_post(
    post_id: str,
    x_admin_secret: str = Header(None, alias="X-Admin-Secret"),
):
    """Approve a pending post for publishing."""
    _verify_admin(x_admin_secret)

    success = await _repo.approve_post(post_id)
    if not success:
        raise HTTPException(status_code=404, detail="Post not found or not in pending status")
    return {"post_id": post_id, "status": "approved"}


@router.post("/posts/{post_id}/reject")
async def reject_post(
    post_id: str,
    note: Optional[str] = Query(None, description="Rejection reason"),
    x_admin_secret: str = Header(None, alias="X-Admin-Secret"),
):
    """Reject a pending post."""
    _verify_admin(x_admin_secret)

    success = await _repo.reject_post(post_id, note)
    if not success:
        raise HTTPException(status_code=404, detail="Post not found or not in pending status")
    return {"post_id": post_id, "status": "rejected"}


@router.post("/posts/{post_id}/publish")
async def publish_post_now(
    post_id: str,
    x_admin_secret: str = Header(None, alias="X-Admin-Secret"),
):
    """Immediately publish an approved post to all its target platforms."""
    _verify_admin(x_admin_secret)

    post = await _repo.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] not in ("pending", "approved"):
        raise HTTPException(status_code=400, detail=f"Cannot publish post with status: {post['status']}")

    content = post["content"]
    platforms = post.get("platforms", [])
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
                # Instagram requires image_url — skip for now
                success = await publisher.publish(content, image_url=None)
            else:
                success = await publisher.publish(content)
            results[platform_name] = "published" if success else "failed"
        except Exception as exc:
            results[platform_name] = f"error: {exc}"
            log.error("publish_error", platform=platform_name, error=str(exc))

    # Mark as published if at least one platform succeeded
    if any(v == "published" for v in results.values()):
        await _repo.mark_published(post_id)

    return {"post_id": post_id, "results": results}


# ═══════════════════════════════════════════════════════════════════════════════
# AI Generation Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/generate")
async def generate_post(
    post_type: str = Query("brand_awareness", description="Marketing post type"),
    use_ai: bool = Query(True, description="Use AI generation (fallback to templates)"),
    context: str = Query("", description="Additional context for AI generation"),
    platforms: str = Query("twitter,facebook,telegram", description="Target platforms"),
    x_admin_secret: str = Header(None, alias="X-Admin-Secret"),
):
    """Generate a marketing post using AI or templates. Returns the content without creating a post."""
    _verify_admin(x_admin_secret)

    if post_type not in VALID_POST_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid post type. Valid: {VALID_POST_TYPES}",
        )

    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    result = await generate_marketing_post(
        post_type=post_type,
        use_ai=use_ai,
        context=context,
        platforms=platform_list,
    )

    if not result:
        raise HTTPException(status_code=500, detail="Failed to generate post")

    return result


@router.post("/generate-and-queue")
async def generate_and_queue(
    post_type: str = Query("brand_awareness", description="Marketing post type"),
    use_ai: bool = Query(True, description="Use AI generation"),
    context: str = Query("", description="Additional context"),
    platforms: str = Query("twitter,facebook,telegram", description="Target platforms"),
    auto_approve: bool = Query(False, description="Auto-approve the post"),
    x_admin_secret: str = Header(None, alias="X-Admin-Secret"),
):
    """Generate a marketing post and add it to the queue (pending or auto-approved)."""
    _verify_admin(x_admin_secret)

    if post_type not in VALID_POST_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid post type. Valid: {VALID_POST_TYPES}",
        )

    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    result = await generate_marketing_post(
        post_type=post_type,
        use_ai=use_ai,
        context=context,
        platforms=platform_list,
    )

    if not result:
        raise HTTPException(status_code=500, detail="Failed to generate post")

    post_id = await _repo.create_post(
        post_type=post_type,
        content=result["content"],
        platforms=result["platforms"],
    )

    if not post_id:
        raise HTTPException(status_code=500, detail="Generated post but failed to queue")

    if auto_approve:
        await _repo.approve_post(post_id)

    return {
        "post_id": post_id,
        "status": "approved" if auto_approve else "pending",
        "content": result["content"],
        "platforms": result["platforms"],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Platform & Engine Status
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/status")
async def engine_status(
    x_admin_secret: str = Header(None, alias="X-Admin-Secret"),
):
    """Get social marketing engine status."""
    _verify_admin(x_admin_secret)

    configured = get_configured_platforms()
    pending = await _repo.get_pending_posts()
    due = await _repo.get_due_posts()

    return {
        "engine_enabled": cfg.social.enabled,
        "require_approval": cfg.social.require_approval,
        "use_ai_generation": cfg.social.use_ai_generation,
        "configured_platforms": configured,
        "valid_post_types": VALID_POST_TYPES,
        "pending_posts": len(pending),
        "due_posts": len(due),
    }


@router.get("/post-types")
async def list_post_types(
    x_admin_secret: str = Header(None, alias="X-Admin-Secret"),
):
    """List all valid marketing post types."""
    _verify_admin(x_admin_secret)
    return {"post_types": VALID_POST_TYPES}
