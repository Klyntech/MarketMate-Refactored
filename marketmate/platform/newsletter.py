"""
marketmate.platform.newsletter
───────────────────────────────
AI-written weekly newsletter.

Stack: Groq (llama-3.3-70b) writes it. Resend delivers it.

Env vars required:
  GROQ_API_KEY      — from console.groq.com (free)
  RESEND_API_KEY    — from resend.com (free, 3000/month)
  RESEND_FROM_EMAIL — e.g. "MarketMate <signals@yourdomain.com>"
  SITE_URL          — e.g. "https://newmate.onrender.com"

Triggered by:
  POST /api/newsletter/send  (protected by NEWSLETTER_SECRET)
  Set a weekly cron on cron-job.org — free, no server needed.

Migrated from newsletter.py.
Import paths updated to marketmate.* prefix.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

GROQ_API     = "https://api.groq.com/openai/v1/chat/completions"
RESEND_API   = "https://api.resend.com/emails"
LEADS_PATH   = "leads.json"


# ─── Load email list ──────────────────────────────────────────────────────────
def load_leads() -> list[str]:
    try:
        with open(LEADS_PATH) as f:
            data = json.load(f)
        return [l["email"] for l in data if l.get("email")]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# ─── Groq: write the newsletter ───────────────────────────────────────────────
async def write_newsletter(week: str) -> dict:
    """
    Calls Groq (llama-3.3-70b — fast, free tier).
    Returns { subject, html } — ready to send.
    """
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        raise ValueError("GROQ_API_KEY not set")

    site_url = os.environ.get("SITE_URL", "https://newmate.onrender.com")

    system_prompt = """You write a weekly XAUUSD trading newsletter for MarketMate.

Rules:
- Concise. No over-writing. Every sentence earns its place.
- Cover only what matters: market structure, key levels, what to watch next week.
- No hype. No "amazing opportunity" language. Institutional tone.
- Include one educational SMC concept (1 paragraph max).
- Output ONLY valid JSON: { "subject": "...", "html": "..." }
- HTML must be self-contained email HTML. Dark background (#0A0B0C). Gold accent (#D4AF37). 
  Max-width 600px. Mobile friendly. Include unsubscribe note at bottom.
- No markdown in the JSON values. Proper escaped HTML only."""

    user_prompt = f"""Write the MarketMate newsletter for the week of {week}.

Include:
1. XAUUSD weekly bias (bullish/bearish/neutral) and WHY in 2-3 sentences.
2. Key levels to watch (2-3 price zones, be specific with ranges).
3. What sessions to focus on and why.
4. One SMC concept explained simply — this week focus on whichever is most relevant (order blocks, FVG, liquidity sweep, BOS/CHoCH).
5. One sentence on risk: remind them to size correctly.

Tone: Direct. Analytical. Like a senior trader briefing a junior. Not a sales pitch."""

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            GROQ_API,
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                "temperature": 0.6,
                "max_tokens":  1800,
                "response_format": {"type": "json_object"},
            },
        )
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]

    result = json.loads(content)

    # Inject unsubscribe footer if not already present
    if "unsubscribe" not in result["html"].lower():
        result["html"] += f"""
        <div style="margin-top:40px;padding-top:20px;border-top:1px solid rgba(255,255,255,0.06);
                    text-align:center;font-family:monospace;font-size:11px;color:rgba(255,255,255,0.2);">
          © MarketMate &nbsp;·&nbsp;
          <a href="{site_url}" style="color:#D4AF37;text-decoration:none;">newmate.onrender.com</a>
          &nbsp;·&nbsp;
          You received this because you signed up for a free trial.
        </div>"""

    return result


# ─── Resend: batch send ───────────────────────────────────────────────────────
async def send_newsletter(subject: str, html: str, recipients: list[str]) -> dict:
    """
    Sends one email per recipient via Resend.
    Resend free tier: 3,000 emails/month, 100/day.
    For larger lists: use Resend's broadcast feature (paid).
    """
    resend_key  = os.environ.get("RESEND_API_KEY", "")
    from_email  = os.environ.get("RESEND_FROM_EMAIL", "MarketMate <onboarding@resend.dev>")

    if not resend_key:
        raise ValueError("RESEND_API_KEY not set")

    sent, failed = 0, []

    async with httpx.AsyncClient(timeout=15) as client:
        for email in recipients:
            try:
                res = await client.post(
                    RESEND_API,
                    headers={
                        "Authorization": f"Bearer {resend_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from":    from_email,
                        "to":      [email],
                        "subject": subject,
                        "html":    html,
                    },
                )
                if res.status_code in (200, 201):
                    sent += 1
                else:
                    failed.append({"email": email, "error": res.text})
            except Exception as e:
                failed.append({"email": email, "error": str(e)})

    return {"sent": sent, "failed": failed, "total": len(recipients)}


# ─── Main entry: called from FastAPI route ────────────────────────────────────
async def run_newsletter() -> dict:
    week    = datetime.now(timezone.utc).strftime("%B %d, %Y")
    leads   = load_leads()

    if not leads:
        return {"ok": False, "error": "No leads to send to", "count": 0}

    log.info("newsletter_start", week=week, recipients=len(leads))

    newsletter = await write_newsletter(week)
    result     = await send_newsletter(newsletter["subject"], newsletter["html"], leads)

    log.info("newsletter_done", **result)
    return {"ok": True, "week": week, "subject": newsletter["subject"], **result}
