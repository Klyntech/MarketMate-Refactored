# Regime Detection Engine

**The highest-ROI project in MarketMate.**

A mediocre strategy becomes excellent when deployed only in its favorable regime.

## Regime Classifications

| Regime | Description | Favorable For |
|--------|-------------|---------------|
| TRENDING | Strong directional move | Trend-following, SMC |
| RANGING | Mean-reverting | Gap fades, bounces, reversals |
| HIGH_VOL | Elevated volatility | Wider stops, reduced size |
| LOW_VOL | Compressed volatility | Breakouts, tighter stops |
| RISK_ON | Equities/crypto rising | Long bias strategies |
| RISK_OFF | Flight to safety | Short/hedge strategies |

## Key Finding

| Strategy | RANGING/LOW_VOL | TRENDING/HIGH_VOL |
|----------|----------------|-------------------|
| MM-002 | PF 3.29 (EURUSD) | PF 0.62 |
| SMC 8-Gate | Works all regimes | Works all regimes (best here) |

## Usage

```python
from regime.regime_detector import RegimeDetector

detector = RegimeDetector()
regime = detector.classify(df, current_bar_index)

# Check if regime is favorable for a strategy type
if regime.is_favorable_for("mean_reversion"):
    # Allow gap fade signals
    
# Get position sizing multiplier
risk_mult = regime.recommended_risk_mult()
```

## Detection Methods

1. **ADX-derived trend strength** — Primary regime classification
2. **ATR percentile** — Volatility regime (HIGH_VOL/LOW_VOL/NORMAL_VOL)
3. **Price vs EMA direction** — Risk appetite (RISK_ON/RISK_OFF/NEUTRAL)
4. **Cross-validation** — Higher confidence when trend and volatility agree

## Classification Confidence

| Combination | Confidence |
|-------------|-----------|
| TRENDING + NORMAL/HIGH_VOL | 0.8 |
| RANGING + LOW/NORMAL_VOL | 0.8 |
| MIXED | 0.3 |
| TRENDING + LOW_VOL | 0.4 (unusual) |

## Performance by Regime

The `regime_performance_table()` method builds a table showing strategy performance broken down by regime. This is critical for determining when a strategy should be active.
