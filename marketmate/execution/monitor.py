"""
marketmate/execution/monitor.py
────────────────────────────────
Real-time price monitor for open trades via Twelve Data WebSocket.

Migrated from services/price_monitor.py. Key changes:
  - All imports use marketmate. prefix
  - Uses EventBus for TP/SL events instead of directly calling
    trade_manager.check_price()
  - Uses ProximityRepo from marketmate.analytics.proximity instead of
    db.proximity

Architecture:
  · Connects to wss://ws.twelvedata.com/v1/quotes/price?apikey=KEY
  · Subscribes to XAU/USD (1 WebSocket credit, separate from API credits)
  · On each tick (~1/sec):
      1. Update in-memory highest_price / lowest_price for all open trades
      2. Fire async DB write (atomic $max/$min, ~20–50 ms, non-blocking)
      3. If price crossed TP1/TP2/TP3/SL → emit event via EventBus
         which triggers the TradeLifecycleManager.check_price() handler

This module is PURELY ADDITIVE — the 10-minute evaluation loop is unchanged.
If the WebSocket disconnects, the evaluation loop continues unaffected.

Reconnection: exponential backoff 2s → 4s → 8s → … → 60s cap.
"""

from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, WebSocketException
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.core.events import EventBus, event_bus as _default_bus, EventType
from marketmate.analytics.proximity import ProximityRepo

if TYPE_CHECKING:
    from marketmate.execution.lifecycle import TradeLifecycleManager

log = get_logger("price_monitor")

_WS_URL = "wss://ws.twelvedata.com/v1/quotes/price"
_SYMBOL = "XAU/USD"

# In-memory state: signal_id → {"highest": float, "lowest": float,
#                                "entry": float, "sl": float,
#                                "tp1": float, "tp2": float, "tp3": float|None,
#                                "direction": str, "symbol": str}
_open_trades: dict[str, dict] = {}
_last_price: float = 0.0
_last_tick_at: Optional[datetime] = None

# Module-level references (set by start_monitor)
_trade_lifecycle_manager: Optional["TradeLifecycleManager"] = None
_event_bus: EventBus = _default_bus
_proximity_repo: ProximityRepo = ProximityRepo()


# ─── Public entry point ───────────────────────────────────────────────────────

async def start_monitor(
    trade_lifecycle_manager: "TradeLifecycleManager",
    event_bus: Optional[EventBus] = None,
) -> None:
    """
    Main loop. Called once in lifespan as an asyncio background task.
    Connects, subscribes, processes ticks, reconnects on failure — forever.
    """
    global _trade_lifecycle_manager, _event_bus

    _trade_lifecycle_manager = trade_lifecycle_manager
    _event_bus = event_bus or _default_bus

    if not _WS_AVAILABLE:
        log.warning("price_monitor_disabled",
                    reason="websockets package not installed; "
                           "add 'websockets' to requirements.txt")
        return

    api_key = getattr(cfg, "twelve_data_api_key", None) or \
              getattr(getattr(cfg, "data", None), "twelve_data_key", None)
    if not api_key:
        log.warning("price_monitor_disabled",
                    reason="TWELVE_DATA_API_KEY not configured")
        return

    # Seed in-memory dict from any already-open trades (handles restarts)
    await _seed_open_trades()

    backoff = 2.0
    while True:
        try:
            url = f"{_WS_URL}?apikey={api_key}"
            log.info("price_monitor_connecting", symbol=_SYMBOL)
            async with websockets.connect(url, ping_interval=20,
                                          ping_timeout=10) as ws:
                backoff = 2.0  # reset on successful connect
                await _subscribe(ws)
                log.info("price_monitor_connected", symbol=_SYMBOL)
                async for raw in ws:
                    await _handle_message(raw)

        except ConnectionClosed as exc:
            log.warning("price_monitor_disconnected",
                        code=exc.code, reason=exc.reason,
                        reconnect_in=backoff)
        except WebSocketException as exc:
            log.warning("price_monitor_ws_error",
                        error=str(exc), reconnect_in=backoff)
        except Exception as exc:
            log.error("price_monitor_unexpected_error",
                      error=str(exc), reconnect_in=backoff)

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60.0)


# ─── WebSocket helpers ────────────────────────────────────────────────────────

async def _subscribe(ws) -> None:
    payload = json.dumps({
        "action": "subscribe",
        "params": {"symbols": _SYMBOL},
    })
    await ws.send(payload)


async def _handle_message(raw: str) -> None:
    global _last_price, _last_tick_at

    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return

    event = msg.get("event")

    if event == "price":
        try:
            price = float(msg["price"])
        except (KeyError, ValueError):
            return

        _last_price = price
        _last_tick_at = datetime.now(timezone.utc)

        await _process_tick(price)

    elif event == "subscribe-status":
        status = msg.get("status")
        if status == "ok":
            log.info("price_monitor_subscribed",
                     symbol=msg.get("symbol", _SYMBOL))
        else:
            log.warning("price_monitor_subscribe_failed", msg=msg)

    elif event == "heartbeat":
        pass  # Twelve Data sends periodic heartbeats — ignore silently

    elif event == "error":
        log.error("price_monitor_server_error", msg=msg)


# ─── Tick processing ──────────────────────────────────────────────────────────

async def _process_tick(price: float) -> None:
    """
    For every open trade:
      1. Update in-memory extreme price
      2. Fire non-blocking DB write
      3. If TP/SL crossed → emit event via EventBus
    """
    if not _open_trades:
        return

    closed_ids: list[str] = []

    for signal_id, state in list(_open_trades.items()):
        direction = state["direction"]

        # ── Update in-memory extremes ──────────────────────────────────────
        if direction == "BUY":
            if price > state["highest"]:
                state["highest"] = price
                # Non-blocking DB write (fire-and-forget)
                asyncio.create_task(
                    _proximity_repo.update_proximity(signal_id, price, direction)
                )
        else:  # SELL
            if price < state["lowest"]:
                state["lowest"] = price
                asyncio.create_task(
                    _proximity_repo.update_proximity(signal_id, price, direction)
                )

        # ── TP / SL hit detection ──────────────────────────────────────────
        tp1 = state["tp1"]
        tp2 = state["tp2"]
        tp3 = state.get("tp3")
        sl  = state["sl"]

        crossed = None
        if direction == "BUY":
            if tp3 and price >= tp3:
                crossed = ("TP3", tp3)
            elif price >= tp2:
                crossed = ("TP2", tp2)
            elif price >= tp1:
                crossed = ("TP1", tp1)
            elif price <= sl:
                crossed = ("SL", sl)
        else:  # SELL
            if tp3 and price <= tp3:
                crossed = ("TP3", tp3)
            elif price <= tp2:
                crossed = ("TP2", tp2)
            elif price <= tp1:
                crossed = ("TP1", tp1)
            elif price >= sl:
                crossed = ("SL", sl)

        if crossed:
            level_name, level_price = crossed
            log.info("price_monitor_level_crossed",
                     signal_id=signal_id, symbol=state.get("symbol"),
                     direction=direction, level=level_name,
                     price=price, level_price=level_price)
            closed_ids.append(signal_id)

            # Emit TP_HIT or LOSS_HIT event via EventBus
            event_type = EventType.LOSS_HIT if level_name == "SL" else EventType.TP_HIT
            await _event_bus.emit(
                event_type,
                {
                    "signal_id": signal_id,
                    "symbol":    state.get("symbol", ""),
                    "direction": direction,
                    "level":     level_name,
                    "price":     price,
                    "level_price": level_price,
                },
            )

            # Also call the TradeLifecycleManager.check_price() directly
            # for immediate handling (the event bus may have async handlers)
            if _trade_lifecycle_manager is not None:
                asyncio.create_task(
                    _trade_lifecycle_manager.check_price(
                        signal_id, price, level_name
                    )
                )

    for sid in closed_ids:
        _open_trades.pop(sid, None)


# ─── Public API for TradeLifecycleManager ─────────────────────────────────────

def register_trade(
    signal_id: str,
    symbol: str,
    direction: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    tp3: float = 0.0,
) -> None:
    """
    Register a newly opened trade with the monitor.
    Called by TradeLifecycleManager when a sim trade opens so the monitor
    starts tracking it immediately without waiting for a restart.
    """
    _open_trades[signal_id] = {
        "symbol":    symbol,
        "direction": direction,
        "entry":     entry,
        "sl":        sl,
        "tp1":       tp1,
        "tp2":       tp2,
        "tp3":       tp3 if tp3 else None,
        "highest":   entry,
        "lowest":    entry,
    }
    # Also init the DB document so flush_proximity works even if the monitor
    # restarts before the trade closes
    asyncio.create_task(
        _proximity_repo.init_proximity(signal_id, symbol, direction, entry, sl, tp1, tp2, tp3)
    )
    log.debug("price_monitor_trade_registered",
              signal_id=signal_id, symbol=symbol, direction=direction)


def unregister_trade(signal_id: str) -> None:
    """Remove a trade from in-memory tracking (called after close is persisted)."""
    _open_trades.pop(signal_id, None)


def get_last_price() -> float:
    """Return the most recent tick price (0.0 if monitor hasn't received a tick yet)."""
    return _last_price


def get_last_tick_age_seconds() -> float | None:
    """How many seconds ago was the last tick received? None if never."""
    if _last_tick_at is None:
        return None
    return (datetime.now(timezone.utc) - _last_tick_at).total_seconds()


# ─── Startup seeding ──────────────────────────────────────────────────────────

async def _seed_open_trades() -> None:
    """
    On monitor startup, read all trade_proximity documents and populate
    the in-memory dict. This handles the case where the process restarted
    while trades were open — we pick up where we left off.
    """
    docs = await _proximity_repo.get_all_open_proximity()
    for doc in docs:
        sid = doc["signal_id"]
        _open_trades[sid] = {
            "symbol":    doc.get("symbol", "XAUUSD"),
            "direction": doc["direction"],
            "entry":     doc["entry"],
            "sl":        doc["sl"],
            "tp1":       doc.get("tp1", doc["tp2"]),
            "tp2":       doc["tp2"],
            "tp3":       doc.get("tp3"),
            "highest":   doc.get("highest_price", doc["entry"]),
            "lowest":    doc.get("lowest_price",  doc["entry"]),
        }
    if docs:
        log.info("price_monitor_seeded_from_db", trade_count=len(docs))
    else:
        log.debug("price_monitor_no_open_trades_to_seed")
