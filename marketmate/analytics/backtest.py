"""
marketmate.analytics.backtest
──────────────────────────────
Historical backtester for the gate-based SMC strategy.

Migrated from analytics/backtest.py.
Import paths updated to marketmate.* prefix.
"""

from __future__ import annotations
import argparse
import asyncio
import csv
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from marketmate.core.config import cfg
from marketmate.data.providers import get_candles
from marketmate.strategy.bias import get_htf_bias
from marketmate.strategy.liquidity import detect_sweep
from marketmate.strategy.zones import find_entry_zone
from marketmate.strategy.confirmations import check_ltf_confirmation
from marketmate.execution.risk import RiskManager
from marketmate.core.logger import get_logger

log = get_logger("backtest")

OUTPUT_DIR = "backtest_results"
_MAX_CANDLES = 4999


@dataclass
class BacktestTrade:
    candle_idx: int
    symbol: str
    direction: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: Optional[float]
    rr: float
    confidence: str
    zone_type: str
    confirm_type: str
    outcome: str = ""
    pnl_r: float = 0.0
    candles_held: int = 0


class Backtester:
    def __init__(self, symbol: str, days: int = 90) -> None:
        self.symbol  = symbol
        self.days    = days
        self.risk    = RiskManager()
        self.trades: list[BacktestTrade] = []

    async def run(self) -> None:
        log.info("backtest_starting", symbol=self.symbol, days=self.days)

        limit = min(self.days * 6, 1000)

        try:
            h4_full  = await get_candles(self.symbol, "4h",  limit=min(limit,         _MAX_CANDLES))
            d_full   = await get_candles(self.symbol, "1d",  limit=min(limit // 6 + 10, _MAX_CANDLES))
            m15_full = await get_candles(self.symbol, "15m", limit=min(limit * 4,     _MAX_CANDLES))
        except Exception as exc:
            log.error("backtest_data_fetch_failed", error=str(exc))
            return

        try:
            m5_full = await get_candles(self.symbol, "5m", limit=min(limit * 4, _MAX_CANDLES))
            log.info("backtest_5m_loaded", candles=len(m5_full))
        except Exception as exc:
            log.warning("backtest_5m_unavailable", error=str(exc))
            m5_full = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        n = len(h4_full)
        min_idx = max(250, cfg.data.htf_candles)

        log.info("backtest_data_loaded",
                 h4=n, d=len(d_full), m15=len(m15_full), m5=len(m5_full),
                 scanning_from=min_idx)

        for i in range(min_idx, n - 10):
            current_ts = h4_full.iloc[i]["timestamp"]

            h4_slice  = h4_full.iloc[:i].copy()
            d_slice   = _align_daily(d_full,   current_ts)
            m15_slice = _align_ltf(m15_full,   current_ts, limit=50)
            m5_slice  = _align_ltf(m5_full,    current_ts, limit=50) if not m5_full.empty else None

            _assert_no_lookahead(h4_slice, current_ts, "h4")
            if d_slice   is not None: _assert_no_lookahead(d_slice,   current_ts, "daily")
            if m15_slice is not None: _assert_no_lookahead(m15_slice, current_ts, "m15")
            if m5_slice  is not None: _assert_no_lookahead(m5_slice,  current_ts, "m5")

            if d_slice is None or len(d_slice) < 50:
                continue
            if m15_slice is None or len(m15_slice) < 20:
                continue

            trade = self._check_signal(i, h4_slice, d_slice, m15_slice, m5_slice)
            if trade is None:
                continue

            future = h4_full.iloc[i + 1: i + 81]
            self._simulate_outcome(trade, future)
            self.trades.append(trade)

            log.debug("backtest_trade", idx=i,
                      direction=trade.direction, outcome=trade.outcome, pnl_r=trade.pnl_r)

        self._print_summary()
        self._save_csv()

    def _check_signal(self, idx, h4, daily, m15, m5):
        bias = get_htf_bias(daily, h4, ema_period=cfg.strategy.ema_period,
                            swing_lookback=cfg.data.swing_lookback)
        if bias is None:
            return None

        sweep = detect_sweep(h4, bias)
        if sweep is None:
            return None

        zone = find_entry_zone(h4, bias)
        if zone is None:
            return None

        confirm = check_ltf_confirmation(m15, m5, bias)
        if confirm is None:
            return None

        current_price = float(h4.iloc[-1]["close"])
        rr_result = self.risk.calculate_rr(
            direction=bias,
            entry_zone_high=zone.zone_high,
            entry_zone_low=zone.zone_low,
            current_price=current_price,
            h4_df=h4,
        )
        if rr_result is None or rr_result["rr"] < cfg.strategy.min_rr:
            return None

        from marketmate.strategy.gates import _assess_confidence
        confidence = _assess_confidence(sweep, zone, confirm)

        return BacktestTrade(
            candle_idx=idx, symbol=self.symbol,
            direction="BUY" if bias == "bullish" else "SELL",
            entry=rr_result["entry"], sl=rr_result["sl"],
            tp1=rr_result["tp1"], tp2=rr_result["tp2"], tp3=rr_result["tp3"],
            rr=rr_result["rr"], confidence=confidence,
            zone_type=zone.zone_type, confirm_type=confirm.signal_type,
        )

    def _simulate_outcome(self, trade, future):
        sl_dist = abs(trade.entry - trade.sl)
        for i, (_, candle) in enumerate(future.iterrows()):
            if trade.direction == "BUY":
                if candle["low"] <= trade.sl:
                    trade.outcome = "SL"; trade.pnl_r = -1.0; trade.candles_held = i + 1; return
                if trade.tp3 and candle["high"] >= trade.tp3:
                    trade.outcome = "TP3"; trade.pnl_r = (trade.tp3 - trade.entry) / sl_dist; trade.candles_held = i + 1; return
                if candle["high"] >= trade.tp2:
                    trade.outcome = "TP2"; trade.pnl_r = 2.0; trade.candles_held = i + 1; return
                if candle["high"] >= trade.tp1:
                    trade.outcome = "TP1"; trade.pnl_r = 1.0; trade.candles_held = i + 1; return
            elif trade.direction == "SELL":
                if candle["high"] >= trade.sl:
                    trade.outcome = "SL"; trade.pnl_r = -1.0; trade.candles_held = i + 1; return
                if trade.tp3 and candle["low"] <= trade.tp3:
                    trade.outcome = "TP3"; trade.pnl_r = (trade.entry - trade.tp3) / sl_dist; trade.candles_held = i + 1; return
                if candle["low"] <= trade.tp2:
                    trade.outcome = "TP2"; trade.pnl_r = 2.0; trade.candles_held = i + 1; return
                if candle["low"] <= trade.tp1:
                    trade.outcome = "TP1"; trade.pnl_r = 1.0; trade.candles_held = i + 1; return
        trade.outcome = "OPEN"; trade.pnl_r = 0.0; trade.candles_held = len(future)

    def _print_summary(self):
        if not self.trades:
            log.info("backtest_no_signals", symbol=self.symbol, days=self.days)
            print("\n⚠️  No signals generated during backtest period.\n")
            return

        total   = len(self.trades)
        wins    = sum(1 for t in self.trades if t.pnl_r > 0)
        losses  = sum(1 for t in self.trades if t.outcome == "SL")
        open_   = sum(1 for t in self.trades if t.outcome == "OPEN")
        closed  = total - open_
        total_r = sum(t.pnl_r for t in self.trades if t.outcome != "OPEN")
        avg_r   = total_r / closed if closed > 0 else 0
        wr      = wins / closed * 100 if closed > 0 else 0

        high_conf = [t for t in self.trades if t.confidence == "HIGH"]
        hc_wins   = sum(1 for t in high_conf if t.pnl_r > 0)
        hc_closed = sum(1 for t in high_conf if t.outcome != "OPEN")
        hc_wr     = hc_wins / hc_closed * 100 if hc_closed > 0 else 0

        log.info("backtest_complete",
                 symbol=self.symbol, days=self.days,
                 total=total, wins=wins, losses=losses, open_trades=open_,
                 win_rate_pct=round(wr, 1), avg_r=round(avg_r, 2), total_r=round(total_r, 2),
                 high_conf_signals=len(high_conf), high_conf_wr=round(hc_wr, 1))

        print(f"""
╔══════════════════════════════════════════╗
║     MarketMate Backtest Results          ║
╠══════════════════════════════════════════╣
║  Symbol:   {self.symbol:<30} ║
║  Period:   {self.days} days{' ' * 25}║
╠══════════════════════════════════════════╣
║  Total Signals:  {total:<23} ║
║  Wins:           {wins:<23} ║
║  Losses (SL):    {losses:<23} ║
║  Open (expired): {open_:<23} ║
║  Win Rate:       {wr:.1f}%{' ' * 21}║
║  Avg R per trade:{avg_r:.2f}R{' ' * 20}║
║  Total R:        {total_r:.2f}R{' ' * 19}║
╠══════════════════════════════════════════╣
║  HIGH Confidence: {len(high_conf)} signals, {hc_wr:.1f}% WR{' ' * 10}║
╚══════════════════════════════════════════╝
""")

    def _save_csv(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        path = os.path.join(OUTPUT_DIR, f"{self.symbol}_{date_str}.csv")
        if not self.trades:
            return
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=asdict(self.trades[0]).keys())
            writer.writeheader()
            for trade in self.trades:
                writer.writerow(asdict(trade))
        print(f"  📄 Trade log saved: {path}\n")


def _assert_no_lookahead(df, current_ts, label):
    if df.empty:
        return
    max_ts = df["timestamp"].max()
    assert max_ts < current_ts, f"Look-ahead violation in {label}: {max_ts} >= {current_ts}"


def _align_daily(daily, current_ts):
    mask = daily["timestamp"] < current_ts
    result = daily[mask].copy()
    return result if not result.empty else None


def _align_ltf(ltf, current_ts, limit=50):
    mask = ltf["timestamp"] < current_ts
    result = ltf[mask].tail(limit).copy()
    return result if len(result) >= 10 else None


async def _run_cli():
    parser = argparse.ArgumentParser(description="MarketMate Backtester")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--days", type=int, default=90)
    args = parser.parse_args()
    bt = Backtester(symbol=args.symbol, days=args.days)
    await bt.run()


if __name__ == "__main__":
    asyncio.run(_run_cli())
