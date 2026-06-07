"""MarketMate API client."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from marketmate.models import (
    MarketState,
    Signal,
    SignalsResponse,
    LiquidityAnalysis,
    HistoricalResponse,
    ErrorResponse,
)


class MarketMateError(Exception):
    """Exception raised for MarketMate API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_type: Optional[str] = None,
        response: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.response = response or {}
        super().__init__(self.message)


class AuthenticationError(MarketMateError):
    """Raised when API key is missing or invalid."""
    pass


class RateLimitError(MarketMateError):
    """Raised when rate limit is exceeded."""
    pass


class MarketMate:
    """
    MarketMate API client.

    Provides access to real-time market state, trading signals,
    liquidity analysis, and historical data.

    Args:
        api_key: Your MarketMate API key (starts with mk_live_ or mk_test_).
        base_url: API base URL. Defaults to https://marketmate-website.onrender.com.
        timeout: Request timeout in seconds. Defaults to 30.

    Examples:
        >>> from marketmate import MarketMate
        >>> client = MarketMate(api_key="mk_live_your_key_here")
        >>>
        >>> # Get market state
        >>> state = client.get_market_state("BTC-USD")
        >>> print(f"Regime: {state.regime}, Conviction: {state.conviction}")
        >>>
        >>> # Get signals
        >>> signals = client.get_signals(symbol="BTC-USD")
        >>> for s in signals.signals:
        ...     print(f"{s.symbol} {s.direction} RR:{s.risk_reward}")
    """

    DEFAULT_BASE_URL = "https://marketmate-website.onrender.com"
    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        if not api_key:
            raise ValueError("API key is required. Get one at https://marketmate-website.onrender.com/dashboard/api-keys")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": f"marketmate-python/2.1.0",
            },
            timeout=timeout,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        """Make an HTTP request and handle errors."""
        response = self._client.request(method, path, **kwargs)

        if response.status_code == 401:
            raise AuthenticationError(
                message="Invalid or missing API key. Check your key at https://marketmate-website.onrender.com/dashboard/api-keys",
                status_code=401,
                error_type="unauthorized",
                response=response.json() if response.content else {},
            )

        if response.status_code == 429:
            raise RateLimitError(
                message="Rate limit exceeded. Please slow down your requests.",
                status_code=429,
                error_type="rate_limited",
                response=response.json() if response.content else {},
            )

        if response.status_code >= 500:
            raise MarketMateError(
                message="MarketMate API is temporarily unavailable. Please try again.",
                status_code=response.status_code,
                error_type="server_error",
                response=response.json() if response.content else {},
            )

        if response.status_code >= 400:
            data = response.json() if response.content else {}
            raise MarketMateError(
                message=data.get("message", data.get("error", f"Request failed with status {response.status_code}")),
                status_code=response.status_code,
                error_type=data.get("error", "client_error"),
                response=data,
            )

        return response.json()

    def verify(self) -> Dict[str, Any]:
        """
        Verify your API key is valid.

        Returns:
            Dict with 'valid' and 'environment' fields.

        Raises:
            AuthenticationError: If the API key is invalid.
        """
        return self._request("GET", "/api/v1/verify")

    def get_market_state(self, symbol: str = "BTC-USD") -> MarketState:
        """
        Get real-time market state for a trading pair.

        Returns current regime, conviction score, volatility, liquidity,
        key support/resistance levels, and trend information.

        Args:
            symbol: Trading pair symbol (e.g., "BTC-USD", "ETH-USD").
                    Defaults to "BTC-USD".

        Returns:
            MarketState object with live market data.

        Raises:
            AuthenticationError: If API key is invalid.
            MarketMateError: If the API request fails.

        Examples:
            >>> state = client.get_market_state("BTC-USD")
            >>> print(f"Regime: {state.regime}")
            >>> print(f"Price: ${state.price.current:,.2f}")
            >>> print(f"Conviction: {state.conviction}")
        """
        data = self._request("GET", "/api/v1/market-state", params={"symbol": symbol})
        return MarketState(**data)

    def get_signals(
        self,
        symbol: Optional[str] = None,
        conviction: Optional[str] = None,
    ) -> SignalsResponse:
        """
        Get active trading signals.

        Returns AI-generated and/or technically-derived trading signals with
        entry zones, stop loss, and take profit levels.

        Args:
            symbol: Filter by trading pair (e.g., "BTC-USD").
            conviction: Filter by conviction level ("HIGH", "MEDIUM", "LOW").

        Returns:
            SignalsResponse with list of Signal objects.

        Raises:
            AuthenticationError: If API key is invalid.
            MarketMateError: If the API request fails.

        Examples:
            >>> # Get all signals
            >>> response = client.get_signals()
            >>> for signal in response.signals:
            ...     print(f"{signal.symbol} {signal.direction} RR:{signal.risk_reward}")
            >>>
            >>> # Filter by symbol and conviction
            >>> response = client.get_signals(symbol="BTC-USD", conviction="HIGH")
        """
        params: Dict[str, str] = {}
        if symbol:
            params["symbol"] = symbol
        if conviction:
            params["conviction"] = conviction

        data = self._request("GET", "/api/v1/signals", params=params)
        return SignalsResponse(**data)

    def get_liquidity(self, symbol: str = "BTC-USD") -> LiquidityAnalysis:
        """
        Get real-time liquidity analysis from orderbook data.

        Returns liquidity pools, potential sweep levels, bid/ask balance,
        and market pressure analysis.

        Args:
            symbol: Trading pair symbol. Defaults to "BTC-USD".

        Returns:
            LiquidityAnalysis with orderbook-derived data.

        Raises:
            AuthenticationError: If API key is invalid.
            MarketMateError: If the API request fails.

        Examples:
            >>> liq = client.get_liquidity("BTC-USD")
            >>> print(f"Score: {liq.score}")
            >>> print(f"Pressure: {liq.balance.pressure}")
            >>> for pool in liq.pools:
            ...     print(f"  {pool.type} @ {pool.level} ({pool.volume})")
        """
        data = self._request("GET", "/api/v1/liquidity", params={"symbol": symbol})
        return LiquidityAnalysis(**data)

    def get_historical(
        self,
        symbol: str = "BTC-USD",
        hours: int = 24,
        interval: str = "1h",
    ) -> HistoricalResponse:
        """
        Get historical market data with regime analysis.

        Returns OHLCV candlestick data with computed regime, conviction,
        volatility, and liquidity scores for each candle.

        Args:
            symbol: Trading pair symbol. Defaults to "BTC-USD".
            hours: Number of hours of history (1-720). Defaults to 24.
            interval: Candle interval. One of: 1m, 5m, 15m, 30m, 1h, 4h, 1d.
                     Defaults to "1h".

        Returns:
            HistoricalResponse with list of HistoricalDataPoint objects.

        Raises:
            AuthenticationError: If API key is invalid.
            MarketMateError: If the API request fails.

        Examples:
            >>> # Get 24 hours of 1H candles
            >>> history = client.get_historical("BTC-USD", hours=24, interval="1h")
            >>> print(f"Period: {history.period.start} to {history.period.end}")
            >>> for point in history.data:
            ...     print(f"{point.timestamp}: {point.regime} @ {point.close}")
            >>>
            >>> # Get 7 days of 4H candles
            >>> history = client.get_historical("BTC-USD", hours=168, interval="4h")
        """
        data = self._request(
            "GET",
            "/api/v1/historical",
            params={"symbol": symbol, "hours": str(hours), "interval": interval},
        )
        return HistoricalResponse(**data)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "MarketMate":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"MarketMate(base_url='{self.base_url}', api_key='{self.api_key[:16]}...')"
