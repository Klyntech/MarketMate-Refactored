"""
marketmate/execution/lifecycle.py
──────────────────────────────────
Virtual Trade Lifecycle Manager

Migrated from lifecycle/trade_manager.py. Renamed from TradeManager to
TradeLifecycleManager to better describe its role.

Key changes from the original:
  - All imports use marketmate. prefix
  - Uses SignalRepository from marketmate.db.repositories.signals instead
    of the direct db.database module
  - Uses ProximityRepo from marketmate.analytics.proximity instead of
    db.proximity
  - Uses EventBus for trade events (trade_opened, tp_hit, loss_hit,
    trade_closed) instead of direct calls
  - Accepts optional event_bus via constructor for event emission

Monitors all OPEN virtual trades using real market prices.
Called by the 10-minute evaluation loop in the Scheduler.

Evaluation uses candle HIGH and LOW (not just close) so that a candle
that crosses both SL and TP in the same bar is handled conservatively:
  - SL is checked first → LOSS takes priority (risk management)
  - If SL not hit, check TPs against HIGH (BUY) or LOW (SELL)

Lifecycle states:
  PENDING  → OPEN     (set by SimExecutor at signal generation)
  OPEN     → RUNNING  (TP1 hit: 50% close, break-even set)
  RUNNING  → CLOSED   (TP2/TP3 or SL)
  OPEN     → CLOSED   (SL before TP1)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

import aiohttp

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.core.events import EventBus, event_bus as _default_bus, EventType
from marketmate.db.repositories.signals import SignalRepository
from marketmate.analytics.proximity import ProximityRepo
from marketmate.strategy.models import Signal

from marketmate.data.engine import fetch_ohlcv

if TYPE_CHECKING:
    from marketmate.delivery.telegram.bot import TelegramDelivery

log = get_logger("lifecycle")

# Partial close percentages (informational — for Telegram messages)
TP1_CLOSE_PCT = 50
TP2_CLOSE_PCT = 75


class TradeLifecycleManager:
    """
    Manages the full lifecycle of virtual trades: from open through
    TP1/TP2/TP3 hits to final close.

    Uses SignalRepository for all signal persistence and ProximityRepo
    for MFE/MAE tracking. Emits domain events via EventBus.
    """

    def __init__(
        self,
        telegram: "TelegramDelivery",
        training_logger=None,
        event_bus: Optional[EventBus] = None,
        signal_repo: Optional[SignalRepository] = None,
        proximity_repo: Optional[ProximityRepo] = None,
    ) -> None:
        self.telegram        = telegram
        self.training_logger = training_logger
        self.event_bus       = event_bus or _default_bus
        self.signal_repo     = signal_repo or SignalRepository()
        self.proximity_repo  = proximity_repo or ProximityRepo()
        self._be_set: set[str] = set()
        # signal_id → mongo doc_id for outcome updates
        self._mongo_doc_ids: dict[str, str] = {}

    def register_mongo_doc(self, signal_id: str, doc_id: str) -> None:
        """Link a signal to its MongoDB training document ID."""
        self._mongo_doc_ids[signal_id] = doc_id

    # ── Entry point ───────────────────────────────────────────────────────────

    async def evaluate_open_trades(self) -> None:
        """
        Called by the 10-minute evaluation loop in the Scheduler.

        Fetches the latest candle for each open virtual trade and evaluates
        SL/TP conditions using candle HIGH and LOW for better accuracy.
        Skips any symbol where price fetch fails (bot continues uninterrupted).
        """
        open_signals = await self.signal_repo.get_open()
        if not open_signals:
            log.debug("no_open_virtual_trades")
            return

        log.info("evaluating_open_trades", count=len(open_signals))

        async with aiohttp.ClientSession() as session:
            await asyncio.gather(
                *[self._evaluate_one(sig, session) for sig in open_signals],
                return_exceptions=True,
            )

    # ── Per-trade evaluation ──────────────────────────────────────────────────

    async def _evaluate_one(
        self,
        sig_dict: dict,
        session: aiohttp.ClientSession,
    ) -> None:
        """
        Evaluate a single virtual trade against the latest candle.

        Uses HIGH/LOW for SL and TP checks. SL is always evaluated first
        to prevent awarding a TP win on a candle that also blew the SL.
        """
        signal_id = sig_dict["id"] if "id" in sig_dict else sig_dict.get("signal_id", "")
        symbol    = sig_dict["symbol"]
        direction = sig_dict["direction"]
        status    = sig_dict["status"]
        entry     = sig_dict.get("mt5_entry_price") or sig_dict.get("entry_mid", 0)
        sl        = sig_dict["stop_loss"]
        tp1       = sig_dict["tp1"]
        tp2       = sig_dict["tp2"]
        tp3       = sig_dict.get("tp3")

        try:
            df = await fetch_ohlcv(
                symbol,
                cfg.sim.eval_timeframe,
                limit=cfg.sim.eval_candles,
                session=session,
            )
        except Exception as exc:
            log.warning("price_fetch_failed_eval",
                        signal_id=signal_id, symbol=symbol, error=str(exc))
            return

        candle       = df.iloc[-1]
        candle_high  = float(candle["high"])
        candle_low   = float(candle["low"])
        current_price = float(candle["close"])

        log.debug(
            "trade_eval",
            signal_id=signal_id, symbol=symbol,
            direction=direction, status=status,
            high=round(candle_high, 4), low=round(candle_low, 4),
            sl=round(sl, 4), tp1=round(tp1, 4),
        )

        # ── Time-based expiry ─────────────────────────────────────────────────
        expiry_hours = getattr(cfg.strategy, "trade_expiry_hours", 24)
        created_at_str = sig_dict.get("created_at") or sig_dict.get("generated_at")
        if created_at_str:
            try:
                created_dt = datetime.fromisoformat(created_at_str)
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
                if age_hours >= expiry_hours:
                    log.info("trade_expired",
                             signal_id=signal_id,
                             age_hours=round(age_hours, 1),
                             expiry_hours=expiry_hours)
                    await self._close_trade(
                        sig_dict,
                        exit_price=current_price,
                        reason="EXPIRED",
                        entry=entry,
                        loss=False,
                    )
                    return
            except Exception:
                pass

        # ── Optional Friday end-of-week close ─────────────────────────────────
        if getattr(cfg.strategy, "close_on_friday", False):
            now = datetime.now(timezone.utc)
            if now.weekday() == 4 and now.hour >= 21:
                log.info("trade_closed_eow", signal_id=signal_id)
                await self._close_trade(
                    sig_dict,
                    exit_price=current_price,
                    reason="EXPIRED",
                    entry=entry,
                    loss=False,
                )
                return

        if direction == "BUY":
            # ── SL first (conservative — adverse move takes priority) ─────────
            if candle_low <= sl:
                await self._close_trade(sig_dict, sl, "SL_HIT",
                                        entry=entry, loss=True)
                return

            # ── TP1 ──────────────────────────────────────────────────────────
            if status in ("OPEN", "PENDING") and candle_high >= tp1:
                await self._on_tp1(sig_dict, tp1, entry)
                status = "RUNNING"

            # ── TP2 ──────────────────────────────────────────────────────────
            if status == "RUNNING" and candle_high >= tp2:
                if not tp3:
                    await self._close_trade(sig_dict, tp2, "TP2_HIT",
                                            entry=entry, loss=False)
                    return
                await self._on_tp2(sig_dict, tp2)
                status = "RUNNING_TP2"

            # ── TP3 ──────────────────────────────────────────────────────────
            if status in ("RUNNING", "RUNNING_TP2") and tp3 and candle_high >= tp3:
                await self._close_trade(sig_dict, tp3, "TP3_HIT",
                                        entry=entry, loss=False)

        elif direction == "SELL":
            # ── SL first ─────────────────────────────────────────────────────
            if candle_high >= sl:
                await self._close_trade(sig_dict, sl, "SL_HIT",
                                        entry=entry, loss=True)
                return

            # ── TP1 ──────────────────────────────────────────────────────────
            if status in ("OPEN", "PENDING") and candle_low <= tp1:
                await self._on_tp1(sig_dict, tp1, entry)
                status = "RUNNING"

            # ── TP2 ──────────────────────────────────────────────────────────
            if status == "RUNNING" and candle_low <= tp2:
                if not tp3:
                    await self._close_trade(sig_dict, tp2, "TP2_HIT",
                                            entry=entry, loss=False)
                    return
                await self._on_tp2(sig_dict, tp2)
                status = "RUNNING_TP2"

            # ── TP3 ──────────────────────────────────────────────────────────
            if status in ("RUNNING", "RUNNING_TP2") and tp3 and candle_low <= tp3:
                await self._close_trade(sig_dict, tp3, "TP3_HIT",
                                        entry=entry, loss=False)

    # ── check_price() — called by price_monitor on TP/SL crossings ───────────

    async def check_price(
        self,
        signal_id: str,
        price: float,
        level: str,
    ) -> None:
        """
        Called by the PriceMonitor on every TP/SL crossing (~1/sec).
        `level` is one of: "TP1", "TP2", "TP3", "SL"

        Looks up the full signal dict from the repository so _close_trade
        has all the data it needs. The monitor has already removed the trade
        from its in-memory dict before this coroutine runs.
        """
        try:
            open_signals = await self.signal_repo.get_open()
            sig_dict = next(
                (s for s in open_signals if (
                    s.get("id") == signal_id or s.get("signal_id") == signal_id
                )),
                None,
            )
            if sig_dict is None:
                log.warning("check_price_signal_not_found",
                            signal_id=signal_id, level=level)
                return

            entry = sig_dict.get("mt5_entry_price") or sig_dict.get("entry_mid", 0)
            loss  = level == "SL"

            reason_map = {
                "TP1": "TP1_HIT",
                "TP2": "TP2_HIT",
                "TP3": "TP3_HIT",
                "SL":  "SL_HIT",
            }
            reason = reason_map.get(level, "TP2_HIT")

            log.info("price_monitor_closing_trade",
                     signal_id=signal_id, level=level,
                     price=price, reason=reason)

            await self._close_trade(
                sig_dict,
                exit_price=price,
                reason=reason,
                entry=entry,
                loss=loss,
            )
        except Exception as exc:
            log.error("check_price_failed",
                      signal_id=signal_id, level=level,
                      price=price, error=str(exc))

    # ── open_trade() — register new trade with the price monitor ─────────────

    async def open_trade(self, signal: Signal, doc_id: Optional[str] = None) -> None:
        """
        Called by SimExecutor (or main.py) immediately after a sim trade opens.
        Registers the trade with the real-time price monitor and the proximity DB.

        Emits a TRADE_OPENED event via the EventBus.
        """
        if doc_id:
            self.register_mongo_doc(signal.id, doc_id)

        # Register with the price monitor (if available)
        try:
            from marketmate.execution.monitor import register_trade
            register_trade(
                signal_id = signal.id,
                symbol    = signal.symbol,
                direction = signal.direction,
                entry     = getattr(signal, "entry_price", signal.entry_mid),
                sl        = signal.stop_loss,
                tp1       = signal.tp1,
                tp2       = signal.tp2,
                tp3       = getattr(signal, "tp3", 0.0) or 0.0,
            )
        except ImportError:
            log.debug("price_monitor_not_available_for_registration")

        # Emit event
        await self.event_bus.emit(
            EventType.TRADE_OPENED,
            {
                "signal_id": signal.id,
                "symbol":    signal.symbol,
                "direction": signal.direction,
                "entry":     signal.entry_mid,
                "sl":        signal.stop_loss,
                "tp1":       signal.tp1,
                "tp2":       signal.tp2,
            },
        )

    # ── TP1 handler ───────────────────────────────────────────────────────────

    async def _on_tp1(self, sig_dict: dict, tp1_price: float, entry: float) -> None:
        signal_id = self._get_signal_id(sig_dict)
        await self.signal_repo.update_status(signal_id, "RUNNING")
        await self.signal_repo.log_trade_event(signal_id, "TP1_HIT", tp1_price)

        signal = _s(sig_dict)
        await self.telegram.send_tp_hit(signal, "TP1", tp1_price)
        await self.telegram.send_partial_close(signal, "TP1", TP1_CLOSE_PCT)
        if signal_id not in self._be_set:
            await self.telegram.send_breakeven(signal, entry)
            self._be_set.add(signal_id)

        doc_id = self._mongo_doc_ids.get(signal_id)
        if self.training_logger and doc_id:
            await self.training_logger.log_status_update(doc_id, "TP1_HIT")

        # Emit event
        await self.event_bus.emit(
            EventType.TP_HIT,
            {
                "signal_id":  signal_id,
                "level":      "TP1",
                "price":      tp1_price,
                "symbol":     sig_dict.get("symbol", ""),
                "direction":  sig_dict.get("direction", ""),
            },
        )

        log.info("tp1_hit", signal_id=signal_id, price=round(tp1_price, 4))

    # ── TP2 handler ───────────────────────────────────────────────────────────

    async def _on_tp2(self, sig_dict: dict, tp2_price: float) -> None:
        signal_id = self._get_signal_id(sig_dict)
        await self.signal_repo.log_trade_event(signal_id, "TP2_HIT", tp2_price)

        signal = _s(sig_dict)
        await self.telegram.send_tp_hit(signal, "TP2", tp2_price)
        await self.telegram.send_partial_close(signal, "TP2", TP2_CLOSE_PCT)

        doc_id = self._mongo_doc_ids.get(signal_id)
        if self.training_logger and doc_id:
            await self.training_logger.log_status_update(doc_id, "TP2_HIT")

        # Emit event
        await self.event_bus.emit(
            EventType.TP_HIT,
            {
                "signal_id":  signal_id,
                "level":      "TP2",
                "price":      tp2_price,
                "symbol":     sig_dict.get("symbol", ""),
                "direction":  sig_dict.get("direction", ""),
            },
        )

        log.info("tp2_hit", signal_id=signal_id, price=round(tp2_price, 4))

    # ── Final close ───────────────────────────────────────────────────────────

    async def _close_trade(
        self,
        sig_dict: dict,
        exit_price: float,
        reason: str,
        entry: float,
        loss: bool,
    ) -> None:
        """
        Close a virtual trade, compute outcome, update MongoDB,
        and send public Telegram notification.

        Flushes proximity data (MFE%/MAE%) from the proximity repo before
        writing the final outcome.
        """
        signal_id = self._get_signal_id(sig_dict)
        direction = sig_dict["direction"]
        sl        = sig_dict["stop_loss"]

        # P&L percentage
        if direction == "BUY":
            pnl_pct = (exit_price - entry) / entry * 100
        else:
            pnl_pct = (entry - exit_price) / entry * 100

        # R-multiple realized
        sl_dist     = abs(entry - sl)
        rr_realized = 0.0
        if sl_dist > 0:
            rr_realized = ((exit_price - entry) / sl_dist if direction == "BUY"
                           else (entry - exit_price) / sl_dist)

        # Outcome classification
        if reason == "EXPIRED":
            outcome = "EXPIRED"
        else:
            outcome = ("WIN"  if rr_realized >  0.1
                       else "LOSS" if rr_realized < -0.1
                       else "BE")

        # Derive which level closed the trade
        hit_tp = {
            "TP1_HIT": "TP1",
            "TP2_HIT": "TP2",
            "TP3_HIT": "TP3",
            "SL_HIT":  "SL",
            "EXPIRED": None,
        }.get(reason)

        # Compute trade duration
        duration_minutes: Optional[int] = None
        created_at_str = sig_dict.get("created_at") or sig_dict.get("generated_at")
        if created_at_str:
            try:
                created_dt = datetime.fromisoformat(created_at_str)
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                delta = datetime.now(timezone.utc) - created_dt
                duration_minutes = int(delta.total_seconds() / 60)
            except Exception:
                pass

        # Flush proximity data from ProximityRepo
        proximity = await self.proximity_repo.flush_proximity(signal_id)

        # Unregister from price monitor (if available)
        try:
            from marketmate.execution.monitor import unregister_trade
            unregister_trade(signal_id)
        except ImportError:
            pass

        # Repository updates
        await self.signal_repo.update_status(signal_id, "CLOSED", reason, round(pnl_pct, 4))
        await self.signal_repo.log_trade_event(signal_id, reason, exit_price,
                                                note=f"rr={round(rr_realized, 2)}")

        # MongoDB outcome update — full lifecycle record including proximity
        doc_id = self._mongo_doc_ids.get(signal_id)
        if self.training_logger and doc_id:
            await self.training_logger.log_outcome(
                doc_id=doc_id,
                outcome=outcome,
                rr_realized=rr_realized,
                hit_tp=hit_tp,
                duration_minutes=duration_minutes,
                proximity=proximity,        # None-safe: log_outcome ignores if None
            )

        # MongoDB signal_archive outcome — ensures /performance can always
        # read from the durable store even after a redeploy wipes SQLite
        try:
            await self.signal_repo.update_outcome(
                signal_id=signal_id,
                outcome=outcome,
                exit_price=exit_price,
                pnl_r=rr_realized,
                candles_held=duration_minutes or 0,
                proximity=proximity,
            )
        except Exception as archive_exc:
            log.warning("signal_archive_outcome_failed",
                        signal_id=signal_id, error=str(archive_exc))

        # Public Telegram notification
        signal = _s(sig_dict)
        if reason == "EXPIRED":
            await self.telegram.send_alert(
                f"⏱ Trade Expired — {sig_dict['symbol']}",
                (
                    f"Direction: {direction}\n"
                    f"Exit price: {exit_price:,.2f}\n"
                    f"Duration: {duration_minutes or '?'} min\n"
                    f"P&L: {pnl_pct:+.2f}%\n"
                    f"MFE: {proximity['mfe_pct'] if proximity else '?'}%  "
                    f"MAE: {proximity['mae_pct'] if proximity else '?'}%"
                ),
            )
        elif loss:
            await self.telegram.send_sl_hit(signal, exit_price)
        else:
            await self.telegram.send_tp_hit(
                signal, reason.replace("_HIT", ""), exit_price
            )

        self._be_set.discard(signal_id)
        self._mongo_doc_ids.pop(signal_id, None)

        # Emit TRADE_CLOSED event
        await self.event_bus.emit(
            EventType.TRADE_CLOSED,
            {
                "signal_id":       signal_id,
                "symbol":          sig_dict.get("symbol", ""),
                "direction":       direction,
                "reason":          reason,
                "outcome":         outcome,
                "exit_price":      exit_price,
                "pnl_pct":         round(pnl_pct, 4),
                "rr_realized":     round(rr_realized, 4),
                "duration_minutes": duration_minutes,
                "hit_tp":          hit_tp,
            },
        )

        # Emit LOSS_HIT event for SL hits
        if loss:
            await self.event_bus.emit(
                EventType.LOSS_HIT,
                {
                    "signal_id":  signal_id,
                    "symbol":     sig_dict.get("symbol", ""),
                    "direction":  direction,
                    "exit_price": exit_price,
                    "sl":         sl,
                },
            )

        log.info(
            "virtual_trade_closed",
            signal_id=signal_id,
            symbol=sig_dict["symbol"],
            reason=reason,
            outcome=outcome,
            hit_tp=hit_tp,
            duration_minutes=duration_minutes,
            rr_realized=round(rr_realized, 4),
            pnl_pct=round(pnl_pct, 4),
            mfe_pct=proximity["mfe_pct"] if proximity else None,
            mae_pct=proximity["mae_pct"] if proximity else None,
            approached_tp=proximity["approached_tp"] if proximity else None,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _get_signal_id(sig_dict: dict) -> str:
        """Extract signal_id from a dict that may use 'id' or 'signal_id'."""
        return sig_dict.get("signal_id") or sig_dict.get("id", "")


# ─── Helper ───────────────────────────────────────────────────────────────────

def _s(d: dict) -> Signal:
    """Reconstruct a Signal shell from a DB dict for notification purposes."""
    s = Signal()
    for attr in ["id", "symbol", "direction", "entry_mid", "entry_low",
                 "entry_high", "stop_loss", "tp1", "tp2", "tp3",
                 "rr", "position_size", "confidence",
                 "zone_type", "confirm_type", "confirm_tf"]:
        if attr in d:
            setattr(s, attr, d[attr])
    # Also set id from signal_id if present
    if "signal_id" in d and not getattr(s, "id", ""):
        s.id = d["signal_id"]
    return s
