"""
marketmate.intelligence.ops
───────────────────────────
OPS: System Operations Layer

FULLY INTERNAL. Never public-facing.
Machine control brain — keeps the system alive, reliable, and scalable.

Position: Runs parallel to the intelligence pipeline.
  RAW DATA → PRISM → VINNI → ATLAS → VANTA → NOVA → Users
                              ↑ OPS (infrastructure) ↑

Created: 2026-05-29
"""

from marketmate.intelligence.ops.controller import OpsController, OpsAction, OpsResult

__all__ = ["OpsController", "OpsAction", "OpsResult"]
