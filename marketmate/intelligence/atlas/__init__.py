"""
marketmate.intelligence.atlas
─────────────────────────────
ATLAS: Core Market Intelligence Engine

Understands structure and meaning of the market.
Sees STRUCTURE, not just movement.
Explains "why", not just "what".
Connects MULTIPLE timeframes.
Interprets LIQUIDITY behavior.

Position in pipeline:
  RAW DATA → PRISM → VINNI → [ATLAS] → VANTA → NOVA

Created: 2026-05-29
"""

from marketmate.intelligence.atlas.engine import AtlasEngine, AtlasAnalysis

__all__ = ["AtlasEngine", "AtlasAnalysis"]
