"""
marketmate.platform
────────────────────
Platform-level concerns: web API routes, subscription lifecycle, newsletter.

This module is the top-level orchestrator for user-facing features.
It must NEVER import from marketmate.strategy or marketmate.execution
— those are internal engine modules with no place in the platform layer.

Packages:
  academy_api    — FastAPI APIRouter for MMAcademy API routes
  academy_repo   — MongoDB-only MMAcademy data access
  subscription   — Subscriber lifecycle, billing, and trial management
  newsletter     — AI-written weekly newsletter via Groq + Resend
  social_repo    — Social engagement data access
"""
