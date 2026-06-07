# Risk Engine

**The risk engine is a portfolio governor, NOT an alpha generator.**

It runs BEFORE any signal is executed. Every signal must pass through all six protection layers.

## Architecture

```
Signal Generated
      │
      ▼
┌─────────────────────┐
│  0. Global Halt?    │ ← If already halted, block immediately
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  1. DCB             │ ← Drawdown Circuit Breaker
│  (MM-004)           │   Daily -3%, Weekly -7%, Monthly -15%
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  2. CLP             │ ← Consecutive Loss Protocol
│  (MM-008)           │   2-loss cooldown, 3-loss reduce, 5-loss halt
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  3. ECB             │ ← Equity Curve Brake
│  (MM-011)           │   Half size below SMA, halt at -20%
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  4. PWP             │ ← Pre-Weekend Protocol
│  (MM-006)           │   Thu 20:00+, Fri 18:00+, Sun pre-21:00
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  5. TMG             │ ← Thin Market Guard
│  (MM-007)           │   Spread > 2× median, low ATR, blocked hours
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  6. CCE             │ ← Correlation Cap
│  (MM-010)           │   Correlation > 0.7, max 2 positions
└─────────┬───────────┘
          │
          ▼
    ✅ ALLOWED (with size_multiplier)
```

## Usage

```python
from risk_engine.risk_manager import RiskManager

rm = RiskManager()

# Pre-trade check
allowed, reason, size_multiplier = rm.check_signal(
    signal,
    current_spread=1.2,
    current_atr=0.0035,
    avg_atr=0.0040,
    current_hour=14,
    current_weekday=2,
)

if not allowed:
    log.warning(f"Signal blocked: {reason}")
else:
    execute_with_size(base_size * size_multiplier)

# Post-trade update
rm.update_after_trade(trade_result)

# Periodic resets
rm.reset_daily()    # 00:00 GMT
rm.reset_weekly()   # Monday 00:00 GMT
rm.reset_monthly()  # 1st of month 00:00 GMT
```

## Configuration

All thresholds are configurable via the `config` dict:

```python
config = {
    "daily_loss_limit_pct": 3.0,
    "weekly_loss_limit_pct": 7.0,
    "monthly_loss_limit_pct": 15.0,
    "pre_weekend_close_hour": 20,
    "no_entry_friday_after_hour": 18,
    "no_entry_sunday_before_hour": 21,
    "spread_mult_threshold": 2.0,
    "atr_session_pct_threshold": 30,
    "blocked_hours": [(0, 6), (12, 13), (20, 23)],
    "strategy_cooldown_after_losses": 2,
    "portfolio_reduction_after_losses": 3,
    "portfolio_halt_after_losses": 5,
    "reduction_pct": 30,
    "restore_after_wins": 3,
    "max_correlation": 0.7,
    "max_open_positions": 2,
    "ecb_window": 10,
    "ecb_drop_pct": 20,
    "risk_per_trade_pct": 5.0,
}
```

## State Persistence

The risk engine state (balance, PnL, drawdown, cooldowns) can be persisted to JSON:

```python
rm.save_state("risk_state.json")
rm.load_state("risk_state.json")
```
