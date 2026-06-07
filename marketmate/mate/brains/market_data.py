"""
marketmate.mate.brains.market_data
──────────────────────────────────
Market Data Brain — answers everything about prices, trends, and market movement.

Capability Domain:
  - Live price queries: "What's gold trading at?"
  - Historical OHLCV: "How has gold been fairing lately?"
  - Trend detection: "Is EURUSD bullish?"
  - Volatility assessment: "How volatile is XAUUSD today?"
  - Session movement: "What happened during London session?"

Functions:
  get_live_price(symbol)          → current bid/ask/mid
  get_ohlcv(symbol, timeframe)    → OHLCV summary
  get_market_summary(symbol)      → trend, change_pct, volatility, structure

This brain NEVER hallucinates prices.
It fetches from MarketDataEngine (live) or MongoDB cache (fallback).
The LLM only narrates what this brain compiles.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.mate.state_store import redis_state_store

log = get_logger("mate.brains.market_data")


class MarketDataBrain:
    """
    Financial cognition primitive for market data.

    Answers: price, trend, volatility, session, historical movement.
    Does NOT answer: signal counts, account state, strategy logic.
    """

    ALIAS_MAP = {
        "gold": "XAUUSD", "silver": "XAGUSD", "euro": "EURUSD",
        "pound": "GBPUSD", "cable": "GBPUSD", "fiber": "EURUSD",
        "yen": "USDJPY", "kiwi": "NZDUSD", "aussie": "AUDUSD",
        "loonie": "USDCAD", "swissy": "USDCHF",
        "bitcoin": "BTCUSD", "btc": "BTCUSD",
        "ethereum": "ETHUSD", "eth": "ETHUSD",
    }

    @classmethod
    def resolve_symbol(cls, raw: str) -> str:
        """Resolve a symbol alias to its canonical form."""
        key = raw.strip().lower()
        return cls.ALIAS_MAP.get(key, raw.strip().upper())

    # ═════════════════════════════════════════════════════════════════════════
    # Core Brain Functions
    # ═════════════════════════════════════════════════════════════════════════

    async def get_live_price(self, symbol: str) -> Dict[str, Any]:
        """
        Get the current live price for a symbol.

        Tries: MarketDataEngine (1d candle) → 4h fallback → CoinGecko (crypto)
               → TwelveData direct → Redis cache → MongoDB fallback.
        """
        symbol = self.resolve_symbol(symbol)

        # 1. Live fetch from data engine (1d)
        try:
            from marketmate.data.engine import fetch_ohlcv
            df = await fetch_ohlcv(symbol, "1d", limit=1)
            if df is not None and not df.empty:
                last = df.iloc[-1]
                return {
                    "symbol": symbol,
                    "price": round(float(last["close"]), 2),
                    "open": round(float(last["open"]), 2),
                    "high": round(float(last["high"]), 2),
                    "low": round(float(last["low"]), 2),
                    "source": "live_1d",
                }
        except Exception as exc:
            log.warning("live_price_1d_failed", symbol=symbol, error=str(exc))

        # 2. 4h fallback
        try:
            from marketmate.data.engine import fetch_ohlcv
            df = await fetch_ohlcv(symbol, "4h", limit=1)
            if df is not None and not df.empty:
                last = df.iloc[-1]
                return {
                    "symbol": symbol,
                    "price": round(float(last["close"]), 2),
                    "high": round(float(last["high"]), 2),
                    "low": round(float(last["low"]), 2),
                    "source": "live_4h",
                }
        except Exception as exc:
            log.warning("live_price_4h_failed", symbol=symbol, error=str(exc))

        # 3. CoinGecko direct (free, no API key, works on data center IPs)
        coingecko_result = await self._fetch_coingecko_price(symbol)
        if coingecko_result:
            return coingecko_result

        # 4. TwelveData direct HTTP fallback (if API key is set)
        twelve_result = await self._fetch_twelvedata_direct(symbol)
        if twelve_result:
            return twelve_result

        # 5. Redis cached state
        state = await redis_state_store.get_symbol_state(symbol)
        if state and state.get("last_signal_direction"):
            return {
                "symbol": symbol,
                "bias": state.get("bias", ""),
                "last_outcome": state.get("last_outcome", ""),
                "source": "redis_state_no_price",
                "hint": "Live price unavailable, showing cached market state",
            }

        # 6. MongoDB fallback — price from last signal entry
        try:
            from marketmate.db.repositories.signals import SignalRepository
            repo = SignalRepository()
            open_sigs = await repo.get_open_signals()
            for s in open_sigs:
                if s.get("symbol", "").upper() == symbol:
                    entry = s.get("entry_mid") or s.get("mt5_entry_price")
                    if entry:
                        return {
                            "symbol": symbol,
                            "price": round(float(entry), 2),
                            "direction": s.get("direction", ""),
                            "source": "mongodb_signal_fallback",
                            "hint": "Price from last signal entry, may not be current",
                        }
        except Exception as exc:
            log.warning("price_mongo_fallback_failed", symbol=symbol, error=str(exc))

        return {"symbol": symbol, "status": "price_unavailable"}

    async def _fetch_coingecko_price(self, symbol: str) -> Dict[str, Any] | None:
        """
        Fetch crypto price from CoinGecko (free, no API key needed).
        Works reliably on data center IPs (Render, etc.).
        """
        # Map symbols to CoinGecko IDs
        COINGECKO_IDS = {
            "BTCUSD": "bitcoin",
            "ETHUSD": "ethereum",
            "XAGUSD": "silver",
            "XAUUSD": "gold",
        }

        cg_id = COINGECKO_IDS.get(symbol.upper())
        if not cg_id:
            return None

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"https://api.coingecko.com/api/v3/simple/price",
                    params={
                        "ids": cg_id,
                        "vs_currencies": "usd",
                        "include_24hr_change": "true",
                        "include_24hr_vol": "true",
                    },
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "MarketMate/1.0",
                    },
                )

                if resp.status_code != 200:
                    log.warning("coingecko_status", symbol=symbol, status=resp.status_code)
                    return None

                data = resp.json()
                coin_data = data.get(cg_id, {})
                price = coin_data.get("usd")

                if price is None:
                    return None

                result = {
                    "symbol": symbol,
                    "price": round(float(price), 2),
                    "source": "coingecko",
                }

                # Add 24h change if available
                change_24h = coin_data.get("usd_24h_change")
                if change_24h is not None:
                    result["change_24h_pct"] = round(float(change_24h), 2)

                # Add 24h volume if available
                vol_24h = coin_data.get("usd_24h_vol")
                if vol_24h is not None:
                    result["volume_24h"] = round(float(vol_24h), 0)

                log.info("coingecko_price_success", symbol=symbol, price=price)
                return result

        except Exception as exc:
            log.warning("coingecko_price_failed", symbol=symbol, error=str(exc))
            return None

    async def _fetch_twelvedata_direct(self, symbol: str) -> Dict[str, Any] | None:
        """
        Fetch price from TwelveData via direct HTTP (bypasses engine issues).
        Only used if TWELVE_DATA_KEY env var is set.
        """
        import os
        api_key = os.environ.get("TWELVE_DATA_KEY", "")
        if not api_key:
            return None

        # Map to TwelveData format
        TD_MAP = {
            "XAUUSD": "XAU/USD",
            "XAGUSD": "XAG/USD",
            "EURUSD": "EUR/USD",
            "GBPUSD": "GBP/USD",
            "USDJPY": "USD/JPY",
            "BTCUSD": "BTC/USD",
            "ETHUSD": "ETH/USD",
        }

        td_symbol = TD_MAP.get(symbol.upper())
        if not td_symbol:
            return None

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.twelvedata.com/price",
                    params={
                        "symbol": td_symbol,
                        "apikey": api_key,
                    },
                )

                if resp.status_code != 200:
                    return None

                data = resp.json()
                price_str = data.get("price")

                if not price_str:
                    return None

                price = float(price_str)
                log.info("twelvedata_direct_success", symbol=symbol, price=price)
                return {
                    "symbol": symbol,
                    "price": round(price, 2),
                    "source": "twelvedata_direct",
                }

        except Exception as exc:
            log.warning("twelvedata_direct_failed", symbol=symbol, error=str(exc))
            return None

    async def get_ohlcv(
        self, symbol: str, timeframe: str = "1d", limit: int = 30,
    ) -> Dict[str, Any]:
        """
        Get OHLCV candles for a symbol and return a compiled summary.

        Not raw data — trend, range, key levels, structure.
        """
        symbol = self.resolve_symbol(symbol)

        try:
            from marketmate.data.engine import fetch_ohlcv
            df = await fetch_ohlcv(symbol, timeframe, limit=limit)
            if df is None or df.empty:
                return {"symbol": symbol, "status": "no_data", "timeframe": timeframe}

            latest = df.iloc[-1]
            first = df.iloc[0]

            close_latest = float(latest["close"])
            close_first = float(first["close"])
            high = float(df["high"].max())
            low = float(df["low"].min())

            change_pct = round((close_latest - close_first) / close_first * 100, 2) if close_first else 0
            trend = "bullish" if change_pct > 0.5 else "bearish" if change_pct < -0.5 else "ranging"

            # Volatility (average range as % of price)
            ranges = (df["high"] - df["low"]) / df["close"]
            avg_volatility = round(float(ranges.mean()) * 100, 2)

            # Recent structure: higher highs / lower lows
            recent = df.tail(5)
            hh_count = (recent["high"].diff().dropna() > 0).sum()
            ll_count = (recent["low"].diff().dropna() < 0).sum()
            half = max(len(recent) / 2, 1)

            if hh_count > half and ll_count <= half:
                structure = "higher highs"
            elif ll_count > half and hh_count <= half:
                structure = "lower lows"
            else:
                structure = "mixed / consolidation"

            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "candle_count": len(df),
                "current_price": round(close_latest, 2),
                "period_high": round(high, 2),
                "period_low": round(low, 2),
                "change_pct": change_pct,
                "trend": trend,
                "avg_volatility_pct": avg_volatility,
                "recent_structure": structure,
                "source": "live",
            }
        except Exception as exc:
            log.warning("ohlcv_fetch_failed", symbol=symbol, error=str(exc))
            return {"symbol": symbol, "status": "ohlcv_unavailable", "timeframe": timeframe}

    async def get_market_summary(self, symbol: str) -> Dict[str, Any]:
        """
        Get a comprehensive market summary for a symbol.

        Combines: current price, trend, volatility, recent structure,
        session context, and any active signal state.
        """
        symbol = self.resolve_symbol(symbol)

        price_data = await self.get_live_price(symbol)
        ohlcv_data = await self.get_ohlcv(symbol, "1d", limit=7)

        # Session context
        now = datetime.now(timezone.utc)
        from datetime import time as dt_time
        try:
            london_open = dt_time(*map(int, cfg.strategy.london_open.split(":")))
            london_close = dt_time(*map(int, cfg.strategy.london_close.split(":")))
            ny_open = dt_time(*map(int, cfg.strategy.ny_open.split(":")))
            ny_close = dt_time(*map(int, cfg.strategy.ny_close.split(":")))
            now_t = now.time()
            if london_open <= now_t <= london_close:
                session = "London"
            elif ny_open <= now_t <= ny_close:
                session = "New York"
            else:
                session = "Off-hours"
        except Exception:
            session = "unknown"

        state = await redis_state_store.get_symbol_state(symbol)

        # Phase 3: Enrich with compiled InstrumentState from StateEngine
        # This is the key bridge — MATE now reads from the v8.0.0 state vector,
        # not just from the legacy flat Redis dict.
        instrument_state = await self._get_instrument_state(symbol)

        summary = {
            "symbol": symbol,
            "current_session": session,
            "utc_time": now.strftime("%H:%M UTC"),
        }

        if price_data.get("price"):
            summary["price"] = price_data["price"]
            summary["price_source"] = price_data.get("source", "unknown")
        if price_data.get("open"):
            summary["day_open"] = price_data["open"]
        if price_data.get("high"):
            summary["day_high"] = price_data["high"]
        if price_data.get("low"):
            summary["day_low"] = price_data["low"]

        if ohlcv_data.get("trend"):
            summary["weekly_trend"] = ohlcv_data["trend"]
            summary["weekly_change_pct"] = ohlcv_data.get("change_pct", 0)
            summary["recent_structure"] = ohlcv_data.get("recent_structure", "")
            summary["volatility"] = ohlcv_data.get("avg_volatility_pct", 0)

        # Legacy flat state (backward compatible)
        if state:
            summary["bias"] = state.get("bias", "")
            summary["last_signal_direction"] = state.get("last_signal_direction", "")
            summary["last_outcome"] = state.get("last_outcome", "")
            summary["recent_wins"] = state.get("recent_wins")
            summary["recent_losses"] = state.get("recent_losses")

        # Phase 3: Compiled state enrichment (from InstrumentState)
        if instrument_state:
            bias = instrument_state.get("bias", {})
            summary["state_bias"] = bias.get("daily_bias", "")
            summary["state_h4_bias"] = bias.get("h4_bias", "")
            summary["conviction_score"] = bias.get("conviction_score", 0)
            summary["regime"] = bias.get("regime", "")
            summary["daily_structure"] = bias.get("daily_structure", "")
            summary["h4_structure"] = bias.get("h4_structure", "")
            summary["daily_above_ema200"] = bias.get("daily_above_ema200")
            summary["h4_above_ema200"] = bias.get("h4_above_ema200")

            risk = instrument_state.get("risk", {})
            summary["volatility_regime"] = risk.get("volatility_regime", "")
            summary["current_rr"] = risk.get("current_rr", 0)

            zones = instrument_state.get("zones", {})
            summary["active_zones_count"] = zones.get("active_zones_count", 0)
            summary["zone_freshness"] = zones.get("zone_freshness", 0)

            liquidity = instrument_state.get("liquidity", {})
            summary["has_recent_sweep"] = liquidity.get("has_recent_sweep", False)
            summary["available_liquidity"] = liquidity.get("available_liquidity_score", 0)

            confirmation = instrument_state.get("confirmation", {})
            summary["alignment_score"] = confirmation.get("alignment_score", 0)

            composite = instrument_state.get("composite", {})
            summary["confidence_tier"] = composite.get("confidence_tier", "")
            summary["overall_signal_quality"] = composite.get("overall_signal_quality", 0)

            # Override legacy bias with compiled state (source of truth)
            if summary.get("state_bias"):
                summary["bias"] = summary["state_bias"]

        return summary

    async def _get_instrument_state(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get the compiled InstrumentState from the StateEngine.

        This reads from the v8.0.0 state vector (memory → Redis → None),
        NOT from the legacy flat Redis dict. This is the canonical source
        of truth for market state.
        """
        try:
            from marketmate.state.engine import get_state_engine
            state_engine = get_state_engine()
            state = await state_engine.get_instrument_state(symbol)
            if state is None:
                return None
            return self._format_state_for_summary(state)
        except Exception as exc:
            log.debug("instrument_state_unavailable", symbol=symbol, error=str(exc))
            return None

    def _format_state_for_summary(self, state) -> Dict[str, Any]:
        """Format InstrumentState for market summary enrichment."""
        return {
            "bias": {
                "daily_bias": state.bias_state.daily_bias.value,
                "h4_bias": state.bias_state.h4_bias.value,
                "daily_structure": state.bias_state.daily_structure,
                "h4_structure": state.bias_state.h4_structure,
                "conviction_score": round(state.bias_state.conviction_score, 3),
                "regime": state.bias_state.regime.value,
                "daily_above_ema200": state.bias_state.daily_above_ema,
                "h4_above_ema200": state.bias_state.h4_above_ema,
            },
            "risk": {
                "volatility_regime": state.risk_state.volatility_regime.value,
                "current_rr": round(state.risk_state.current_rr, 2),
            },
            "zones": {
                "active_zones_count": len(state.zone_state.active_zones),
                "zone_freshness": round(state.zone_state.zone_freshness, 3),
            },
            "liquidity": {
                "has_recent_sweep": len(state.liquidity_state.recent_sweeps) > 0,
                "available_liquidity_score": round(
                    state.liquidity_state.available_liquidity_score, 3
                ),
            },
            "confirmation": {
                "alignment_score": round(state.confirm_state.alignment_score, 3),
            },
            "composite": {
                "confidence_tier": state.confidence_tier,
                "overall_signal_quality": round(state.overall_signal_quality, 3),
            },
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

market_data_brain = MarketDataBrain()
