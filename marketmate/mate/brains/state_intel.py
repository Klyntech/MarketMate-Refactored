"""
marketmate.mate.brains.state_intel
───────────────────────────────────
State Intelligence Brain — reads compiled InstrumentState from the StateEngine.

This is the KEY Phase 3 bridge: MATE now consumes the v8.0.0 compiled state
(Scan → Features → State → Events → MATE), NOT the legacy flat Redis dicts.

Capability Domain:
  - Market regime: "What's the current regime for gold?"
  - Conviction scores: "How bullish is EURUSD right now?"
  - Zone state: "Are there active order blocks on BTCUSD?"
  - Liquidity state: "Has there been a liquidity sweep on XAUUSD?"
  - Confirmation alignment: "Is the confirmation aligned with bias?"
  - State transitions: "Has gold's bias changed recently?"
  - Cross-instrument regime: "What's the overall market regime?"

Functions:
  get_instrument_state(symbol)     → full InstrumentState for a symbol
  get_market_regime()              → regime across all instruments
  get_conviction_chart()           → conviction scores for all instruments
  get_state_transitions(symbol)    → recent StateDiff transitions
  get_zone_state(symbol)           → active/approaching zones
  get_liquidity_state(symbol)      → sweep status, available liquidity

This brain NEVER fabricates state.
It reads from StateEngine (memory → Redis → None).
The LLM only narrates what this brain compiles.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("mate.brains.state_intel")


class StateIntelBrain:
    """
    Financial cognition primitive for compiled market state.

    Answers: regime, conviction, zone state, liquidity state, transitions.
    Does NOT answer: live prices, signal counts, account balance, strategy theory.

    This brain is the PRIMARY consumer of the v8.0.0 StateEngine output.
    It reads InstrumentState models — not raw features, not flat Redis dicts.
    """

    # ═════════════════════════════════════════════════════════════════════════
    # Core Brain Functions
    # ═════════════════════════════════════════════════════════════════════════

    async def get_instrument_state(self, symbol: str) -> Dict[str, Any]:
        """
        Get the full compiled InstrumentState for a symbol.

        This is the canonical state vector — bias, liquidity, zones,
        confirmation, risk — all normalized from the gate pipeline.
        """
        symbol = symbol.upper().strip()

        try:
            from marketmate.state.engine import get_state_engine
            state_engine = get_state_engine()
            state = await state_engine.get_instrument_state(symbol)

            if state is None:
                return {
                    "symbol": symbol,
                    "status": "no_state",
                    "hint": f"No compiled state available for {symbol}. The StateEngine may not have processed a scan for this symbol yet.",
                }

            return self._format_instrument_state(state)

        except Exception as exc:
            log.warning("state_intel_get_failed", symbol=symbol, error=str(exc))
            return {"symbol": symbol, "status": "error", "error": str(exc)}

    async def get_market_regime(self) -> Dict[str, Any]:
        """
        Get the current market regime across all tracked instruments.

        Returns per-instrument regime classification and the overall
        market regime from the MarketStateVector.
        """
        try:
            from marketmate.state.engine import get_state_engine
            state_engine = get_state_engine()
            market_state = await state_engine.get_market_state()

            instruments = {}
            for sym, state in market_state.instruments.items():
                instruments[sym] = {
                    "directional_regime": state.bias_state.regime.value,
                    "volatility_regime": state.risk_state.volatility_regime.value,
                    "conviction": round(state.bias_state.conviction_score, 3),
                    "bias": state.bias_state.daily_bias.value,
                    "active_zones": len(state.zone_state.active_zones),
                    "available_liquidity": round(
                        state.liquidity_state.available_liquidity_score, 3
                    ),
                }

            return {
                "market_regime": market_state.market_regime.value,
                "instruments": instruments,
                "scan_cycle": market_state.scan_cycle,
                "updated_at": market_state.updated_at.isoformat(),
                "instrument_count": len(instruments),
            }

        except Exception as exc:
            log.warning("market_regime_failed", error=str(exc))
            return {"status": "error", "error": str(exc)}

    async def get_conviction_chart(self) -> Dict[str, Any]:
        """
        Get conviction scores across all tracked instruments.

        Returns a compact view suitable for building real-time conviction
        charts — scores range from -1.0 (bearish) to +1.0 (bullish).
        """
        try:
            from marketmate.state.engine import get_state_engine
            state_engine = get_state_engine()
            market_state = await state_engine.get_market_state()

            convictions = {}
            for sym, state in market_state.instruments.items():
                convictions[sym] = {
                    "conviction_score": round(state.bias_state.conviction_score, 3),
                    "bias": state.bias_state.daily_bias.value,
                    "regime": state.bias_state.regime.value,
                    "volatility_regime": state.risk_state.volatility_regime.value,
                    "active_zones": len(state.zone_state.active_zones),
                    "scan_count": state.scan_count,
                    "last_scan_at": state.last_scan_at.isoformat(),
                }

            return {
                "convictions": convictions,
                "market_regime": market_state.market_regime.value,
                "scan_cycle": market_state.scan_cycle,
            }

        except Exception as exc:
            log.warning("conviction_chart_failed", error=str(exc))
            return {"status": "error", "error": str(exc)}

    async def get_state_transitions(self, symbol: str = "") -> Dict[str, Any]:
        """
        Get recent state transition events from the StateObserver.

        Returns the most recent state diffs/transitions, optionally
        filtered by symbol. These represent the material changes
        in market state — bias flips, zone formation, sweeps, etc.
        """
        try:
            from marketmate.mate.observer import state_observer

            if symbol:
                transitions = state_observer.get_recent_transitions(
                    symbol.upper().strip()
                )
            else:
                transitions = state_observer.get_all_recent_transitions()

            return {
                "transitions": transitions,
                "count": len(transitions),
                "source": "state_observer",
            }

        except Exception as exc:
            log.warning("state_transitions_failed", symbol=symbol, error=str(exc))
            return {"status": "error", "transitions": [], "error": str(exc)}

    async def get_zone_state(self, symbol: str) -> Dict[str, Any]:
        """
        Get the zone state (active/approaching/expired) for a symbol.

        Returns order block and FVG zones with freshness scores and
        status classification.
        """
        symbol = symbol.upper().strip()

        try:
            from marketmate.state.engine import get_state_engine
            state_engine = get_state_engine()
            state = await state_engine.get_instrument_state(symbol)

            if state is None:
                return {"symbol": symbol, "status": "no_state"}

            zs = state.zone_state

            active = [
                {
                    "zone_type": z.zone_type,
                    "direction": z.direction,
                    "zone_high": z.zone_high,
                    "zone_low": z.zone_low,
                    "zone_mid": z.zone_mid,
                    "freshness": z.freshness_score,
                    "formed_at": z.formed_at.isoformat(),
                }
                for z in zs.active_zones
            ]

            approaching = [
                {
                    "zone_type": z.zone_type,
                    "direction": z.direction,
                    "zone_high": z.zone_high,
                    "zone_low": z.zone_low,
                    "freshness": z.freshness_score,
                }
                for z in zs.approaching_zones
            ]

            return {
                "symbol": symbol,
                "active_zones": active,
                "approaching_zones": approaching,
                "expired_count": len(zs.expired_zones),
                "zone_freshness": round(zs.zone_freshness, 3),
                "active_count": len(active),
                "approaching_count": len(approaching),
            }

        except Exception as exc:
            log.warning("zone_state_failed", symbol=symbol, error=str(exc))
            return {"symbol": symbol, "status": "error", "error": str(exc)}

    async def get_liquidity_state(self, symbol: str) -> Dict[str, Any]:
        """
        Get the liquidity state for a symbol.

        Returns active liquidity levels, recent sweeps, and the
        available liquidity score.
        """
        symbol = symbol.upper().strip()

        try:
            from marketmate.state.engine import get_state_engine
            state_engine = get_state_engine()
            state = await state_engine.get_instrument_state(symbol)

            if state is None:
                return {"symbol": symbol, "status": "no_state"}

            ls = state.liquidity_state

            recent_sweeps = [
                {
                    "price": s.price,
                    "level_type": s.level_type,
                    "swept_at": s.swept_at.isoformat() if s.swept_at else None,
                }
                for s in ls.recent_sweeps
            ]

            active_levels_count = len(ls.active_levels)
            # Summarize level types
            swing_highs = sum(
                1 for lvl in ls.active_levels if lvl.level_type == "swing_high"
            )
            swing_lows = sum(
                1 for lvl in ls.active_levels if lvl.level_type == "swing_low"
            )

            return {
                "symbol": symbol,
                "available_liquidity_score": round(
                    ls.available_liquidity_score, 3
                ),
                "active_levels_count": active_levels_count,
                "swing_highs": swing_highs,
                "swing_lows": swing_lows,
                "recent_sweeps": recent_sweeps,
                "sweep_rate": round(ls.sweep_rate, 3),
                "has_recent_sweep": len(recent_sweeps) > 0,
            }

        except Exception as exc:
            log.warning("liquidity_state_failed", symbol=symbol, error=str(exc))
            return {"symbol": symbol, "status": "error", "error": str(exc)}

    async def get_confirmation_state(self, symbol: str) -> Dict[str, Any]:
        """
        Get the confirmation (BOS/CHoCH) state for a symbol.

        Returns recent BOS/CHoCH patterns, alignment score with bias,
        and pattern rate.
        """
        symbol = symbol.upper().strip()

        try:
            from marketmate.state.engine import get_state_engine
            state_engine = get_state_engine()
            state = await state_engine.get_instrument_state(symbol)

            if state is None:
                return {"symbol": symbol, "status": "no_state"}

            cs = state.confirm_state

            recent_bos = [
                {
                    "direction": p.direction,
                    "break_level": p.break_level,
                    "timeframe": p.timeframe,
                    "detected_at": p.detected_at.isoformat() if p.detected_at else None,
                }
                for p in cs.recent_bos
            ]

            recent_choch = [
                {
                    "direction": p.direction,
                    "break_level": p.break_level,
                    "timeframe": p.timeframe,
                    "detected_at": p.detected_at.isoformat() if p.detected_at else None,
                }
                for p in cs.recent_choch
            ]

            return {
                "symbol": symbol,
                "alignment_score": round(cs.alignment_score, 3),
                "pattern_rate": round(cs.pattern_rate, 3),
                "recent_bos": recent_bos,
                "recent_choch": recent_choch,
                "bos_count": len(recent_bos),
                "choch_count": len(recent_choch),
            }

        except Exception as exc:
            log.warning("confirmation_state_failed", symbol=symbol, error=str(exc))
            return {"symbol": symbol, "status": "error", "error": str(exc)}

    # ═════════════════════════════════════════════════════════════════════════
    # Formatting
    # ═════════════════════════════════════════════════════════════════════════

    def _format_instrument_state(self, state) -> Dict[str, Any]:
        """Format a full InstrumentState into a MATE-friendly dict."""
        return {
            "symbol": state.symbol,
            "bias": {
                "daily_bias": state.bias_state.daily_bias.value,
                "h4_bias": state.bias_state.h4_bias.value,
                "daily_structure": state.bias_state.daily_structure,
                "h4_structure": state.bias_state.h4_structure,
                "conviction_score": round(state.bias_state.conviction_score, 3),
                "regime": state.bias_state.regime.value,
                "resolution_path": state.bias_state.resolution_path,
                "daily_above_ema200": state.bias_state.daily_above_ema,
                "h4_above_ema200": state.bias_state.h4_above_ema,
            },
            "liquidity": {
                "available_liquidity_score": round(
                    state.liquidity_state.available_liquidity_score, 3
                ),
                "active_levels_count": len(state.liquidity_state.active_levels),
                "recent_sweeps_count": len(state.liquidity_state.recent_sweeps),
                "sweep_rate": round(state.liquidity_state.sweep_rate, 3),
                "has_recent_sweep": len(state.liquidity_state.recent_sweeps) > 0,
            },
            "zones": {
                "active_zones_count": len(state.zone_state.active_zones),
                "approaching_zones_count": len(state.zone_state.approaching_zones),
                "expired_zones_count": len(state.zone_state.expired_zones),
                "zone_freshness": round(state.zone_state.zone_freshness, 3),
                "active_zone_types": list(
                    {z.zone_type for z in state.zone_state.active_zones}
                ),
            },
            "confirmation": {
                "alignment_score": round(state.confirm_state.alignment_score, 3),
                "pattern_rate": round(state.confirm_state.pattern_rate, 3),
                "bos_count": len(state.confirm_state.recent_bos),
                "choch_count": len(state.confirm_state.recent_choch),
            },
            "risk": {
                "atr": round(state.risk_state.atr, 4),
                "sl_distance_pips": round(state.risk_state.sl_distance_pips, 1),
                "volatility_regime": state.risk_state.volatility_regime.value,
                "current_rr": round(state.risk_state.current_rr, 2),
            },
            "composite": {
                "overall_signal_quality": round(state.overall_signal_quality, 3),
                "confidence_score": round(state.confidence_score, 3),
                "confidence_tier": state.confidence_tier,
                "setup_score": round(state.setup_score, 3),
            },
            "metadata": {
                "scan_count": state.scan_count,
                "last_scan_at": state.last_scan_at.isoformat(),
                "last_signal_at": (
                    state.last_signal_at.isoformat() if state.last_signal_at else None
                ),
            },
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

state_intel_brain = StateIntelBrain()
