"""
marketmate.intelligence.nova
────────────────────────────
NOVA: Real-time Market Companion (Entry Layer)

Fast. Accessible. Everyday intelligence.
Public-facing brain of MarketMate.

Position in pipeline:
  RAW DATA → PRISM → VINNI → ATLAS → VANTA → [NOVA] → Users

Created: 2026-05-29
"""

from marketmate.intelligence.nova.layer import NovaLayer, NovaSummary

__all__ = ["NovaLayer", "NovaSummary"]
