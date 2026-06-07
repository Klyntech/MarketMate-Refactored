"""
marketmate.mate_ops
───────────────────
MATE-Ops: Autonomous infrastructure intelligence for MarketMate.

5-stage pipeline: Observe → Analyze → Plan → Execute → Verify

Authority levels control what actions the agent may take:
  0 = Read-only (observe, analyze, report)
  1 = Safe operations (restart workers, clear caches, rotate logs)
  2 = Destructive (requires explicit human approval)

Every state-modifying action passes through the PermissionGate
safety layer, which validates authority levels and logs every
decision — including denied actions.

Phase 2 additions:
  - AnomalyDetector: Statistical anomaly detection with rolling baselines
  - CircuitBreaker: Auto-break connections to failing services
  - AutoRemediator: Safe Level 1 auto-remediation with cooldown policies
  - ObservationHistory: Persistent history with pattern matching
  - EscalationToken: Time-limited authority escalation with auto-deescalation
  - Sanitizer / RateLimiter: Message sanitization and rate limiting
"""

from marketmate.mate_ops.agent import MATEOpsAgent
from marketmate.mate_ops.permission_gate import AuthorityLevel, EscalationToken, PermissionGate

__all__ = [
    "MATEOpsAgent",
    "AuthorityLevel",
    "EscalationToken",
    "PermissionGate",
]
