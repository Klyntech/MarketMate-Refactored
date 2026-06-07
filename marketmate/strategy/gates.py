"""
marketmate/strategy/gates.py
──────────────────────────────
Gate 3: News / High-Impact Event Filter

Migrated from strategy/news_filter.py with updated imports.

Sources:
  Primary:  ForexFactory calendar (scraped — free)
  Fallback: FinnHub economic calendar (free tier)

Rules:
  - Skip trading 30 min BEFORE a high-impact or medium-impact event
  - Skip trading 30 min AFTER a high-impact or medium-impact event
  - Only filter for pairs relevant to the current symbol
    (e.g., USD events affect BTCUSDT, XAUUSD, all USD pairs)

Currency map: symbol → affected currencies
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import aiohttp

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("news_filter")

# Minutes before/after high-impact event to block trading
BLOCK_BEFORE_MINUTES = 30
BLOCK_AFTER_MINUTES  = 30

# Symbol → currencies affected
SYMBOL_CURRENCY_MAP: dict[str, list[str]] = {
    "BTCUSDT":  ["USD"],
    "ETHUSDT":  ["USD"],
    "XAUUSD":   ["USD", "XAU"],
    "EURUSD":   ["EUR", "USD"],
    "GBPUSD":   ["GBP", "USD"],
    "USDJPY":   ["USD", "JPY"],
    "AUDUSD":   ["AUD", "USD"],
    "USDCAD":   ["USD", "CAD"],
    "NZDUSD":   ["NZD", "USD"],
    "USDCHF":   ["USD", "CHF"],
}


class NewsFilter:
    def __init__(self) -> None:
        # Cache: list of (event_time_utc, currency, impact, title)
        self._events: list[dict] = []
        self._last_fetch: Optional[datetime] = None
        self._cache_ttl_minutes = 60   # Refresh every hour

    async def is_news_window(
        self,
        symbol: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> bool:
        """
        Returns True if trading should be blocked due to upcoming/recent
        high-impact news for the given symbol.
        """
        await self._ensure_events_loaded(session)

        now = datetime.now(timezone.utc)
        affected_currencies = SYMBOL_CURRENCY_MAP.get(symbol.upper(), ["USD"])

        for event in self._events:
            event_time: datetime = event["time"]
            currency: str = event["currency"]
            impact: str = event["impact"]

            if impact.lower() not in ("high", "medium"):
                continue

            if currency not in affected_currencies:
                continue

            # Check window: block if within [event_time - before, event_time + after]
            window_start = event_time - timedelta(minutes=BLOCK_BEFORE_MINUTES)
            window_end   = event_time + timedelta(minutes=BLOCK_AFTER_MINUTES)

            if window_start <= now <= window_end:
                log.info(
                    "news_block_active",
                    symbol=symbol,
                    news_event=event.get("title", "unknown"),
                    currency=currency,
                    event_time=event_time.isoformat(),
                    minutes_to_event=round((event_time - now).total_seconds() / 60, 1),
                )
                return True

        return False

    async def _ensure_events_loaded(
        self,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        if (
            self._last_fetch is None
            or (now - self._last_fetch).total_seconds() > self._cache_ttl_minutes * 60
        ):
            await self._fetch_events(session)

    async def _fetch_events(
        self,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        """
        Fetch today's high-impact events.
        Tries FinnHub first (reliable JSON API), falls back to empty list.
        """
        _own_session = session is None
        if _own_session:
            session = aiohttp.ClientSession()

        try:
            events = await self._fetch_finnhub(session)
            if not events:
                events = []
            self._events = events
            self._last_fetch = datetime.now(timezone.utc)
            log.info("news_events_loaded", count=len(events))
        except Exception as exc:
            log.warning("news_fetch_failed", error=str(exc))
            # Fail open — don't block trading just because news API is down
            self._events = []
            self._last_fetch = datetime.now(timezone.utc)
        finally:
            if _own_session:
                await session.close()

    async def _fetch_finnhub(
        self,
        session: aiohttp.ClientSession,
    ) -> list[dict]:
        """
        FinnHub economic calendar — free tier, no auth required for basic data.
        Returns today's events only.
        """
        today = datetime.now(timezone.utc)
        from_date = today.strftime("%Y-%m-%d")
        to_date   = today.strftime("%Y-%m-%d")

        url = "https://finnhub.io/api/v1/calendar/economic"
        params = {"from": from_date, "to": to_date}

        # FinnHub free doesn't require key for this endpoint
        finnhub_key = cfg.data.alpha_vantage_key  # reuse any key field if needed
        if finnhub_key:
            params["token"] = finnhub_key

        try:
            async with session.get(
                url, params=params,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        except Exception:
            return []

        events = []
        for item in data.get("economicCalendar", []):
            impact = str(item.get("impact", "")).lower()
            if impact not in ("high", "medium"):
                continue

            try:
                # FinnHub time format: "2024-01-15 08:30:00"
                time_str = item.get("time", "")
                if not time_str:
                    continue
                event_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                event_time = event_time.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            events.append({
                "time":     event_time,
                "currency": str(item.get("country", "USD")).upper(),
                "impact":   impact,
                "title":    item.get("event", ""),
            })

        return events


# ─── Standalone helper for gate runner ───────────────────────────────────────

# Singleton
_news_filter = NewsFilter()


async def is_high_impact_news(
    symbol: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> bool:
    """Public interface used by SignalEngine."""
    return await _news_filter.is_news_window(symbol, session)
