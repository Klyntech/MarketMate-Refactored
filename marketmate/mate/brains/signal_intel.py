"""
marketmate.mate.brains.signal_intel
───────────────────────────────────
Signal Intelligence Brain — answers everything about signals, counts, and quality.

Capability Domain:
  - Signal counts: "How many signals last week?"
  - Win rate stats: "What's the win rate?"
  - Active signals: "What signals are open?"
  - Signal explanations: "Why was this signal generated?"
  - Per-symbol signal analytics: "How has gold performed?"

Functions:
  get_signal_stats(days)              → total, wins, losses, win_rate, avg_rr
  get_signal_count(days)              → count + breakdown
  get_active_signals()                → currently open signals
  explain_signal(symbol)              → gate trace, sweep, BOS/CHoCH, RR
  get_per_symbol_stats()              → breakdown by symbol

This brain NEVER estimates signal counts.
It queries MongoDB directly for accurate numbers.
The LLM only narrates what this brain compiles.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.mate.state_store import redis_state_store

log = get_logger("mate.brains.signal_intel")


class SignalIntelBrain:
    """
    Financial cognition primitive for signal intelligence.

    Answers: signal counts, win rates, active signals, signal explanations.
    Does NOT answer: prices, account balance, strategy theory.
    """

    # ═════════════════════════════════════════════════════════════════════════
    # Core Brain Functions
    # ═════════════════════════════════════════════════════════════════════════

    async def get_signal_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get performance statistics for signals over N days.

        Tries Redis first, falls back to MongoDB.
        """
        # 1. Try Redis cached metrics
        metrics = {}
        for metric in ["winrate", "avg_rr", "total_trades", "profit_factor"]:
            value = await redis_state_store.get_perf(metric, f"{days}d")
            if value:
                metrics[metric] = value.get("value") if isinstance(value, dict) else value

        if metrics and metrics.get("total_trades"):
            return {"window_days": days, "metrics": metrics, "source": "redis"}

        # 2. MongoDB fallback
        try:
            from marketmate.db.repositories.signals import SignalRepository
            repo = SignalRepository()
            stats = await repo.get_performance_stats(days=days)
            return {
                "window_days": days,
                "metrics": {
                    "total_trades": stats.get("total", 0),
                    "wins": stats.get("wins", 0),
                    "losses": stats.get("losses", 0),
                    "win_rate": round(stats.get("wins", 0) / max(stats.get("total", 1), 1), 4),
                    "avg_rr": stats.get("avg_rr", 0),
                    "pnl_pct": stats.get("pnl_pct", 0),
                },
                "source": "mongodb_fallback",
            }
        except Exception as exc:
            log.warning("signal_stats_failed", error=str(exc))
            return {"window_days": days, "status": "no_data"}

    async def get_signal_count(self, days: int = 7) -> Dict[str, Any]:
        """
        Count signals generated in a time window.

        Always queries MongoDB for accuracy — Redis doesn't store raw counts.
        """
        try:
            from marketmate.db.repositories.signals import SignalRepository
            repo = SignalRepository()
            stats = await repo.get_performance_stats(days=days)

            # Open signal count
            open_sigs = await repo.get_open_signals()

            # Total signals generated in period (including open)
            total_generated = 0
            try:
                db = await repo._manager.get_db()
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                if db is not None:
                    total_generated = await db["signal_archive"].count_documents({
                        "generated_at": {"$gte": cutoff},
                    })
            except Exception:
                pass

            return {
                "days": days,
                "total_signals_generated": total_generated,
                "closed_trades": stats.get("total", 0),
                "wins": stats.get("wins", 0),
                "losses": stats.get("losses", 0),
                "breakeven": stats.get("breakeven", 0),
                "open_now": len(open_sigs),
                "win_rate": round(stats.get("wins", 0) / max(stats.get("total", 1), 1), 4),
                "avg_rr": stats.get("avg_rr", 0),
                "source": "mongodb",
            }
        except Exception as exc:
            log.warning("signal_count_failed", error=str(exc))
            return {"days": days, "status": "no_data", "error": str(exc)}

    async def get_active_signals(self) -> Dict[str, Any]:
        """
        Get all currently active/open signals.

        Tries Redis first, falls back to MongoDB.
        """
        # 1. Redis fast path
        signals = {}
        for symbol in cfg.strategy.pairs:
            signal = await redis_state_store.get_active_signal(symbol)
            if signal:
                signals[symbol] = signal

        if signals:
            return {"active_signals": signals, "count": len(signals), "source": "redis"}

        # 2. MongoDB fallback
        try:
            from marketmate.db.repositories.signals import SignalRepository
            repo = SignalRepository()
            open_sigs = await repo.get_open_signals()
            for s in open_sigs:
                sym = s.get("symbol", "")
                if sym:
                    signals[sym] = {
                        "signal_id": s.get("signal_id", ""),
                        "direction": s.get("direction", ""),
                        "entry": s.get("entry_mid", 0),
                        "stop_loss": s.get("stop_loss", 0),
                        "tp1": s.get("tp1", 0),
                        "confidence": s.get("confidence", ""),
                    }
            return {
                "active_signals": signals,
                "count": len(signals),
                "source": "mongodb_fallback",
            }
        except Exception as exc:
            log.warning("active_signals_failed", error=str(exc))
            return {"active_signals": {}, "count": 0}

    async def explain_signal(self, symbol: str = "") -> Dict[str, Any]:
        """
        Explain a signal using its gate trace, sweep, BOS/CHoCH, HTF bias.

        Fetches the most recent signal and compiles the full pipeline trace
        into structured context for MATE to narrate.
        """
        try:
            from marketmate.db.repositories.signals import SignalRepository
            repo = SignalRepository()

            signal = None
            if symbol:
                # Try open signals first
                open_sigs = await repo.get_open_signals()
                signal = next(
                    (s for s in open_sigs if s.get("symbol", "").upper() == symbol.upper()),
                    None,
                )
                if not signal:
                    # Try closed signals
                    trades = await repo.get_virtual_trade_history(limit=10)
                    signal = next(
                        (t for t in trades if t.get("symbol", "").upper() == symbol.upper()),
                        None,
                    )
            else:
                open_sigs = await repo.get_open_signals()
                signal = open_sigs[-1] if open_sigs else None
                if not signal:
                    trades = await repo.get_virtual_trade_history(limit=5)
                    signal = trades[0] if trades else None

            if not signal:
                return {"status": "no_signal", "hint": "No recent signal found to explain"}

            # Compile the gate trace and pipeline context
            explanation = {
                "signal_id": signal.get("id") or signal.get("signal_id", "unknown"),
                "symbol": signal.get("symbol", ""),
                "direction": signal.get("direction", ""),
                "entry_zone": (
                    f"{signal.get('entry_low', 0):.2f} - {signal.get('entry_high', 0):.2f}"
                    if signal.get("entry_low") else str(signal.get("entry_mid", ""))
                ),
                "stop_loss": signal.get("stop_loss", 0),
                "tp1": signal.get("tp1", 0),
                "tp2": signal.get("tp2", 0),
                "rr": signal.get("rr", 0),
                "confidence": signal.get("confidence", ""),
                "zone_type": signal.get("zone_type", ""),
                "confirm_type": signal.get("confirm_type", ""),
                "confirm_tf": signal.get("confirm_tf", ""),
                "swept_level": signal.get("swept_level", 0),
                "status": signal.get("status", ""),
                "confidence_score": signal.get("confidence_score"),
                "setup_score_total": signal.get("setup_score_total"),
                "gate_trace": signal.get("gate_trace", []),
            }

            # Enrich with Redis live state
            sym = signal.get("symbol", "")
            if sym:
                live_state = await redis_state_store.get_symbol_state(sym)
                if live_state:
                    explanation["current_bias"] = live_state.get("bias", "")
                    explanation["last_outcome"] = live_state.get("last_outcome", "")

            # Phase 3: Enrich with compiled InstrumentState from StateEngine
            compiled_state = await self._get_compiled_state(sym)
            if compiled_state:
                explanation["compiled_bias"] = compiled_state.get("bias", {}).get("daily_bias", "")
                explanation["compiled_conviction"] = compiled_state.get("bias", {}).get("conviction_score", 0)
                explanation["compiled_regime"] = compiled_state.get("bias", {}).get("regime", "")
                explanation["compiled_alignment"] = compiled_state.get("confirmation", {}).get("alignment_score", 0)
                explanation["compiled_volatility"] = compiled_state.get("risk", {}).get("volatility_regime", "")

            return explanation

        except Exception as exc:
            return {"error": str(exc)}

    async def _get_compiled_state(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get compiled InstrumentState from StateEngine for signal enrichment."""
        try:
            from marketmate.state.engine import get_state_engine
            state_engine = get_state_engine()
            state = await state_engine.get_instrument_state(symbol)
            if state is None:
                return None
            return {
                "bias": {
                    "daily_bias": state.bias_state.daily_bias.value,
                    "conviction_score": round(state.bias_state.conviction_score, 3),
                    "regime": state.bias_state.regime.value,
                },
                "confirmation": {
                    "alignment_score": round(state.confirm_state.alignment_score, 3),
                },
                "risk": {
                    "volatility_regime": state.risk_state.volatility_regime.value,
                },
            }
        except Exception:
            return None

    async def get_per_symbol_stats(self, limit: int = 20) -> Dict[str, Any]:
        """
        Get signal statistics broken down by symbol.

        Useful for identifying which symbols are performing well or poorly.
        """
        try:
            from marketmate.db.repositories.signals import SignalRepository
            repo = SignalRepository()
            recent = await repo.get_virtual_trade_history(limit=limit)

            symbol_stats: dict[str, dict] = {}
            for t in recent:
                symbol = t.get("symbol", "unknown")
                if symbol not in symbol_stats:
                    symbol_stats[symbol] = {"wins": 0, "losses": 0, "total_rr": 0.0, "count": 0}
                symbol_stats[symbol]["count"] += 1
                outcome = (t.get("outcome") or "").upper()
                if outcome == "WIN":
                    symbol_stats[symbol]["wins"] += 1
                elif outcome == "LOSS":
                    symbol_stats[symbol]["losses"] += 1
                symbol_stats[symbol]["total_rr"] += t.get("pnl_r", 0) or 0

            # Compute win rates
            for sym, stats in symbol_stats.items():
                total = max(stats["count"], 1)
                stats["win_rate"] = round(stats["wins"] / total, 4)
                stats["avg_rr"] = round(stats["total_rr"] / total, 2)

            return {"symbol_breakdown": symbol_stats, "total_recent": len(recent)}
        except Exception as exc:
            return {"error": str(exc)}


# ─── Singleton ────────────────────────────────────────────────────────────────

signal_intel_brain = SignalIntelBrain()
