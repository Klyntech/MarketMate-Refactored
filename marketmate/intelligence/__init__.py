"""
marketmate.intelligence
────────────────────────
MarketMate 6-Layer Intelligence Stack — Phase 3

Data Flow:
  RAW MARKET DATA → PRISM (data integrity) → VINNI (data monitoring)
  → ATLAS (market reasoning) → VANTA (validation + agent)
  → NOVA (user delivery) → Users/API/Telegram

  OPS runs parallel — infrastructure operations, keeping system alive.

Layer Responsibilities:
  PRISM  — Data truth. Passive, strict, mathematical. NON-AGENT.
  VINNI  — Data observation. Watch, analyze, report. OBSERVATION ONLY.
  ATLAS  — Market meaning. Structure, reasoning, multi-timeframe. ANALYSIS.
  VANTA  — System judgment. Validation + bounded creation. THE AGENT.
  NOVA   — User communication. Fast, accessible, public-facing. DELIVERY.
  OPS    — Infrastructure control. Deploy, scale, heal. MACHINE CONTROL.

Critical Rule: Each layer NEVER overlaps responsibilities.
If they overlap → the system becomes unstable.

Created: 2026-05-29
Phase: 3 (High Agency)
"""

from marketmate.intelligence.prism import PrismValidator, PrismResult
from marketmate.intelligence.vinni import VinniMonitor, VinniDiagnostic
from marketmate.intelligence.atlas import AtlasEngine, AtlasAnalysis
from marketmate.intelligence.nova import NovaLayer, NovaSummary
from marketmate.intelligence.vanta import VantaAgent, VantaValidation, VantaBuildPlan
from marketmate.intelligence.ops import OpsController, OpsAction, OpsResult

__all__ = [
    "PrismValidator", "PrismResult",
    "VinniMonitor", "VinniDiagnostic",
    "AtlasEngine", "AtlasAnalysis",
    "NovaLayer", "NovaSummary",
    "VantaAgent", "VantaValidation", "VantaBuildPlan",
    "OpsController", "OpsAction", "OpsResult",
]
