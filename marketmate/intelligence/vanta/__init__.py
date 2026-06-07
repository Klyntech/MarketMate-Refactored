"""
marketmate.intelligence.vanta
─────────────────────────────
VANTA: Truth Validator + System Builder Agent

THE ONLY layer with creation/building capabilities.
Judgment brain — validates correctness of intelligence and builds systems when needed.

Position in pipeline:
  RAW DATA → PRISM → VINNI → ATLAS → [VANTA] → NOVA → Users

Created: 2026-05-29
"""

from marketmate.intelligence.vanta.agent import VantaAgent, VantaValidation, VantaBuildPlan

__all__ = ["VantaAgent", "VantaValidation", "VantaBuildPlan"]
