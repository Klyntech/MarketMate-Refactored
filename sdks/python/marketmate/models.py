"""Pydantic models for MarketMate API responses."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KeyLevels(BaseModel):
    """Support and resistance key price levels."""
    support: List[float] = Field(default_factory=list, description="Support price levels")
    resistance: List[float] = Field(default_factory=list, description="Resistance price levels")


class Trend(BaseModel):
    """Market trend information."""
    direction: str = Field(description="Trend direction: bullish, bearish, or neutral")
    strength: float = Field(description="Trend strength (0-1)")
    timeframe: str = Field(description="Analysis timeframe (e.g., 4H)")


class PriceData(BaseModel):
    """Current price and 24h statistics."""
    current: float = Field(description="Current price")
    change_24h: float = Field(description="24h price change percentage")
    high_24h: float = Field(description="24h high price")
    low_24h: float = Field(description="24h low price")
    volume_24h: float = Field(description="24h volume in base currency")
    quote_volume_24h: int = Field(description="24h volume in quote currency")


class MarketState(BaseModel):
    """Real-time market state for a trading pair."""
    symbol: str = Field(description="Trading pair symbol")
    regime: str = Field(description="Market regime: trending_bullish, trending_bearish, ranging, volatile")
    conviction: float = Field(description="Conviction score (0-1)")
    volatility: str = Field(description="Volatility level: low, normal, elevated, extreme")
    liquidity: float = Field(description="Liquidity score (0-1)")
    price: Optional[PriceData] = Field(default=None, description="Current price data")
    key_levels: Optional[KeyLevels] = Field(default=None, description="Key support/resistance levels")
    trend: Optional[Trend] = Field(default=None, description="Trend information")
    source: str = Field(default="binance", description="Data source")
    updated_at: str = Field(description="Last update timestamp (ISO 8601)")


class EntryZone(BaseModel):
    """Entry zone for a signal."""
    low: float = Field(description="Entry zone lower bound")
    high: float = Field(description="Entry zone upper bound")
    mid: float = Field(description="Entry zone midpoint")


class Signal(BaseModel):
    """Trading signal with entry, risk management, and target levels."""
    signal_id: str = Field(description="Unique signal identifier")
    symbol: str = Field(description="Trading pair symbol")
    direction: str = Field(description="Trade direction: LONG or SHORT")
    entry_zone: EntryZone = Field(description="Entry price zone")
    stop_loss: float = Field(description="Stop loss price")
    take_profit_1: float = Field(description="First take profit target")
    take_profit_2: Optional[float] = Field(default=None, description="Second take profit target")
    take_profit_3: Optional[float] = Field(default=None, description="Third take profit target")
    risk_reward: float = Field(description="Risk/reward ratio")
    conviction: str = Field(description="Conviction level: HIGH, MEDIUM, or LOW")
    zone_type: str = Field(description="Zone type: demand_zone, supply_zone, etc.")
    confirmation: str = Field(description="Confirmation type")
    status: str = Field(description="Signal status: ACTIVE, CLOSED, etc.")
    source: Optional[str] = Field(default=None, description="Signal source")
    disclaimer: Optional[str] = Field(default=None, description="Risk disclaimer")
    created_at: str = Field(description="Signal creation timestamp (ISO 8601)")


class SignalsResponse(BaseModel):
    """Response containing trading signals."""
    signals: List[Signal] = Field(default_factory=list)
    count: int = Field(description="Number of signals returned")
    source: Optional[str] = Field(default=None)
    note: Optional[str] = Field(default=None)
    timestamp: str = Field(description="Response timestamp")


class LiquidityPool(BaseModel):
    """A significant liquidity pool in the orderbook."""
    level: float = Field(description="Price level")
    type: str = Field(description="Pool type: demand or supply")
    volume: str = Field(description="Volume at this level")
    quantity: float = Field(description="Quantity at this level")
    strength: float = Field(description="Relative strength vs average")


class LiquiditySweep(BaseModel):
    """A potential sweep level (thin liquidity behind a wall)."""
    level: float = Field(description="Price level")
    direction: str = Field(description="Sweep direction: bearish or bullish")
    thin_liquidity: Optional[str] = Field(default=None)
    wall_above: Optional[str] = Field(default=None)
    wall_below: Optional[str] = Field(default=None)


class OrderbookSummary(BaseModel):
    """Top of book summary."""
    best_bid: float = Field(description="Best bid price")
    best_ask: float = Field(description="Best ask price")
    spread: float = Field(description="Absolute spread")
    spread_pct: float = Field(description="Spread as percentage")


class LiquidityBalance(BaseModel):
    """Bid/ask depth balance."""
    bid_depth: int = Field(description="Total bid depth value")
    ask_depth: int = Field(description="Total ask depth value")
    ratio: float = Field(description="Bid/total ratio (>0.5 = buying pressure)")
    pressure: str = Field(description="Market pressure: buying, selling, or neutral")


class LiquidityAnalysis(BaseModel):
    """Real-time liquidity analysis from orderbook data."""
    symbol: str = Field(description="Trading pair symbol")
    current_price: float = Field(description="Current market price")
    score: float = Field(description="Liquidity score (0-1)")
    balance: Optional[LiquidityBalance] = Field(default=None)
    pools: List[LiquidityPool] = Field(default_factory=list)
    sweeps: List[LiquiditySweep] = Field(default_factory=list)
    orderbook_summary: Optional[OrderbookSummary] = Field(default=None)
    volume_24h: float = Field(default=0)
    source: str = Field(default="binance")
    disclaimer: Optional[str] = Field(default=None)
    updated_at: str = Field(description="Last update timestamp")


class HistoricalDataPoint(BaseModel):
    """A single historical data point with OHLCV and analysis."""
    timestamp: str = Field(description="Candle timestamp (ISO 8601)")
    open: float = Field(description="Open price")
    high: float = Field(description="High price")
    low: float = Field(description="Low price")
    close: float = Field(description="Close price")
    volume: float = Field(description="Volume")
    regime: str = Field(description="Detected market regime")
    conviction: float = Field(description="Conviction score (0-1)")
    volatility: str = Field(description="Volatility level")
    liquidity_score: float = Field(description="Liquidity score (0-1)")


class HistoricalPeriod(BaseModel):
    """Time period metadata."""
    start: Optional[str] = None
    end: Optional[str] = None
    candles: int = 0


class HistoricalSummary(BaseModel):
    """Summary statistics for the historical period."""
    start_price: float = 0
    end_price: float = 0
    change_pct: float = 0
    high: float = 0
    low: float = 0
    total_volume: float = 0
    regime_distribution: Dict[str, int] = Field(default_factory=dict)


class HistoricalResponse(BaseModel):
    """Response containing historical market data."""
    symbol: str = Field(description="Trading pair symbol")
    interval: str = Field(description="Candle interval")
    period: Optional[HistoricalPeriod] = None
    summary: Optional[HistoricalSummary] = None
    data: List[HistoricalDataPoint] = Field(default_factory=list)
    source: str = Field(default="binance")
    updated_at: str = Field(description="Last update timestamp")


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str = Field(description="Error type")
    message: Optional[str] = Field(default=None, description="Error description")
    details: Optional[str] = Field(default=None, description="Error details")
