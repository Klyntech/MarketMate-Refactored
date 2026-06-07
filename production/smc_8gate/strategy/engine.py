"""
marketmate/strategy/engine.py
──────────────────────────────
SignalEngine — the unified strategy engine for MarketMate.

Combines the responsibilities of three previously separate modules:
  - GateRunner      (strategy/gates.py)    → gate pipeline execution
  - build_signal    (signals/builder.py)   → Signal construction
  - SignalDeduplicator (signals/deduplicator.py) → dedup checking

The SignalEngine.run() method:
  1. Runs all 8 gates sequentially (G1→G8)
  2. If all gates pass, builds a Signal via _create_signal()
  3. Checks dedup internally — returns None if duplicate
  4. Registers the signal with the dedup tracker
  5. Emits events via the optional event_bus callback
  6. Returns the typed Signal object directly

Gate order (fail-fast, cheapest first):
  G1  Session Filter          (pure time check -- zero I/O)
  G2  Daily Limit + Drawdown  (DB read -- single query)
  G3  News Filter             (cached HTTP -- 1 request/hour)
  G4  HTF Bias                (H4 + Daily OHLCV)
  G5  Liquidity Sweep         (uses H4 data already fetched)
  G6  Entry Zone              (uses H4 data already fetched)
  G7  LTF Confirmation        (M15 + M5 OHLCV)
  G8  RR Validation           (pure math)

G4 Neutral-Bias Behaviour:
  If HTF bias is "neutral", the gate immediately rejects. No trade should
  be taken when the higher timeframes don't agree on direction. A liquidity
  sweep alone does NOT establish directional bias — it only confirms that
  liquidity was taken, not where price will go next.
"""

from __future__ import annotations

from datetime import datetime, time, timezone, timedelta
from typing import Any, Callable, Optional

import asyncio

from signal_engine.core.config import cfg
from signal_engine.data.engine import fetch_ohlcv
from signal_engine.execution.risk import RiskManager
from signal_engine.core.logger import get_logger

from signal_engine.strategy.models import (
    DailyState,
    GateResult,
    GateTraceEntry,
    Signal,
    SweepResult,
    EntryZone,
    ConfirmResult,
)
from signal_engine.strategy.bias import get_htf_bias, compute_ema
from signal_engine.strategy.liquidity import detect_sweep
from signal_engine.strategy.zones import find_entry_zone
from signal_engine.strategy.confirmations import check_ltf_confirmation
from signal_engine.strategy.gates import is_high_impact_news
from signal_engine.strategy.scoring import compute_confidence, compute_weighted_score
from signal_engine.strategy.features import (
    BiasFeatures,
    SweepFeatures,
    ZoneCandidate,
    ZoneFeatures,
    ConfirmFeatures,
    ConfirmPattern,
    RRFeatures,
    ScanFeatures,
)
from signal_engine.strategy.liquidity import _strict_swing_highs, _strict_swing_lows
from signal_engine.strategy.dedup import is_duplicate_signal, get_effective_cooldown, get_effective_flip_cooldown


log = get_logger("signal_engine")


# ─── Gate trace helpers ───────────────────────────────────────────────────────

def _gate_pass(name: str, values: dict[str, Any] = None) -> dict:
    return {"gate": name, "status": "pass", "values": values or {}}

def _gate_fail(name: str, reason: str, values: dict[str, Any] = None) -> dict:
    return {"gate": name, "status": "fail", "reason": reason, "values": values or {}}


# ─── Dedup constants ─────────────────────────────────────────────────────────

# Cooldown: don't re-signal same symbol+direction within this many minutes.
COOLDOWN_MINUTES = int(
    getattr(cfg.strategy, "dedup_cooldown_minutes", 0) or 30
)

# Directional flip fast-track cooldown
FLIP_COOLDOWN_MINUTES = int(
    getattr(cfg.strategy, "dedup_flip_cooldown_minutes", 0) or 10
)


# ─── EventBus type ────────────────────────────────────────────────────────────

# The event_bus can be any callable that accepts an event name (str) and
# keyword arguments.  This allows loose coupling — the engine doesn't care
# whether it's an actual EventBus, a simple logger, or None.
EventBusCallback = Optional[Callable[..., None]]


# ─── SignalEngine ─────────────────────────────────────────────────────────────

class SignalEngine:
    """
    Unified strategy engine that runs all gates, builds signals, and
    handles dedup in a single cohesive class.
    """

    def __init__(
        self,
        risk_manager: RiskManager,
        daily_state: DailyState,
        event_bus: EventBusCallback = None,
    ) -> None:
        self.risk = risk_manager
        self.state = daily_state
        self.event_bus = event_bus

        # ── Internal dedup state ───────────────────────────────────────────
        self._cooldown = timedelta(minutes=COOLDOWN_MINUTES)
        self._flip_cooldown = timedelta(minutes=FLIP_COOLDOWN_MINUTES)
        # key: (symbol, direction) -> last Signal
        self._last_signals: dict[tuple, Signal] = {}
        # key: (symbol, direction) -> last H4 candle timestamp
        self._last_h4_ts: dict[tuple, str] = {}
        # key: symbol -> (direction, Signal)  — for flip detection
        self._last_signal_any_dir: dict[str, tuple[str, Signal]] = {}
        # key: symbol -> latest ATR value (for ATR-relative dedup)
        self._last_atr: dict[str, float] = {}

    # ─── Public API ────────────────────────────────────────────────────────

    async def run(self, symbol: str) -> Optional[Signal]:
        """
        Run the full strategy pipeline for `symbol`.

        Returns a Signal if all gates pass and the signal is not a duplicate,
        or None if the pipeline rejects at any point.

        IMPORTANT (v8.0.0): Even on failure, this method now emits a
        gate_features_computed event with partial features so the StateEngine
        can track state evolution across ALL scan cycles, not just passing ones.
        """
        result = await self._run_gates(symbol)

        if not result.passed:
            # Emit partial features for state engine even on failure.
            # The state engine needs to know what the market looks like
            # even when no signal is generated — otherwise it goes blind
            # between signals.
            self._emit_failed_scan_features(symbol, result)
            # Emit the scan_completed event for telemetry
            self._emit("scan_completed", symbol=symbol, passed=False,
                       failed_at=result.failed_at or "")
            return None

        # Build signal from gate result
        signal = self._create_signal(result)

        # ── Dedup check (ATR-relative via dedup.py) ────────────────────────
        last_signal = self._last_signals.get((signal.symbol, signal.direction))
        last_any_dir_entry = self._last_signal_any_dir.get(signal.symbol)
        atr = self._last_atr.get(signal.symbol)

        if last_signal is not None:
            last_any = last_any_dir_entry if last_any_dir_entry else None
            if is_duplicate_signal(signal, last_signal, last_any, atr=atr):
                log.info(
                    "signal_rejected_duplicate",
                    signal_id=signal.id,
                    symbol=signal.symbol,
                    direction=signal.direction,
                    atr_based=atr is not None,
                )
                return None
        else:
            # No same-direction signal — check flip fast-track
            if last_any_dir_entry is not None:
                last_dir, last_sig = last_any_dir_entry
                if last_dir != signal.direction:
                    elapsed = datetime.now(timezone.utc) - last_sig.created_at
                    flip_cd = get_effective_flip_cooldown(signal.symbol)
                    if elapsed < flip_cd:
                        log.info(
                            "signal_rejected_flip_cooldown",
                            symbol=signal.symbol,
                            direction=signal.direction,
                            minutes_ago=round(elapsed.total_seconds() / 60, 1),
                        )
                        return None

        # Same-H4-candle check
        if result.h4_candle_ts and self._is_same_h4_candle(
            signal.symbol, signal.direction, result.h4_candle_ts
        ):
            log.info(
                "signal_rejected_same_h4_candle",
                signal_id=signal.id,
                symbol=signal.symbol,
                h4_candle_ts=result.h4_candle_ts,
            )
            return None

        # Register with dedup tracker
        await self._register(signal, result.h4_candle_ts)

        # Emit event via event_bus
        self._emit("signal_created", signal=signal.to_dict())
        self._emit("scan_completed", symbol=signal.symbol, passed=True)

        return signal

    async def load_dedup_state(self) -> None:
        """
        Restore deduplication state from MongoDB after a restart.

        Loads both timestamps from signal_state AND the most recent signal
        details from signal_archive so that zone-overlap and price-proximity
        checks work correctly after a restart.
        """
        from signal_engine.db.repositories.signal_state import SignalStateRepository

        for symbol in cfg.strategy.pairs:
            for direction in ("BUY", "SELL"):
                ts = await SignalStateRepository().get_last_signal_time(symbol, direction)
                if ts:
                    if datetime.now(timezone.utc) - ts < self._cooldown:
                        s = await self._load_signal_from_archive(symbol, direction, ts)
                        if s is None:
                            s = Signal()
                            s.symbol = symbol
                            s.direction = direction
                            s.created_at = ts
                            s.entry_low = 0.0
                            s.entry_high = 0.0
                        self._last_signals[(symbol, direction)] = s
                        self._last_signal_any_dir[symbol] = (direction, s)
                        log.info(
                            "dedup_state_restored",
                            symbol=symbol,
                            direction=direction,
                            last_signal_at=ts.isoformat(),
                            has_zone_data=s.entry_low > 0 or s.entry_high > 0,
                        )

    # ─── Signal Creation ───────────────────────────────────────────────────

    def _create_signal(self, result: GateResult) -> Signal:
        """
        Convert a passed GateResult into a Signal.
        Only callable when result.passed is True.
        """
        if not result.passed:
            raise ValueError("Cannot build signal from a failed gate result.")

        direction_label = "BUY" if result.direction == "bullish" else "SELL"
        entry_mid = (result.entry_low + result.entry_high) / 2

        signal = Signal(
            symbol           = result.symbol,
            direction        = direction_label,
            entry_low        = result.entry_low,
            entry_high       = result.entry_high,
            entry_mid        = round(entry_mid, 6),
            stop_loss        = result.stop_loss,
            tp1              = result.tp1,
            tp2              = result.tp2,
            tp3              = result.tp3,
            rr               = result.rr,
            position_size    = result.position_size,
            confidence       = result.confidence,
            zone_type        = result.zone.zone_type    if result.zone    else "",
            confirm_type     = result.confirm.signal_type if result.confirm else "",
            confirm_tf       = result.confirm.timeframe   if result.confirm else "",
            swept_level      = result.sweep.swept_level   if result.sweep   else 0.0,
            strategy_version = cfg.strategy.version,
        )

        log.info(
            "signal_built",
            signal_id=signal.id,
            symbol=signal.symbol,
            direction=signal.direction,
            rr=signal.rr,
            confidence=signal.confidence,
        )
        return signal

    # ─── Gate Pipeline (G1-G8) ────────────────────────────────────────────

    async def _run_gates(self, symbol: str) -> GateResult:
        """
        Run all gates for `symbol`. Emits one structured `gate_trace` log
        event after the run, capturing every gate's pass/fail status.
        """
        ts    = datetime.now(timezone.utc).isoformat()
        trace: list[dict] = []

        # ── G1: Session ───────────────────────────────────────────────────
        now_utc = datetime.now(timezone.utc)
        if not self._in_session(now_utc):
            reason = (
                "weekend_no_trading"
                if now_utc.weekday() >= 5
                else "outside_trading_session"
            )
            human = (
                "Weekend -- market closed"
                if now_utc.weekday() >= 5
                else "Outside London/NY session"
            )
            trace.append(_gate_fail("G1_SESSION", reason,
                                    {"utc_time": str(now_utc.time()),
                                     "utc_date": now_utc.strftime("%Y-%m-%d"),
                                     "weekday":  now_utc.strftime("%A"),
                                     "london_session": f"{cfg.strategy.london_open}–{cfg.strategy.london_close}",
                                     "ny_session":     f"{cfg.strategy.ny_open}–{cfg.strategy.ny_close}"}))
            log.info("gate_rejected_session",
                     symbol=symbol, utc_time=str(now_utc.time()),
                     weekday=now_utc.strftime("%A"),
                     reason=reason,
                     trading_window=f"{cfg.strategy.london_open}–{cfg.strategy.ny_close}")
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="G1_SESSION", reason=human,
                              trace=trace)
        trace.append(_gate_pass("G1_SESSION", {"utc_time": str(now_utc)}))

        # ── G2: Daily limit + drawdown + per-direction limit ─────────────
        if self.state.trades_today >= cfg.strategy.max_trades_per_day:
            trace.append(_gate_fail("G2_DAILY_LIMIT",
                                    "daily_trade_limit_reached",
                                    {"trades_today": self.state.trades_today,
                                     "max":          cfg.strategy.max_trades_per_day}))
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="G2_DAILY_LIMIT",
                              reason=f"Daily limit reached ({cfg.strategy.max_trades_per_day})",
                              trace=trace)

        max_per_direction = int(
            getattr(cfg.strategy, "max_trades_per_direction_per_day", 0) or 2
        )
        if self.state.buy_trades_today >= max_per_direction:
            trace.append(_gate_fail("G2_DAILY_LIMIT",
                                    "daily_buy_limit_reached",
                                    {"buy_trades_today": self.state.buy_trades_today,
                                     "max_per_direction": max_per_direction}))
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="G2_DAILY_LIMIT",
                              reason=f"Daily BUY limit reached ({max_per_direction})",
                              trace=trace)
        if self.state.sell_trades_today >= max_per_direction:
            trace.append(_gate_fail("G2_DAILY_LIMIT",
                                    "daily_sell_limit_reached",
                                    {"sell_trades_today": self.state.sell_trades_today,
                                     "max_per_direction": max_per_direction}))
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="G2_DAILY_LIMIT",
                              reason=f"Daily SELL limit reached ({max_per_direction})",
                              trace=trace)

        if self.state.consecutive_losses >= cfg.risk.max_consecutive_losses:
            trace.append(_gate_fail("G2b_DRAWDOWN",
                                    "max_consecutive_losses_hit",
                                    {"consecutive_losses": self.state.consecutive_losses,
                                     "max":                cfg.risk.max_consecutive_losses}))
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="G2b_DRAWDOWN",
                              reason=(f"Drawdown protection: "
                                      f"{self.state.consecutive_losses} consecutive losses"),
                              trace=trace)
        trace.append(_gate_pass("G2_LIMITS",
                                {"trades_today":       self.state.trades_today,
                                 "consecutive_losses": self.state.consecutive_losses}))

        # ── G3: News filter ───────────────────────────────────────────────
        news_blocked = False
        try:
            news_blocked = await is_high_impact_news(symbol)
        except Exception as exc:
            log.warning("news_check_error", symbol=symbol, error=str(exc))

        if news_blocked:
            trace.append(_gate_fail("G3_NEWS", "high_impact_event_window",
                                    {"symbol": symbol}))
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="G3_NEWS",
                              reason="High-impact event within block window",
                              trace=trace)
        trace.append(_gate_pass("G3_NEWS", {"blocked": False}))

        # ── Fetch OHLCV (parallel) ────────────────────────────────────────
        daily_df = h4_df = m15_df = m5_df = None
        try:
            daily_df, h4_df, m15_df, m5_df = await asyncio.gather(
                fetch_ohlcv(symbol, "1d",  limit=cfg.data.htf_candles),
                fetch_ohlcv(symbol, "4h",  limit=cfg.data.htf_candles),
                fetch_ohlcv(symbol, "15m", limit=cfg.data.ltf_candles),
                fetch_ohlcv(symbol, "5m",  limit=cfg.data.ltf_candles),
            )
        except Exception as exc:
            log.error("data_fetch_failed", symbol=symbol, error=str(exc))
            trace.append(_gate_fail("DATA_FETCH", str(exc)))
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="DATA_FETCH",
                              reason=f"Data unavailable: {exc}",
                              trace=trace)

        # Log candle counts for pipeline diagnostics
        log.info("data_fetch_result",
                 symbol=symbol,
                 daily_candles=len(daily_df) if daily_df is not None else 0,
                 h4_candles=len(h4_df) if h4_df is not None else 0,
                 m15_candles=len(m15_df) if m15_df is not None else 0,
                 m5_candles=len(m5_df) if m5_df is not None else 0,
                 htf_required=cfg.data.htf_candles,
                 ltf_required=cfg.data.ltf_candles)

        # Store whichever timeframes were successfully fetched -- fire-and-forget
        _live_frames: dict = {}
        if daily_df is not None and not daily_df.empty: _live_frames["1d"]  = daily_df
        if h4_df    is not None and not h4_df.empty:    _live_frames["4h"]  = h4_df
        if m15_df   is not None and not m15_df.empty:   _live_frames["15m"] = m15_df
        if m5_df    is not None and not m5_df.empty:    _live_frames["5m"]  = m5_df
        if _live_frames:
            log.debug("live_candles_available", symbol=symbol, timeframes=list(_live_frames.keys()))

        if h4_df is None or h4_df.empty:
            log.error("h4_data_missing", symbol=symbol)
            trace.append(_gate_fail("DATA_FETCH", "h4_dataframe_unavailable",
                                    {"symbol": symbol}))
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="DATA_FETCH",
                              reason="H4 data unavailable -- cannot evaluate entry",
                              trace=trace)

        current_price = float(h4_df.iloc[-1]["close"])

        # ── G4: HTF Bias ─────────────────────────────────────────────────
        bias = get_htf_bias(daily_df, h4_df)

        if bias == "neutral":
            trace.append(_gate_fail("G4_HTF_BIAS", "no_clear_htf_bias",
                                    {"current_price":  round(current_price, 4),
                                     "daily_provided": daily_df is not None,
                                     "h4_provided":    h4_df is not None}))
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="G4_HTF_BIAS",
                              reason="No clear HTF bias -- both timeframes neutral or conflicting",
                              trace=trace)

        ema_val = float(compute_ema(h4_df["close"], cfg.strategy.ema_period).iloc[-1])
        trace.append(_gate_pass("G4_HTF_BIAS",
                                {"bias":          bias,
                                 "current_price": round(current_price, 4),
                                 "ema200_h4":     round(ema_val, 4),
                                 "daily_provided": daily_df is not None}))

        # ── G5: Liquidity Sweep ───────────────────────────────────────────
        sweep = detect_sweep(h4_df, bias)
        if sweep is None:
            # Diagnostic: log how many swing levels existed but weren't swept.
            from signal_engine.strategy.liquidity import _strict_swing_highs, _strict_swing_lows
            _lb = cfg.data.swing_lookback
            _fc = cfg.strategy.sweep_freshness_candles
            _se = len(h4_df) - _fc
            _sh = _strict_swing_highs(h4_df.iloc[:_se], _lb) if _se > _lb * 2 else []
            _sl = _strict_swing_lows(h4_df.iloc[:_se], _lb) if _se > _lb * 2 else []
            trace.append(_gate_fail("G5_SWEEP", "no_recent_sweep",
                                    {"bias": bias,
                                     "swing_highs_available": len(_sh),
                                     "swing_lows_available": len(_sl),
                                     "freshness_window": _fc,
                                     "min_sweep_pct": cfg.strategy.min_sweep_pct,
                                     "hint": "No candle swept any swing level in freshness window"}))
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="G5_SWEEP",
                              reason="No recent liquidity sweep",
                              trace=trace)
        trace.append(_gate_pass("G5_SWEEP",
                                {"type":         sweep.type,
                                 "level":        round(sweep.swept_level, 4),
                                 "strength":     sweep.strength,
                                 "close_inside": sweep.close_inside,
                                 "candles_ago":  sweep.candles_ago}))

        return await self._run_gates_from_g6(
            symbol, ts, trace, h4_df, m15_df, m5_df,
            bias, sweep, current_price,
        )

    # ── Shared G6-G8 execution path ──────────────────────────────────────

    async def _run_gates_from_g6(
        self,
        symbol:         str,
        ts:             str,
        trace:          list[dict],
        h4_df,
        m15_df,
        m5_df,
        bias:           str,
        sweep:          SweepResult,
        current_price:  float,
    ) -> GateResult:
        """G6 through G8."""

        # ── G6: Entry Zone ────────────────────────────────────────────────
        zone = find_entry_zone(h4_df, bias)
        if zone is None:
            trace.append(_gate_fail("G6_ZONE", "no_valid_ob_or_fvg",
                                    {"bias": bias,
                                     "ob_search_lookback": cfg.strategy.ob_search_lookback,
                                     "min_fvg_pct": cfg.strategy.min_fvg_pct,
                                     "fvg_freshness": cfg.strategy.fvg_freshness_candles,
                                     "hint": "No OB with displacement or FVG with min gap found"}))
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="G6_ZONE",
                              reason="No valid OB or FVG entry zone",
                              trace=trace)
        trace.append(_gate_pass("G6_ZONE",
                                {"zone_type": zone.zone_type,
                                 "zone_high": round(zone.zone_high, 4),
                                 "zone_low":  round(zone.zone_low, 4),
                                 "zone_mid":  round(zone.zone_mid, 4)}))

        # ── G7: LTF Confirmation ──────────────────────────────────────────
        confirm = check_ltf_confirmation(m15_df, m5_df, bias)
        if confirm is None:
            m15_count = len(m15_df) if m15_df is not None else 0
            m5_count  = len(m5_df) if m5_df is not None else 0
            trace.append(_gate_fail("G7_LTF_CONFIRM", "no_bos_or_choch",
                                    {"bias": bias,
                                     "m15_candles": m15_count,
                                     "m5_candles": m5_count,
                                     "hint": "No BOS or CHoCH pattern on M15 or M5"}))
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="G7_LTF_CONFIRM",
                              reason="No BOS/CHoCH on M5 or M15",
                              trace=trace)
        trace.append(_gate_pass("G7_LTF_CONFIRM",
                                {"signal_type": confirm.signal_type,
                                 "timeframe":   confirm.timeframe,
                                 "break_level": round(confirm.break_level, 4)}))

        # ── G8: RR Validation ─────────────────────────────────────────────
        rr_result = self.risk.calculate_rr(
            direction=bias,
            entry_zone_high=zone.zone_high,
            entry_zone_low=zone.zone_low,
            current_price=current_price,
            h4_df=h4_df,
        )
        if rr_result is None or rr_result["rr"] < cfg.strategy.min_rr:
            rr_val = rr_result["rr"] if rr_result else 0.0
            trace.append(_gate_fail("G8_RR", "insufficient_rr",
                                    {"rr": round(rr_val, 2),
                                     "min_rr": cfg.strategy.min_rr}))
            self._emit_trace(symbol, ts, trace, passed=False)
            return GateResult(passed=False, failed_at="G8_RR",
                              reason=f"RR {rr_val:.2f} < min {cfg.strategy.min_rr}",
                              trace=trace)
        trace.append(_gate_pass("G8_RR",
                                {"rr":    round(rr_result["rr"], 2),
                                 "entry": round(rr_result["entry"], 4),
                                 "sl":    round(rr_result["sl"], 4),
                                 "tp1":   round(rr_result["tp1"], 4),
                                 "tp2":   round(rr_result["tp2"], 4),
                                 "atr":   round(rr_result["atr"], 4)}))

        # Cache ATR for ATR-relative dedup (keyed by symbol)
        if rr_result.get("atr", 0) > 0:
            self._last_atr[symbol] = rr_result["atr"]

        # ── All gates passed ──────────────────────────────────────────────

        # ── Advanced Scoring (v8.0.0) ──────────────────────────────────────
        # Use multi-factor confidence scoring instead of binary 4-point system.
        # Falls back to binary if advanced scoring fails.
        confidence_result = None
        setup_result = None
        try:
            confidence_result = compute_confidence(
                sweep=sweep, zone=zone, confirm=confirm,
                h4_df=h4_df,
            )
            confidence = confidence_result["tier"]
        except Exception as exc:
            log.warning("advanced_scoring_fallback", error=str(exc))
            confidence = _assess_confidence(sweep, zone, confirm)

        try:
            setup_result = compute_weighted_score(
                sweep=sweep, zone=zone, confirm=confirm,
                bias=bias, rr=rr_result["rr"],
                h4_df=h4_df,
            )
        except Exception as exc:
            log.warning("setup_scoring_fallback", error=str(exc))

        position_size = self.risk.position_size(
            stop_loss_distance=abs(rr_result["entry"] - rr_result["sl"])
        )

        # Extract H4 candle timestamp for same-candle dedup filter.
        h4_candle_ts = ""
        try:
            if h4_df is not None and not h4_df.empty:
                last_bar = h4_df.iloc[-1]
                if hasattr(last_bar.name, 'isoformat'):
                    h4_candle_ts = last_bar.name.isoformat()
                else:
                    h4_candle_ts = str(last_bar.name)
        except Exception:
            pass

        # ── Build enriched ScanFeatures ───────────────────────────────────
        scan_features = self._build_scan_features(
            symbol=symbol, ts=ts, trace=trace,
            bias=bias, sweep=sweep, zone=zone, confirm=confirm,
            rr_result=rr_result, h4_df=h4_df,
            confidence=confidence,
            confidence_result=confidence_result,
            setup_result=setup_result,
        )

        self._emit_trace(symbol, ts, trace, passed=True,
                         confidence=confidence, direction=bias)

        # Emit scan_features event for the state engine
        self._emit("gate_features_computed", **scan_features.to_dict())

        return GateResult(
            passed=True,
            symbol=symbol,
            direction=bias,
            bias=bias,
            sweep=sweep,
            zone=zone,
            confirm=confirm,
            entry_low=zone.zone_low,
            entry_high=zone.zone_high,
            stop_loss=rr_result["sl"],
            tp1=rr_result["tp1"],
            tp2=rr_result["tp2"],
            tp3=rr_result["tp3"] or 0.0,
            rr=rr_result["rr"],
            confidence=confidence,
            position_size=position_size,
            h4_candle_ts=h4_candle_ts,
            trace=trace,
        )

    # ─── Dedup Helpers ────────────────────────────────────────────────────

    def _is_same_h4_candle(self, symbol: str, direction: str, h4_candle_ts: str) -> bool:
        """Check if we already generated a signal from the same H4 candle."""
        key = (symbol, direction)
        last_ts = self._last_h4_ts.get(key)
        if last_ts and last_ts == h4_candle_ts:
            log.info(
                "duplicate_suppressed_same_h4_candle",
                symbol=symbol,
                direction=direction,
                h4_candle_ts=h4_candle_ts,
            )
            return True
        return False

    async def _register(self, signal: Signal, h4_candle_ts: str = "") -> None:
        """
        Register a new signal and persist to MongoDB SYNCHRONOUSLY.
        """
        key = (signal.symbol, signal.direction)
        self._last_signals[key] = signal
        self._last_signal_any_dir[signal.symbol] = (signal.direction, signal)

        if h4_candle_ts:
            self._last_h4_ts[key] = h4_candle_ts

        log.debug("signal_registered", signal_id=signal.id, key=str(key),
                  swept_level=round(signal.swept_level, 4) if signal.swept_level else 0)

        # Persist to MongoDB
        try:
            from signal_engine.db.repositories.signal_state import SignalStateRepository
            await SignalStateRepository().set_last_signal_time(signal.symbol, signal.direction, signal.created_at)
        except Exception as exc:
            log.warning(
                "dedup_persist_failed",
                signal_id=signal.id,
                error=str(exc),
                hint="Signal still registered in memory -- next scan may see stale state",
            )

    async def _load_signal_from_archive(
        self, symbol: str, direction: str, ts: datetime
    ) -> Optional[Signal]:
        """Load the most recent signal from MongoDB signal_archive."""
        try:
            from signal_engine.db import get_signals_repo
            all_signals = await get_signals_repo().get_all_signals(limit=100)
            for doc in all_signals:
                if (doc.get("symbol") == symbol and
                    doc.get("direction") == direction):
                    s = Signal()
                    s.symbol = symbol
                    s.direction = direction
                    s.created_at = ts
                    s.entry_low = doc.get("entry_low", 0.0)
                    s.entry_high = doc.get("entry_high", 0.0)
                    s.entry_mid = doc.get("entry_mid", 0.0)
                    s.stop_loss = doc.get("stop_loss", 0.0)
                    s.swept_level = doc.get("swept_level", 0.0)
                    return s
        except Exception as exc:
            log.warning("dedup_archive_load_failed",
                        symbol=symbol, direction=direction,
                        error=str(exc))
        return None

    def _clear_old(self, max_age_hours: int = 24) -> None:
        """Prune entries older than max_age_hours to prevent unbounded growth."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        to_remove = [
            k for k, s in self._last_signals.items()
            if s.created_at < cutoff
        ]
        for k in to_remove:
            del self._last_signals[k]
            self._last_h4_ts.pop(k, None)

        flip_remove = [
            sym for sym, (_, sig) in self._last_signal_any_dir.items()
            if sig.created_at < cutoff
        ]
        for sym in flip_remove:
            del self._last_signal_any_dir[sym]

        if to_remove or flip_remove:
            log.debug("dedup_cache_pruned",
                      direction_removed=len(to_remove),
                      flip_removed=len(flip_remove))

    # ─── Event Emission ───────────────────────────────────────────────────

    def _emit(self, event: str, **kwargs: Any) -> None:
        """Emit an event via the event_bus if available (fire-and-forget)."""
        if self.event_bus is not None:
            try:
                asyncio.create_task(
                    self.event_bus.emit(event, payload=kwargs)
                )
            except Exception as exc:
                log.warning("event_bus_error", event_name=event, error=str(exc))

    def _emit_trace(
        self,
        symbol: str,
        ts: str,
        trace: list[dict],
        passed: bool,
        **extra: Any,
    ) -> None:
        """Build a human-readable summary and emit/log the gate trace."""
        if not passed and trace:
            last = trace[-1]
            failed_gate = last.get("gate", "?")
            reason      = last.get("reason", "?")
            summary = f"REJECTED at {failed_gate}: {reason}"
        else:
            summary = "ALL GATES PASSED"

        log.info(
            "gate_trace",
            pair=symbol,
            timestamp=ts,
            passed=passed,
            gates_executed=len(trace),
            summary=summary,
            trace=trace,
            **extra,
        )

        # Emit trace event
        self._emit("gate_trace", symbol=symbol, passed=passed,
                   summary=summary, trace=trace, **extra)

    # ─── ScanFeatures Builder ─────────────────────────────────────────────

    def _emit_failed_scan_features(
        self, symbol: str, result: GateResult
    ) -> None:
        """
        Emit partial ScanFeatures for a failed scan cycle.

        Even when gates fail, the StateEngine needs to know the current
        market state (bias, available liquidity, etc.) so it can track
        state evolution continuously. Without this, the state engine
        goes blind between signals.

        Extracts whatever features ARE available from the gate trace
        and emits them as a gate_features_computed event.
        """
        ts = datetime.now(timezone.utc).isoformat()

        # Build partial BiasFeatures from what we know
        bias_features = None
        bias = ""
        # Check if G4 passed (meaning we have bias info)
        for entry in (result.trace or []):
            if entry.get("gate") == "G4_HTF_BIAS":
                if entry.get("status") == "pass":
                    bias = entry.get("values", {}).get("bias", "")
                break

        # Only build features if we at least got past G3 (news filter)
        # and have OHLCV data — otherwise there's nothing useful to extract
        if result.failed_at and result.failed_at in ("G1_SESSION", "G2_DAILY_LIMIT",
                "G2b_DRAWDOWN", "G3_NEWS"):
            # Pre-data gates — no market features to extract
            self._emit("gate_features_computed",
                       symbol=symbol, timestamp=ts, passed=False,
                       failed_at=result.failed_at or "",
                       bias_features=None, sweep_features=None,
                       zone_features=None, confirm_features=None,
                       rr_features=None)
            return

        # We have OHLCV data — extract what we can
        h4_ema = 0.0
        current_price = 0.0
        try:
            # Attempt to re-compute from cached data (best effort)
            h4_ema = 0.0  # Not re-fetching here — would be I/O waste
            current_price = 0.0
        except Exception:
            pass

        bias_features = BiasFeatures(
            daily_bias="neutral",
            h4_bias=bias,
            resolved_bias=bias if bias else "neutral",
            current_price=current_price,
        ) if bias else None

        scan_features = ScanFeatures(
            symbol=symbol,
            timestamp=ts,
            bias_features=bias_features,
            passed=False,
            failed_at=result.failed_at or "",
            session_active=True,
            trades_today=self.state.trades_today,
        )

        self._emit("gate_features_computed", **scan_features.to_dict())

    def _build_scan_features(
        self,
        symbol: str,
        ts: str,
        trace: list[dict],
        bias: str,
        sweep: SweepResult,
        zone: EntryZone,
        confirm: ConfirmResult,
        rr_result: dict,
        h4_df,
        confidence: str,
        confidence_result: Optional[dict] = None,
        setup_result: Optional[dict] = None,
    ) -> ScanFeatures:
        """
        Build enriched ScanFeatures from gate pipeline outputs.

        This is the key transformation: from lossy gate outputs to
        rich feature vectors that capture ALL intermediate computations.
        """
        # ── BiasFeatures (G4) ─────────────────────────────────────────────
        daily_ema = 0.0
        h4_ema = float(compute_ema(h4_df["close"], cfg.strategy.ema_period).iloc[-1]) if h4_df is not None and len(h4_df) > 0 else 0.0
        current_price = float(h4_df.iloc[-1]["close"]) if h4_df is not None and len(h4_df) > 0 else 0.0

        # Extract per-TF bias from trace
        daily_bias = "neutral"
        h4_bias = "neutral"
        resolution_path = ""
        for entry in trace:
            if entry.get("gate") == "G4_HTF_BIAS" and entry.get("status") == "pass":
                vals = entry.get("values", {})
                h4_bias = bias  # The resolved bias IS the h4 contribution
                resolution_path = "full_agreement"  # Best guess from trace

        bias_features = BiasFeatures(
            daily_ema200=daily_ema,
            h4_ema200=h4_ema,
            daily_bias=daily_bias,
            h4_bias=h4_bias,
            resolved_bias=bias,
            current_price=current_price,
            resolution_path=resolution_path,
            h4_above_ema=current_price > h4_ema if h4_ema > 0 else False,
        )

        # ── SweepFeatures (G5) ────────────────────────────────────────────
        all_swing_highs = []
        all_swing_lows = []
        try:
            _lb = cfg.data.swing_lookback
            _fc = cfg.strategy.sweep_freshness_candles
            _se = len(h4_df) - _fc if h4_df is not None else 0
            if _se > _lb * 2 and h4_df is not None:
                all_swing_highs = _strict_swing_highs(h4_df.iloc[:_se], _lb)
                all_swing_lows = _strict_swing_lows(h4_df.iloc[:_se], _lb)
        except Exception:
            pass

        sweep_features = SweepFeatures(
            all_swing_highs=all_swing_highs,
            all_swing_lows=all_swing_lows,
            available_swing_highs=len(all_swing_highs),
            available_swing_lows=len(all_swing_lows),
            best_sweep_type=sweep.type if sweep else "",
            best_sweep_level=sweep.swept_level if sweep else 0.0,
            best_sweep_strength=sweep.strength if sweep else "",
            best_sweep_close_inside=sweep.close_inside if sweep else False,
            best_sweep_candles_ago=sweep.candles_ago if sweep else 0,
            best_sweep_distance=sweep.sweep_distance if sweep else 0.0,
            sweep_found=sweep is not None,
            freshness_window=cfg.strategy.sweep_freshness_candles,
            min_sweep_pct=cfg.strategy.min_sweep_pct,
        )

        # ── ZoneFeatures (G6) ────────────────────────────────────────────
        winner = ZoneCandidate(
            zone_type=zone.zone_type if zone else "",
            direction=zone.direction if zone else "",
            zone_high=zone.zone_high if zone else 0.0,
            zone_low=zone.zone_low if zone else 0.0,
            zone_mid=zone.zone_mid if zone else 0.0,
            candle_idx=zone.candle_idx if zone else 0,
            is_winner=True,
        ) if zone else None

        zone_features = ZoneFeatures(
            all_candidates=[winner] if winner else [],
            winner_zone_type=zone.zone_type if zone else "",
            winner_zone_high=zone.zone_high if zone else 0.0,
            winner_zone_low=zone.zone_low if zone else 0.0,
            ob_candidates_count=1 if zone and zone.zone_type == "order_block" else 0,
            fvg_candidates_count=1 if zone and zone.zone_type == "fvg" else 0,
            zone_found=zone is not None,
            ob_search_lookback=cfg.strategy.ob_search_lookback,
            min_fvg_pct=cfg.strategy.min_fvg_pct,
            fvg_freshness_candles=cfg.strategy.fvg_freshness_candles,
        )

        # ── ConfirmFeatures (G7) ─────────────────────────────────────────
        winner_pattern = ConfirmPattern(
            signal_type=confirm.signal_type if confirm else "",
            direction=confirm.direction if confirm else "",
            break_level=confirm.break_level if confirm else 0.0,
            timeframe=confirm.timeframe if confirm else "",
            is_winner=True,
        ) if confirm else None

        confirm_features = ConfirmFeatures(
            m15_result=winner_pattern if winner_pattern and winner_pattern.timeframe == "M15" else None,
            m5_result=winner_pattern if winner_pattern and winner_pattern.timeframe == "M5" else None,
            all_patterns=[winner_pattern] if winner_pattern else [],
            winner_signal_type=confirm.signal_type if confirm else "",
            winner_timeframe=confirm.timeframe if confirm else "",
            confirmation_found=confirm is not None,
        )

        # ── RRFeatures (G8) ──────────────────────────────────────────────
        atr_val = rr_result.get("atr", 0.0)
        sl_dist = abs(rr_result.get("entry", 0) - rr_result.get("sl", 0))
        rr_features = RRFeatures(
            rr=rr_result.get("rr", 0.0),
            entry=rr_result.get("entry", 0.0),
            sl=rr_result.get("sl", 0.0),
            tp1=rr_result.get("tp1", 0.0),
            tp2=rr_result.get("tp2", 0.0),
            tp3=rr_result.get("tp3", 0.0),
            atr_value=atr_val,
            sl_distance_pips=sl_dist,
            sl_distance_atr_ratio=sl_dist / atr_val if atr_val > 0 else 0.0,
            rr_passed=rr_result.get("rr", 0) >= cfg.strategy.min_rr,
            min_rr=cfg.strategy.min_rr,
        )

        # ── Composite ScanFeatures ────────────────────────────────────────
        return ScanFeatures(
            symbol=symbol,
            timestamp=ts,
            bias_features=bias_features,
            sweep_features=sweep_features,
            zone_features=zone_features,
            confirm_features=confirm_features,
            rr_features=rr_features,
            passed=True,
            confidence_score=confidence_result.get("score", 0.0) if confidence_result else 0.0,
            confidence_tier=confidence,
            confidence_breakdown=confidence_result.get("breakdown", {}) if confidence_result else {},
            setup_score=setup_result.get("total", 0.0) if setup_result else 0.0,
            setup_breakdown=setup_result.get("breakdown", {}) if setup_result else {},
            session_active=True,
            trades_today=self.state.trades_today,
        )

    # ─── Session Helper ───────────────────────────────────────────────────

    def _in_session(self, now_utc: datetime) -> bool:
        # Weekends: Saturday=5, Sunday=6 -- XAUUSD market is closed
        if now_utc.weekday() >= 5:
            return False

        now_time = now_utc.time()

        def _t(s: str) -> time:
            h, m = s.split(":")
            return time(int(h), int(m))

        in_london = _t(cfg.strategy.london_open)  <= now_time <= _t(cfg.strategy.london_close)
        in_ny     = _t(cfg.strategy.ny_open)       <= now_time <= _t(cfg.strategy.ny_close)
        return in_london or in_ny


# ─── Confidence Assessment (v1 binary) ───────────────────────────────────────

def _assess_confidence(
    sweep:   SweepResult,
    zone:    EntryZone,
    confirm: ConfirmResult,
) -> str:
    """
    Original 4-point binary confidence assessment.
    Score >= 3 → HIGH, else MEDIUM.
    """
    score = 0
    if sweep.close_inside:                score += 1   # clean stop hunt
    if zone.zone_type == "order_block":   score += 1   # OB > FVG
    if confirm.signal_type == "CHoCH":    score += 1   # CHoCH > BOS
    if confirm.timeframe == "M15":        score += 1   # M15 > M5
    return "HIGH" if score >= 3 else "MEDIUM"
