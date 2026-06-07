"""
Paper Trading Framework
═══════════════════════
Runs the deployment candidate stack in paper mode:
  - 8-Gate SMC (all instruments)
  - Risk Engine (6 protection modules)

Rules:
  1. NO parameter changes during the test period
  2. Every modification resets the clock
  3. Track 30-day, 60-day, 90-day milestones
  4. Record every signal, every block, every fill

This is NOT a backtest. This is forward testing with real-time
data to verify the edge survives out-of-sample.

Usage:
  tracker = PaperTradeTracker()
  tracker.record_signal(signal, regime)
  tracker.record_fill(signal, fill_price, fill_time)
  tracker.record_block(signal, reason)
  tracker.generate_report()
"""

import json
import numpy as np
import pandas as pd
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path


@dataclass
class PaperSignal:
    """A signal generated during paper trading."""
    signal_id: str
    strategy_id: str
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    tp2: float
    tp3: float
    rr_ratio: float
    timestamp: str
    regime: str = ""
    risk_mult: float = 1.0
    status: str = "PENDING"  # PENDING, FILLED, BLOCKED, EXPIRED, CLOSED
    block_reason: str = ""
    fill_price: float = 0.0
    fill_time: str = ""
    exit_price: float = 0.0
    exit_time: str = ""
    exit_reason: str = ""
    pnl_r: float = 0.0
    pnl_pct: float = 0.0
    duration_hours: float = 0.0


class PaperTradeTracker:
    """
    Tracks paper trading signals, fills, and performance.
    Enforces strict no-modification rules.
    """

    def __init__(self, config: Dict = None, save_path: str = None):
        self.config = config or self.default_config()
        self.save_path = Path(save_path or "/home/z/my-project/paper_trade/tracker.json")
        self.save_path.parent.mkdir(parents=True, exist_ok=True)

        self.signals: List[PaperSignal] = []
        self.start_date: Optional[str] = None
        self.last_modified: Optional[str] = None
        self.parameter_hash: str = ""  # Hash of initial parameters
        self.modifications: List[Dict] = []  # Track any changes
        self.milestones: Dict[str, Dict] = {}

        # Load existing state if available
        self._load_state()

    @staticmethod
    def default_config() -> Dict:
        return {
            "strategies": ["SMC_8G"],
            "instruments": [
                'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD',
                'AUDUSD', 'NZDUSD', 'EURJPY', 'GBPJPY', 'EURGBP',
                'XAUUSD', 'XAGUSD', 'BTCUSD', 'ETHUSD', 'SOLUSD',
                'US500', 'NAS100', 'US30'
            ],
            "starting_balance": 1000.0,
            "risk_per_trade_pct": 1.0,
            "milestone_days": [30, 60, 90],
        }

    def record_signal(self, strategy_id: str, symbol: str, direction: str,
                      entry_price: float, sl: float, tp: float,
                      tp2: float = 0, tp3: float = 0, rr: float = 0,
                      regime: str = "", risk_mult: float = 1.0) -> str:
        """Record a new signal. Returns signal ID."""
        signal_id = f"{strategy_id}_{symbol}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        signal = PaperSignal(
            signal_id=signal_id,
            strategy_id=strategy_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=sl,
            take_profit=tp,
            tp2=tp2,
            tp3=tp3,
            rr_ratio=rr,
            timestamp=datetime.utcnow().isoformat(),
            regime=regime,
            risk_mult=risk_mult,
        )

        if self.start_date is None:
            self.start_date = datetime.utcnow().isoformat()

        self.signals.append(signal)
        self._save_state()
        return signal_id

    def record_fill(self, signal_id: str, fill_price: float, fill_time: str = None):
        """Record that a signal was filled."""
        for sig in self.signals:
            if sig.signal_id == signal_id:
                sig.status = "FILLED"
                sig.fill_price = fill_price
                sig.fill_time = fill_time or datetime.utcnow().isoformat()
                break
        self._save_state()

    def record_block(self, signal_id: str, reason: str):
        """Record that a signal was blocked by risk engine."""
        for sig in self.signals:
            if sig.signal_id == signal_id:
                sig.status = "BLOCKED"
                sig.block_reason = reason
                break
        self._save_state()

    def record_exit(self, signal_id: str, exit_price: float, exit_reason: str,
                    pnl_r: float = 0, pnl_pct: float = 0, duration_hours: float = 0):
        """Record a trade exit."""
        for sig in self.signals:
            if sig.signal_id == signal_id:
                sig.status = "CLOSED"
                sig.exit_price = exit_price
                sig.exit_time = datetime.utcnow().isoformat()
                sig.exit_reason = exit_reason
                sig.pnl_r = pnl_r
                sig.pnl_pct = pnl_pct
                sig.duration_hours = duration_hours
                break
        self._save_state()

    def record_modification(self, description: str, old_value: Any, new_value: Any):
        """
        Record a parameter modification. THIS RESETS THE CLOCK.
        """
        self.modifications.append({
            "timestamp": datetime.utcnow().isoformat(),
            "description": description,
            "old_value": str(old_value),
            "new_value": str(new_value),
            "warning": "CLOCK RESET — milestone tracking restarted",
        })
        self.start_date = datetime.utcnow().isoformat()
        self.last_modified = datetime.utcnow().isoformat()
        self.milestones = {}
        self._save_state()

    def generate_report(self) -> Dict:
        """Generate paper trading report with milestone tracking."""
        if self.start_date is None:
            return {"status": "NO_DATA", "message": "No signals recorded yet"}

        start = datetime.fromisoformat(self.start_date.replace('Z', '+00:00').replace('+00:00', ''))
        now = datetime.utcnow()
        days_elapsed = (now - start).days

        filled_signals = [s for s in self.signals if s.status == "FILLED"]
        closed_signals = [s for s in self.signals if s.status == "CLOSED"]
        blocked_signals = [s for s in self.signals if s.status == "BLOCKED"]
        pending_signals = [s for s in self.signals if s.status == "PENDING"]

        # Performance metrics
        if closed_signals:
            pnls = [s.pnl_r for s in closed_signals]
            wins = [p for p in pnls if p > 0]
            losses = [abs(p) for p in pnls if p < 0]
            pf = sum(wins) / sum(losses) if sum(losses) > 0 else 0
            wr = len(wins) / len(pnls)
            avg_r = np.mean(pnls)
        else:
            pf = wr = avg_r = 0

        # Milestones
        for milestone_day in self.config["milestone_days"]:
            if days_elapsed >= milestone_day and f"day_{milestone_day}" not in self.milestones:
                # Calculate milestone stats
                milestone_key = f"day_{milestone_day}"
                cutoff = start + timedelta(days=milestone_day)
                milestone_trades = [s for s in closed_signals
                                   if s.exit_time and datetime.fromisoformat(s.exit_time.replace('Z', '').replace('+00:00', '')) <= cutoff]

                if milestone_trades:
                    mpnls = [s.pnl_r for s in milestone_trades]
                    mwins = [p for p in mpnls if p > 0]
                    mlosses = [abs(p) for p in mpnls if p < 0]
                    mpf = sum(mwins) / sum(mlosses) if sum(mlosses) > 0 else 0

                    self.milestones[milestone_key] = {
                        "date_reached": cutoff.isoformat(),
                        "trades": len(milestone_trades),
                        "pf": round(mpf, 4),
                        "wr": round(len(mwins) / len(mpnls), 4) if mpnls else 0,
                        "avg_r": round(np.mean(mpnls), 4) if mpnls else 0,
                        "cum_r": round(sum(mpnls), 2),
                    }

        # Per-strategy breakdown
        strat_stats = {}
        for sig in closed_signals:
            sid = sig.strategy_id
            if sid not in strat_stats:
                strat_stats[sid] = []
            strat_stats[sid].append(sig.pnl_r)

        strat_summary = {}
        for sid, pnls in strat_stats.items():
            wins = [p for p in pnls if p > 0]
            losses = [abs(p) for p in pnls if p < 0]
            strat_summary[sid] = {
                "trades": len(pnls),
                "pf": round(sum(wins) / sum(losses), 4) if sum(losses) > 0 else 0,
                "wr": round(len(wins) / len(pnls), 4),
                "avg_r": round(np.mean(pnls), 4),
            }

        # Per-instrument breakdown
        inst_stats = {}
        for sig in closed_signals:
            sym = sig.symbol
            if sym not in inst_stats:
                inst_stats[sym] = []
            inst_stats[sym].append(sig.pnl_r)

        inst_summary = {}
        for sym, pnls in inst_stats.items():
            wins = [p for p in pnls if p > 0]
            losses = [abs(p) for p in pnls if p < 0]
            inst_summary[sym] = {
                "trades": len(pnls),
                "pf": round(sum(wins) / sum(losses), 4) if sum(losses) > 0 else 0,
                "wr": round(len(wins) / len(pnls), 4),
                "avg_r": round(np.mean(pnls), 4),
            }

        # Risk engine stats
        block_reasons = {}
        for sig in blocked_signals:
            reason = sig.block_reason.split(":")[0] if ":" in sig.block_reason else sig.block_reason
            block_reasons[reason] = block_reasons.get(reason, 0) + 1

        report = {
            "status": "ACTIVE" if days_elapsed < 90 else "MATURE",
            "start_date": self.start_date,
            "days_elapsed": days_elapsed,
            "last_modification": self.last_modified,
            "modifications_count": len(self.modifications),
            "clock_reset": len(self.modifications) > 0,
            "summary": {
                "total_signals": len(self.signals),
                "filled": len(filled_signals),
                "closed": len(closed_signals),
                "blocked": len(blocked_signals),
                "pending": len(pending_signals),
                "portfolio_pf": round(pf, 4),
                "portfolio_wr": round(wr, 4),
                "portfolio_avg_r": round(avg_r, 4),
                "cum_pnl_r": round(sum(s.pnl_r for s in closed_signals), 2),
            },
            "strategy_breakdown": strat_summary,
            "instrument_breakdown": inst_summary,
            "risk_engine_blocks": block_reasons,
            "milestones": self.milestones,
            "deployment_checklist": {
                "30_day_positive": self.milestones.get("day_30", {}).get("avg_r", 0) > 0 if "day_30" in self.milestones else None,
                "60_day_positive": self.milestones.get("day_60", {}).get("avg_r", 0) > 0 if "day_60" in self.milestones else None,
                "90_day_positive": self.milestones.get("day_90", {}).get("avg_r", 0) > 0 if "day_90" in self.milestones else None,
                "pf_above_1_1": pf > 1.1 if closed_signals else None,
                "no_parameter_changes": len(self.modifications) == 0,
            },
        }

        self._save_state()
        return report

    def _save_state(self):
        """Save tracker state to disk."""
        state = {
            "start_date": self.start_date,
            "last_modified": self.last_modified,
            "parameter_hash": self.parameter_hash,
            "modifications": self.modifications,
            "milestones": self.milestones,
            "config": self.config,
            "signals": [asdict(s) for s in self.signals],
        }
        self.save_path.write_text(json.dumps(state, indent=2, default=str))

    def _load_state(self):
        """Load tracker state from disk."""
        if not self.save_path.exists():
            return
        try:
            state = json.loads(self.save_path.read_text())
            self.start_date = state.get("start_date")
            self.last_modified = state.get("last_modified")
            self.parameter_hash = state.get("parameter_hash", "")
            self.modifications = state.get("modifications", [])
            self.milestones = state.get("milestones", {})
            self.config = state.get("config", self.config)
            self.signals = [PaperSignal(**s) for s in state.get("signals", [])]
        except Exception:
            pass  # Start fresh if corrupted
