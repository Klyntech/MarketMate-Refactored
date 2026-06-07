"""
marketmate/state/engine.py
─────────────────────────────
State Engine — the architectural centerpiece of MarketMate Intelligence.

Transforms MarketMate from a system that computes and discards state on
every scan cycle into a system that maintains a continuous, evolving,
queryable model of market conditions.

The StateEngine:
  1. Receives enriched ScanFeatures from the gate pipeline
  2. Normalizes gate features into InstrumentState sub-models
  3. Computes StateDiffs (deltas) between consecutive states
  4. Persists to Redis (hot) + MongoDB (warm) via StateStore
  5. Emits state transition events via EventBus
  6. Provides APIs for querying current and historical state

New in v8.0.0 (Intelligence Infrastructure).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncio

from marketmate.core.config import cfg
from marketmate.core.events import event_bus
from marketmate.core.logger import get_logger
from marketmate.state.models import (
    BiasDirection,
    BiasState,
    ConfirmState,
    ConfirmationPattern,
    InstrumentState,
    LiquidityLevel,
    LiquidityState,
    MarketRegime,
    MarketStateVector,
    RiskState,
    StateDiff,
    StateDiffField,
    TrackedZone,
    VolatilityRegime,
    ZoneState,
    ZoneStatus,
)
from marketmate.state.store import get_state_store, StateStore
from marketmate.strategy.features import ScanFeatures

log = get_logger("state_engine")


# ─── Feature → State Normalizers ──────────────────────────────────────────────

def normalize_bias_state(features: ScanFeatures) -> BiasState:
    """
    Convert gate G4 BiasFeatures into a BiasState model.

    Computes conviction_score from EMA position + structure alignment.
    """
    bf = features.bias_features
    if bf is None:
        return BiasState()

    # Compute conviction score (-1.0 to +1.0)
    # Weight: EMA position (0.4), structure (0.3), resolution (0.3)
    conviction = 0.0

    # EMA contribution
    if bf.resolved_bias == "bullish":
        conviction += 0.4  # Price above EMA on aligned TFs
    elif bf.resolved_bias == "bearish":
        conviction -= 0.4

    # Structure contribution
    if bf.daily_structure == "bullish" and bf.h4_structure == "bullish":
        conviction += 0.3
    elif bf.daily_structure == "bearish" and bf.h4_structure == "bearish":
        conviction -= 0.3
    elif bf.daily_structure == "bullish" or bf.h4_structure == "bullish":
        conviction += 0.15
    elif bf.daily_structure == "bearish" or bf.h4_structure == "bearish":
        conviction -= 0.15

    # Resolution path bonus
    if bf.resolution_path == "full_agreement":
        conviction += 0.3 if conviction > 0 else -0.3
    elif bf.resolution_path == "daily_neutral_fallback_to_h4":
        conviction *= 0.7  # Slightly reduced conviction

    conviction = max(-1.0, min(1.0, conviction))

    # Determine regime
    regime = MarketRegime.TRANSITIONAL
    if abs(conviction) > 0.5:
        regime = MarketRegime.TRENDING
    elif abs(conviction) < 0.2:
        regime = MarketRegime.RANGING

    return BiasState(
        daily_ema200=bf.daily_ema200,
        h4_ema200=bf.h4_ema200,
        daily_bias=BiasDirection(bf.daily_bias),
        h4_bias=BiasDirection(bf.h4_bias),
        daily_structure=bf.daily_structure,
        h4_structure=bf.h4_structure,
        daily_above_ema=bf.daily_above_ema,
        h4_above_ema=bf.h4_above_ema,
        conviction_score=conviction,
        regime=regime,
        resolution_path=bf.resolution_path,
        current_price=bf.current_price,
    )


def normalize_liquidity_state(features: ScanFeatures) -> LiquidityState:
    """Convert gate G5 SweepFeatures into a LiquidityState model."""
    sf = features.sweep_features
    if sf is None:
        return LiquidityState()

    active_highs = [
        LiquidityLevel(price=h, level_type="swing_high", is_swept=False)
        for h in sf.all_swing_highs
    ]
    active_lows = [
        LiquidityLevel(price=l, level_type="swing_low", is_swept=False)
        for l in sf.all_swing_lows
    ]

    recent_sweeps = []
    if sf.sweep_found:
        level_type = "swing_low" if sf.best_sweep_type == "buy" else "swing_high"
        recent_sweeps.append(
            LiquidityLevel(
                price=sf.best_sweep_level,
                level_type=level_type,
                is_swept=True,
                swept_at=datetime.now(timezone.utc),
            )
        )

    # Compute available liquidity score
    total_levels = sf.available_swing_highs + sf.available_swing_lows
    swept_count = 1 if sf.sweep_found else 0
    available_score = 0.0
    if total_levels > 0:
        # Score based on ratio of unswept to total levels
        available_score = min(1.0, (total_levels - swept_count) / max(total_levels, 1))

    # Compute sweep rate (sweeps per hour, rolling estimate)
    # Since we don't have exact timestamps for each historical sweep,
    # we estimate based on: if sweep was found this cycle, increment rate.
    # A more accurate rate would require storing sweep timestamps.
    sweep_rate = 0.0
    if sf.sweep_found:
        # Approximate: 1 sweep per scan interval (typically 5 min = 12/hour)
        scan_interval_hours = max(cfg.app.scan_interval_seconds / 3600.0, 0.1)
        sweep_rate = round(1.0 / scan_interval_hours, 2)

    return LiquidityState(
        active_levels=active_highs + active_lows,
        recent_sweeps=recent_sweeps,
        sweep_rate=sweep_rate,
        available_liquidity_score=available_score,
    )


def normalize_zone_state(features: ScanFeatures) -> ZoneState:
    """Convert gate G6 ZoneFeatures into a ZoneState model."""
    zf = features.zone_features
    if zf is None:
        return ZoneState()

    active = []
    approaching = []
    expired = []

    for candidate in zf.all_candidates:
        freshness = 1.0 if candidate.is_winner else 0.5
        zone = TrackedZone(
            zone_type=candidate.zone_type,
            direction=candidate.direction,
            zone_high=candidate.zone_high,
            zone_low=candidate.zone_low,
            zone_mid=candidate.zone_mid,
            status=ZoneStatus.ACTIVE if candidate.is_winner else ZoneStatus.APPROACHING,
            freshness_score=freshness,
            candle_idx=candidate.candle_idx,
        )
        if candidate.is_winner:
            active.append(zone)
        else:
            approaching.append(zone)

    # Compute overall zone freshness
    freshness = 0.0
    if active:
        freshness = max(z.freshness_score for z in active)

    return ZoneState(
        active_zones=active,
        approaching_zones=approaching,
        expired_zones=expired,
        zone_freshness=freshness,
    )


def normalize_confirm_state(features: ScanFeatures) -> ConfirmState:
    """Convert gate G7 ConfirmFeatures into a ConfirmState model."""
    cf = features.confirm_features
    if cf is None:
        return ConfirmState()

    recent_bos = []
    recent_choch = []

    for pattern in cf.all_patterns:
        cp = ConfirmationPattern(
            signal_type=pattern.signal_type,
            direction=pattern.direction,
            break_level=pattern.break_level,
            timeframe=pattern.timeframe,
        )
        if pattern.signal_type == "BOS":
            recent_bos.append(cp)
        else:
            recent_choch.append(cp)

    # Compute alignment score
    alignment = 0.0
    if cf.confirmation_found:
        # Higher score for CHoCH on M15 (strongest confirmation)
        if cf.winner_signal_type == "CHoCH" and cf.winner_timeframe == "M15":
            alignment = 1.0
        elif cf.winner_signal_type == "CHoCH":
            alignment = 0.8
        elif cf.winner_timeframe == "M15":
            alignment = 0.7
        else:
            alignment = 0.5

    # Compute pattern rate (patterns per hour, rolling estimate)
    pattern_rate = 0.0
    if cf.confirmation_found:
        total_patterns = len(recent_bos) + len(recent_choch)
        scan_interval_hours = max(cfg.app.scan_interval_seconds / 3600.0, 0.1)
        pattern_rate = round(total_patterns / scan_interval_hours, 2)

    return ConfirmState(
        recent_bos=recent_bos,
        recent_choch=recent_choch,
        pattern_rate=pattern_rate,
        alignment_score=alignment,
    )


def normalize_risk_state(features: ScanFeatures) -> RiskState:
    """Convert gate G8 RRFeatures into a RiskState model."""
    rf = features.rr_features
    if rf is None:
        return RiskState()

    # Determine volatility regime from ATR/SL ratio
    vol_regime = VolatilityRegime.NORMAL
    if rf.sl_distance_atr_ratio > 2.0:
        vol_regime = VolatilityRegime.EXTREME
    elif rf.sl_distance_atr_ratio > 1.5:
        vol_regime = VolatilityRegime.HIGH
    elif rf.sl_distance_atr_ratio < 0.5:
        vol_regime = VolatilityRegime.LOW

    return RiskState(
        atr=rf.atr_value,
        sl_distance_pips=rf.sl_distance_pips,
        volatility_regime=vol_regime,
        current_rr=rf.rr,
    )


# ─── State Diff Computation ───────────────────────────────────────────────────

def compute_state_diff(
    symbol: str,
    old_state: Optional[InstrumentState],
    new_state: InstrumentState,
) -> StateDiff:
    """
    Compute the diff between two consecutive InstrumentState snapshots.

    Only records meaningful changes (not every field on every scan).
    """
    changes: List[StateDiffField] = []
    bias_changed = False
    zone_formed = False
    zone_expired = False
    sweep_detected = False
    regime_changed = False

    if old_state is None:
        # First state for this instrument — everything is new
        changes.append(StateDiffField(
            field_path="instrument_state",
            change_type="created",
        ))
        return StateDiff(
            symbol=symbol,
            bias_changed=True,
            zone_formed=True,
        )

    # Bias change detection
    old_bias = old_state.bias_state.daily_bias
    new_bias = new_state.bias_state.daily_bias
    if old_bias != new_bias:
        changes.append(StateDiffField(
            field_path="bias_state.daily_bias",
            old_value=float(old_bias.value) if hasattr(old_bias, 'value') else 0.0,
            new_value=float(new_bias.value) if hasattr(new_bias, 'value') else 0.0,
            change_type="updated",
        ))
        bias_changed = True

    # Conviction score significant change
    old_conv = old_state.bias_state.conviction_score
    new_conv = new_state.bias_state.conviction_score
    # Use the configured threshold from StateConfig (default 0.2)
    _threshold = float(getattr(cfg.state, 'conviction_change_threshold', 0.2))
    if abs(new_conv - old_conv) >= _threshold:
        changes.append(StateDiffField(
            field_path="bias_state.conviction_score",
            old_value=old_conv,
            new_value=new_conv,
            change_type="updated",
        ))

    # Regime change detection
    old_regime = old_state.bias_state.regime
    new_regime = new_state.bias_state.regime
    if old_regime != new_regime:
        regime_changed = True
        changes.append(StateDiffField(
            field_path="bias_state.regime",
            change_type="updated",
        ))

    # Zone change detection
    old_zone_count = len(old_state.zone_state.active_zones)
    new_zone_count = len(new_state.zone_state.active_zones)
    if new_zone_count > old_zone_count:
        zone_formed = True
    elif new_zone_count < old_zone_count:
        zone_expired = True

    # Sweep detection
    old_sweep_count = len(old_state.liquidity_state.recent_sweeps)
    new_sweep_count = len(new_state.liquidity_state.recent_sweeps)
    if new_sweep_count > old_sweep_count:
        sweep_detected = True

    # Volatility regime change
    old_vol = old_state.risk_state.volatility_regime
    new_vol = new_state.risk_state.volatility_regime
    if old_vol != new_vol:
        changes.append(StateDiffField(
            field_path="risk_state.volatility_regime",
            change_type="updated",
        ))

    return StateDiff(
        symbol=symbol,
        changes=changes,
        bias_changed=bias_changed,
        zone_formed=zone_formed,
        zone_expired=zone_expired,
        sweep_detected=sweep_detected,
        regime_changed=regime_changed,
    )


# ─── State Engine ─────────────────────────────────────────────────────────────

class StateEngine:
    """
    Central state management engine.

    Receives ScanFeatures from the gate pipeline, normalizes them into
    InstrumentState models, computes diffs, persists, and emits events.
    """

    def __init__(self) -> None:
        self._store: StateStore = get_state_store()
        self._market_state = MarketStateVector()
        self._last_states: Dict[str, InstrumentState] = {}
        self._snapshot_interval_minutes: int = cfg.state.snapshot_interval_minutes
        self._max_expired_zones: int = cfg.state.max_expired_zones
        self._max_recent_patterns: int = cfg.state.max_recent_patterns
        self._conviction_change_threshold: float = cfg.state.conviction_change_threshold
        self._last_snapshot_at: Dict[str, datetime] = {}
        self._scan_cycle = 0

    # ─── Public API ──────────────────────────────────────────────────────

    async def process_scan_features(self, features: ScanFeatures) -> StateDiff:
        """
        Process a ScanFeatures object from the gate pipeline.

        This is the main entry point. The gate pipeline produces
        ScanFeatures on every scan cycle, and the StateEngine
        normalizes, diffs, persists, and emits events.

        Args:
            features: Enriched feature vector from a complete scan cycle

        Returns:
            StateDiff representing the changes (may be empty)
        """
        symbol = features.symbol
        self._scan_cycle += 1

        # 1. Normalize features into sub-states
        bias_state = normalize_bias_state(features)
        liquidity_state = normalize_liquidity_state(features)
        zone_state = normalize_zone_state(features)
        confirm_state = normalize_confirm_state(features)
        risk_state = normalize_risk_state(features)

        # 2. Build new InstrumentState
        new_state = InstrumentState(
            symbol=symbol,
            bias_state=bias_state,
            liquidity_state=liquidity_state,
            zone_state=zone_state,
            confirm_state=confirm_state,
            risk_state=risk_state,
            overall_signal_quality=features.setup_score if features.passed else 0.0,
            confidence_score=features.confidence_score,
            confidence_tier=features.confidence_tier,
            setup_score=features.setup_score,
            scan_count=1,
            last_scan_at=datetime.now(timezone.utc),
        )

        # Merge with existing state (increment scan_count, preserve history)
        old_state = self._last_states.get(symbol)
        if old_state is not None:
            new_state.scan_count = old_state.scan_count + 1
            new_state.last_signal_at = old_state.last_signal_at
            # Preserve existing zone/confirmation history
            new_state.zone_state.expired_zones = (
                old_state.zone_state.expired_zones + old_state.zone_state.active_zones
            )[-self._max_expired_zones :]
            new_state.confirm_state.recent_bos = (
                old_state.confirm_state.recent_bos + confirm_state.recent_bos
            )[-self._max_recent_patterns :]
            new_state.confirm_state.recent_choch = (
                old_state.confirm_state.recent_choch + confirm_state.recent_choch
            )[-self._max_recent_patterns :]

        # 3. Compute diff
        diff = compute_state_diff(symbol, old_state, new_state)

        # 4. Store in memory
        self._last_states[symbol] = new_state
        self._market_state.instruments[symbol] = new_state
        self._market_state.scan_cycle = self._scan_cycle
        self._market_state.updated_at = datetime.now(timezone.utc)

        # 5. Persist to Redis (hot layer) — every scan cycle
        await self._store.save_current_state(new_state)
        await self._store.save_market_state(self._market_state)

        # 6. Persist diff
        await self._store.save_diff(diff)

        # 7. Persist snapshot to MongoDB (warm layer) — at intervals
        await self._maybe_save_snapshot(symbol, new_state)

        # 8. Emit state transition events via EventBus
        # This is the critical "State → Events" link in the pipeline:
        #   Scan → Features → State → Events → Storage
        #   Without this, the event layer is disconnected from state transitions.
        self._emit_transition_events(symbol, diff, old_state, new_state)

        # 9. Log material changes
        if diff.has_material_change:
            log.info(
                "state_transition_detected",
                symbol=symbol,
                bias_changed=diff.bias_changed,
                zone_formed=diff.zone_formed,
                zone_expired=diff.zone_expired,
                sweep_detected=diff.sweep_detected,
                regime_changed=diff.regime_changed,
                conviction_score=round(new_state.bias_state.conviction_score, 3),
                regime=new_state.bias_state.regime.value,
            )

        return diff

    async def get_instrument_state(self, symbol: str) -> Optional[InstrumentState]:
        """Get current state for an instrument (memory → Redis → None)."""
        # Check memory first
        if symbol in self._last_states:
            return self._last_states[symbol]
        # Fall back to Redis
        return await self._store.load_current_state(symbol)

    async def get_market_state(self) -> MarketStateVector:
        """Get the complete MarketStateVector."""
        return self._market_state

    async def get_historical_states(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        limit: int = 100,
    ) -> List[InstrumentState]:
        """Load historical state snapshots from MongoDB."""
        return await self._store.load_historical_states(symbol, start, end, limit)

    async def initialize(self) -> None:
        """
        Bootstrap the state engine from Redis on startup.

        Loads existing states for all configured pairs from Redis
        so that the engine has state immediately after restart.
        """
        log.info("state_engine_initializing")

        for symbol in cfg.strategy.pairs:
            state = await self._store.load_current_state(symbol)
            if state is not None:
                self._last_states[symbol] = state
                self._market_state.instruments[symbol] = state
                log.info(
                    "state_engine_bootstrapped",
                    symbol=symbol,
                    scan_count=state.scan_count,
                    conviction=round(state.bias_state.conviction_score, 3),
                )

        log.info(
            "state_engine_initialized",
            instruments_loaded=len(self._last_states),
            scan_cycle=self._scan_cycle,
        )

    # ─── Event Emission ────────────────────────────────────────────────────

    def _emit_transition_events(
        self,
        symbol: str,
        diff: StateDiff,
        old_state: Optional[InstrumentState],
        new_state: InstrumentState,
    ) -> None:
        """
        Emit typed events for each material state transition detected.

        This is the bridge between the State layer and the Event layer:
          State → Events → (subscribers: MATE, Telegram, API, ML)

        Each event carries structured, validated state — not raw features.
        Consumers subscribe to specific event types they care about.
        """
        if not diff.has_material_change:
            return

        try:
            # bias_changed → BiasChangedEvent
            if diff.bias_changed:
                old_bias = old_state.bias_state.daily_bias.value if old_state else "none"
                asyncio.create_task(event_bus.emit("bias_changed", {
                    "symbol": symbol,
                    "old_bias": old_bias,
                    "new_bias": new_state.bias_state.daily_bias.value,
                    "conviction_score": round(new_state.bias_state.conviction_score, 3),
                    "resolution_path": new_state.bias_state.resolution_path,
                    "daily_ema200": new_state.bias_state.daily_ema200,
                    "h4_ema200": new_state.bias_state.h4_ema200,
                }))

            # zone_formed → ZoneFormedEvent
            if diff.zone_formed and new_state.zone_state.active_zones:
                latest_zone = new_state.zone_state.active_zones[-1]
                asyncio.create_task(event_bus.emit("zone_formed", {
                    "symbol": symbol,
                    "zone_type": latest_zone.zone_type,
                    "direction": latest_zone.direction,
                    "zone_high": latest_zone.zone_high,
                    "zone_low": latest_zone.zone_low,
                    "freshness_score": latest_zone.freshness_score,
                }))

            # zone_expired → ZoneExpiredEvent
            if diff.zone_expired and new_state.zone_state.expired_zones:
                latest_expired = new_state.zone_state.expired_zones[-1]
                asyncio.create_task(event_bus.emit("zone_expired", {
                    "symbol": symbol,
                    "zone_type": latest_expired.zone_type,
                    "direction": latest_expired.direction,
                    "zone_high": latest_expired.zone_high,
                    "zone_low": latest_expired.zone_low,
                }))

            # sweep_detected → SweepDetectedEvent
            if diff.sweep_detected and new_state.liquidity_state.recent_sweeps:
                latest_sweep = new_state.liquidity_state.recent_sweeps[-1]
                asyncio.create_task(event_bus.emit("sweep_detected", {
                    "symbol": symbol,
                    "swept_level": latest_sweep.price,
                    "sweep_type": latest_sweep.level_type,
                    "direction": "bullish" if latest_sweep.level_type == "swing_low" else "bearish",
                    "available_levels": len(new_state.liquidity_state.active_levels),
                    "sweep_rate": new_state.liquidity_state.sweep_rate,
                }))

            # regime_changed → RegimeChangedEvent
            if diff.regime_changed:
                old_regime = old_state.bias_state.regime.value if old_state else "none"
                asyncio.create_task(event_bus.emit("regime_changed", {
                    "symbol": symbol,
                    "old_regime": old_regime,
                    "new_regime": new_state.bias_state.regime.value,
                    "confidence": round(new_state.bias_state.conviction_score, 3),
                    "conviction_score": round(new_state.bias_state.conviction_score, 3),
                }))

        except Exception as exc:
            log.warning(
                "state_event_emission_failed",
                symbol=symbol,
                error=str(exc),
            )

    # ─── Internal ────────────────────────────────────────────────────────

    async def _maybe_save_snapshot(self, symbol: str, state: InstrumentState) -> None:
        """Save a snapshot to MongoDB at the configured interval."""
        now = datetime.now(timezone.utc)
        last = self._last_snapshot_at.get(symbol)

        should_save = (
            last is None
            or (now - last).total_seconds() >= self._snapshot_interval_minutes * 60
        )

        if should_save:
            await self._store.save_snapshot(state)
            self._last_snapshot_at[symbol] = now
            log.debug("state_snapshot_saved", symbol=symbol)


# ─── Singleton ────────────────────────────────────────────────────────────────

_state_engine: Optional[StateEngine] = None


def get_state_engine() -> StateEngine:
    """Get or create the singleton StateEngine."""
    global _state_engine
    if _state_engine is None:
        _state_engine = StateEngine()
    return _state_engine
