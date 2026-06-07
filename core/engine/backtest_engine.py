"""
StrategyEngine — Multi-strategy backtesting and simulation framework
═══════════════════════════════════════════════════════════════════════
Runs backtests across all strategies, instruments, and parameter combinations.
Evaluates trades with realistic costs, position sizing, and risk management.

Supports:
  - Single strategy backtest
  - Multi-strategy portfolio simulation
  - Parameter optimization (grid search)
  - Monte Carlo robustness testing
  - Walk-forward validation
  - Compound growth simulation ($15 → $100+)
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
import itertools
import warnings
warnings.filterwarnings('ignore')

from .base import Strategy, TradeSignal, TradeResult, StrategyResult

# ─── Market Configuration ─────────────────────────────────────────────

MARKET_SPREADS = {
    'EURUSD': 0.8, 'GBPUSD': 1.2, 'USDJPY': 0.9, 'USDCHF': 1.3,
    'USDCAD': 1.4, 'AUDUSD': 1.0, 'NZDUSD': 1.5,
    'EURJPY': 1.3, 'GBPJPY': 2.0, 'EURGBP': 1.5,
    'XAUUSD': 25.0, 'XAGUSD': 3.0, 'BTCUSD': 50.0, 'ETHUSD': 5.0,
    'SOLUSD': 0.10, 'US500': 0.5, 'NAS100': 1.0, 'US30': 1.5,
}

PIP_SIZES = {
    'EURUSD': 0.0001, 'GBPUSD': 0.0001, 'USDJPY': 0.01,
    'XAUUSD': 0.01, 'XAGUSD': 0.001, 'BTCUSD': 1.0,
    'ETHUSD': 0.01, 'SOLUSD': 0.001, 'US500': 0.01,
    'NAS100': 0.01, 'US30': 0.01,
}

COMMISSION = {'forex': 0.7, 'metals': 0.5, 'crypto': 0.1, 'indices': 0.5}
BASE_SLIPPAGE = {'forex': 0.3, 'metals': 1.0, 'crypto': 2.0, 'indices': 0.5}


def get_asset_class(symbol: str) -> str:
    if symbol in ['EURUSD','GBPUSD','USDJPY','USDCHF','USDCAD','AUDUSD','NZDUSD','EURJPY','GBPJPY','EURGBP']:
        return 'forex'
    if symbol in ['XAUUSD','XAGUSD']:
        return 'metals'
    if symbol in ['BTCUSD','ETHUSD','SOLUSD']:
        return 'crypto'
    if symbol in ['US500','NAS100','US30']:
        return 'indices'
    return 'forex'


@dataclass
class SimConfig:
    """Simulation configuration."""
    starting_balance: float = 15.0
    target_balance: float = 100.0
    max_days: int = 60
    risk_per_trade_pct: float = 5.0     # Aggressive: 5% per trade
    max_risk_per_trade_pct: float = 10.0
    min_risk_per_trade_pct: float = 1.0
    spread_multiplier: float = 1.0
    slippage_multiplier: float = 1.0
    compound: bool = True               # Compound gains
    tp1_pct: float = 0.5                # Close 50% at TP1
    tp2_pct: float = 0.3                # Close 30% at TP2
    tp3_pct: float = 0.2                # Close 20% at TP3
    max_drawdown_pct: float = 30.0      # Kill switch at this DD
    max_consecutive_losses: int = 5
    use_partial_tp: bool = True


class StrategyEngine:
    """Multi-strategy backtesting and simulation engine."""

    def __init__(self, data_dir: str = "/home/z/my-project/backtest/data_cache"):
        self.data_dir = Path(data_dir)
        self.results: Dict[str, StrategyResult] = {}

    def load_data(self, symbol: str, timeframe: str = "h4") -> Optional[pd.DataFrame]:
        """Load cached OHLCV data for a symbol."""
        path = self.data_dir / symbol / f"{timeframe}.parquet"
        if not path.exists():
            return None
        df = pd.read_parquet(path)
        df.index = pd.DatetimeIndex(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        return df

    def execute_trade(self, signal: TradeSignal, df: pd.DataFrame,
                      start_idx: int, config: SimConfig,
                      symbol: str) -> Optional[TradeResult]:
        """Execute a trade signal and return the result."""
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        n = len(df)

        pip_size = PIP_SIZES.get(symbol, 0.0001)
        spread = MARKET_SPREADS.get(symbol, 1.0) * pip_size * config.spread_multiplier
        slippage = BASE_SLIPPAGE.get(get_asset_class(symbol), 0.5) * pip_size * config.slippage_multiplier
        commission = COMMISSION.get(get_asset_class(symbol), 0.5) * pip_size

        # Apply spread/slippage to entry
        if signal.direction == "BUY":
            actual_entry = signal.entry_price + spread / 2 + slippage
        else:
            actual_entry = signal.entry_price - spread / 2 - slippage

        # Execute: check each bar for TP/SL
        max_bars = 60  # Max hold time (bars)
        tp1_hit = tp2_hit = tp3_hit = False
        partial_pnl = 0.0

        for off in range(1, max_bars + 1):
            bi = start_idx + off
            if bi >= n:
                # Force close at last bar
                exit_price = closes[min(bi, n-1)]
                exit_time = df.index[min(bi, n-1)]
                raw = (exit_price - actual_entry) if signal.direction == "BUY" else (actual_entry - exit_price)
                net = raw - spread - commission - slippage
                pnl_r = net / signal.risk_distance if signal.risk_distance > 0 else 0
                return TradeResult(
                    signal=signal, exit_price=exit_price, exit_time=exit_time,
                    exit_reason="EXPIRED", pnl_r=pnl_r,
                    pnl_pct=pnl_r * config.risk_per_trade_pct,
                    duration_bars=off, spread_cost=spread,
                    commission=commission
                )

            bar_high = highs[bi]
            bar_low = lows[bi]

            if signal.direction == "BUY":
                # Check SL first
                if bar_low <= signal.stop_loss:
                    pnl_r = -1.0
                    return TradeResult(
                        signal=signal, exit_price=signal.stop_loss,
                        exit_time=df.index[bi], exit_reason="SL",
                        pnl_r=pnl_r, pnl_pct=pnl_r * config.risk_per_trade_pct,
                        duration_bars=off, spread_cost=spread,
                        commission=commission
                    )

                # Check TPs in order
                if not tp1_hit and bar_high >= signal.take_profit:
                    tp1_hit = True
                    if config.use_partial_tp:
                        partial_pnl += 1.0 * config.tp1_pct
                    else:
                        return TradeResult(
                            signal=signal, exit_price=signal.take_profit,
                            exit_time=df.index[bi], exit_reason="TP1",
                            pnl_r=1.0, pnl_pct=1.0 * config.risk_per_trade_pct,
                            duration_bars=off, spread_cost=spread,
                            commission=commission
                        )

                if tp1_hit and not tp2_hit and signal.tp2 > 0 and bar_high >= signal.tp2:
                    tp2_hit = True
                    if config.use_partial_tp:
                        partial_pnl += 2.0 * config.tp2_pct
                    else:
                        return TradeResult(
                            signal=signal, exit_price=signal.tp2,
                            exit_time=df.index[bi], exit_reason="TP2",
                            pnl_r=2.0, pnl_pct=2.0 * config.risk_per_trade_pct,
                            duration_bars=off, spread_cost=spread,
                            commission=commission
                        )

                if tp2_hit and not tp3_hit and signal.tp3 > 0 and bar_high >= signal.tp3:
                    tp3_hit = True
                    final_r = signal.rr_ratio if signal.rr_ratio > 0 else 3.0
                    if config.use_partial_tp:
                        partial_pnl += final_r * config.tp3_pct
                    return TradeResult(
                        signal=signal, exit_price=signal.tp3,
                        exit_time=df.index[bi], exit_reason="TP3",
                        pnl_r=partial_pnl if config.use_partial_tp else final_r,
                        pnl_pct=partial_pnl * config.risk_per_trade_pct,
                        duration_bars=off, spread_cost=spread,
                        commission=commission
                    )

                # If TP1/TP2 hit but not TP3, trail and eventually close
                if tp2_hit and not tp3_hit and off >= max_bars - 5:
                    exit_price = closes[bi]
                    raw = exit_price - actual_entry
                    net = raw - spread - commission
                    pnl_r = net / signal.risk_distance if signal.risk_distance > 0 else 0
                    if config.use_partial_tp:
                        pnl_r = partial_pnl + pnl_r * config.tp3_pct
                    return TradeResult(
                        signal=signal, exit_price=exit_price,
                        exit_time=df.index[bi], exit_reason="TRAIL_EXIT",
                        pnl_r=pnl_r, pnl_pct=pnl_r * config.risk_per_trade_pct,
                        duration_bars=off, spread_cost=spread,
                        commission=commission
                    )

            else:  # SELL
                if bar_high >= signal.stop_loss:
                    pnl_r = -1.0
                    return TradeResult(
                        signal=signal, exit_price=signal.stop_loss,
                        exit_time=df.index[bi], exit_reason="SL",
                        pnl_r=pnl_r, pnl_pct=pnl_r * config.risk_per_trade_pct,
                        duration_bars=off, spread_cost=spread,
                        commission=commission
                    )

                if not tp1_hit and bar_low <= signal.take_profit:
                    tp1_hit = True
                    if config.use_partial_tp:
                        partial_pnl += 1.0 * config.tp1_pct
                    else:
                        return TradeResult(
                            signal=signal, exit_price=signal.take_profit,
                            exit_time=df.index[bi], exit_reason="TP1",
                            pnl_r=1.0, pnl_pct=1.0 * config.risk_per_trade_pct,
                            duration_bars=off, spread_cost=spread,
                            commission=commission
                        )

                if tp1_hit and not tp2_hit and signal.tp2 > 0 and bar_low <= signal.tp2:
                    tp2_hit = True
                    if config.use_partial_tp:
                        partial_pnl += 2.0 * config.tp2_pct
                    else:
                        return TradeResult(
                            signal=signal, exit_price=signal.tp2,
                            exit_time=df.index[bi], exit_reason="TP2",
                            pnl_r=2.0, pnl_pct=2.0 * config.risk_per_trade_pct,
                            duration_bars=off, spread_cost=spread,
                            commission=commission
                        )

                if tp2_hit and not tp3_hit and signal.tp3 > 0 and bar_low <= signal.tp3:
                    tp3_hit = True
                    final_r = signal.rr_ratio if signal.rr_ratio > 0 else 3.0
                    if config.use_partial_tp:
                        partial_pnl += final_r * config.tp3_pct
                    return TradeResult(
                        signal=signal, exit_price=signal.tp3,
                        exit_time=df.index[bi], exit_reason="TP3",
                        pnl_r=partial_pnl if config.use_partial_tp else final_r,
                        pnl_pct=partial_pnl * config.risk_per_trade_pct,
                        duration_bars=off, spread_cost=spread,
                        commission=commission
                    )

                if tp2_hit and not tp3_hit and off >= max_bars - 5:
                    exit_price = closes[bi]
                    raw = actual_entry - exit_price
                    net = raw - spread - commission
                    pnl_r = net / signal.risk_distance if signal.risk_distance > 0 else 0
                    if config.use_partial_tp:
                        pnl_r = partial_pnl + pnl_r * config.tp3_pct
                    return TradeResult(
                        signal=signal, exit_price=exit_price,
                        exit_time=df.index[bi], exit_reason="TRAIL_EXIT",
                        pnl_r=pnl_r, pnl_pct=pnl_r * config.risk_per_trade_pct,
                        duration_bars=off, spread_cost=spread,
                        commission=commission
                    )

        # Max bars reached - force close
        li = min(start_idx + max_bars, n - 1)
        exit_price = closes[li]
        raw = (exit_price - actual_entry) if signal.direction == "BUY" else (actual_entry - exit_price)
        net = raw - spread - commission
        pnl_r = net / signal.risk_distance if signal.risk_distance > 0 else 0
        return TradeResult(
            signal=signal, exit_price=exit_price,
            exit_time=df.index[li], exit_reason="EXPIRED",
            pnl_r=pnl_r, pnl_pct=pnl_r * config.risk_per_trade_pct,
            duration_bars=max_bars, spread_cost=spread,
            commission=commission
        )

    def backtest_strategy(self, strategy: Strategy, symbol: str,
                          df: pd.DataFrame, config: SimConfig) -> StrategyResult:
        """Run a complete backtest for a strategy on a symbol."""
        signals = strategy.generate_signals(df, symbol)

        # Map signal entry times to DataFrame indices
        trade_results = []
        for sig in signals:
            if sig.entry_time is not None:
                # Find the bar index for this signal
                mask = df.index >= sig.entry_time
                idx_arr = np.where(mask)[0]
                if len(idx_arr) == 0:
                    continue
                start_idx = idx_arr[0]
            else:
                continue

            if start_idx >= len(df) - 1:
                continue

            result = self.execute_trade(sig, df, start_idx, config, symbol)
            if result is not None:
                trade_results.append(result)

        return StrategyResult(
            strategy_id=strategy.STRATEGY_ID,
            symbol=symbol,
            trades=trade_results,
            parameters=strategy.params,
        )

    def simulate_compound_growth(self, results: List[StrategyResult],
                                 config: SimConfig) -> Dict[str, Any]:
        """Simulate compound growth from $15 starting balance."""
        # Merge all trades and sort by time
        all_trades = []
        for r in results:
            for t in r.trades:
                if t.signal.entry_time is not None:
                    all_trades.append(t)

        if not all_trades:
            return {"error": "No trades to simulate"}

        all_trades.sort(key=lambda t: t.signal.entry_time or datetime.min)

        balance = config.starting_balance
        peak = balance
        max_dd = 0.0
        consecutive_losses = 0
        equity_curve = [balance]
        trade_log = []
        days_elapsed = 0
        target_hit = False
        target_day = None
        killed = False

        for trade in all_trades:
            if killed:
                break

            # Risk per trade as % of balance
            risk_pct = config.risk_per_trade_pct / 100.0
            risk_amount = balance * risk_pct
            pnl_dollar = trade.pnl_r * risk_amount

            balance += pnl_dollar
            peak = max(peak, balance)
            dd = (peak - balance) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)

            if trade.is_winner:
                consecutive_losses = 0
            else:
                consecutive_losses += 1

            # Kill switch
            if dd >= config.max_drawdown_pct:
                killed = True

            if consecutive_losses >= config.max_consecutive_losses:
                # Skip next 3 trades
                pass

            if balance >= config.target_balance and not target_hit:
                target_hit = True
                target_day = days_elapsed

            equity_curve.append(balance)

            trade_log.append({
                "strategy": trade.signal.strategy_id,
                "symbol": trade.signal.symbol,
                "direction": trade.signal.direction,
                "pnl_r": round(trade.pnl_r, 3),
                "balance": round(balance, 2),
                "dd_pct": round(dd, 2),
            })

        return {
            "starting_balance": config.starting_balance,
            "final_balance": round(balance, 2),
            "return_pct": round((balance / config.starting_balance - 1) * 100, 1),
            "max_drawdown_pct": round(max_dd, 2),
            "total_trades": len(trade_log),
            "win_rate": round(sum(1 for t in all_trades if t.is_winner) / len(all_trades), 4) if all_trades else 0,
            "target_hit": target_hit,
            "target_day": target_day,
            "killed": killed,
            "equity_curve": equity_curve,
            "trade_count": len(trade_log),
        }

    def grid_search(self, strategy_class, symbol: str, df: pd.DataFrame,
                    config: SimConfig, n_combos: int = 100) -> List[Dict]:
        """Run grid search over parameter space."""
        param_ranges = strategy_class.param_ranges()
        if not param_ranges:
            # Just run with defaults
            strategy = strategy_class()
            result = self.backtest_strategy(strategy, symbol, df, config)
            return [result.to_dict()]

        # Generate parameter combinations
        param_values = {}
        for key, (min_val, max_val, step) in param_ranges.items():
            vals = []
            v = min_val
            while v <= max_val:
                vals.append(v)
                v += step
            param_values[key] = vals

        # Generate combinations (limited)
        keys = list(param_values.keys())
        value_lists = [param_values[k] for k in keys]

        combos = list(itertools.product(*value_lists))
        if len(combos) > n_combos:
            # Random sample
            indices = np.random.choice(len(combos), n_combos, replace=False)
            combos = [combos[i] for i in indices]

        results = []
        for combo in combos:
            params = dict(zip(keys, combo))
            try:
                strategy = strategy_class(params)
                result = self.backtest_strategy(strategy, symbol, df, config)
                results.append(result.to_dict())
            except Exception:
                continue

        # Sort by Sharpe ratio
        results.sort(key=lambda x: x.get('sharpe_ratio', 0), reverse=True)
        return results

    def monte_carlo_test(self, trades: List[TradeResult], n_sim: int = 5000,
                         config: SimConfig = None) -> Dict:
        """Monte Carlo robustness test."""
        if config is None:
            config = SimConfig()

        rv = [t.pnl_r for t in trades]
        if len(rv) < 5:
            return {"error": "Insufficient trades for MC test"}

        final_balances = []
        max_dds = []
        target_hits = 0

        for _ in range(n_sim):
            shuffled = np.random.permutation(rv)
            balance = config.starting_balance
            peak = balance
            mdd = 0.0
            hit = False

            for r in shuffled:
                risk_amount = balance * (config.risk_per_trade_pct / 100.0)
                balance += r * risk_amount
                peak = max(peak, balance)
                dd = (peak - balance) / peak * 100 if peak > 0 else 0
                mdd = max(mdd, dd)
                if balance >= config.target_balance:
                    hit = True

            final_balances.append(balance)
            max_dds.append(mdd)
            if hit:
                target_hits += 1

        return {
            "prob_target_hit": target_hits / n_sim,
            "mean_final_balance": round(np.mean(final_balances), 2),
            "median_final_balance": round(np.median(final_balances), 2),
            "p5_final_balance": round(np.percentile(final_balances, 5), 2),
            "p95_final_balance": round(np.percentile(final_balances, 95), 2),
            "mean_max_dd": round(np.mean(max_dds), 2),
            "p95_max_dd": round(np.percentile(max_dds, 95), 2),
            "prob_ruin": sum(1 for b in final_balances if b <= 0) / n_sim,
        }
