"""
signal_engine/delivery/telegram/validator.py
──────────────────────────────────────────────
Pre-delivery signal validation layer.

Every signal must pass sanity checks before it reaches the Telegram channel.
This is the last line of defence against malformed, dangerous, or nonsensical
signals being broadcast to subscribers.

Checks performed:
  1. Required fields present (symbol, direction, entry, SL, TP1, TP2, RR)
  2. Direction is valid (BUY/SELL)
  3. Price levels are internally consistent
     - BUY:  entry < TP1 < TP2 < TP3 (if present), SL < entry
     - SELL: entry > TP1 > TP2 > TP3 (if present), SL > entry
  4. RR is positive and above minimum threshold
  5. Entry zone is not degenerate (zero-width)
  6. Stop loss distance is not dangerously tight (< 5 pips equivalent)
  7. TP levels are in the correct order relative to entry
  8. Signal freshness (not older than a configurable max age)

Returns: (is_valid: bool, reasons: list[str])
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from signal_engine.core.config import cfg
from signal_engine.core.logger import get_logger

log = get_logger("signal_validator")

# ─── Configuration ─────────────────────────────────────────────────────────────

# Maximum signal age before delivery (default: 10 minutes)
MAX_SIGNAL_AGE_MINUTES = 10

# Minimum SL distance as fraction of entry price
# (e.g., 0.0005 = 5 pips on a 5-digit broker for a ~1.0000 quote)
MIN_SL_DISTANCE_PCT = 0.0005

# Minimum RR to broadcast (override from strategy config if higher)
MIN_BROADCAST_RR = 1.0


def validate_signal(signal) -> tuple[bool, list[str]]:
    """
    Validate a signal before Telegram delivery.

    Args:
        signal: Signal dataclass instance or dict-like object

    Returns:
        Tuple of (is_valid, list_of_rejection_reasons)
        If is_valid is True, the reasons list will be empty.
    """
    reasons: list[str] = []

    # ── Helper to get attribute from either dataclass or dict ───────────────
    def _get(key: str, default=None):
        if isinstance(signal, dict):
            return signal.get(key, default)
        return getattr(signal, key, default)

    # ── 1. Required fields ──────────────────────────────────────────────────
    symbol    = _get("symbol", "")
    direction = _get("direction", "")
    entry_mid = _get("entry_mid", 0.0)
    entry_low = _get("entry_low", 0.0)
    entry_high = _get("entry_high", 0.0)
    sl        = _get("stop_loss", _get("sl", 0.0))
    tp1       = _get("tp1", 0.0)
    tp2       = _get("tp2", 0.0)
    tp3       = _get("tp3", 0.0)
    rr        = _get("rr", 0.0)
    created_at = _get("created_at")

    if not symbol:
        reasons.append("Missing symbol")
    if not direction:
        reasons.append("Missing direction")
    if not entry_mid or entry_mid <= 0:
        reasons.append(f"Invalid entry_mid: {entry_mid}")
    if not sl or sl <= 0:
        reasons.append(f"Invalid stop_loss: {sl}")
    if not tp1 or tp1 <= 0:
        reasons.append(f"Invalid tp1: {tp1}")
    if not tp2 or tp2 <= 0:
        reasons.append(f"Invalid tp2: {tp2}")

    # Early return if critical fields are missing
    if reasons:
        log.warning("signal_validation_failed", reasons=reasons)
        return (False, reasons)

    # ── 2. Direction validity ───────────────────────────────────────────────
    if direction not in ("BUY", "SELL"):
        reasons.append(f"Invalid direction: {direction}")

    # ── 3. Price level consistency ──────────────────────────────────────────
    if direction == "BUY":
        # For BUY: SL < entry, entry < TP1 < TP2
        if sl >= entry_mid:
            reasons.append(
                f"BUY signal: SL ({sl}) >= entry ({entry_mid})"
            )
        if tp1 <= entry_mid:
            reasons.append(
                f"BUY signal: TP1 ({tp1}) <= entry ({entry_mid})"
            )
        if tp2 <= tp1:
            reasons.append(
                f"BUY signal: TP2 ({tp2}) <= TP1 ({tp1})"
            )
        if tp3 and tp3 > 0 and tp3 <= tp2:
            reasons.append(
                f"BUY signal: TP3 ({tp3}) <= TP2 ({tp2})"
            )

    elif direction == "SELL":
        # For SELL: SL > entry, entry > TP1 > TP2
        if sl <= entry_mid:
            reasons.append(
                f"SELL signal: SL ({sl}) <= entry ({entry_mid})"
            )
        if tp1 >= entry_mid:
            reasons.append(
                f"SELL signal: TP1 ({tp1}) >= entry ({entry_mid})"
            )
        if tp2 >= tp1:
            reasons.append(
                f"SELL signal: TP2 ({tp2}) >= TP1 ({tp1})"
            )
        if tp3 and tp3 > 0 and tp3 >= tp2:
            reasons.append(
                f"SELL signal: TP3 ({tp3}) >= TP2 ({tp2})"
            )

    # ── 4. RR validation ────────────────────────────────────────────────────
    if rr <= 0:
        reasons.append(f"Invalid RR: {rr}")
    elif rr < MIN_BROADCAST_RR:
        reasons.append(
            f"RR {rr:.2f} below broadcast minimum {MIN_BROADCAST_RR}"
        )

    # ── 5. Entry zone degeneracy ────────────────────────────────────────────
    if entry_low > 0 and entry_high > 0:
        zone_width = entry_high - entry_low
        zone_mid = (entry_high + entry_low) / 2
        if zone_mid > 0 and (zone_width / zone_mid) < 1e-8:
            reasons.append("Entry zone is degenerate (zero-width)")

    # ── 6. SL distance sanity ───────────────────────────────────────────────
    sl_distance = abs(entry_mid - sl)
    if entry_mid > 0 and (sl_distance / entry_mid) < MIN_SL_DISTANCE_PCT:
        reasons.append(
            f"SL distance ({sl_distance:.6f}) is dangerously tight "
            f"(< {MIN_SL_DISTANCE_PCT * 100:.3f}% of entry)"
        )

    # ── 7. Signal freshness ─────────────────────────────────────────────────
    if created_at is not None:
        try:
            if isinstance(created_at, datetime):
                signal_time = created_at
            elif isinstance(created_at, str):
                signal_time = datetime.fromisoformat(created_at)
            else:
                signal_time = None

            if signal_time is not None:
                age = datetime.now(timezone.utc) - signal_time
                if age > timedelta(minutes=MAX_SIGNAL_AGE_MINUTES):
                    reasons.append(
                        f"Signal is {age.total_seconds() / 60:.1f} minutes old "
                        f"(max: {MAX_SIGNAL_AGE_MINUTES} min)"
                    )
        except Exception as exc:
            log.debug("signal_age_check_skipped", error=str(exc))

    # ── Result ──────────────────────────────────────────────────────────────
    is_valid = len(reasons) == 0
    if not is_valid:
        log.warning(
            "signal_validation_failed",
            symbol=symbol,
            direction=direction,
            reasons=reasons,
        )
    else:
        log.debug("signal_validation_passed", symbol=symbol, direction=direction)

    return (is_valid, reasons)
