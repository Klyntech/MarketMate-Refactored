"""
marketmate.api.auth
────────────────────
Authentication routes and session utilities.

Extracted from main.py auth section.

Provides:
  - Session utilities (_session_create, _session_verify, _set_session_cookie, etc.)
  - Telegram OAuth verification (_verify_telegram_auth)
  - Google OAuth routes
  - FastAPI APIRouter with auth routes

Routes:
  GET  /login                    — Login page
  GET  /auth/telegram/callback   — Telegram OAuth callback
  GET  /auth/google              — Google OAuth redirect
  GET  /auth/google/callback     — Google OAuth callback
  GET  /auth/logout              — Logout
  GET  /api/me                   — Current user info

Migrated from main.py.
Import paths updated to marketmate.* prefix.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from typing import Optional

from fastapi import APIRouter, Cookie, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.db.repositories.subscribers import SubscriberRepository
from marketmate.db.repositories.audit import AuditRepository

log = get_logger("api.auth")

router = APIRouter(tags=["auth"])

# ─── Repository singletons ────────────────────────────────────────────────────
_subscriber_repo = SubscriberRepository()
_audit_repo = AuditRepository()


# ─── Session utilities ────────────────────────────────────────────────────

def _session_create(data: dict, days: int = 7) -> str:
    # SECURITY: Reject session creation if the secret is not configured.
    # This prevents forged sessions when SESSION_SECRET is empty.
    if not cfg.app.session_secret:
        log.error("session_secret_not_configured")
        raise ValueError("SESSION_SECRET is not configured — cannot create sessions")
    payload = json.dumps({**data, "exp": time.time() + days * 86_400})
    encoded = base64.urlsafe_b64encode(payload.encode()).decode()
    sig     = hmac.new(
        cfg.app.session_secret.encode(), encoded.encode(), hashlib.sha256
    ).hexdigest()
    return f"{encoded}.{sig}"


def _session_verify(token: str) -> Optional[dict]:
    try:
        # SECURITY: Reject all sessions if secret is not configured.
        # This prevents forged sessions when SESSION_SECRET is empty.
        if not cfg.app.session_secret:
            return None
        encoded, sig = token.rsplit(".", 1)
        expected = hmac.new(
            cfg.app.session_secret.encode(), encoded.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + "==").decode()
        )
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def _set_session_cookie(response: Response, data: dict) -> None:
    token = _session_create(data)
    response.set_cookie(
        key="mm_session", value=token,
        max_age=7 * 86_400,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key="mm_session", path="/")


def _get_user_from_cookie(mm_session: Optional[str]) -> Optional[dict]:
    return _session_verify(mm_session) if mm_session else None


# ─── Telegram OAuth verification ─────────────────────────────────────────

def _verify_telegram_auth(params: dict) -> bool:
    auth_hash = params.get("hash", "")
    check_data = {k: v for k, v in params.items() if k != "hash"}
    check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(check_data.items())
    )
    secret_key = hashlib.sha256(cfg.telegram.bot_token.encode()).digest()
    expected   = hmac.new(
        secret_key, check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, auth_hash):
        return False
    if time.time() - int(params.get("auth_date", 0)) > 86_400:
        return False
    return True


# ─── Routes ───────────────────────────────────────────────────────────────

@router.get("/login")
async def login_page(mm_session: str = Cookie(default=None)):
    if _get_user_from_cookie(mm_session):
        return RedirectResponse(url="/desk", status_code=302)
    # Login page is now served by Next.js at /login
    return RedirectResponse(url="/login", status_code=302)


@router.get("/auth/telegram/callback")
async def telegram_auth_callback(request: Request):
    params = dict(request.query_params)

    if not params.get("hash"):
        return RedirectResponse(url="/login?error=missing_hash", status_code=302)

    if not _verify_telegram_auth(params):
        log.warning("telegram_auth_invalid", params_keys=list(params.keys()))
        return RedirectResponse(url="/login?error=invalid_auth", status_code=302)

    telegram_id = str(params.get("id", ""))
    first_name  = params.get("first_name", "")
    username    = params.get("username", "")
    photo_url   = params.get("photo_url", "")

    sub = await _subscriber_repo.get_by_chat_id(telegram_id)
    if not sub or (sub.get("status") or "").lower() not in ("active", "trial"):
        log.info("telegram_auth_non_subscriber", telegram_id=telegram_id)
        return RedirectResponse(
            url="/login?error=not_subscriber", status_code=302
        )

    session_data = {
        "telegram_id": telegram_id,
        "first_name":  first_name,
        "username":    username,
        "photo_url":   photo_url,
    }
    response = RedirectResponse(url="/auto-trade", status_code=302)
    _set_session_cookie(response, session_data)

    log.info("telegram_auth_success",
             telegram_id=telegram_id, username=username)
    await _audit_repo.log_event(
        telegram_id, username, first_name, "WEB_LOGIN", {}
    )
    return response


@router.get("/auth/google")
async def auth_google(request: Request):
    """Redirect to Google OAuth consent screen."""
    client_id = cfg.google_oauth.client_id
    if not client_id:
        return JSONResponse({"error": "Google OAuth not configured"}, status_code=500)

    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
    if cfg.google_oauth.redirect_uri:
        redirect_uri = cfg.google_oauth.redirect_uri
    elif render_host:
        redirect_uri = f"https://{render_host}/auth/google/callback"
    else:
        redirect_uri = "http://localhost:8000/auth/google/callback"

    scope       = cfg.google_oauth.scopes
    state       = request.query_params.get("next", "/learn")
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={urllib.parse.quote(client_id)}&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"response_type=code&"
        f"scope={urllib.parse.quote(scope)}&"
        f"access_type=offline&"
        f"prompt=consent&"
        f"state={urllib.parse.quote(state)}"
    )
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/auth/google/callback")
async def auth_google_callback(request: Request):
    """Handle Google OAuth callback — exchange code for user info."""
    import httpx as _httpx

    code  = request.query_params.get("code")
    state = request.query_params.get("state", "/learn")
    error = request.query_params.get("error")

    if error:
        log.warning("google_oauth_error", error=error)
        return RedirectResponse(url=f"/login?error=google_{error}", status_code=302)

    if not code:
        return RedirectResponse(url="/login?error=google_no_code", status_code=302)

    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
    if cfg.google_oauth.redirect_uri:
        redirect_uri = cfg.google_oauth.redirect_uri
    elif render_host:
        redirect_uri = f"https://{render_host}/auth/google/callback"
    else:
        redirect_uri = "http://localhost:8000/auth/google/callback"

    try:
        async with _httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code":          code,
                    "client_id":     cfg.google_oauth.client_id,
                    "client_secret": cfg.google_oauth.client_secret,
                    "redirect_uri":  redirect_uri,
                    "grant_type":    "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

        # Decode id_token to get user info.
        # SECURITY: Verify the JWT signature using Google's public keys.
        # This prevents token forgery attacks where an attacker crafts a
        # fake JWT with arbitrary claims (email, sub, etc).
        id_token_str = token_data.get("id_token", "")
        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests
            claims = google_id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                cfg.google_oauth.client_id,
            )
        except ImportError:
            # SECURITY FIX: No insecure fallback — reject the login entirely
            # if google-auth is not installed. Decoding JWT without verifying
            # the signature allows arbitrary identity forgery.
            log.error("google_auth_not_installed_rejecting_login")
            return RedirectResponse(
                url="/login?error=google_auth_required", status_code=302
            )

        google_id = str(claims.get("sub", ""))
        email     = claims.get("email", "")
        name      = claims.get("name", "")
        picture   = claims.get("picture", "")

        if not google_id:
            return RedirectResponse(url="/login?error=google_no_sub", status_code=302)

        session_data = {
            "google_id": google_id,
            "email":     email,
            "name":      name,
            "picture":   picture,
        }
        response = RedirectResponse(url=state, status_code=302)
        _set_session_cookie(response, session_data)

        log.info("google_auth_success", google_id=google_id, email=email)
        return response

    except Exception as exc:
        log.error("google_oauth_callback_error", error=str(exc))
        return RedirectResponse(url="/login?error=google_callback_failed", status_code=302)


@router.get("/auth/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    _clear_session_cookie(response)
    return response


@router.get("/api/me")
async def api_me(mm_session: str = Cookie(default=None)):
    user = _get_user_from_cookie(mm_session)
    if not user:
        return JSONResponse({"authenticated": False}, status_code=401)
    return JSONResponse({
        "authenticated": True,
        "telegram_id":   user.get("telegram_id"),
        "first_name":    user.get("first_name"),
        "username":      user.get("username"),
        "photo_url":     user.get("photo_url"),
        "google_id":     user.get("google_id"),
        "email":         user.get("email"),
        "name":          user.get("name"),
        "picture":       user.get("picture"),
    })
