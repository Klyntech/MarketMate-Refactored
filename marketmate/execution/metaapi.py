"""
marketmate/execution/metaapi.py
────────────────────────────────
MetaAPI integration via direct REST API — no SDK required.
Uses httpx (already in requirements.txt). No aiohttp conflict.

Migrated from services/metaapi_service.py. Updated imports to use
marketmate. prefix. Logic unchanged.

Two separate MetaAPI base URLs:
  PROVISIONING_URL  — create / deploy / undeploy / remove accounts
  CLIENT_URL        — read live terminal data (balance, equity)

Fix from original:
  - METAAPI_TOKEN was read at module level → KeyError crashed the
    entire FastAPI app on startup when the env var wasn't set.
    Token is now read lazily inside each function call.
  - Account information was fetched from the provisioning API, which
    does not serve terminal data. Fixed to use the client API URL.
  - Test accounts are now cleaned up (undeployed + removed) after
    test_connection() regardless of success or failure.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

import httpx

from marketmate.core.logger import get_logger

log = get_logger("metaapi")

# MetaAPI endpoints — provisioning manages accounts, client reads terminal data
PROVISIONING_URL = "https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai"
CLIENT_URL       = "https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai"

DEPLOY_TIMEOUT_S   = 90   # seconds to wait for broker to accept connection
POLL_INTERVAL_S    = 3    # seconds between status polls


def _headers() -> dict:
    """
    Build auth headers. Read token lazily so a missing env var does NOT
    crash the app on import — it only fails when the endpoint is called.
    """
    token = os.environ.get("METAAPI_TOKEN", "")
    if not token:
        raise RuntimeError(
            "METAAPI_TOKEN environment variable is not set. "
            "Add it in Render → Environment → Environment Variables."
        )
    return {"auth-token": token, "Content-Type": "application/json"}


async def test_connection(
    broker:   str,
    login:    str,
    password: str,
    server:   str,
) -> dict:
    """
    1. Provision a temporary MetaAPI account.
    2. Deploy it and wait for connection.
    3. Fetch balance / equity from the CLIENT API (not provisioning).
    4. Undeploy and remove the account — no orphaned cloud resources.

    Returns a plain dict:
      success → { connected, balance, equity, currency, leverage, server, latency_ms }
      failure → { connected: False, error: str }
    """
    account_id: Optional[str] = None
    t_start = time.time()

    try:
        hdrs = _headers()
    except RuntimeError as e:
        return {"connected": False, "error": str(e)}

    try:
        async with httpx.AsyncClient(timeout=30) as client:

            # ── 1. Provision ─────────────────────────────────────────────────
            prov = await client.post(
                f"{PROVISIONING_URL}/users/current/accounts",
                headers=hdrs,
                json={
                    "name":        f"MM-test-{login[-4:]}",
                    "type":        "cloud",
                    "login":       login,
                    "password":    password,
                    "server":      server,
                    "platform":    "mt5",
                    "application": "RPC",
                    "magic":       0,
                },
            )
            if prov.status_code not in (200, 201):
                return {"connected": False,
                        "error": _parse_error(prov)}
            account_id = prov.json()["_id"]
            log.info("metaapi_test_provisioned", account_id=account_id[-8:])

            # ── 2. Deploy ─────────────────────────────────────────────────────
            dep = await client.post(
                f"{PROVISIONING_URL}/users/current/accounts/{account_id}/deploy",
                headers=hdrs,
            )
            if dep.status_code not in (200, 204):
                return {"connected": False, "error": _parse_error(dep)}

            # ── 3. Poll until CONNECTED ───────────────────────────────────────
            deadline = time.time() + DEPLOY_TIMEOUT_S
            while time.time() < deadline:
                status = await client.get(
                    f"{PROVISIONING_URL}/users/current/accounts/{account_id}",
                    headers=hdrs,
                )
                state = status.json()
                conn  = state.get("connectionStatus", "")
                phase = state.get("state", "")
                log.debug("metaapi_poll", state=phase, connection=conn)

                if conn == "CONNECTED":
                    break
                if phase in ("FAILED", "ERROR"):
                    return {"connected": False,
                            "error": f"Deployment failed: {state.get('quoteStreamingIntervalInSeconds', conn)}"}
                await asyncio.sleep(POLL_INTERVAL_S)
            else:
                return {"connected": False,
                        "error": f"Broker server '{server}' did not connect within {DEPLOY_TIMEOUT_S}s. "
                                 "Verify the server name in your MT5 terminal."}

            # ── 4. Fetch account information via CLIENT API ───────────────────
            info_resp = await client.get(
                f"{CLIENT_URL}/users/current/accounts/{account_id}/account-information",
                headers=hdrs,
            )
            if info_resp.status_code != 200:
                return {"connected": False,
                        "error": f"Connected but could not read account data: {_parse_error(info_resp)}"}

            info    = info_resp.json()
            latency = round((time.time() - t_start) * 1000)

            log.info("metaapi_test_success",
                     broker=broker, balance=info.get("balance"), latency_ms=latency)

            return {
                "connected":  True,
                "balance":    info.get("balance"),
                "equity":     info.get("equity"),
                "currency":   info.get("currency", "USD"),
                "leverage":   info.get("leverage"),
                "server":     server,
                "latency_ms": latency,
            }

    except RuntimeError as e:
        return {"connected": False, "error": str(e)}
    except httpx.TimeoutException:
        return {"connected": False, "error": "Request timed out — MetaAPI may be slow. Try again."}
    except Exception as exc:
        log.error("metaapi_test_error", error=str(exc))
        return {"connected": False, "error": _human_error(str(exc))}

    finally:
        # Always clean up the test account — never leave orphaned resources
        if account_id:
            await _cleanup(account_id)


async def provision_account(
    chat_id:  str,
    broker:   str,
    login:    str,
    password: str,
    server:   str,
    nickname: str,
) -> dict:
    """
    Provision a permanent MetaAPI account for a subscriber.
    Returns { ok: True, meta_api_account_id } or { ok: False, error }.
    """
    try:
        hdrs = _headers()
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            prov = await client.post(
                f"{PROVISIONING_URL}/users/current/accounts",
                headers=hdrs,
                json={
                    "name":        f"MM-{chat_id[-6:]}-{nickname[:20]}",
                    "type":        "cloud",
                    "login":       login,
                    "password":    password,
                    "server":      server,
                    "platform":    "mt5",
                    "application": "RPC",
                    "magic":       0,
                },
            )
            if prov.status_code not in (200, 201):
                return {"ok": False, "error": _parse_error(prov)}

            account_id = prov.json()["_id"]

            dep = await client.post(
                f"{PROVISIONING_URL}/users/current/accounts/{account_id}/deploy",
                headers=hdrs,
            )
            if dep.status_code not in (200, 204):
                return {"ok": False, "error": _parse_error(dep)}

            # Wait for connection
            deadline = time.time() + DEPLOY_TIMEOUT_S
            while time.time() < deadline:
                status = await client.get(
                    f"{PROVISIONING_URL}/users/current/accounts/{account_id}",
                    headers=hdrs,
                )
                if status.json().get("connectionStatus") == "CONNECTED":
                    break
                await asyncio.sleep(POLL_INTERVAL_S)
            else:
                await _cleanup(account_id)
                return {"ok": False, "error": "Broker did not connect in time. Check server name."}

            log.info("metaapi_provision_success",
                     chat_id=chat_id, account_id=account_id[-8:])
            return {"ok": True, "meta_api_account_id": account_id}

    except Exception as exc:
        log.error("metaapi_provision_error", error=str(exc))
        return {"ok": False, "error": _human_error(str(exc))}


async def remove_account(meta_api_account_id: str) -> None:
    """Undeploy and remove a MetaAPI account. Best-effort — never raises."""
    await _cleanup(meta_api_account_id)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _cleanup(account_id: str) -> None:
    """Undeploy then remove. Swallows all errors."""
    try:
        hdrs = _headers()
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(
                f"{PROVISIONING_URL}/users/current/accounts/{account_id}/undeploy",
                headers=hdrs,
            )
            await asyncio.sleep(1)
            await client.delete(
                f"{PROVISIONING_URL}/users/current/accounts/{account_id}",
                headers=hdrs,
            )
        log.debug("metaapi_account_cleaned_up", account_id=account_id[-8:])
    except Exception as exc:
        log.warning("metaapi_cleanup_failed", error=str(exc))


def _parse_error(response: httpx.Response) -> str:
    """Extract a readable message from a failed MetaAPI response."""
    try:
        body = response.json()
        return body.get("message") or body.get("error") or str(body)
    except Exception:
        return f"HTTP {response.status_code}"


def _human_error(raw: str) -> str:
    s = raw.lower()
    if "40102" in raw or "invalid login" in s:
        return "Invalid account number. Double-check the digits."
    if "40103" in raw or "invalid password" in s:
        return "Incorrect password. Careful — 3 wrong attempts can lock the account."
    if "40104" in raw or "invalid server" in s:
        return "Server not found. Check the exact server name in MT5 → bottom status bar."
    if "timeout" in s:
        return "Connection timed out. The broker server may be busy — try again in 30 seconds."
    if "quota" in s or "limit" in s:
        return "MetaAPI rate limit reached. Please try again in a few minutes."
    return raw[:200]
