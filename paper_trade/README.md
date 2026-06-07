# Paper Trading Framework

**This is NOT a backtest. This is forward testing with real-time data to verify the edge survives out-of-sample.**

## Deployment Stack

| Component | Status | Notes |
|-----------|--------|-------|
| 8-Gate SMC | Active | All instruments |
| Risk Engine | Active | 6 protection modules |
| Regime Filter | Active | Block unfavorable regimes |

## Rules

1. **NO parameter changes** during the test period
2. Every modification **resets the clock**
3. Track every signal, every block, every fill
4. 30-day, 60-day, 90-day milestones

## Usage

```python
from paper_trade.tracker import PaperTradeTracker

tracker = PaperTradeTracker()

# Record a signal
signal_id = tracker.record_signal(
    strategy_id="SMC_8G",
    symbol="XAUUSD",
    direction="BUY",
    entry_price=2345.50,
    sl=2338.00,
    tp=2354.50,
    rr=2.1,
    regime="TRENDING + NORMAL_VOL",
    risk_mult=1.0
)

# Record fill
tracker.record_fill(signal_id, fill_price=2345.60)

# Record risk engine block
tracker.record_block(signal_id, "DCB: Daily drawdown limit reached")

# Record exit
tracker.record_exit(signal_id, exit_price=2354.50, exit_reason="TP1", pnl_r=1.0)

# Generate report
report = tracker.generate_report()
```

## Deployment Checklist

| Milestone | Criteria | Status |
|-----------|----------|--------|
| 30-day | Positive avg R | — |
| 60-day | Positive avg R | — |
| 90-day | Positive avg R | — |
| PF | > 1.1 | — |
| No modifications | 0 changes | — |

## Warning

If ANY parameter is modified during the test period, the clock resets to Day 0. This includes:
- Strategy parameters (ATR periods, RR thresholds, etc.)
- Risk engine thresholds
- Instrument lists
- Session hours

Each modification is logged with timestamp, old value, and new value.
