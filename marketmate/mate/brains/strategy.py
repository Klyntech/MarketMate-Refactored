"""
marketmate.mate.brains.strategy
───────────────────────────────
Strategy Brain — academy, education, and strategy theory explanations.

Capability Domain:
  - SMC concepts: "What is BOS?", "Explain CHoCH"
  - RR explanations: "How does risk-reward work?"
  - Strategy parameters: "What's the min RR threshold?"
  - Gate pipeline: "How does signal generation work?"
  - Session rules: "When does MarketMate scan?"

Functions:
  explain_concept(concept)           → BOS, CHoCH, FVG, OB, liquidity sweep, etc.
  get_strategy_params()              → current strategy configuration
  explain_gate_pipeline()            → G1-G8 gate logic
  get_session_schedule()             → London/NY session times

This brain answers from config and documentation — NOT from live data.
The LLM narrates but the definitions come from the strategy codebase.
"""

from __future__ import annotations

from typing import Any, Dict

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("mate.brains.strategy")


class StrategyBrain:
    """
    Financial cognition primitive for strategy theory and education.

    Answers: SMC concepts, strategy params, gate pipeline, session schedule.
    Does NOT answer: live prices, signal counts, account balance.
    """

    # ── SMC Concept Definitions ─────────────────────────────────────────────
    CONCEPTS = {
        "bos": {
            "name": "Break of Structure (BOS)",
            "definition": (
                "A BOS occurs when price breaks a significant swing point in the direction "
                "of the prevailing trend. In an uptrend, a BOS is a break above a prior swing high. "
                "In a downtrend, it is a break below a prior swing low. BOS confirms trend continuation "
                "and is used by MarketMate as LTF (lower timeframe) confirmation that the pullback is over "
                "and the original trend is resuming."
            ),
        },
        "choch": {
            "name": "Change of Character (CHoCH)",
            "definition": (
                "A CHoCH is the first break of structure against the prevailing trend — it signals "
                "a potential trend reversal. In an uptrend, a CHoCH is a break below the last higher low. "
                "In a downtrend, it is a break above the last lower high. MarketMate uses CHoCH as "
                "confirmation that market structure has shifted and a counter-trend setup may be forming."
            ),
        },
        "fvg": {
            "name": "Fair Value Gap (FVG)",
            "definition": (
                "A FVG is a 3-candle imbalance where the high of candle 1 does not overlap with "
                "the low of candle 3 (bullish FVG) or the low of candle 1 does not overlap with "
                "the high of candle 3 (bearish FVG). This gap represents inefficient price delivery — "
                "the market tends to revisit these zones to fill the gap. MarketMate uses FVGs as "
                "entry zones and requires a minimum FVG size (pct of price) and freshness (recent candles)."
            ),
        },
        "ob": {
            "name": "Order Block (OB)",
            "definition": (
                "An Order Block is the last bearish candle before a bullish impulse move (bullish OB) "
                "or the last bullish candle before a bearish impulse move (bearish OB). These represent "
                "institutional accumulation/distribution zones. MarketMate identifies OBs with minimum "
                "displacement candles and expiry limits — old OBs lose potency."
            ),
        },
        "sweep": {
            "name": "Liquidity Sweep",
            "definition": (
                "A liquidity sweep occurs when price moves beyond a key swing high or swing low to "
                "trigger stop losses and pending orders, then reverses sharply. This is institutional "
                "behavior — large players need liquidity to fill their positions. MarketMate requires "
                "a recent sweep as part of signal generation — signals without a sweep are rejected at Gate 5."
            ),
        },
        "rr": {
            "name": "Risk-Reward Ratio (RR)",
            "definition": (
                "The Risk-Reward Ratio compares the potential loss (distance to stop loss) with the "
                "potential gain (distance to take profit). A 1:2 RR means risking 1 unit to gain 2. "
                f"MarketMate requires a minimum RR of {cfg.strategy.min_rr} — signals with lower RR "
                "are rejected at Gate 8. Higher RR signals are prioritized in scoring."
            ),
        },
        "liquidity": {
            "name": "Liquidity",
            "definition": (
                "In SMC, liquidity refers to clusters of stop losses and pending orders resting above "
                "key swing highs (buy stops) and below key swing lows (sell stops). Institutional traders "
                "target these zones to fill large positions. MarketMate's sweep detection identifies when "
                "these liquidity pools are being taken."
            ),
        },
        "htf_bias": {
            "name": "Higher Timeframe Bias",
            "definition": (
                "HTF Bias is the directional bias determined from higher timeframe charts (daily, 4H). "
                "MarketMate uses EMA alignment and swing structure on HTF to determine whether the "
                "dominant trend is bullish, bearish, or neutral. Signals against HTF bias are filtered "
                "at Gate 4 — only neutral bias with a confirmed sweep is allowed."
            ),
        },
    }

    # ── Gate Pipeline Definitions ───────────────────────────────────────────
    GATES = {
        "G1_SESSION": "Weekend check + trading session filter (London/NY hours only)",
        "G2_DAILY_LIMIT": "Max trades per day / per direction per day",
        "G2b_DRAWDOWN": "Max consecutive losses — pauses trading if threshold hit",
        "G3_NEWS": "High-impact economic event window filter",
        "G4_HTF_BIAS": "Higher timeframe bias must be directional (or neutral with sweep)",
        "G5_SWEEP": "Recent liquidity sweep must exist near price",
        "G6_ZONE": "Valid order block or fair value gap must be present",
        "G7_LTF_CONFIRM": "Lower timeframe BOS or CHoCH confirmation required",
        "G8_RR": f"Risk-reward ratio must meet minimum ({cfg.strategy.min_rr})",
        "DEDUP": "Duplicate signal filter: cooldown, zone overlap, price proximity, flip cooldown",
    }

    # ═════════════════════════════════════════════════════════════════════════
    # Core Brain Functions
    # ═════════════════════════════════════════════════════════════════════════

    async def explain_concept(self, concept: str) -> Dict[str, Any]:
        """
        Explain an SMC concept by name.

        Handles: BOS, CHoCH, FVG, OB, sweep, RR, liquidity, HTF bias.
        """
        key = concept.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
        # Map common variations
        key_map = {
            "breakofstructure": "bos",
            "changeofcharacter": "choch",
            "fairvaluegap": "fvg",
            "orderblock": "ob",
            "liquiditysweep": "sweep",
            "riskreward": "rr",
            "riskrewardratio": "rr",
            "highertimeframebias": "htf_bias",
        }
        key = key_map.get(key, key)

        if key in self.CONCEPTS:
            return {"concept": key, **self.CONCEPTS[key]}
        return {
            "concept": concept,
            "status": "unknown_concept",
            "available": list(self.CONCEPTS.keys()),
        }

    async def get_strategy_params(self) -> Dict[str, Any]:
        """Get the current strategy configuration."""
        return {
            "pairs": cfg.strategy.pairs,
            "max_trades_per_day": cfg.strategy.max_trades_per_day,
            "max_trades_per_direction_per_day": cfg.strategy.max_trades_per_direction_per_day,
            "min_rr": cfg.strategy.min_rr,
            "dedup_cooldown_minutes": cfg.strategy.dedup_cooldown_minutes,
            "risk_per_trade_pct": cfg.risk.risk_per_trade_pct,
            "account_size": cfg.risk.account_size,
            "max_consecutive_losses": cfg.risk.max_consecutive_losses,
            "scan_interval_seconds": cfg.app.scan_interval_seconds,
        }

    async def explain_gate_pipeline(self) -> Dict[str, Any]:
        """
        Explain the full signal generation gate pipeline.

        Returns the G1-G8 gate logic and dedup filter.
        """
        return {
            "pipeline": "Signal Generation Pipeline",
            "gates": self.GATES,
            "flow": (
                "Market Scan → G1 (Session) → G2 (Daily Limit) → G2b (Drawdown) → "
                "G3 (News) → G4 (HTF Bias) → G5 (Sweep) → G6 (Zone) → "
                "G7 (LTF Confirm) → G8 (RR) → Dedup → Signal Generated"
            ),
            "scoring": (
                "Signals are assessed on 4 binary factors: sweep close-inside, "
                "order-block zone, CHoCH confirmation, M15 timeframe. "
                "Score >= 3 → HIGH confidence, else MEDIUM. "
                "No minimum score threshold — all signals that pass G1-G8 are emitted."
            ),
        }

    async def get_session_schedule(self) -> Dict[str, Any]:
        """Get the trading session schedule."""
        return {
            "london": f"{cfg.strategy.london_open} - {cfg.strategy.london_close} UTC",
            "new_york": f"{cfg.strategy.ny_open} - {cfg.strategy.ny_close} UTC",
            "scan_interval": f"Every {cfg.app.scan_interval_seconds}s during sessions",
            "pairs": cfg.strategy.pairs,
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

strategy_brain = StrategyBrain()
