"""
marketmate/strategy/dedup.py
──────────────────────────────
ATR-Relative Deduplication Logic.

Replaces the fixed-percentage thresholds in the original dedup system
with ATR-relative thresholds that automatically adapt to each
instrument's volatility regime.

Key improvements over the original:
  - Structure-distance threshold: 0.3% → 0.3 × ATR (adapts to volatility)
  - Price-proximity threshold:    0.2% → 0.2 × ATR (adapts to volatility)
  - Zone-overlap threshold:       80%  → remains percentage-based (dimensionless)
  - Directional flip cooldown:    10 min fixed → configurable per symbol
  - Standard cooldown:            30 min fixed → configurable per symbol

Backward Compatibility:
  Falls back to the original fixed-percentage thresholds when ATR
  is unavailable (e.g., during restart before first scan completes).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.strategy.models import Signal

log = get_logger("dedup")


# ─── ATR-relative threshold defaults ─────────────────────────────────────────

# Multipliers: threshold = multiplier × ATR
# These are calibrated so that at average ATR, the thresholds are
# approximately equivalent to the original fixed percentages.
ATR_STRUCTURE_DISTANCE_MULT = float(
    getattr(cfg.strategy, "dedup_atr_structure_mult", 0) or 0.3
)
ATR_PRICE_PROXIMITY_MULT = float(
    getattr(cfg.strategy, "dedup_atr_proximity_mult", 0) or 0.2
)

# Fallback fixed-percentage thresholds (used when ATR is not available)
FALLBACK_STRUCTURE_DISTANCE_PCT = 0.003   # 0.3%
FALLBACK_PRICE_PROXIMITY_PCT = 0.002      # 0.2%

# Zone overlap is already dimensionless — keep as percentage
ZONE_OVERLAP_PCT = 0.80

# Per-symbol cooldown overrides (keyed by symbol)
# Format: {symbol: {"cooldown_min": int, "flip_cooldown_min": int}}
_SYMBOL_COOLDOWN_OVERRIDES: dict = {}


def configure_symbol_cooldowns(overrides: dict) -> None:
    """
    Configure per-symbol cooldown overrides.

    Args:
        overrides: Dict mapping symbol to cooldown config.
                   Example: {"BTCUSD": {"cooldown_min": 20, "flip_cooldown_min": 5}}
    """
    global _SYMBOL_COOLDOWN_OVERRIDES
    _SYMBOL_COOLDOWN_OVERRIDES = overrides
    log.info("dedup_symbol_cooldowns_configured", overrides=overrides)


def get_effective_cooldown(symbol: str) -> timedelta:
    """Get the effective standard cooldown for a symbol."""
    override = _SYMBOL_COOLDOWN_OVERRIDES.get(symbol, {})
    minutes = override.get("cooldown_min", cfg.strategy.dedup_cooldown_minutes)
    return timedelta(minutes=minutes)


def get_effective_flip_cooldown(symbol: str) -> timedelta:
    """Get the effective flip cooldown for a symbol."""
    override = _SYMBOL_COOLDOWN_OVERRIDES.get(symbol, {})
    minutes = override.get(
        "flip_cooldown_min",
        int(getattr(cfg.strategy, "dedup_flip_cooldown_minutes", 0) or 10)
    )
    return timedelta(minutes=minutes)


# ─── ATR-relative threshold computation ──────────────────────────────────────

def compute_structure_distance_threshold(atr: Optional[float], price: float) -> float:
    """
    Compute the structure-distance threshold.

    When ATR is available: threshold = ATR_STRUCTURE_DISTANCE_MULT × ATR
    When ATR is unavailable: threshold = FALLBACK_STRUCTURE_DISTANCE_PCT × price

    Args:
        atr: Current ATR value for the instrument (None if unavailable)
        price: Current price (used for fallback percentage calculation)

    Returns:
        Threshold in absolute price units
    """
    if atr is not None and atr > 0:
        threshold = ATR_STRUCTURE_DISTANCE_MULT * atr
        log.debug(
            "structure_distance_threshold_atr",
            threshold=round(threshold, 6),
            atr=round(atr, 6),
            multiplier=ATR_STRUCTURE_DISTANCE_MULT,
        )
        return threshold
    # Fallback to fixed percentage
    threshold = FALLBACK_STRUCTURE_DISTANCE_PCT * price
    log.debug(
        "structure_distance_threshold_fallback",
        threshold=round(threshold, 6),
        price=round(price, 6),
        pct=FALLBACK_STRUCTURE_DISTANCE_PCT,
    )
    return threshold


def compute_price_proximity_threshold(atr: Optional[float], price: float) -> float:
    """
    Compute the price-proximity threshold.

    When ATR is available: threshold = ATR_PRICE_PROXIMITY_MULT × ATR
    When ATR is unavailable: threshold = FALLBACK_PRICE_PROXIMITY_PCT × price

    Args:
        atr: Current ATR value for the instrument (None if unavailable)
        price: Current price (used for fallback percentage calculation)

    Returns:
        Threshold in absolute price units
    """
    if atr is not None and atr > 0:
        threshold = ATR_PRICE_PROXIMITY_MULT * atr
        log.debug(
            "price_proximity_threshold_atr",
            threshold=round(threshold, 6),
            atr=round(atr, 6),
            multiplier=ATR_PRICE_PROXIMITY_MULT,
        )
        return threshold
    # Fallback to fixed percentage
    threshold = FALLBACK_PRICE_PROXIMITY_PCT * price
    log.debug(
        "price_proximity_threshold_fallback",
        threshold=round(threshold, 6),
        price=round(price, 6),
        pct=FALLBACK_PRICE_PROXIMITY_PCT,
    )
    return threshold


# ─── Dedup Check Functions ────────────────────────────────────────────────────

def is_structurally_distinct(
    new_signal: Signal,
    last_signal: Signal,
    atr: Optional[float] = None,
) -> bool:
    """
    Check if two signals are structurally distinct using ATR-relative thresholds.

    Two signals are structurally distinct if their swept levels differ by
    more than the structure-distance threshold. This means they target
    different liquidity pools and are independently valid.

    Args:
        new_signal: The candidate signal
        last_signal: The previous signal for the same symbol+direction
        atr: Current ATR value (None for fallback to fixed percentages)

    Returns:
        True if structurally distinct (not a duplicate)
    """
    if new_signal.swept_level <= 0 or last_signal.swept_level <= 0:
        return False

    diff = abs(new_signal.swept_level - last_signal.swept_level)
    threshold = compute_structure_distance_threshold(atr, last_signal.swept_level)
    is_distinct = diff > threshold

    if is_distinct:
        log.info(
            "dedup_structure_distinct",
            symbol=new_signal.symbol,
            direction=new_signal.direction,
            new_level=round(new_signal.swept_level, 4),
            last_level=round(last_signal.swept_level, 4),
            diff=round(diff, 6),
            threshold=round(threshold, 6),
            atr_based=atr is not None,
        )

    return is_distinct


def is_price_proximate(
    new_signal: Signal,
    last_signal: Signal,
    atr: Optional[float] = None,
) -> bool:
    """
    Check if two signals have entry prices that are too close together.

    Uses ATR-relative thresholds when available, falling back to
    fixed percentages otherwise.

    Args:
        new_signal: The candidate signal
        last_signal: The previous signal
        atr: Current ATR value (None for fallback)

    Returns:
        True if prices are too close (signal is a duplicate)
    """
    if last_signal.entry_mid <= 0 or new_signal.entry_mid <= 0:
        return False

    price_diff = abs(new_signal.entry_mid - last_signal.entry_mid)
    threshold = compute_price_proximity_threshold(atr, last_signal.entry_mid)
    is_duplicate = price_diff < threshold

    if is_duplicate:
        log.info(
            "dedup_price_proximate",
            symbol=new_signal.symbol,
            direction=new_signal.direction,
            price_diff=round(price_diff, 6),
            threshold=round(threshold, 6),
            new_entry=round(new_signal.entry_mid, 4),
            last_entry=round(last_signal.entry_mid, 4),
            atr_based=atr is not None,
        )

    return is_duplicate


def zones_overlap(
    new_signal: Signal,
    last_signal: Signal,
) -> float:
    """
    Calculate zone overlap percentage between two signals.

    Zone overlap is dimensionless (0.0-1.0) so it does not need
    ATR normalization. A high overlap indicates the same entry zone
    is being targeted.

    Returns:
        Overlap percentage (0.0 to 1.0+)
    """
    if (new_signal.entry_low <= 0 or new_signal.entry_high <= 0 or
            last_signal.entry_low <= 0 or last_signal.entry_high <= 0):
        return 0.0

    # Overlap = intersection / min_zone_width
    overlap_low = max(new_signal.entry_low, last_signal.entry_low)
    overlap_high = min(new_signal.entry_high, last_signal.entry_high)

    if overlap_high <= overlap_low:
        return 0.0

    overlap_width = overlap_high - overlap_low
    new_width = new_signal.entry_high - new_signal.entry_low
    last_width = last_signal.entry_high - last_signal.entry_low

    min_width = min(new_width, last_width)
    if min_width <= 0:
        return 0.0

    return overlap_width / min_width


def is_duplicate_signal(
    new_signal: Signal,
    last_signal: Signal,
    last_any_dir: Optional[tuple[str, Signal]] = None,
    atr: Optional[float] = None,
) -> bool:
    """
    Comprehensive ATR-relative dedup check.

    Checks in order:
    1. Structure-distance: Different liquidity pool → bypass cooldown
    2. Directional flip fast-track: Opposite direction, reduced cooldown
    3. Standard cooldown: Same direction, standard cooldown
    4. Zone overlap: Same entry zone
    5. Price proximity: Entry prices too close

    Args:
        new_signal: The candidate signal
        last_signal: The previous signal for same (symbol, direction)
        last_any_dir: Tuple of (direction, Signal) for last signal in any direction
        atr: Current ATR value for the instrument

    Returns:
        True if the signal is a duplicate (should be rejected)
    """
    # ── 1. Structure-distance check (ATR-relative) ───────────────────────
    if is_structurally_distinct(new_signal, last_signal, atr):
        # Different liquidity pool — still check zone overlap for safety
        overlap = zones_overlap(new_signal, last_signal)
        if overlap > ZONE_OVERLAP_PCT:
            log.info(
                "dedup_rejected_zone_overlap_despite_structure_distinct",
                symbol=new_signal.symbol,
                direction=new_signal.direction,
                overlap_pct=round(overlap, 3),
            )
            return True
        return False  # Structurally distinct, not a duplicate

    # ── 2. Time cooldown (context-aware, per-symbol) ─────────────────────
    elapsed = datetime.now(timezone.utc) - last_signal.created_at

    if last_any_dir is not None:
        last_dir, _ = last_any_dir
        if last_dir != new_signal.direction:
            # Opposite direction — use flip cooldown
            flip_cooldown = get_effective_flip_cooldown(new_signal.symbol)
            if elapsed < flip_cooldown:
                log.info(
                    "dedup_rejected_flip_cooldown",
                    symbol=new_signal.symbol,
                    direction=new_signal.direction,
                    minutes_ago=round(elapsed.total_seconds() / 60, 1),
                    flip_cooldown_minutes=flip_cooldown.total_seconds() / 60,
                )
                return True
        else:
            # Same direction — use standard cooldown
            cooldown = get_effective_cooldown(new_signal.symbol)
            if elapsed < cooldown:
                log.info(
                    "dedup_rejected_cooldown",
                    symbol=new_signal.symbol,
                    direction=new_signal.direction,
                    minutes_ago=round(elapsed.total_seconds() / 60, 1),
                    cooldown_minutes=cooldown.total_seconds() / 60,
                )
                return True
    else:
        # No last_any_dir — use standard cooldown
        cooldown = get_effective_cooldown(new_signal.symbol)
        if elapsed < cooldown:
            log.info(
                "dedup_rejected_cooldown",
                symbol=new_signal.symbol,
                direction=new_signal.direction,
                minutes_ago=round(elapsed.total_seconds() / 60, 1),
                cooldown_minutes=cooldown.total_seconds() / 60,
            )
            return True

    # ── 3. Zone overlap check ────────────────────────────────────────────
    overlap = zones_overlap(new_signal, last_signal)
    if overlap > ZONE_OVERLAP_PCT:
        log.info(
            "dedup_rejected_zone_overlap",
            symbol=new_signal.symbol,
            direction=new_signal.direction,
            overlap_pct=round(overlap, 3),
        )
        return True

    # ── 4. Price proximity check (ATR-relative) ──────────────────────────
    if is_price_proximate(new_signal, last_signal, atr):
        return True

    return False
