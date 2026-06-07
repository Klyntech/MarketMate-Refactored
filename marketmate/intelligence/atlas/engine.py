"""
marketmate.intelligence.atlas.engine
─────────────────────────────────────
ATLAS: Market Reasoning Engine

Understands STRUCTURE, not just movement.
Explains "why", not just "what".
Connects MULTIPLE timeframes.
Interprets LIQUIDITY behavior.

ATLAS is the analytical core that transforms validated market data
(from PRISM) into structured market intelligence. It does NOT make
trading decisions — it REASONS about market conditions so that
downstream layers (VANTA, NOVA) can act with full context.

Capabilities:
  1. Market structure analysis — BOS / CHoCH / consolidation detection
  2. Liquidity sweep detection and interpretation
  3. Order flow interpretation (abstracted from price behavior)
  4. Multi-timeframe alignment (M15 → H1 → D1)
  5. Conviction scoring with explanatory reasoning
  6. Support/resistance zone reasoning
  7. Regime classification (trend / range / transition / volatile)
  8. Trade context evaluation (setup quality, not execution)
  9. Pattern recognition across sessions

Position in pipeline:
  RAW DATA → PRISM → VINNI → [ATLAS] → VANTA → NOVA

Critical Rules:
  - ATLAS does NOT take actions or modify data.
  - ATLAS does NOT execute trades or manage positions.
  - ATLAS REASONS about what the market is doing and WHY.
  - ATLAS respects PRISM flags — data quality affects confidence.
  - Every conclusion includes reasoning (never a bare score).

Created: 2026-05-29
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from marketmate.core.logger import get_logger

log = get_logger("intelligence.atlas")


# ─── Enums ────────────────────────────────────────────────────────────────────

class MarketRegime(str, Enum):
    """Market regime classifications."""
    TREND = "trend"
    RANGE = "range"
    TRANSITION = "transition"
    VOLATILE = "volatile"


class StructureType(str, Enum):
    """Market structure classifications."""
    BOS = "bos"                # Break of Structure — trend continuation
    CHOCH = "choch"            # Change of Character — trend reversal
    CONSOLIDATION = "consolidation"
    UNDEFINED = "undefined"


class TimeframeAlignment(str, Enum):
    """Multi-timeframe alignment states."""
    ALIGNED = "aligned"
    MIXED = "mixed"
    CONFLICTING = "conflicting"


class LiquidityType(str, Enum):
    """Types of liquidity zones."""
    EQUAL_HIGHS = "equal_highs"
    EQUAL_LOWS = "equal_lows"
    SWING = "swing"


class ZoneType(str, Enum):
    """Support / resistance zone types."""
    SUPPORT = "support"
    RESISTANCE = "resistance"


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class LiquidityZone:
    """
    A detected liquidity zone.

    Attributes:
        level: Price level of the liquidity zone.
        type: Kind of liquidity (equal_highs, equal_lows, swing).
        strength: Strength score 0.0-1.0.
        distance_pct: Distance from current price as percentage.
    """
    level: float
    type: str  # LiquidityType value
    strength: float = 0.0
    distance_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for downstream consumption."""
        return {
            "level": self.level,
            "type": self.type,
            "strength": round(self.strength, 4),
            "distance_pct": round(self.distance_pct, 4),
        }


@dataclass
class SupportResistanceZone:
    """
    A support or resistance zone with multi-timeframe context.

    Attributes:
        price: The price level of the zone.
        type: Whether this is support or resistance.
        strength: Strength score 0.0-1.0.
        timeframe: Timeframe where this zone was identified.
        touches: Number of times price has reacted at this level.
    """
    price: float
    type: str  # ZoneType value
    strength: float = 0.0
    timeframe: str = ""
    touches: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for downstream consumption."""
        return {
            "price": self.price,
            "type": self.type,
            "strength": round(self.strength, 4),
            "timeframe": self.timeframe,
            "touches": self.touches,
        }


@dataclass
class LiquiditySweepEvent:
    """
    A detected liquidity sweep event.

    Attributes:
        level: The price level that was swept.
        direction: Whether liquidity above or below was taken.
        strength: How decisive the sweep was (0.0-1.0).
        closed_beyond: Whether price closed beyond the swept level.
        candles_ago: How many candles ago the sweep occurred.
    """
    level: float
    direction: str  # "bullish_sweep" | "bearish_sweep"
    strength: float = 0.0
    closed_beyond: bool = False
    candles_ago: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level,
            "direction": self.direction,
            "strength": round(self.strength, 4),
            "closed_beyond": self.closed_beyond,
            "candles_ago": self.candles_ago,
        }


@dataclass
class AtlasAnalysis:
    """
    Structured analysis result from the ATLAS engine.

    This is the primary output of ATLAS — a comprehensive market
    intelligence snapshot that downstream layers (VANTA, NOVA)
    consume to make decisions.

    Every field includes reasoning context, not just raw scores.
    ATLAS explains WHY, not just WHAT.

    Attributes:
        symbol: Trading symbol analyzed.
        regime: Current market regime classification.
        structure: Market structure type (BOS/CHoCH/consolidation/undefined).
        liquidity_zones: Detected liquidity zones with strength.
        timeframe_alignment: Multi-timeframe alignment state.
        conviction: Conviction score 0-100 with explanatory reasoning.
        conviction_reasoning: Human-readable explanation of conviction score.
        support_resistance: Support and resistance zones.
        confidence: Overall confidence in this analysis (0.0-1.0).
        data_quality_flags: PRISM flags that affect this analysis.
        timestamp: When this analysis was produced.
    """
    symbol: str
    regime: str  # MarketRegime value
    structure: str  # StructureType value
    liquidity_zones: List[Dict[str, Any]]  # List of LiquidityZone.to_dict()
    timeframe_alignment: str  # TimeframeAlignment value
    conviction: int  # 0-100
    conviction_reasoning: str
    support_resistance: List[Dict[str, Any]]  # List of SupportResistanceZone.to_dict()
    confidence: float  # 0.0-1.0
    data_quality_flags: List[str]
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to structured dictionary for downstream consumption."""
        return {
            "symbol": self.symbol,
            "regime": self.regime,
            "structure": self.structure,
            "liquidity_zones": self.liquidity_zones,
            "timeframe_alignment": self.timeframe_alignment,
            "conviction": self.conviction,
            "conviction_reasoning": self.conviction_reasoning,
            "support_resistance": self.support_resistance,
            "confidence": round(self.confidence, 4),
            "data_quality_flags": self.data_quality_flags,
            "timestamp": self.timestamp,
        }


# ─── ATLAS Engine ─────────────────────────────────────────────────────────────

class AtlasEngine:
    """
    Market Reasoning Engine — the analytical core of MarketMate Intelligence.

    ATLAS transforms validated market data into structured market intelligence.
    It does NOT make trading decisions — it REASONS about market conditions
    so that downstream layers (VANTA, NOVA) can act with full context.

    Key Principles:
      - Every conclusion includes reasoning (never a bare score).
      - Respects PRISM data quality flags — bad data reduces confidence.
      - Multi-timeframe analysis is mandatory, not optional.
      - Structure analysis (BOS/CHoCH) is the foundation, not indicators.
      - Liquidity behavior is interpreted, not just detected.

    Configuration:
        swing_lookback: Candles to look back for swing point detection.
        equal_level_tolerance_pct: Price tolerance for "equal highs/lows".
        sweep_freshness_candles: Max candles ago for a sweep to be "recent".
        consolidation_candles: Min candles for consolidation detection.
        atr_period: Period for ATR calculation (volatility proxy).
        min_zone_touches: Minimum touches for a valid S/R zone.
    """

    def __init__(
        self,
        swing_lookback: int = 5,
        equal_level_tolerance_pct: float = 0.05,
        sweep_freshness_candles: int = 10,
        consolidation_candles: int = 8,
        atr_period: int = 14,
        min_zone_touches: int = 2,
    ) -> None:
        """Initialize ATLAS engine with configurable thresholds."""
        self._swing_lookback = swing_lookback
        self._equal_level_tolerance_pct = equal_level_tolerance_pct
        self._sweep_freshness_candles = sweep_freshness_candles
        self._consolidation_candles = consolidation_candles
        self._atr_period = atr_period
        self._min_zone_touches = min_zone_touches

        # Analysis history for regime tracking
        self._regime_history: Dict[str, List[str]] = {}
        self._max_regime_history = 50

        # Zone tracking across analyses
        self._tracked_zones: Dict[str, List[SupportResistanceZone]] = {}

        log.info(
            "atlas_initialized",
            swing_lookback=swing_lookback,
            equal_level_tolerance_pct=equal_level_tolerance_pct,
            sweep_freshness_candles=sweep_freshness_candles,
            consolidation_candles=consolidation_candles,
        )

    # ─── Public API ──────────────────────────────────────────────────────

    def analyze_market_data(
        self,
        symbol: str,
        candles: List[Dict],
        prism_flags: Optional[List[Any]] = None,
    ) -> AtlasAnalysis:
        """
        Perform full market analysis for a symbol.

        This is the main entry point. Takes validated candle data
        and optional PRISM flags, produces a comprehensive AtlasAnalysis.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT").
            candles: List of OHLCV candle dicts with keys:
                     open, high, low, close, volume, timestamp.
                     Should be pre-validated by PRISM.
            prism_flags: Optional list of PRISM validation results
                         that may affect analysis confidence.

        Returns:
            AtlasAnalysis with regime, structure, liquidity, conviction, etc.
        """
        if not candles or len(candles) < self._swing_lookback * 2:
            log.warning(
                "atlas_insufficient_data",
                symbol=symbol,
                candles_provided=len(candles) if candles else 0,
                minimum_required=self._swing_lookback * 2,
            )
            return AtlasAnalysis(
                symbol=symbol,
                regime=MarketRegime.UNDEFINED.value if hasattr(MarketRegime, 'UNDEFINED') else "undefined",
                structure=StructureType.UNDEFINED.value,
                liquidity_zones=[],
                timeframe_alignment=TimeframeAlignment.MIXED.value,
                conviction=0,
                conviction_reasoning="Insufficient candle data for analysis",
                support_resistance=[],
                confidence=0.0,
                data_quality_flags=self.respect_prism_flags(prism_flags or []),
            )

        # 1. Classify regime
        regime = self.classify_regime(candles)

        # 2. Detect market structure
        structure = self.detect_structure(candles)

        # 3. Detect liquidity sweeps
        sweep_events = self.detect_liquidity_sweeps(candles)
        liquidity_zones = self._build_liquidity_zones(candles, sweep_events)

        # 4. Identify support/resistance zones
        support_resistance = self.identify_zones(candles)

        # 5. Default timeframe alignment (single TF analysis is "mixed")
        timeframe_alignment = TimeframeAlignment.MIXED.value

        # 6. Process PRISM flags
        data_quality_flags = self.respect_prism_flags(prism_flags or [])

        # 7. Build initial analysis for conviction scoring
        analysis = AtlasAnalysis(
            symbol=symbol,
            regime=regime,
            structure=structure,
            liquidity_zones=[z.to_dict() for z in liquidity_zones],
            timeframe_alignment=timeframe_alignment,
            conviction=0,  # Placeholder — scored below
            conviction_reasoning="",
            support_resistance=[z.to_dict() for z in support_resistance],
            confidence=0.0,  # Placeholder — computed below
            data_quality_flags=data_quality_flags,
        )

        # 8. Score conviction with reasoning
        conviction, reasoning = self.score_conviction(analysis)
        analysis.conviction = conviction
        analysis.conviction_reasoning = reasoning

        # 9. Compute overall confidence
        analysis.confidence = self._compute_confidence(analysis)

        # Track regime history
        self._update_regime_history(symbol, regime)

        log.info(
            "atlas_analysis_complete",
            symbol=symbol,
            regime=regime,
            structure=structure,
            conviction=conviction,
            confidence=round(analysis.confidence, 3),
            liquidity_zones_found=len(liquidity_zones),
            sr_zones_found=len(support_resistance),
            data_quality_issues=len(data_quality_flags),
        )

        return analysis

    def classify_regime(self, candles: List[Dict]) -> str:
        """
        Classify the current market regime.

        Uses a combination of trend strength, volatility, and range
        detection to determine if the market is trending, ranging,
        in transition, or volatile.

        Args:
            candles: OHLCV candle data.

        Returns:
            One of: "trend", "range", "transition", "volatile"
        """
        if len(candles) < 20:
            return MarketRegime.TRANSITION.value

        # Compute trend strength via linear regression slope
        closes = [c.get("close", 0) for c in candles[-50:]]
        if len(closes) < 20 or any(c == 0 for c in closes):
            return MarketRegime.TRANSITION.value

        trend_strength = self._compute_trend_strength(closes)

        # Compute volatility via ATR ratio
        atr_values = self._compute_atr_series(candles, self._atr_period)
        if not atr_values:
            return MarketRegime.TRANSITION.value

        current_atr = atr_values[-1]
        avg_atr = sum(atr_values) / len(atr_values)
        volatility_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0

        # Compute range efficiency (how much price moved vs total range)
        range_efficiency = self._compute_range_efficiency(closes)

        # Decision logic
        if volatility_ratio > 2.0:
            regime = MarketRegime.VOLATILE
        elif trend_strength > 0.6 and range_efficiency > 0.5:
            regime = MarketRegime.TREND
        elif trend_strength < 0.3 and range_efficiency < 0.3:
            regime = MarketRegime.RANGE
        elif 0.3 <= trend_strength <= 0.6:
            regime = MarketRegime.TRANSITION
        else:
            # Default: if range_efficiency is low, likely ranging
            regime = MarketRegime.RANGE if range_efficiency < 0.4 else MarketRegime.TREND

        log.debug(
            "atlas_regime_classified",
            regime=regime.value,
            trend_strength=round(trend_strength, 3),
            volatility_ratio=round(volatility_ratio, 3),
            range_efficiency=round(range_efficiency, 3),
        )

        return regime.value

    def detect_structure(self, candles: List[Dict]) -> str:
        """
        Detect market structure — BOS, CHoCH, or consolidation.

        BOS (Break of Structure): Price breaks a swing point in the
        direction of the prevailing trend, confirming trend continuation.

        CHoCH (Change of Character): Price breaks a swing point AGAINST
        the prevailing trend, signaling potential reversal.

        Consolidation: Price is trading within a defined range without
        breaking significant swing points.

        Args:
            candles: OHLCV candle data.

        Returns:
            One of: "bos", "choch", "consolidation", "undefined"
        """
        if len(candles) < self._swing_lookback * 3:
            return StructureType.UNDEFINED.value

        # Detect swing highs and lows
        swing_highs = self._find_swing_highs(candles)
        swing_lows = self._find_swing_lows(candles)

        if not swing_highs or not swing_lows:
            return StructureType.UNDEFINED.value

        # Get recent structure
        last_high_idx, last_high_price = swing_highs[-1]
        last_low_idx, last_low_price = swing_lows[-1]

        # Need at least 2 swing points of each type for comparison
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return StructureType.UNDEFINED.value

        prev_high_idx, prev_high_price = swing_highs[-2]
        prev_low_idx, prev_low_price = swing_lows[-2]

        # Current price
        current_price = candles[-1].get("close", 0)
        if current_price == 0:
            return StructureType.UNDEFINED.value

        # Determine prevailing trend from swing point sequence
        higher_highs = last_high_price > prev_high_price
        higher_lows = last_low_price > prev_low_price
        lower_highs = last_high_price < prev_high_price
        lower_lows = last_low_price < prev_low_price

        # BOS: Price breaks swing in direction of trend
        if higher_highs and higher_lows and current_price > last_high_price:
            log.debug("atlas_structure_bos", direction="bullish")
            return StructureType.BOS.value

        if lower_highs and lower_lows and current_price < last_low_price:
            log.debug("atlas_structure_bos", direction="bearish")
            return StructureType.BOS.value

        # CHoCH: Price breaks swing AGAINST trend
        if higher_highs and higher_lows and current_price < last_low_price:
            log.debug("atlas_structure_choch", direction="bearish_reversal")
            return StructureType.CHOCH.value

        if lower_highs and lower_lows and current_price > last_high_price:
            log.debug("atlas_structure_choch", direction="bullish_reversal")
            return StructureType.CHOCH.value

        # Check for consolidation
        if self._is_consolidating(candles):
            return StructureType.CONSOLIDATION.value

        # If recent close broke a prior swing but not clearly BOS/CHoCH
        if current_price > prev_high_price or current_price < prev_low_price:
            return StructureType.BOS.value

        return StructureType.CONSOLIDATION.value

    def detect_liquidity_sweeps(self, candles: List[Dict]) -> List[LiquiditySweepEvent]:
        """
        Detect and interpret liquidity sweep events.

        A liquidity sweep occurs when price moves beyond a significant
        swing level (taking stop losses / liquidity resting there) and
        then reverses. This is critical for understanding institutional
        order flow behavior.

        Args:
            candles: OHLCV candle data.

        Returns:
            List of LiquiditySweepEvent objects for recent sweeps.
        """
        sweeps: List[LiquiditySweepEvent] = []

        if len(candles) < self._swing_lookback * 3:
            return sweeps

        swing_highs = self._find_swing_highs(candles)
        swing_lows = self._find_swing_lows(candles)

        # Check recent candles (within freshness window) for sweeps
        freshness_start = max(0, len(candles) - self._sweep_freshness_candles)

        for i in range(freshness_start, len(candles)):
            candle = candles[i]
            high = candle.get("high", 0)
            low = candle.get("low", 0)
            close = candle.get("close", 0)

            if high == 0 or low == 0:
                continue

            # Check for sweep of swing highs (bearish sweep — liquidity above taken)
            for sh_idx, sh_price in swing_highs:
                if sh_idx >= i:
                    continue  # Don't check swing points at or after current candle
                if high > sh_price:
                    # Price swept above the swing high
                    closed_beyond = close > sh_price
                    penetration = (high - sh_price) / sh_price if sh_price > 0 else 0
                    strength = min(1.0, penetration * 100)  # Normalize

                    sweeps.append(LiquiditySweepEvent(
                        level=sh_price,
                        direction="bearish_sweep",
                        strength=strength,
                        closed_beyond=closed_beyond,
                        candles_ago=len(candles) - 1 - i,
                    ))
                    break  # Only record the most significant sweep per candle

            # Check for sweep of swing lows (bullish sweep — liquidity below taken)
            for sl_idx, sl_price in swing_lows:
                if sl_idx >= i:
                    continue
                if low < sl_price:
                    closed_beyond = close < sl_price
                    penetration = (sl_price - low) / sl_price if sl_price > 0 else 0
                    strength = min(1.0, penetration * 100)

                    sweeps.append(LiquiditySweepEvent(
                        level=sl_price,
                        direction="bullish_sweep",
                        strength=strength,
                        closed_beyond=closed_beyond,
                        candles_ago=len(candles) - 1 - i,
                    ))
                    break

        # Deduplicate: keep strongest sweep per level
        sweeps = self._deduplicate_sweeps(sweeps)

        if sweeps:
            log.debug(
                "atlas_sweeps_detected",
                count=len(sweeps),
                directions=[s.direction for s in sweeps],
            )

        return sweeps

    def check_timeframe_alignment(
        self,
        m15_data: Optional[List[Dict]] = None,
        h1_data: Optional[List[Dict]] = None,
        d1_data: Optional[List[Dict]] = None,
    ) -> str:
        """
        Check multi-timeframe alignment (M15 → H1 → D1).

        Alignment means all timeframes tell the same story:
        - All trending in the same direction = ALIGNED
        - Some agree, some neutral = MIXED
        - Conflicting directions = CONFLICTING

        This is critical for trade quality — setups with aligned
        timeframes have significantly higher win rates.

        Args:
            m15_data: M15 candle data (optional).
            h1_data: H1 candle data (optional).
            d1_data: D1 candle data (optional).

        Returns:
            One of: "aligned", "mixed", "conflicting"
        """
        biases: List[str] = []

        for label, data in [("m15", m15_data), ("h1", h1_data), ("d1", d1_data)]:
            if data and len(data) >= 20:
                bias = self._compute_timeframe_bias(data)
                biases.append(bias)
                log.debug(
                    "atlas_tf_bias",
                    timeframe=label,
                    bias=bias,
                    candles=len(data),
                )

        if len(biases) < 2:
            # Insufficient data for alignment check
            return TimeframeAlignment.MIXED.value

        bullish_count = biases.count("bullish")
        bearish_count = biases.count("bearish")
        neutral_count = biases.count("neutral")

        # All agree (excluding neutral)
        if bullish_count == len(biases) or bearish_count == len(biases):
            return TimeframeAlignment.ALIGNED.value

        # Conflicting — some bullish, some bearish
        if bullish_count > 0 and bearish_count > 0:
            return TimeframeAlignment.CONFLICTING.value

        # Mixed — some aligned, some neutral
        if neutral_count > 0:
            return TimeframeAlignment.MIXED.value

        return TimeframeAlignment.MIXED.value

    def score_conviction(self, analysis: AtlasAnalysis) -> Tuple[int, str]:
        """
        Score market conviction with explanatory reasoning.

        Conviction is NOT a probability — it measures how CLEAR the
        market picture is. High conviction means the market is telling
        a coherent story across multiple dimensions.

        Scoring dimensions (each contributes to the final score):
          - Regime clarity (0-25): Trend > Range > Transition > Volatile
          - Structure quality (0-25): BOS > CHoCH > Consolidation > Undefined
          - Timeframe alignment (0-25): Aligned > Mixed > Conflicting
          - Data quality (0-25): Based on PRISM flags

        Args:
            analysis: The AtlasAnalysis to score.

        Returns:
            Tuple of (conviction_score: int, reasoning: str).
        """
        reasons: List[str] = []
        score = 0

        # ── Regime clarity (0-25) ──────────────────────────────────────
        regime_scores = {
            MarketRegime.TREND.value: 25,
            MarketRegime.RANGE.value: 18,
            MarketRegime.TRANSITION.value: 10,
            MarketRegime.VOLATILE.value: 5,
        }
        regime_score = regime_scores.get(analysis.regime, 5)
        score += regime_score
        if regime_score >= 20:
            reasons.append(f"Clear {analysis.regime} regime (+{regime_score})")
        elif regime_score >= 10:
            reasons.append(f"Moderate {analysis.regime} regime (+{regime_score})")
        else:
            reasons.append(f"Unclear {analysis.regime} regime (+{regime_score})")

        # ── Structure quality (0-25) ───────────────────────────────────
        structure_scores = {
            StructureType.BOS.value: 25,
            StructureType.CHOCH.value: 20,
            StructureType.CONSOLIDATION.value: 10,
            StructureType.UNDEFINED.value: 3,
        }
        struct_score = structure_scores.get(analysis.structure, 3)
        score += struct_score
        if struct_score >= 20:
            reasons.append(f"Strong {analysis.structure} structure (+{struct_score})")
        elif struct_score >= 10:
            reasons.append(f"{analysis.structure} structure (+{struct_score})")
        else:
            reasons.append(f"Weak structure ({analysis.structure}) (+{struct_score})")

        # ── Timeframe alignment (0-25) ────────────────────────────────
        alignment_scores = {
            TimeframeAlignment.ALIGNED.value: 25,
            TimeframeAlignment.MIXED.value: 12,
            TimeframeAlignment.CONFLICTING.value: 3,
        }
        align_score = alignment_scores.get(analysis.timeframe_alignment, 12)
        score += align_score
        if align_score >= 20:
            reasons.append(f"Multi-TF aligned (+{align_score})")
        elif align_score >= 10:
            reasons.append(f"Multi-TF mixed (+{align_score})")
        else:
            reasons.append(f"Multi-TF conflicting (+{align_score})")

        # ── Data quality (0-25) ────────────────────────────────────────
        quality_penalty = len(analysis.data_quality_flags) * 5
        quality_score = max(0, 25 - quality_penalty)
        score += quality_score
        if quality_score >= 20:
            reasons.append(f"Clean data (+{quality_score})")
        elif quality_score > 0:
            reasons.append(
                f"Data quality reduced by {len(analysis.data_quality_flags)} PRISM flags (+{quality_score})"
            )
        else:
            reasons.append("Data quality too poor for reliable analysis (+0)")

        # ── Liquidity bonus/penalty ────────────────────────────────────
        if analysis.liquidity_zones:
            strong_zones = [z for z in analysis.liquidity_zones if z.get("strength", 0) > 0.5]
            if strong_zones:
                score = min(100, score + 5)
                reasons.append(f"Liquidity zones with strong interest (+5)")

        # Clamp to 0-100
        score = max(0, min(100, score))

        reasoning = "; ".join(reasons)

        log.debug(
            "atlas_conviction_scored",
            score=score,
            regime_score=regime_score,
            structure_score=struct_score,
            alignment_score=align_score,
            quality_score=quality_score,
        )

        return score, reasoning

    def identify_zones(self, candles: List[Dict]) -> List[SupportResistanceZone]:
        """
        Identify support and resistance zones.

        Zones are identified from:
          1. Swing points that have been tested multiple times
          2. Round number levels (psychological levels)
          3. Previous structure break levels

        Zones are scored by:
          - Number of touches (more = stronger)
          - Recency weighting (recent touches matter more)
          - Volume at the level (higher = stronger)

        Args:
            candles: OHLCV candle data.

        Returns:
            List of SupportResistanceZone objects.
        """
        zones: List[SupportResistanceZone] = []

        if len(candles) < self._swing_lookback * 2:
            return zones

        current_price = candles[-1].get("close", 0)
        if current_price == 0:
            return zones

        # Collect all swing points
        swing_highs = self._find_swing_highs(candles)
        swing_lows = self._find_swing_lows(candles)

        # Cluster nearby swing highs → resistance zones
        resistance_levels = self._cluster_levels(
            [(idx, price) for idx, price in swing_highs],
            current_price,
        )
        for level, touches, strength in resistance_levels:
            if touches >= self._min_zone_touches:
                zones.append(SupportResistanceZone(
                    price=level,
                    type=ZoneType.RESISTANCE.value,
                    strength=strength,
                    timeframe="current",
                    touches=touches,
                ))

        # Cluster nearby swing lows → support zones
        support_levels = self._cluster_levels(
            [(idx, price) for idx, price in swing_lows],
            current_price,
        )
        for level, touches, strength in support_levels:
            if touches >= self._min_zone_touches:
                zones.append(SupportResistanceZone(
                    price=level,
                    type=ZoneType.SUPPORT.value,
                    strength=strength,
                    timeframe="current",
                    touches=touches,
                ))

        # Sort by distance from current price (nearest first)
        zones.sort(key=lambda z: abs(z.price - current_price))

        # Keep only top zones (prevent noise)
        zones = zones[:10]

        log.debug(
            "atlas_zones_identified",
            total=len(zones),
            support=len([z for z in zones if z.type == ZoneType.SUPPORT.value]),
            resistance=len([z for z in zones if z.type == ZoneType.RESISTANCE.value]),
        )

        return zones

    def respect_prism_flags(self, prism_flags: List[Any]) -> List[str]:
        """
        Process PRISM data quality flags and note their impact on analysis.

        ATLAS respects PRISM unconditionally — if PRISM says data is
        unreliable, ATLAS adjusts its confidence accordingly.

        Args:
            prism_flags: List of PRISM validation results or flag strings.

        Returns:
            List of flag strings that affect this analysis.
        """
        flags: List[str] = []

        for flag in prism_flags:
            # Handle PrismResult objects (from PRISM layer)
            if hasattr(flag, "check") and hasattr(flag, "status"):
                if flag.status in ("warn", "fail"):
                    flag_str = f"{flag.check.value}:{flag.status}"
                    flags.append(flag_str)
                    log.info(
                        "atlas_respecting_prism_flag",
                        check=flag.check.value if hasattr(flag.check, 'value') else str(flag.check),
                        status=flag.status,
                        detail=getattr(flag, "detail", ""),
                    )
            # Handle string flags
            elif isinstance(flag, str):
                flags.append(flag)
            # Handle dict flags
            elif isinstance(flag, dict):
                check = flag.get("check", "unknown")
                status = flag.get("status", "warn")
                if status in ("warn", "fail"):
                    flags.append(f"{check}:{status}")

        return flags

    # ─── Status ──────────────────────────────────────────────────────────

    @property
    def status(self) -> Dict[str, Any]:
        """Return ATLAS engine status."""
        return {
            "layer": "atlas",
            "role": "market_reasoning",
            "agent": False,
            "analysis_type": "structure_and_liquidity",
            "tracked_symbols": list(self._regime_history.keys()),
            "configuration": {
                "swing_lookback": self._swing_lookback,
                "equal_level_tolerance_pct": self._equal_level_tolerance_pct,
                "sweep_freshness_candles": self._sweep_freshness_candles,
                "consolidation_candles": self._consolidation_candles,
                "atr_period": self._atr_period,
                "min_zone_touches": self._min_zone_touches,
            },
        }

    # ─── Internal: Swing Detection ───────────────────────────────────────

    def _find_swing_highs(self, candles: List[Dict]) -> List[Tuple[int, float]]:
        """
        Find swing high points in candle data.

        A swing high is a candle whose high is higher than the highs
        of the N candles before and after it.

        Returns:
            List of (candle_index, high_price) tuples.
        """
        return self._find_swing_points(candles, "high")

    def _find_swing_lows(self, candles: List[Dict]) -> List[Tuple[int, float]]:
        """
        Find swing low points in candle data.

        A swing low is a candle whose low is lower than the lows
        of the N candles before and after it.

        Returns:
            List of (candle_index, low_price) tuples.
        """
        return self._find_swing_points(candles, "low")

    def _find_swing_points(
        self, candles: List[Dict], price_key: str
    ) -> List[Tuple[int, float]]:
        """
        Generic swing point detection.

        For "high": finds swing highs (local maxima).
        For "low": finds swing lows (local minima).

        Args:
            candles: OHLCV candle data.
            price_key: "high" or "low".

        Returns:
            List of (index, price) tuples for swing points.
        """
        swings: List[Tuple[int, float]] = []
        n = self._swing_lookback

        if len(candles) < n * 2 + 1:
            return swings

        for i in range(n, len(candles) - n):
            current_val = candles[i].get(price_key, 0)
            if current_val == 0:
                continue

            is_swing = True
            for j in range(1, n + 1):
                neighbor_before = candles[i - j].get(price_key, 0)
                neighbor_after = candles[i + j].get(price_key, 0)

                if price_key == "high":
                    if neighbor_before >= current_val or neighbor_after >= current_val:
                        is_swing = False
                        break
                else:  # "low"
                    if neighbor_before <= current_val or neighbor_after <= current_val:
                        is_swing = False
                        break

            if is_swing:
                swings.append((i, current_val))

        return swings

    # ─── Internal: Liquidity Zone Building ───────────────────────────────

    def _build_liquidity_zones(
        self,
        candles: List[Dict],
        sweep_events: List[LiquiditySweepEvent],
    ) -> List[LiquidityZone]:
        """
        Build liquidity zones from swing points and equal levels.

        Detects:
          - Equal highs: Multiple swing highs at approximately the same level
          - Equal lows: Multiple swing lows at approximately the same level
          - Unswept swing levels: Active liquidity pools
        """
        zones: List[LiquidityZone] = []

        if not candles:
            return zones

        current_price = candles[-1].get("close", 0)
        if current_price == 0:
            return zones

        swing_highs = self._find_swing_highs(candles)
        swing_lows = self._find_swing_lows(candles)

        # Detect equal highs (pool of buy-side liquidity)
        equal_high_clusters = self._find_equal_levels(swing_highs)
        for cluster_price, count in equal_high_clusters:
            strength = min(1.0, count / 4.0)  # More touches = stronger
            distance_pct = abs(cluster_price - current_price) / current_price * 100 if current_price > 0 else 0
            zones.append(LiquidityZone(
                level=cluster_price,
                type=LiquidityType.EQUAL_HIGHS.value,
                strength=strength,
                distance_pct=distance_pct,
            ))

        # Detect equal lows (pool of sell-side liquidity)
        equal_low_clusters = self._find_equal_levels(swing_lows)
        for cluster_price, count in equal_low_clusters:
            strength = min(1.0, count / 4.0)
            distance_pct = abs(cluster_price - current_price) / current_price * 100 if current_price > 0 else 0
            zones.append(LiquidityZone(
                level=cluster_price,
                type=LiquidityType.EQUAL_LOWS.value,
                strength=strength,
                distance_pct=distance_pct,
            ))

        # Add unswept swing levels
        swept_levels = {s.level for s in sweep_events}
        for idx, price in swing_highs + swing_lows:
            if price not in swept_levels:
                distance_pct = abs(price - current_price) / current_price * 100 if current_price > 0 else 0
                zones.append(LiquidityZone(
                    level=price,
                    type=LiquidityType.SWING.value,
                    strength=0.3,  # Base strength for unswept levels
                    distance_pct=distance_pct,
                ))

        # Sort by distance (nearest first)
        zones.sort(key=lambda z: z.distance_pct)

        return zones[:15]  # Limit to prevent noise

    def _find_equal_levels(
        self, swing_points: List[Tuple[int, float]]
    ) -> List[Tuple[float, int]]:
        """
        Find clusters of approximately equal price levels.

        Returns list of (cluster_price, count) tuples.
        """
        if not swing_points:
            return []

        clusters: List[Tuple[float, int]] = []
        used: set = set()

        prices = [p for _, p in swing_points]

        for i, (idx_i, price_i) in enumerate(swing_points):
            if i in used:
                continue

            cluster_prices = [price_i]
            used.add(i)

            for j, (idx_j, price_j) in enumerate(swing_points):
                if j in used or j == i:
                    continue

                if price_i > 0 and abs(price_j - price_i) / price_i * 100 < self._equal_level_tolerance_pct:
                    cluster_prices.append(price_j)
                    used.add(j)

            if len(cluster_prices) >= 2:
                avg_price = sum(cluster_prices) / len(cluster_prices)
                clusters.append((avg_price, len(cluster_prices)))

        return clusters

    # ─── Internal: Level Clustering ──────────────────────────────────────

    def _cluster_levels(
        self,
        swing_points: List[Tuple[int, float]],
        current_price: float,
    ) -> List[Tuple[float, int, float]]:
        """
        Cluster nearby swing points into zones.

        Returns list of (level_price, touch_count, strength) tuples.
        """
        if not swing_points:
            return []

        clusters: List[Tuple[float, int, float]] = []
        used: set = set()
        prices = [p for _, p in swing_points]
        tolerance = self._equal_level_tolerance_pct / 100.0

        for i, (idx_i, price_i) in enumerate(swing_points):
            if i in used:
                continue

            cluster_prices = [price_i]
            cluster_indices = [idx_i]
            used.add(i)

            for j, (idx_j, price_j) in enumerate(swing_points):
                if j in used or j == i:
                    continue

                if price_i > 0 and abs(price_j - price_i) / price_i < tolerance:
                    cluster_prices.append(price_j)
                    cluster_indices.append(idx_j)
                    used.add(j)

            avg_price = sum(cluster_prices) / len(cluster_prices)
            touches = len(cluster_prices)

            # Strength: based on touches and recency
            max_idx = max(cluster_indices)
            recency_weight = max_idx / len(swing_points) if swing_points else 0.5
            strength = min(1.0, (touches / 3.0) * 0.7 + recency_weight * 0.3)

            clusters.append((avg_price, touches, strength))

        return clusters

    # ─── Internal: Technical Computations ────────────────────────────────

    def _compute_trend_strength(self, closes: List[float]) -> float:
        """
        Compute trend strength via linear regression R-squared.

        Returns:
            R-squared value 0.0-1.0 (higher = stronger trend).
        """
        n = len(closes)
        if n < 5:
            return 0.0

        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(closes) / n

        ss_xx = sum((xi - x_mean) ** 2 for xi in x)
        ss_xy = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, closes))
        ss_yy = sum((yi - y_mean) ** 2 for yi in closes)

        if ss_xx == 0 or ss_yy == 0:
            return 0.0

        r_squared = (ss_xy ** 2) / (ss_xx * ss_yy)

        # Determine direction and use directional R-squared
        slope = ss_xy / ss_xx if ss_xx != 0 else 0
        if slope < 0:
            # For bearish trends, we still want positive strength
            pass

        return min(1.0, r_squared)

    def _compute_range_efficiency(self, closes: List[float]) -> float:
        """
        Compute range efficiency: how far price moved vs total range.

        High efficiency = price moved decisively (trending).
        Low efficiency = price oscillated (ranging).

        Returns:
            Efficiency value 0.0-1.0.
        """
        if len(closes) < 2:
            return 0.0

        total_move = abs(closes[-1] - closes[0])
        max_price = max(closes)
        min_price = min(closes)
        total_range = max_price - min_price

        if total_range == 0:
            return 0.0

        return total_move / total_range

    def _compute_atr_series(
        self, candles: List[Dict], period: int
    ) -> List[float]:
        """
        Compute ATR (Average True Range) series.

        Returns:
            List of ATR values.
        """
        if len(candles) < period + 1:
            return []

        true_ranges: List[float] = []
        for i in range(1, len(candles)):
            high = candles[i].get("high", 0)
            low = candles[i].get("low", 0)
            prev_close = candles[i - 1].get("close", 0)

            if high == 0 or low == 0:
                continue

            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return [sum(true_ranges) / len(true_ranges)] if true_ranges else []

        # Simple moving average of true ranges
        atr_values: List[float] = []
        for i in range(period - 1, len(true_ranges)):
            window = true_ranges[i - period + 1: i + 1]
            atr_values.append(sum(window) / period)

        return atr_values

    def _compute_timeframe_bias(self, candles: List[Dict]) -> str:
        """
        Compute directional bias for a single timeframe.

        Uses EMA position and recent price action to determine
        if the timeframe is bullish, bearish, or neutral.

        Returns:
            "bullish", "bearish", or "neutral"
        """
        if len(candles) < 20:
            return "neutral"

        closes = [c.get("close", 0) for c in candles]
        if any(c == 0 for c in closes):
            return "neutral"

        # Simple EMA estimate
        ema_period = min(20, len(closes))
        multiplier = 2 / (ema_period + 1)
        ema = closes[0]
        for close in closes[1:ema_period]:
            ema = (close - ema) * multiplier + ema

        current_price = closes[-1]

        # Compute recent momentum
        recent_closes = closes[-5:]
        momentum = 0
        for i in range(1, len(recent_closes)):
            momentum += 1 if recent_closes[i] > recent_closes[i - 1] else -1

        if current_price > ema and momentum > 0:
            return "bullish"
        elif current_price < ema and momentum < 0:
            return "bearish"
        else:
            return "neutral"

    def _is_consolidating(self, candles: List[Dict]) -> bool:
        """
        Check if price is in a consolidation pattern.

        Consolidation is identified when:
          - Price range is narrow relative to ATR
          - No swing points have been broken recently
          - Candles overlap significantly
        """
        if len(candles) < self._consolidation_candles:
            return False

        recent = candles[-self._consolidation_candles:]
        highs = [c.get("high", 0) for c in recent]
        lows = [c.get("low", 0) for c in recent]

        if any(h == 0 for h in highs) or any(l == 0 for l in lows):
            return False

        range_size = max(highs) - min(lows)
        atr_values = self._compute_atr_series(candles, self._atr_period)
        avg_atr = atr_values[-1] if atr_values else 0

        if avg_atr == 0:
            return False

        # Consolidation: range is less than 2x ATR
        return range_size < avg_atr * 2

    def _compute_confidence(self, analysis: AtlasAnalysis) -> float:
        """
        Compute overall confidence in this analysis.

        Confidence differs from conviction:
          - Conviction: How clear the market picture is
          - Confidence: How reliable our analysis is

        Confidence is reduced by:
          - PRISM data quality flags
          - Insufficient data
          - Conflicting signals
        """
        base_confidence = 0.7

        # Reduce for each PRISM flag
        flag_penalty = len(analysis.data_quality_flags) * 0.1

        # Reduce for conflicting alignment
        if analysis.timeframe_alignment == TimeframeAlignment.CONFLICTING.value:
            flag_penalty += 0.15
        elif analysis.timeframe_alignment == TimeframeAlignment.MIXED.value:
            flag_penalty += 0.05

        # Reduce for undefined structure
        if analysis.structure == StructureType.UNDEFINED.value:
            flag_penalty += 0.2

        # Reduce for volatile regime (harder to analyze)
        if analysis.regime == MarketRegime.VOLATILE.value:
            flag_penalty += 0.1

        confidence = max(0.1, base_confidence - flag_penalty)

        return min(1.0, confidence)

    # ─── Internal: Utilities ─────────────────────────────────────────────

    def _update_regime_history(self, symbol: str, regime: str) -> None:
        """Track regime history for a symbol."""
        if symbol not in self._regime_history:
            self._regime_history[symbol] = []

        self._regime_history[symbol].append(regime)

        if len(self._regime_history[symbol]) > self._max_regime_history:
            self._regime_history[symbol] = self._regime_history[symbol][-self._max_regime_history:]

    def _deduplicate_sweeps(
        self, sweeps: List[LiquiditySweepEvent]
    ) -> List[LiquiditySweepEvent]:
        """
        Deduplicate sweep events, keeping the strongest per level.

        Two sweeps are considered duplicates if they have the same
        direction and their levels are within tolerance.
        """
        if not sweeps:
            return []

        deduped: List[LiquiditySweepEvent] = []

        for sweep in sweeps:
            is_duplicate = False
            for i, existing in enumerate(deduped):
                if existing.direction != sweep.direction:
                    continue
                level_diff = abs(existing.level - sweep.level)
                if existing.level > 0 and level_diff / existing.level * 100 < self._equal_level_tolerance_pct:
                    # Same level — keep the stronger sweep
                    if sweep.strength > existing.strength:
                        deduped[i] = sweep
                    is_duplicate = True
                    break

            if not is_duplicate:
                deduped.append(sweep)

        return deduped
