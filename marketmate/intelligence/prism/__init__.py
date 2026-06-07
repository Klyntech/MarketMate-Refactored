"""
marketmate.intelligence.prism
─────────────────────────────
PRISM: Data Integrity + Market Reality Layer

PASSIVE. STRICT. MATHEMATICAL. BORING.
NOT an agent. Does NOT take actions. Does NOT modify data.
Only validates, verifies, and reports.

All market data passes through PRISM before reaching any other layer.
If PRISM flags data as unreliable, downstream layers MUST respect that.

Position in pipeline:
  RAW MARKET DATA → [PRISM] → VINNI → ATLAS → VANTA → NOVA → Users

Checks:
  - Feed validation: missing candles, stale prices, websocket disconnects
  - Cross-provider price verification
  - Timestamp drift detection
  - Candle integrity: malformed OHLC, impossible highs/lows, duplicates
  - Provider reliability scoring
  - Data normalization verification
  - State engine input validation gate

Created: 2026-05-29
"""

from marketmate.intelligence.prism.validator import (
    PrismValidator,
    PrismResult,
    PrismCheck,
    PrismSeverity,
    PrismAction,
)

__all__ = ["PrismValidator", "PrismResult", "PrismCheck", "PrismSeverity", "PrismAction"]
