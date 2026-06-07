"""
marketmate/mate_ops/tools.py
─────────────────────────────
MATE-Ops tool definitions for the LLM agent.

These tools are registered with the MATE Agent's tool-calling
interface so the LLM can invoke monitoring and diagnostic actions.

Each tool is an OpenAI-format function definition with:
  - name:         Action identifier (matches PermissionGate ACTION_AUTHORITY_MAP)
  - description:  What the tool does (LLM reads this to decide which tool to call)
  - parameters:   JSON Schema for the tool's input arguments

Authority levels per tool:
  Level 0 (Read-only): check_health, check_ollama_status, read_logs,
                        check_metrics, check_website
  Level 1 (Safe ops):  restart_service, clear_cache, notify_team
  Level 2 (Destructive): not exposed as tools — require human approval
"""

from __future__ import annotations

from typing import Any, Dict, List


# ─── Tool Definitions ─────────────────────────────────────────────────────────

MATE_OPS_TOOLS: List[Dict[str, Any]] = [
    # ── Level 0: Read-only tools ────────────────────────────────────────────────

    {
        "type": "function",
        "function": {
            "name": "check_health",
            "description": (
                "Check MarketMate API health. Returns uptime, status, and "
                "basic service availability. Use for 'is the API up', "
                "'health check', 'system status'."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_ollama_status",
            "description": (
                "Check Ollama LLM inference service status. Returns "
                "available models, memory usage, and response time. "
                "Use for 'is Ollama running', 'LLM status', 'model availability'."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_logs",
            "description": (
                "Read application logs. Filter by level (ERROR, WARNING, INFO, DEBUG), "
                "source module, and search query. Returns the most recent matching log "
                "entries. Use for 'show me errors', 'recent logs', 'what happened'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "description": "Log level filter: ERROR, WARNING, INFO, DEBUG",
                        "enum": ["ERROR", "WARNING", "INFO", "DEBUG"],
                    },
                    "source": {
                        "type": "string",
                        "description": "Source module filter (e.g. 'scheduler', 'signal_engine', 'llm_provider')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of log entries to return (default 50, max 200)",
                        "default": 50,
                    },
                    "query": {
                        "type": "string",
                        "description": "Text search query to filter log messages",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_metrics",
            "description": (
                "Query Prometheus metrics. Supports PromQL queries and "
                "returns time-series data for API latency, error rates, "
                "request throughput, and custom metrics. "
                "Use for 'what's the error rate', 'API latency', 'throughput'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "PromQL query (e.g. 'rate(http_requests_total[5m])')",
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Time range for the query (e.g. '5m', '1h', '24h', '7d')",
                        "default": "5m",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_website",
            "description": (
                "Check website health via headless browser. Verifies the "
                "page loads, checks SSL certificate validity, measures "
                "response time, and optionally validates page content. "
                "Use for 'is the website up', 'check SSL', 'page load time'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to check (e.g. 'https://newmarketmate.onrender.com')",
                    },
                    "check_ssl": {
                        "type": "boolean",
                        "description": "Whether to verify SSL certificate validity (default true)",
                        "default": True,
                    },
                },
                "required": ["url"],
            },
        },
    },

    # ── Level 1: Safe operations ────────────────────────────────────────────────

    {
        "type": "function",
        "function": {
            "name": "restart_service",
            "description": (
                "Restart a container service. Use for unresponsive services, "
                "memory leaks, or stuck workers. Supported services depend on "
                "the deployment configuration. "
                "USE WITH CAUTION — this briefly interrupts the service."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Service to restart (e.g. 'marketmate-api', 'worker', 'ollama')",
                    },
                },
                "required": ["service_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_cache",
            "description": (
                "Clear Redis cache keys matching a pattern. Use for "
                "stale data issues, cache corruption, or forced refresh. "
                "Supports glob patterns (e.g. 'state:*', 'session:*'). "
                "USE WITH CAUTION — cleared caches will regenerate on next request."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Redis key pattern to clear (e.g. 'state:*', 'cache:*', '*')",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify_team",
            "description": (
                "Send an alert to the team via Telegram. Use for "
                "escalating issues that need human attention, reporting "
                "anomalies, or confirming automated actions. "
                "Messages are sent to the admin chat."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Alert message to send to the team",
                    },
                    "severity": {
                        "type": "string",
                        "description": "Severity level: info, warning, critical",
                        "enum": ["info", "warning", "critical"],
                        "default": "info",
                    },
                },
                "required": ["message"],
            },
        },
    },
]
