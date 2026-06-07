"""
marketmate.intelligence.vinni
─────────────────────────────
VINNI: Market Data Intelligence Monitor

Observation ONLY. Does NOT fix things. Does NOT restart servers.
Does NOT deploy code. Does NOT execute shell commands.
Does NOT control systems directly.

Verbs: Observe, Analyze, Validate, Report, Recommend.
NOT: Execute, Deploy, Restart, Modify, Control.

Position in pipeline:
  RAW DATA → PRISM (validate) → [VINNI] (observe) → ATLAS → VANTA → NOVA

Created: 2026-05-29
"""

from marketmate.intelligence.vinni.monitor import VinniMonitor, VinniDiagnostic

__all__ = ["VinniMonitor", "VinniDiagnostic"]
