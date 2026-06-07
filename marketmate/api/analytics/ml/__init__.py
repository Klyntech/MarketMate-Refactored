"""
marketmate.analytics.ml
───────────────────────
Experimental ML module — stubs for future ML features.

IMPORTANT: ML stubs must NEVER be in the import path of production code.
They subscribe to EventBus events independently and operate as optional
sidecar processors. If the model fails to load or is not configured,
all functionality falls back gracefully to static/default behaviour.

Modules:
  ranking       — Signal ranking model stub
  scoring       — Adaptive scoring stub
  reinforcement — RL risk management stub
  prediction    — Price prediction stub
"""
