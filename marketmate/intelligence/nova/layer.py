"""
marketmate.intelligence.nova.layer
───────────────────────────────────
NOVA: Real-time Market Companion — Delivery Layer

Fast. Accessible. Everyday intelligence.
The public-facing brain of MarketMate.

NOVA is the FRONT DOOR of the intelligence pipeline.
It translates complex analysis from upstream layers into simple,
accessible language that anyone can understand.

CRITICAL RULES:
  1. NOVA NEVER fabricates data. If PRISM flagged issues, NOVA reports them.
  2. NOVA does NOT perform deep analysis — that is ATLAS's job.
  3. NOVA speaks plain language. No jargon without explanation.
  4. NOVA respects data quality flags. Degraded data → cautious delivery.

Responsibilities:
  - Live market summaries (multi-asset snapshot)
  - Simple explanations of price movement
  - News + sentiment summarization
  - Quick signal interpretation (NOT deep analysis)
  - Academy assistant (beginner-friendly teaching)
  - "What is happening right now?" queries
  - Basic regime label (trend / range / volatile)

Position in pipeline:
  RAW DATA → PRISM → VINNI → ATLAS → VANTA → [NOVA] → Users

Created: 2026-05-29
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from marketmate.core.logger import get_logger

log = get_logger("intelligence.nova")


# ─── Constants ────────────────────────────────────────────────────────────────

REGIME_LABELS = {"trend", "range", "volatile", "unknown"}
QUALITY_LABELS = {"verified", "degraded", "unreliable"}

# Thresholds for escalation to ATLAS (deeper analysis)
ESCALATION_CHANGE_PCT = 3.0       # |change| > 3% → escalate
ESCALATION_VOLATILE_REGIME = True  # volatile regime → escalate
ESCALATION_DATA_DEGRADED = True    # degraded/unreliable data → escalate

# Emoji mapping for Telegram formatting
REGIME_EMOJI = {
    "trend": "📈",
    "range": "↔️",
    "volatile": "⚡",
    "unknown": "❓",
}

QUALITY_EMOJI = {
    "verified": "✅",
    "degraded": "⚠️",
    "unreliable": "🚫",
}

MOVEMENT_DIRECTION = {
    "up": "rising",
    "down": "falling",
    "flat": "sideways",
}


# ─── Nova Summary ─────────────────────────────────────────────────────────────

@dataclass
class NovaSummary:
    """
    A structured market summary produced by NOVA.

    This is the primary output of the NOVA layer — a clean, accessible
    snapshot that can be delivered via Telegram, API, or web dashboard.

    NOVA NEVER fabricates fields. If upstream data is missing, the field
    reflects that honestly (e.g., regime="unknown", data_quality="degraded").

    Attributes:
        symbol: Trading symbol (e.g., "BTCUSDT", "EURUSD").
        regime: Current market regime — "trend", "range", "volatile", "unknown".
        movement: Plain language description of current price movement.
        key_levels: Important price levels — support, resistance, current.
        change_pct: 24-hour change percentage.
        context: Brief situational context (e.g., "Trading near session high").
        data_quality: PRISM-verified quality label — "verified", "degraded", "unreliable".
        timestamp: ISO 8601 timestamp when this summary was generated.
        atlas_available: Whether deeper ATLAS analysis is available for this symbol.
    """

    symbol: str
    regime: str  # "trend" | "range" | "volatile" | "unknown"
    movement: str
    key_levels: Dict[str, float]  # {"support": ..., "resistance": ..., "current": ...}
    change_pct: float
    context: str
    data_quality: str  # "verified" | "degraded" | "unreliable"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    atlas_available: bool = False

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if self.regime not in REGIME_LABELS:
            log.warning(
                "nova_invalid_regime",
                symbol=self.symbol,
                regime=self.regime,
                fallback="unknown",
            )
            self.regime = "unknown"

        if self.data_quality not in QUALITY_LABELS:
            log.warning(
                "nova_invalid_quality",
                symbol=self.symbol,
                data_quality=self.data_quality,
                fallback="unreliable",
            )
            self.data_quality = "unreliable"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to structured dictionary for downstream consumption."""
        return {
            "symbol": self.symbol,
            "regime": self.regime,
            "movement": self.movement,
            "key_levels": self.key_levels,
            "change_pct": round(self.change_pct, 4),
            "context": self.context,
            "data_quality": self.data_quality,
            "timestamp": self.timestamp,
            "atlas_available": self.atlas_available,
        }


# ─── Nova Layer ───────────────────────────────────────────────────────────────

class NovaLayer:
    """
    NOVA: Real-time Market Companion — The Front Door.

    NOVA is the final delivery layer in the intelligence pipeline.
    It takes validated market data (from PRISM), observation context
    (from VINNI), deep analysis (from ATLAS), and agent decisions
    (from VANTA) — and translates everything into simple, accessible
    language for users.

    Key Principle: NOVA translates complexity into clarity.
    It NEVER fabricates data. If PRISM flagged data issues, NOVA
    reports "Data quality: degraded" and tells users to be cautious.

    Usage:
        nova = NovaLayer()
        summary = nova.generate_summary(
            symbol="BTCUSDT",
            market_data={"price": 67500, "change_24h": 2.3, ...},
            atlas_analysis={"regime": "trend", "bias": "bullish", ...},
            prism_flags=[PrismResult(...)],
        )
        telegram_msg = nova.format_for_telegram(summary)

    Configuration:
        escalation_change_pct: Absolute % change that triggers ATLAS escalation.
        respect_prism_flags: Whether to check PRISM flags for data quality.
    """

    def __init__(
        self,
        escalation_change_pct: float = ESCALATION_CHANGE_PCT,
        respect_prism_flags: bool = True,
    ) -> None:
        """Initialize NOVA delivery layer."""
        self._escalation_change_pct = escalation_change_pct
        self._respect_prism_flags = respect_prism_flags

        # Summary history for tracking and de-duplication
        self._recent_summaries: Dict[str, NovaSummary] = {}
        self._summary_count: int = 0

        log.info(
            "nova_initialized",
            escalation_change_pct=escalation_change_pct,
            respect_prism_flags=respect_prism_flags,
        )

    # ── Core: Generate Summary ────────────────────────────────────────────

    def generate_summary(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        atlas_analysis: Optional[Dict[str, Any]] = None,
        prism_flags: Optional[List[Any]] = None,
    ) -> NovaSummary:
        """
        Generate a NOVA summary for a single symbol.

        This is the primary entry point. It takes raw market data,
        optional ATLAS analysis, and PRISM flags — then produces
        a clean, accessible summary.

        NOVA NEVER fabricates data:
          - If ATLAS analysis is unavailable, regime defaults to "unknown".
          - If PRISM flags indicate issues, data_quality reflects that.
          - If key price levels are missing, they default to 0.0.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT").
            market_data: Dict with price data. Expected keys:
                price (float), change_24h (float), high_24h (float),
                low_24h (float), volume_24h (float, optional).
            atlas_analysis: Optional ATLAS output with keys:
                regime (str), bias (str), key_levels (dict), context (str).
            prism_flags: Optional list of PrismResult objects from PRISM validation.

        Returns:
            A NovaSummary with accessible, plain-language market snapshot.
        """
        if prism_flags is None:
            prism_flags = []

        # ── Determine data quality from PRISM flags ───────────────────────
        data_quality = self._assess_data_quality(prism_flags)

        # ── Extract price data ────────────────────────────────────────────
        current_price = float(market_data.get("price", 0))
        change_pct = float(market_data.get("change_24h", 0))
        high_24h = float(market_data.get("high_24h", 0))
        low_24h = float(market_data.get("low_24h", 0))

        # ── Determine regime ──────────────────────────────────────────────
        regime = self._determine_regime(market_data, atlas_analysis)

        # ── Build key levels ──────────────────────────────────────────────
        key_levels = self._build_key_levels(
            market_data=market_data,
            atlas_analysis=atlas_analysis,
            current_price=current_price,
            high_24h=high_24h,
            low_24h=low_24h,
        )

        # ── Generate plain-language movement description ──────────────────
        movement = self._describe_movement(
            change_pct=change_pct,
            regime=regime,
            current_price=current_price,
            high_24h=high_24h,
            low_24h=low_24h,
        )

        # ── Build context string ──────────────────────────────────────────
        context = self._build_context(
            symbol=symbol,
            market_data=market_data,
            atlas_analysis=atlas_analysis,
            data_quality=data_quality,
        )

        # ── Check ATLAS availability ──────────────────────────────────────
        atlas_available = atlas_analysis is not None and len(atlas_analysis) > 0

        summary = NovaSummary(
            symbol=symbol.upper(),
            regime=regime,
            movement=movement,
            key_levels=key_levels,
            change_pct=change_pct,
            context=context,
            data_quality=data_quality,
            atlas_available=atlas_available,
        )

        # Cache and track
        self._recent_summaries[symbol.upper()] = summary
        self._summary_count += 1

        log.info(
            "nova_summary_generated",
            symbol=symbol.upper(),
            regime=regime,
            data_quality=data_quality,
            change_pct=round(change_pct, 4),
            atlas_available=atlas_available,
        )

        return summary

    # ── Multi-Asset Snapshot ──────────────────────────────────────────────

    def generate_multi_asset_snapshot(
        self,
        symbols: List[str],
        data: Dict[str, Dict[str, Any]],
    ) -> List[NovaSummary]:
        """
        Generate NOVA summaries for multiple symbols at once.

        Useful for "What is happening right now?" queries and
        multi-asset dashboard views.

        Args:
            symbols: List of trading symbols to summarize.
            data: Dict mapping each symbol to its market_data dict.
                  May also include "atlas" and "prism_flags" sub-keys.

        Returns:
            List of NovaSummary objects, one per symbol.
        """
        summaries: List[NovaSummary] = []

        for symbol in symbols:
            symbol_data = data.get(symbol, {})
            market_data = symbol_data.get("market_data", symbol_data)
            atlas_analysis = symbol_data.get("atlas", None)
            prism_flags = symbol_data.get("prism_flags", [])

            summary = self.generate_summary(
                symbol=symbol,
                market_data=market_data,
                atlas_analysis=atlas_analysis,
                prism_flags=prism_flags,
            )
            summaries.append(summary)

        log.info(
            "nova_multi_asset_snapshot",
            symbol_count=len(summaries),
            symbols=[s.symbol for s in summaries],
        )

        return summaries

    # ── Formatting: Telegram ──────────────────────────────────────────────

    def format_for_telegram(self, summary: NovaSummary) -> str:
        """
        Format a NovaSummary for Telegram delivery.

        Uses emoji, clear structure, and plain language.
        Respects Telegram message length and formatting constraints.

        Args:
            summary: The NovaSummary to format.

        Returns:
            A formatted string ready for Telegram delivery.
        """
        regime_emoji = REGIME_EMOJI.get(summary.regime, "❓")
        quality_emoji = QUALITY_EMOJI.get(summary.data_quality, "🚫")

        # Direction arrow
        if summary.change_pct > 0:
            direction = "🟢"
        elif summary.change_pct < 0:
            direction = "🔴"
        else:
            direction = "⚪"

        # Key levels string
        levels_parts: List[str] = []
        current = summary.key_levels.get("current", 0)
        support = summary.key_levels.get("support", 0)
        resistance = summary.key_levels.get("resistance", 0)

        if current > 0:
            levels_parts.append(f"Now: {current:,.2f}")
        if support > 0:
            levels_parts.append(f"Support: {support:,.2f}")
        if resistance > 0:
            levels_parts.append(f"Resistance: {resistance:,.2f}")

        levels_str = " | ".join(levels_parts) if levels_parts else "Levels unavailable"

        # Quality warning
        quality_line = ""
        if summary.data_quality == "degraded":
            quality_line = "\n⚠️ Data quality is degraded — treat with caution."
        elif summary.data_quality == "unreliable":
            quality_line = "\n🚫 Data quality is unreliable — do NOT trade on this alone."

        # ATLAS escalation hint
        atlas_line = ""
        if not summary.atlas_available:
            atlas_line = "\n💡 Deeper analysis may be available — ask for details."

        message = (
            f"{regime_emoji} <b>{summary.symbol}</b>\n"
            f"{direction} {summary.change_pct:+.2f}% (24h)\n"
            f"📊 {summary.movement}\n"
            f"📍 {levels_str}\n"
            f"💬 {summary.context}\n"
            f"{quality_emoji} Data: {summary.data_quality}"
            f"{quality_line}{atlas_line}"
        )

        return message

    # ── Formatting: API ───────────────────────────────────────────────────

    def format_for_api(self, summary: NovaSummary) -> Dict[str, Any]:
        """
        Format a NovaSummary as an API response dict.

        Clean, structured, machine-readable. Suitable for REST endpoints
        and programmatic consumption.

        Args:
            summary: The NovaSummary to format.

        Returns:
            A dict suitable for JSON serialization in API responses.
        """
        return {
            "symbol": summary.symbol,
            "regime": summary.regime,
            "movement": summary.movement,
            "change_pct": round(summary.change_pct, 4),
            "key_levels": {
                k: round(v, 4) for k, v in summary.key_levels.items()
            },
            "context": summary.context,
            "data_quality": summary.data_quality,
            "timestamp": summary.timestamp,
            "atlas_available": summary.atlas_available,
            "should_escalate": self.should_escalate_to_atlas(summary),
        }

    # ── Formatting: Web Dashboard ─────────────────────────────────────────

    def format_for_web(self, summary: NovaSummary) -> Dict[str, Any]:
        """
        Format a NovaSummary for web dashboard rendering.

        Includes display-ready fields like emoji, color hints,
        and formatted values for frontend consumption.

        Args:
            summary: The NovaSummary to format.

        Returns:
            A dict with both raw and display-ready fields.
        """
        # Determine display color
        if summary.change_pct > 0:
            color = "green"
        elif summary.change_pct < 0:
            color = "red"
        else:
            color = "gray"

        return {
            # Raw data
            "symbol": summary.symbol,
            "regime": summary.regime,
            "movement": summary.movement,
            "change_pct": round(summary.change_pct, 4),
            "key_levels": {
                k: round(v, 4) for k, v in summary.key_levels.items()
            },
            "context": summary.context,
            "data_quality": summary.data_quality,
            "timestamp": summary.timestamp,
            "atlas_available": summary.atlas_available,
            # Display helpers
            "display": {
                "regime_emoji": REGIME_EMOJI.get(summary.regime, "❓"),
                "quality_emoji": QUALITY_EMOJI.get(summary.data_quality, "🚫"),
                "change_color": color,
                "change_direction": "up" if summary.change_pct > 0 else "down" if summary.change_pct < 0 else "flat",
                "regime_label": summary.regime.capitalize(),
                "quality_label": summary.data_quality.capitalize(),
                "formatted_change": f"{summary.change_pct:+.2f}%",
            },
        }

    # ── Escalation Decision ───────────────────────────────────────────────

    def should_escalate_to_atlas(self, summary: NovaSummary) -> bool:
        """
        Determine whether a summary warrants escalation to ATLAS for deeper analysis.

        Escalation triggers:
          - Large price movement (|change_pct| > threshold)
          - Volatile regime detected
          - Data quality is degraded or unreliable
          - User might benefit from deeper understanding

        NOVA does NOT perform deep analysis itself. If conditions warrant
        it, this method returns True so that upstream ATLAS analysis can
        be requested and delivered.

        Args:
            summary: The NovaSummary to evaluate.

        Returns:
            True if ATLAS analysis should be requested for this symbol.
        """
        reasons: List[str] = []

        # Large move
        if abs(summary.change_pct) >= self._escalation_change_pct:
            reasons.append(
                f"large_move={summary.change_pct:+.2f}%"
            )

        # Volatile regime
        if ESCALATION_VOLATILE_REGIME and summary.regime == "volatile":
            reasons.append("volatile_regime")

        # Data quality issues
        if ESCALATION_DATA_DEGRADED and summary.data_quality in ("degraded", "unreliable"):
            reasons.append(f"data_quality={summary.data_quality}")

        should_escalate = len(reasons) > 0

        if should_escalate:
            log.info(
                "nova_escalation_recommended",
                symbol=summary.symbol,
                reasons=reasons,
            )

        return should_escalate

    # ── Status ────────────────────────────────────────────────────────────

    @property
    def status(self) -> Dict[str, Any]:
        """
        Return NOVA layer status for health checks and monitoring.

        Includes summary statistics, configuration, and tracked symbols.
        """
        return {
            "layer": "nova",
            "role": "user_delivery",
            "agent": False,
            "summaries_generated": self._summary_count,
            "symbols_tracked": list(self._recent_summaries.keys()),
            "config": {
                "escalation_change_pct": self._escalation_change_pct,
                "respect_prism_flags": self._respect_prism_flags,
            },
        }

    # ── Internal: Data Quality Assessment ─────────────────────────────────

    def _assess_data_quality(self, prism_flags: List[Any]) -> str:
        """
        Assess data quality based on PRISM validation flags.

        Translates PRISM's structured results into NOVA's simple
        quality labels: verified, degraded, unreliable.

        Rules:
          - No flags → "verified"
          - Any "warn" flags → "degraded"
          - Any "fail" or "critical" flags → "unreliable"
          - Any HALT_PROCESSING action → "unreliable"

        Args:
            prism_flags: List of PrismResult objects.

        Returns:
            Quality label string.
        """
        if not prism_flags:
            return "verified"

        has_warning = False
        has_critical = False

        for flag in prism_flags:
            # Handle string flags (e.g., "CRITICAL: FEED_DELAY 12000ms")
            if isinstance(flag, str):
                flag_upper = flag.upper()
                if "CRITICAL" in flag_upper or "FAIL" in flag_upper or "HALT" in flag_upper or "UNRELIABLE" in flag_upper:
                    has_critical = True
                    break
                if "WARN" in flag_upper or "DEGRADED" in flag_upper or "DEVIATION" in flag_upper:
                    has_warning = True
                continue

            # PrismResult objects
            status = getattr(flag, "status", "pass")
            severity = getattr(flag, "severity", "")
            action = getattr(flag, "recommended_action", "")

            # Check for critical conditions
            severity_val = severity.value if hasattr(severity, "value") else str(severity)
            action_val = action.value if hasattr(action, "value") else str(action)

            if status == "fail" or severity_val == "critical":
                has_critical = True
                break

            if action_val == "halt_processing":
                has_critical = True
                break

            if status == "warn" or severity_val == "warning":
                has_warning = True

        if has_critical:
            return "unreliable"
        if has_warning:
            return "degraded"
        return "verified"

    # ── Internal: Regime Determination ────────────────────────────────────

    def _determine_regime(
        self,
        market_data: Dict[str, Any],
        atlas_analysis: Optional[Dict[str, Any]],
    ) -> str:
        """
        Determine the current market regime.

        Priority:
          1. ATLAS regime label (if available) — most reliable
          2. Simple heuristic from price data (fallback)
          3. "unknown" if insufficient data

        Args:
            market_data: Raw market data dict.
            atlas_analysis: Optional ATLAS analysis output.

        Returns:
            Regime label: "trend", "range", "volatile", "unknown".
        """
        # Prefer ATLAS regime
        if atlas_analysis and "regime" in atlas_analysis:
            atlas_regime = atlas_analysis["regime"]
            if atlas_regime in REGIME_LABELS:
                return atlas_regime

        # Fallback: simple heuristic from price action
        high = float(market_data.get("high_24h", 0))
        low = float(market_data.get("low_24h", 0))
        change = abs(float(market_data.get("change_24h", 0)))

        if high <= 0 or low <= 0:
            return "unknown"

        # Range percentage (high-low relative to midpoint)
        mid = (high + low) / 2
        if mid == 0:
            return "unknown"

        range_pct = (high - low) / mid * 100

        # Large range or large move → volatile
        if range_pct > 5.0 or change > 4.0:
            return "volatile"

        # Moderate directional move → trend
        if change > 1.5:
            return "trend"

        # Small range → range-bound
        return "range"

    # ── Internal: Key Levels Builder ──────────────────────────────────────

    def _build_key_levels(
        self,
        market_data: Dict[str, Any],
        atlas_analysis: Optional[Dict[str, Any]],
        current_price: float,
        high_24h: float,
        low_24h: float,
    ) -> Dict[str, float]:
        """
        Build key price levels for the summary.

        Priority:
          1. ATLAS key_levels (if available) — most accurate
          2. 24h high/low as support/resistance (fallback)
          3. Current price only (minimal)

        Args:
            market_data: Raw market data dict.
            atlas_analysis: Optional ATLAS analysis output.
            current_price: Current price.
            high_24h: 24-hour high.
            low_24h: 24-hour low.

        Returns:
            Dict with "support", "resistance", "current" keys.
        """
        key_levels: Dict[str, float] = {"current": current_price}

        # Prefer ATLAS levels
        if atlas_analysis and "key_levels" in atlas_analysis:
            atlas_levels = atlas_analysis["key_levels"]
            if isinstance(atlas_levels, dict):
                if "support" in atlas_levels:
                    key_levels["support"] = float(atlas_levels["support"])
                if "resistance" in atlas_levels:
                    key_levels["resistance"] = float(atlas_levels["resistance"])
                return key_levels

        # Fallback: use 24h range
        if low_24h > 0:
            key_levels["support"] = low_24h
        if high_24h > 0:
            key_levels["resistance"] = high_24h

        return key_levels

    # ── Internal: Movement Description ────────────────────────────────────

    def _describe_movement(
        self,
        change_pct: float,
        regime: str,
        current_price: float,
        high_24h: float,
        low_24h: float,
    ) -> str:
        """
        Generate a plain-language description of current price movement.

        NOVA speaks simply. No jargon. No complex technical terms
        without explanation. Just clear, honest description.

        Args:
            change_pct: 24-hour change percentage.
            regime: Current market regime.
            current_price: Current price.
            high_24h: 24-hour high.
            low_24h: 24-hour low.

        Returns:
            Plain-language movement description.
        """
        # Direction
        if change_pct > 2.0:
            direction = "rising strongly"
        elif change_pct > 0.5:
            direction = "rising"
        elif change_pct > -0.5:
            direction = "moving sideways"
        elif change_pct > -2.0:
            direction = "falling"
        else:
            direction = "falling sharply"

        # Regime context
        regime_note = ""
        if regime == "volatile":
            regime_note = " with high volatility"
        elif regime == "range":
            regime_note = " within a range"
        elif regime == "trend":
            regime_note = " in a trend"

        # Position relative to 24h range
        position = ""
        if current_price > 0 and high_24h > 0 and low_24h > 0:
            range_size = high_24h - low_24h
            if range_size > 0:
                pct_through = (current_price - low_24h) / range_size * 100
                if pct_through > 80:
                    position = ", near the 24h high"
                elif pct_through < 20:
                    position = ", near the 24h low"
                else:
                    position = ", in the middle of the 24h range"

        return f"{direction}{regime_note}{position}"

    # ── Internal: Context Builder ─────────────────────────────────────────

    def _build_context(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        atlas_analysis: Optional[Dict[str, Any]],
        data_quality: str,
    ) -> str:
        """
        Build a brief context string for the summary.

        Combines ATLAS insights with market data to produce a
        single-line context that helps users understand the
        current situation quickly.

        Args:
            symbol: Trading symbol.
            market_data: Raw market data dict.
            atlas_analysis: Optional ATLAS analysis output.
            data_quality: PRISM-assessed data quality.

        Returns:
            Brief context string.
        """
        parts: List[str] = []

        # ATLAS context (if available)
        if atlas_analysis:
            if "context" in atlas_analysis:
                parts.append(str(atlas_analysis["context"]))
            if "bias" in atlas_analysis:
                bias = atlas_analysis["bias"]
                if bias in ("bullish", "bearish", "neutral"):
                    parts.append(f"Bias: {bias}")

        # Price position context (if no ATLAS)
        if not parts:
            high = float(market_data.get("high_24h", 0))
            low = float(market_data.get("low_24h", 0))
            price = float(market_data.get("price", 0))

            if price > 0 and high > 0 and low > 0:
                range_size = high - low
                if range_size > 0:
                    pct_through = (price - low) / range_size * 100
                    if pct_through > 80:
                        parts.append("Trading near session high")
                    elif pct_through < 20:
                        parts.append("Trading near session low")
                    else:
                        parts.append("Trading within session range")
                else:
                    parts.append("Minimal price movement this session")

        # Data quality warning in context
        if data_quality == "degraded":
            parts.append("⚠ Data quality degraded — be cautious")
        elif data_quality == "unreliable":
            parts.append("⚠ Data quality unreliable — do not rely on this alone")

        return " | ".join(parts) if parts else "No additional context available"

    # ── Utility: Get Recent Summary ───────────────────────────────────────

    def get_recent_summary(self, symbol: str) -> Optional[NovaSummary]:
        """
        Retrieve the most recent summary for a symbol.

        Args:
            symbol: Trading symbol (case-insensitive).

        Returns:
            The most recent NovaSummary, or None if not tracked.
        """
        return self._recent_summaries.get(symbol.upper())

    # ── Utility: Clear Cache ──────────────────────────────────────────────

    def clear_cache(self) -> None:
        """Clear the recent summaries cache."""
        count = len(self._recent_summaries)
        self._recent_summaries.clear()
        log.info("nova_cache_cleared", entries_cleared=count)
