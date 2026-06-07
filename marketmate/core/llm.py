"""
marketmate/core/llm.py
───────────────────────
Multi-provider LLM client with automatic fallback.

Migrated from ``services/llm_provider.py`` into ``marketmate.core``.
Import paths updated to use ``marketmate.core.config`` and
``marketmate.core.logger``.

Provider stack (configurable via LLM_PROVIDER_STACK env var):
  1. Gemini   (primary — huge context, generous free tier)
  2. OpenRouter (fallback — one API, many models)
  3. Groq     (last resort — fast but small context)

Each provider implements a single async method: chat().
The LLMProvider.run() method tries providers in order,
falling through on rate limits (429), server errors (5xx),
or timeouts. Non-retryable errors (401, 413) abort immediately.

CRITICAL FIX (v2): Model resolution across providers.
  Previous version passed the same model name (e.g. "gemini-2.0-flash")
  to every provider in the fallback stack. This caused:
    - OpenRouter: 400 "gemini-2.0-flash is not a valid model ID"
    - Groq: 404 "The model `gemini-2.0-flash` does not exist"
  Now each provider resolves cross-provider model names to its own
  equivalent via `resolve_model()`. If no mapping exists, the provider
  falls back to its own default_model.

Architecture decisions:
  - All providers use the OpenAI-compatible chat/completions format.
    Gemini has a native REST API but also supports OpenAI format
    via the `openai` SDK with a custom base_url. We use the
    native REST API for Gemini (simpler, no extra SDK dependency).
  - Token budget estimation uses a conservative 4-chars-per-token
    heuristic. This prevents 413 Payload Too Large errors.
  - Rate limit detection: HTTP 429 -> automatic fallback to next
    provider. No waiting/retrying on the same provider — the point
    of fallback is to keep moving.
  - Context window limits are tracked per model. If a prompt would
    exceed the limit, it's truncated before sending (with a warning).

Usage:
    from marketmate.core.llm import llm_provider

    result = await llm_provider.chat(
        system_prompt="You are a teacher.",
        user_prompt="Explain order blocks.",
        max_tokens=2048,
        temperature=0.7,
    )
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("llm_provider")


# ─── Provider RPM Limits ─────────────────────────────────────────────────────
# Default RPM for each provider. These can be overridden via env vars.
# Set to 0 to disable client-side throttling (not recommended).

PROVIDER_RPM_DEFAULTS: dict[str, int] = {
    "gemini": 12,       # Gemini free tier is ~15 RPM; we stay under to avoid 429s
    "openrouter": 60,   # OpenRouter free tier is generous
    "groq": 30,         # Groq free tier ~30 RPM
    "mistral": 60,      # Mistral free tier ~1 req/sec = 60 RPM
    "together": 60,     # Together free tier is generous
}


def _get_provider_rpm(provider_name: str) -> int:
    """Get the RPM for a provider from env var or default."""
    env_key = f"{provider_name.upper()}_RPM_LIMIT"
    env_val = os.environ.get(env_key, "")
    if env_val:
        try:
            return int(env_val)
        except ValueError:
            pass
    return PROVIDER_RPM_DEFAULTS.get(provider_name, 60)


# ─── Provider-Side Rate Limiter (Token Bucket) ─────────────────────────────────
# Prevents hitting provider 429s by throttling requests client-side.
# Each provider gets its own bucket with configurable RPM.

class ProviderRateLimiter:
    """
    Token-bucket rate limiter for a single LLM provider.

    Prevents 429 errors by throttling requests before they're sent.
    When the bucket is empty, callers can either:
      - await wait_for_token() to block until a token is available
      - call try_acquire() to get a non-blocking check

    This replaces the reactive pattern (fire request → catch 429 → fallback)
    with a proactive pattern (wait for capacity → send request → success).
    """

    def __init__(self, rpm: int, provider_name: str = "unknown"):
        self._rpm = rpm
        self._interval = 60.0 / max(rpm, 1)  # seconds between tokens
        self._provider_name = provider_name
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def wait_for_token(self, timeout: float = 10.0) -> bool:
        """
        Wait until a request slot is available, then consume it.

        Returns True if a token was acquired within the timeout.
        Returns False if timeout expired (caller should fall through to next provider).
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            wait_time = self._interval - elapsed

            if wait_time > 0:
                if wait_time > timeout:
                    log.info(
                        "provider_rate_limiter_skip",
                        provider=self._provider_name,
                        wait_required_s=round(wait_time, 2),
                        timeout_s=timeout,
                        hint="Wait too long, falling through to next provider",
                    )
                    return False

                log.info(
                    "provider_rate_limiter_wait",
                    provider=self._provider_name,
                    wait_s=round(wait_time, 2),
                    rpm=self._rpm,
                )
                await asyncio.sleep(wait_time)

            self._last_request_time = time.monotonic()
            return True

    def try_acquire(self) -> bool:
        """Non-blocking check: return True if a token is available right now."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        return elapsed >= self._interval

    @property
    def rpm(self) -> int:
        return self._rpm

    @property
    def wait_time(self) -> float:
        """Seconds until next token is available."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        remaining = self._interval - elapsed
        return max(0, remaining)


# ─── Exceptions ───────────────────────────────────────────────────────────────

class LLMRateLimitError(Exception):
    """HTTP 429 — provider rate limit hit. Triggers fallback."""
    pass


class LLMPayloadTooLargeError(Exception):
    """HTTP 413 — prompt exceeds model context. Not retryable."""
    pass


class LLMAuthError(Exception):
    """HTTP 401/403 — invalid API key. Not retryable."""
    pass


class LLMAllProvidersFailedError(Exception):
    """Every provider in the stack failed."""
    pass


# ─── Model context limits ────────────────────────────────────────────────────

MODEL_CONTEXT_LIMITS: dict[str, int] = {
    # Gemini
    "gemini-2.0-flash":        1_048_576,
    "gemini-2.0-flash-lite":   1_048_576,
    "gemini-1.5-flash":        1_048_576,
    "gemini-1.5-pro":          2_097_152,
    # OpenRouter (varies by underlying model)
    "google/gemini-2.0-flash": 1_048_576,
    "google/gemini-2.0-flash-001": 1_048_576,
    "deepseek/deepseek-chat":  131_072,
    "meta-llama/llama-3.3-70b-instruct": 131_072,
    "qwen/qwen3-32b":          131_072,
    # Groq
    "llama-3.3-70b-versatile":                    128_000,
    "llama-3.1-8b-instant":                       128_000,
    "meta-llama/llama-4-scout-17b-16e-instruct":  128_000,
    "qwen/qwen3-32b":                             128_000,
    "gemma2-9b-it":                               8_192,
    # Mistral
    "mistral-small-latest":    128_000,
    "open-mistral-nemo":       128_000,
    "mistral-large-latest":    128_000,
    # Together
    "meta-llama/Llama-3.3-70B-Instruct-Turbo": 131_072,
    "deepseek-ai/DeepSeek-V3":                  131_072,
    "Qwen/Qwen2.5-72B-Instruct-Turbo":         131_072,
}


def _get_context_limit(model: str) -> int:
    """Return the context window limit for a model, defaulting to 128k."""
    return MODEL_CONTEXT_LIMITS.get(model, 128_000)


# ─── Cross-provider model mapping ────────────────────────────────────────────
# When generate() calls chat(model="gemini-2.0-flash"), each provider
# must resolve this to its OWN equivalent. If no mapping exists, the
# provider falls back to its default_model (which is always valid for
# that provider).

# Maps a "logical" model name to each provider's equivalent.
# This is the SINGLE SOURCE OF TRUTH for cross-provider model resolution.
CROSS_PROVIDER_MODEL_MAP: dict[str, dict[str, str]] = {
    "gemini-2.0-flash": {
        "gemini":     "gemini-2.0-flash",
        "openrouter": "google/gemini-2.0-flash-001",
        "groq":       "llama-3.3-70b-versatile",
        "mistral":    "mistral-small-latest",
        "together":   "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    },
    "gemini-1.5-flash": {
        "gemini":     "gemini-1.5-flash",
        "openrouter": "google/gemini-1.5-flash",
        "groq":       "llama-3.3-70b-versatile",
        "mistral":    "mistral-small-latest",
        "together":   "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    },
    "gemini-2.0-flash-lite": {
        "gemini":     "gemini-2.0-flash-lite",
        "openrouter": "google/gemini-2.0-flash-lite-001",
        "groq":       "llama-3.1-8b-instant",
        "mistral":    "open-mistral-nemo",
        "together":   "Qwen/Qwen2.5-72B-Instruct-Turbo",
    },
}


# ─── Token estimation ────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """Conservative token estimation: 1 token ~ 4 characters."""
    return len(text) // 4


def truncate_to_budget(
    text: str,
    budget_tokens: int,
    label: str = "user_prompt",
) -> str:
    """Truncate text to fit within a token budget (4 chars per token)."""
    budget_chars = budget_tokens * 4
    if len(text) <= budget_chars:
        return text
    truncated = text[:budget_chars]
    log.warning("prompt_truncated",
                label=label,
                original_chars=len(text),
                truncated_chars=len(truncated),
                budget_tokens=budget_tokens)
    return truncated


# ─── Provider base ────────────────────────────────────────────────────────────

@dataclass
class ProviderResult:
    """Result from a single provider call."""
    text: str
    provider: str
    model: str
    latency_ms: float
    tokens_estimated: int = 0


class BaseProvider:
    """Abstract base for LLM providers."""

    name: str = "base"

    def __init__(self, api_key: str, default_model: str, base_url: str = ""):
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = base_url

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def resolve_model(self, model: str | None) -> str | None:
        """Resolve a model name for this provider.

        When a cross-provider model is requested (e.g. "gemini-2.0-flash"
        from generate()), each provider maps it to its own equivalent
        via CROSS_PROVIDER_MODEL_MAP. If no mapping exists AND the model
        doesn't look like a native model for this provider, return None
        (causing the provider to use its own default_model).

        This fixes the critical bug where "gemini-2.0-flash" was sent
        to OpenRouter (400: "not a valid model ID") and Groq (404:
        "model does not exist").
        """
        if model is None:
            return None

        # 1. Check if this is a cross-provider model with an explicit mapping
        if model in CROSS_PROVIDER_MODEL_MAP:
            mapped = CROSS_PROVIDER_MODEL_MAP[model].get(self.name)
            if mapped:
                return mapped
            # No mapping for this provider -> use default
            return None

        # 2. If the model looks like it belongs to this provider, use it as-is.
        #    Each provider subclass can override this with its own prefix checks.
        if self._owns_model(model):
            return model

        # 3. Unknown model that doesn't belong to this provider -> use default
        return None

    def _owns_model(self, model: str) -> bool:
        """Return True if model is a native model name for this provider.
        Subclasses should override this with provider-specific prefix checks."""
        return False

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResult:
        raise NotImplementedError

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> dict:
        """
        Send a chat completion request with tool-calling support.

        Returns:
            Dict with:
              - content: assistant text (may be empty)
              - tool_calls: list of tool call dicts (may be empty)
              - latency_ms: request latency in milliseconds
        """
        raise NotImplementedError


# ─── Gemini provider ─────────────────────────────────────────────────────────

class GeminiProvider(BaseProvider):
    """
    Google Gemini API provider.

    Uses the native REST API (generativelanguage.googleapis.com).
    Supports up to 1M token context on Flash models.
    Free tier: ~15 RPM, ~1,500 requests/day.

    Includes client-side rate limiter to prevent 429 errors.
    The limiter throttles requests to stay within the Gemini free
    tier budget. When the budget is exhausted, the request falls
    through to the next provider in the stack instead of waiting.

    The Gemini API format differs from OpenAI:
      - URL: /v1beta/models/{model}:generateContent?key={API_KEY}
      - Body: {"contents": [...], "systemInstruction": {...}}
    """

    name = "gemini"
    _model_prefixes = ("gemini-",)

    def __init__(self, api_key: str, default_model: str = "gemini-2.0-flash"):
        super().__init__(api_key, default_model,
                         base_url="https://generativelanguage.googleapis.com")
        # Client-side rate limiter: prevents 429s by throttling requests
        rpm = _get_provider_rpm("gemini")
        self._rate_limiter = ProviderRateLimiter(rpm=rpm, provider_name="gemini")

    def _owns_model(self, model: str) -> bool:
        return any(model.startswith(p) for p in self._model_prefixes)

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResult:
        model = model or self.default_model
        context_limit = _get_context_limit(model)

        # Client-side rate limiting: wait for capacity or skip to next provider
        # Timeout of 5s means we'll wait briefly, but fall through if too busy
        acquired = await self._rate_limiter.wait_for_token(timeout=5.0)
        if not acquired:
            raise LLMRateLimitError(
                f"Gemini client-side rate limit ({self._rate_limiter.rpm} RPM) — "
                f"skipping to next provider"
            )

        # Token budget guard
        estimated_prompt_tokens = estimate_tokens(system_prompt + user_prompt)
        if estimated_prompt_tokens + max_tokens > context_limit:
            budget = context_limit - max_tokens - estimate_tokens(system_prompt) - 100
            if budget < 200:
                raise LLMPayloadTooLargeError(
                    f"Gemini prompt too large for {model}: "
                    f"{estimated_prompt_tokens} estimated tokens"
                )
            user_prompt = truncate_to_budget(user_prompt, budget, "gemini_user_prompt")

        url = f"{self.base_url}/v1beta/models/{model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]},
            ],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, json=payload)
        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 429:
            raise LLMRateLimitError(f"Gemini rate limit (429) on {model}")
        if resp.status_code in (401, 403):
            raise LLMAuthError(f"Gemini auth error ({resp.status_code})")
        if resp.status_code == 413:
            raise LLMPayloadTooLargeError(f"Gemini payload too large for {model}")
        if resp.status_code >= 500:
            raise LLMRateLimitError(f"Gemini server error ({resp.status_code}) on {model}")
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API error: {resp.status_code} — {resp.text[:300]}")

        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            # Handle blocked content (safety filters)
            block_reason = ""
            try:
                block_reason = data.get("candidates", [{}])[0].get(
                    "finishReason", "UNKNOWN"
                )
            except Exception:
                pass
            if block_reason == "SAFETY":
                raise RuntimeError(
                    f"Gemini blocked response (safety filter). "
                    f"Try rephrasing the prompt. Block reason: {block_reason}"
                )
            raise RuntimeError(f"Gemini response parse error: {exc}")

        return ProviderResult(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=round(latency_ms, 1),
            tokens_estimated=estimate_tokens(text),
        )

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> dict:
        """
        Gemini-native tool calling via the REST API.

        Converts OpenAI-format messages and tools into Gemini's
        functionDeclarations / functionCall format, then converts
        the response back to OpenAI-compatible tool_calls format.

        Includes client-side rate limiting to prevent 429 errors.
        """
        import json as _json
        model = model or self.default_model

        # Client-side rate limiting: wait for capacity or skip to next provider
        acquired = await self._rate_limiter.wait_for_token(timeout=5.0)
        if not acquired:
            raise LLMRateLimitError(
                f"Gemini client-side rate limit ({self._rate_limiter.rpm} RPM) — "
                f"skipping to next provider"
            )

        # ── Convert OpenAI tools → Gemini functionDeclarations ────────────
        gemini_functions = []
        for tool in tools:
            func = tool.get("function", {})
            gemini_functions.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {}),
            })

        # ── Convert OpenAI messages → Gemini contents ─────────────────────
        gemini_contents = []
        system_text = ""
        for msg in messages:
            role = msg.get("role", "")

            if role == "system":
                system_text += (msg.get("content") or "") + "\n"
                continue

            if role == "user":
                gemini_contents.append({
                    "role": "user",
                    "parts": [{"text": msg.get("content") or ""}],
                })

            elif role == "assistant":
                parts = []
                content = msg.get("content") or ""
                if content:
                    parts.append({"text": content})
                # Convert OpenAI tool_calls → Gemini functionCall parts
                for tc in msg.get("tool_calls") or []:
                    func = tc.get("function", {})
                    try:
                        args = _json.loads(func.get("arguments", "{}")) if isinstance(func.get("arguments"), str) else func.get("arguments", {})
                    except _json.JSONDecodeError:
                        args = {}
                    parts.append({
                        "functionCall": {
                            "name": func.get("name", ""),
                            "args": args,
                        }
                    })
                if parts:
                    gemini_contents.append({"role": "model", "parts": parts})

            elif role == "tool":
                tool_call_id = msg.get("tool_call_id", "")
                content = msg.get("content") or ""
                try:
                    result_dict = _json.loads(content) if isinstance(content, str) else content
                except _json.JSONDecodeError:
                    result_dict = {"result": content}
                # Find matching function name from prior tool_calls in messages
                func_name = tool_call_id  # fallback
                for prev_msg in messages:
                    if prev_msg.get("role") == "assistant":
                        for tc in prev_msg.get("tool_calls") or []:
                            if tc.get("id") == tool_call_id:
                                func_name = tc.get("function", {}).get("name", tool_call_id)
                                break
                gemini_contents.append({
                    "role": "function",
                    "parts": [{
                        "functionResponse": {
                            "name": func_name,
                            "response": result_dict if isinstance(result_dict, dict) else {"result": str(result_dict)},
                        }
                    }],
                })

        # If no user message exists, add one (Gemini requires at least one user turn)
        if not any(c.get("role") == "user" for c in gemini_contents):
            gemini_contents.insert(0, {
                "role": "user",
                "parts": [{"text": "Please respond to the above."}],
            })

        url = f"{self.base_url}/v1beta/models/{model}:generateContent?key={self.api_key}"

        payload: dict[str, Any] = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system_text.strip():
            payload["systemInstruction"] = {"parts": [{"text": system_text.strip()}]}

        if gemini_functions:
            payload["tools"] = [{"functionDeclarations": gemini_functions}]

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, json=payload)
        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 429:
            raise LLMRateLimitError(f"Gemini rate limit (429) on {model}")
        if resp.status_code in (401, 403):
            raise LLMAuthError(f"Gemini auth error ({resp.status_code})")
        if resp.status_code == 413:
            raise LLMPayloadTooLargeError(f"Gemini payload too large for {model}")
        if resp.status_code >= 500:
            raise LLMRateLimitError(f"Gemini server error ({resp.status_code}) on {model}")
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API error: {resp.status_code} — {resp.text[:300]}")

        data = resp.json()

        # ── Parse Gemini response → OpenAI-compatible format ──────────────
        content = ""
        tool_calls = []

        try:
            candidate = data["candidates"][0]
            parts = candidate.get("content", {}).get("parts", [])

            for part in parts:
                if "text" in part:
                    content += part["text"]
                elif "functionCall" in part:
                    fc = part["functionCall"]
                    tool_calls.append({
                        "id": f"call_{len(tool_calls)}_{fc.get('name', '')}",
                        "type": "function",
                        "function": {
                            "name": fc.get("name", ""),
                            "arguments": _json.dumps(fc.get("args", {})),
                        },
                    })
        except (KeyError, IndexError):
            pass

        return {
            "content": content,
            "tool_calls": tool_calls,
            "latency_ms": round(latency_ms, 1),
        }


# ─── OpenRouter provider ────────────────────────────────────────────────────

class OpenRouterProvider(BaseProvider):
    """
    OpenRouter provider — one API, many models.

    OpenAI-compatible chat/completions endpoint.
    Falls back across models automatically if configured.
    Free tier is smaller than Gemini but excellent as backup.

    Models: google/gemini-2.0-flash-001, deepseek/deepseek-chat,
            meta-llama/llama-3.3-70b-instruct, qwen/qwen3-32b
    """

    name = "openrouter"
    _model_prefixes = ("google/", "deepseek/", "meta-llama/", "qwen/", "anthropic/")

    def __init__(self, api_key: str, default_model: str = "google/gemini-2.0-flash-001"):
        super().__init__(api_key, default_model,
                         base_url="https://openrouter.ai/api/v1")

    def _owns_model(self, model: str) -> bool:
        return any(model.startswith(p) for p in self._model_prefixes)

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResult:
        model = model or self.default_model
        context_limit = _get_context_limit(model)

        estimated_prompt_tokens = estimate_tokens(system_prompt + user_prompt)
        if estimated_prompt_tokens + max_tokens > context_limit:
            budget = context_limit - max_tokens - estimate_tokens(system_prompt) - 100
            if budget < 200:
                raise LLMPayloadTooLargeError(
                    f"OpenRouter prompt too large for {model}: "
                    f"{estimated_prompt_tokens} estimated tokens"
                )
            user_prompt = truncate_to_budget(user_prompt, budget, "openrouter_user_prompt")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://newmarketmate.onrender.com",
            "X-Title": "MarketMate Academy",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, headers=headers, json=payload)
        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 429:
            raise LLMRateLimitError(f"OpenRouter rate limit (429) on {model}")
        if resp.status_code in (401, 403):
            raise LLMAuthError(f"OpenRouter auth error ({resp.status_code})")
        if resp.status_code == 413:
            raise LLMPayloadTooLargeError(f"OpenRouter payload too large for {model}")
        if resp.status_code >= 500:
            raise LLMRateLimitError(f"OpenRouter server error ({resp.status_code}) on {model}")
        if resp.status_code != 200:
            raise RuntimeError(
                f"OpenRouter API error: {resp.status_code} — {resp.text[:300]}"
            )

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"OpenRouter response parse error: {exc}")

        return ProviderResult(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=round(latency_ms, 1),
            tokens_estimated=estimate_tokens(text),
        )

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> dict:
        """OpenAI-compatible tool calling via OpenRouter."""
        model = model or self.default_model

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://newmarketmate.onrender.com",
            "X-Title": "MarketMate Academy",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, headers=headers, json=payload)
        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 429:
            raise LLMRateLimitError(f"OpenRouter rate limit (429) on {model}")
        if resp.status_code in (401, 403):
            raise LLMAuthError(f"OpenRouter auth error ({resp.status_code})")
        if resp.status_code == 413:
            raise LLMPayloadTooLargeError(f"OpenRouter payload too large for {model}")
        if resp.status_code >= 500:
            raise LLMRateLimitError(f"OpenRouter server error ({resp.status_code}) on {model}")
        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter API error: {resp.status_code} — {resp.text[:300]}")

        data = resp.json()
        content = ""
        tool_calls = []

        try:
            choice = data["choices"][0]
            msg = choice.get("message", {})
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []
        except (KeyError, IndexError):
            pass

        return {
            "content": content,
            "tool_calls": tool_calls,
            "latency_ms": round(latency_ms, 1),
        }


# ─── Groq provider ───────────────────────────────────────────────────────────

class GroqProvider(BaseProvider):
    """
    Groq provider — ultra-fast inference, small context.

    Good for: short rewrites, quick reviews, assistant replies.
    Bad for: full module expansion (3,200+ words), giant JSON payloads,
             long educational drafts.

    Free tier: ~30 RPM (varies), 6k-128k token limits by model.
    """

    name = "groq"
    _model_prefixes = ("llama-", "gemma2-", "meta-llama/llama-4", "qwen/qwen3")

    def __init__(self, api_key: str, default_model: str = "llama-3.3-70b-versatile"):
        super().__init__(api_key, default_model,
                         base_url="https://api.groq.com/openai/v1")

    def _owns_model(self, model: str) -> bool:
        return any(model.startswith(p) for p in self._model_prefixes)

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResult:
        model = model or self.default_model
        context_limit = _get_context_limit(model)

        estimated_prompt_tokens = estimate_tokens(system_prompt + user_prompt)
        if estimated_prompt_tokens + max_tokens > context_limit:
            budget = context_limit - max_tokens - estimate_tokens(system_prompt) - 100
            if budget < 200:
                raise LLMPayloadTooLargeError(
                    f"Groq prompt too large for {model}: "
                    f"{estimated_prompt_tokens} estimated tokens"
                )
            user_prompt = truncate_to_budget(user_prompt, budget, "groq_user_prompt")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=headers, json=payload)
        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 429:
            raise LLMRateLimitError(f"Groq rate limit (429) on {model}")
        if resp.status_code in (401, 403):
            raise LLMAuthError(f"Groq auth error ({resp.status_code})")
        if resp.status_code == 413:
            raise LLMPayloadTooLargeError(f"Groq payload too large for {model}")
        if resp.status_code >= 500:
            raise LLMRateLimitError(f"Groq server error ({resp.status_code}) on {model}")
        if resp.status_code != 200:
            raise RuntimeError(
                f"Groq API error: {resp.status_code} — {resp.text[:300]}"
            )

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Groq response parse error: {exc}")

        return ProviderResult(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=round(latency_ms, 1),
            tokens_estimated=estimate_tokens(text),
        )

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> dict:
        """OpenAI-compatible tool calling via Groq."""
        model = model or self.default_model

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=headers, json=payload)
        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 429:
            raise LLMRateLimitError(f"Groq rate limit (429) on {model}")
        if resp.status_code in (401, 403):
            raise LLMAuthError(f"Groq auth error ({resp.status_code})")
        if resp.status_code == 413:
            raise LLMPayloadTooLargeError(f"Groq payload too large for {model}")
        if resp.status_code >= 500:
            raise LLMRateLimitError(f"Groq server error ({resp.status_code}) on {model}")
        if resp.status_code != 200:
            raise RuntimeError(f"Groq API error: {resp.status_code} — {resp.text[:300]}")

        data = resp.json()
        content = ""
        tool_calls = []

        try:
            choice = data["choices"][0]
            msg = choice.get("message", {})
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []
        except (KeyError, IndexError):
            pass

        return {
            "content": content,
            "tool_calls": tool_calls,
            "latency_ms": round(latency_ms, 1),
        }


# ─── Mistral provider ────────────────────────────────────────────────────────

class MistralProvider(BaseProvider):
    """
    Mistral AI provider — clean educational writing, low hallucination.

    Good for: structured educational content, technical prose.
    Free tier: ~1 req/sec, generous monthly token allowance.

    OpenAI-compatible chat/completions endpoint.
    """

    name = "mistral"
    _model_prefixes = ("mistral-", "open-mistral-")

    def __init__(self, api_key: str, default_model: str = "mistral-small-latest"):
        super().__init__(api_key, default_model,
                         base_url="https://api.mistral.ai/v1")

    def _owns_model(self, model: str) -> bool:
        return any(model.startswith(p) for p in self._model_prefixes)

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResult:
        model = model or self.default_model
        context_limit = _get_context_limit(model)

        estimated_prompt_tokens = estimate_tokens(system_prompt + user_prompt)
        if estimated_prompt_tokens + max_tokens > context_limit:
            budget = context_limit - max_tokens - estimate_tokens(system_prompt) - 100
            if budget < 200:
                raise LLMPayloadTooLargeError(
                    f"Mistral prompt too large for {model}: "
                    f"{estimated_prompt_tokens} estimated tokens"
                )
            user_prompt = truncate_to_budget(user_prompt, budget, "mistral_user_prompt")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, headers=headers, json=payload)
        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 429:
            raise LLMRateLimitError(f"Mistral rate limit (429) on {model}")
        if resp.status_code in (401, 403):
            raise LLMAuthError(f"Mistral auth error ({resp.status_code})")
        if resp.status_code == 413:
            raise LLMPayloadTooLargeError(f"Mistral payload too large for {model}")
        if resp.status_code >= 500:
            raise LLMRateLimitError(f"Mistral server error ({resp.status_code}) on {model}")
        if resp.status_code != 200:
            raise RuntimeError(
                f"Mistral API error: {resp.status_code} — {resp.text[:300]}"
            )

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Mistral response parse error: {exc}")

        return ProviderResult(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=round(latency_ms, 1),
            tokens_estimated=estimate_tokens(text),
        )

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> dict:
        """OpenAI-compatible tool calling via Mistral."""
        model = model or self.default_model

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, headers=headers, json=payload)
        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 429:
            raise LLMRateLimitError(f"Mistral rate limit (429) on {model}")
        if resp.status_code in (401, 403):
            raise LLMAuthError(f"Mistral auth error ({resp.status_code})")
        if resp.status_code == 413:
            raise LLMPayloadTooLargeError(f"Mistral payload too large for {model}")
        if resp.status_code >= 500:
            raise LLMRateLimitError(f"Mistral server error ({resp.status_code}) on {model}")
        if resp.status_code != 200:
            raise RuntimeError(f"Mistral API error: {resp.status_code} — {resp.text[:300]}")

        data = resp.json()
        content = ""
        tool_calls = []

        try:
            choice = data["choices"][0]
            msg = choice.get("message", {})
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []
        except (KeyError, IndexError):
            pass

        return {
            "content": content,
            "tool_calls": tool_calls,
            "latency_ms": round(latency_ms, 1),
        }


# ─── Together AI provider ────────────────────────────────────────────────────

class TogetherProvider(BaseProvider):
    """
    Together AI provider — open-source models at scale.

    Good for: Llama, DeepSeek, Qwen, Mixtral without infrastructure.
    OpenAI-compatible chat/completions endpoint.
    """

    name = "together"
    _model_prefixes = ("meta-llama/Llama-", "deepseek-ai/", "Qwen/")

    def __init__(self, api_key: str, default_model: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo"):
        super().__init__(api_key, default_model,
                         base_url="https://api.together.xyz/v1")

    def _owns_model(self, model: str) -> bool:
        return any(model.startswith(p) for p in self._model_prefixes)

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResult:
        model = model or self.default_model
        context_limit = _get_context_limit(model)

        estimated_prompt_tokens = estimate_tokens(system_prompt + user_prompt)
        if estimated_prompt_tokens + max_tokens > context_limit:
            budget = context_limit - max_tokens - estimate_tokens(system_prompt) - 100
            if budget < 200:
                raise LLMPayloadTooLargeError(
                    f"Together prompt too large for {model}: "
                    f"{estimated_prompt_tokens} estimated tokens"
                )
            user_prompt = truncate_to_budget(user_prompt, budget, "together_user_prompt")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, headers=headers, json=payload)
        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 429:
            raise LLMRateLimitError(f"Together rate limit (429) on {model}")
        if resp.status_code in (401, 403):
            raise LLMAuthError(f"Together auth error ({resp.status_code})")
        if resp.status_code == 413:
            raise LLMPayloadTooLargeError(f"Together payload too large for {model}")
        if resp.status_code >= 500:
            raise LLMRateLimitError(f"Together server error ({resp.status_code}) on {model}")
        if resp.status_code != 200:
            raise RuntimeError(
                f"Together API error: {resp.status_code} — {resp.text[:300]}"
            )

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Together response parse error: {exc}")

        return ProviderResult(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=round(latency_ms, 1),
            tokens_estimated=estimate_tokens(text),
        )

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> dict:
        """OpenAI-compatible tool calling via Together AI."""
        model = model or self.default_model

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, headers=headers, json=payload)
        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 429:
            raise LLMRateLimitError(f"Together rate limit (429) on {model}")
        if resp.status_code in (401, 403):
            raise LLMAuthError(f"Together auth error ({resp.status_code})")
        if resp.status_code == 413:
            raise LLMPayloadTooLargeError(f"Together payload too large for {model}")
        if resp.status_code >= 500:
            raise LLMRateLimitError(f"Together server error ({resp.status_code}) on {model}")
        if resp.status_code != 200:
            raise RuntimeError(f"Together API error: {resp.status_code} — {resp.text[:300]}")

        data = resp.json()
        content = ""
        tool_calls = []

        try:
            choice = data["choices"][0]
            msg = choice.get("message", {})
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []
        except (KeyError, IndexError):
            pass

        return {
            "content": content,
            "tool_calls": tool_calls,
            "latency_ms": round(latency_ms, 1),
        }


# ─── Provider registry ───────────────────────────────────────────────────────

PROVIDER_CLASSES: dict[str, type[BaseProvider]] = {
    "gemini": GeminiProvider,
    "openrouter": OpenRouterProvider,
    "groq": GroqProvider,
    "mistral": MistralProvider,
    "together": TogetherProvider,
}


# ─── Main LLM Provider (fallback stack) ──────────────────────────────────────

class LLMProvider:
    """
    Multi-provider LLM client with automatic fallback.

    Usage:
        provider = LLMProvider()
        result = await provider.chat(system_prompt, user_prompt)

    The provider stack is configured via LLM_PROVIDER_STACK env var
    (comma-separated, e.g. "gemini,openrouter,groq"). Providers
    without API keys are silently skipped.

    For generation tasks (long drafts), use:
        result = await provider.generate(system_prompt, user_prompt)

    This uses the generation-specific model from config. This model
    should be one with a large context window (e.g. Gemini Flash).
    Groq should NOT be the primary generation provider — its small
    context window (8k-128k) and strict rate limits make it a poor
    choice for 3,200+ word outputs.

    CRITICAL: When a cross-provider model name is passed (e.g.
    "gemini-2.0-flash" from generate()), each provider resolves it
    to its own equivalent via resolve_model(). This prevents sending
    a Gemini-only model name to OpenRouter (400) or Groq (404).
    """

    def __init__(self):
        llm_cfg = cfg.llm
        self._stack: list[BaseProvider] = []
        self._generation_model = llm_cfg.generation_model
        self._review_models = llm_cfg.review_models

        # Build provider stack from config
        for name in llm_cfg.provider_stack:
            name = name.strip().lower()
            cls = PROVIDER_CLASSES.get(name)
            if not cls:
                log.warning("llm_provider_unknown", name=name,
                            hint="Skipping unknown provider in stack")
                continue

            # Get API key for this provider
            api_key = self._get_api_key(name)
            if not api_key:
                log.info("llm_provider_no_key", name=name,
                         hint=f"Set {name.upper()}_API_KEY to enable this provider")
                continue

            default_model = self._get_default_model(name)
            provider = cls(api_key=api_key, default_model=default_model)
            self._stack.append(provider)
            log.info("llm_provider_registered", name=name, model=default_model)

        if not self._stack:
            log.error("llm_no_providers",
                      hint="No LLM providers configured. Set at least one API key: "
                           "GEMINI_API_KEY, OPENROUTER_API_KEY, or GROQ_API_KEY")

    @staticmethod
    def _get_api_key(name: str) -> str:
        """Return the API key for a provider from environment variables."""
        key_map = {
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "groq": "GROQ_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "together": "TOGETHER_API_KEY",
        }
        env_var = key_map.get(name, f"{name.upper()}_API_KEY")
        return os.environ.get(env_var, "") or ""

    @staticmethod
    def _get_default_model(name: str) -> str:
        """Return the default model for a provider."""
        model_map = {
            "gemini": "gemini-2.0-flash",
            "openrouter": "google/gemini-2.0-flash-001",
            "groq": "llama-3.3-70b-versatile",
            "mistral": "mistral-small-latest",
            "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        }
        return model_map.get(name, "")

    @property
    def available_providers(self) -> list[str]:
        return [p.name for p in self._stack]

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        prefer_provider: str | None = None,
    ) -> str:
        """
        Send a chat completion request through the provider stack.

        Tries providers in order. Falls through on rate limits and
        server errors. Raises on auth errors and payload-too-large.

        Args:
            system_prompt:  System instruction.
            user_prompt:    User message content.
            model:          Override model (uses provider default if None).
                            Cross-provider models (e.g. "gemini-2.0-flash")
                            are automatically resolved per-provider.
            max_tokens:     Maximum response tokens.
            temperature:    Sampling temperature.
            prefer_provider: Try this provider first, then fall through the stack.

        Returns:
            The assistant's response text.

        Raises:
            LLMAllProvidersFailedError: Every provider failed.
            LLMPayloadTooLargeError: Prompt too large for all providers.
        """
        if not self._stack:
            raise LLMAllProvidersFailedError(
                "No LLM providers configured. Set at least one API key."
            )

        # If a preferred provider is specified, try it first
        ordered = list(self._stack)
        if prefer_provider:
            preferred = [p for p in self._stack if p.name == prefer_provider]
            others = [p for p in self._stack if p.name != prefer_provider]
            ordered = preferred + others

        errors: list[str] = []

        for provider in ordered:
            # ── CRITICAL FIX: Resolve model per-provider ─────────────────
            # When a cross-provider model name is passed (e.g. "gemini-2.0-flash"
            # from generate()), each provider maps it to its own equivalent.
            # Gemini -> "gemini-2.0-flash" (native)
            # OpenRouter -> "google/gemini-2.0-flash-001" (OpenRouter format)
            # Groq -> "llama-3.3-70b-versatile" (completely different model)
            # If no mapping exists, provider falls back to its own default.
            resolved_model = provider.resolve_model(model)

            try:
                result = await provider.chat(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=resolved_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                log.info("llm_chat_success",
                         provider=result.provider,
                         model=result.model,
                         requested_model=model,
                         resolved_model=resolved_model,
                         latency_ms=result.latency_ms,
                         tokens_estimated=result.tokens_estimated)
                return result.text

            except LLMRateLimitError as exc:
                errors.append(f"{provider.name}: {exc}")
                log.warning("llm_provider_rate_limited",
                            provider=provider.name,
                            error=str(exc),
                            hint="Falling through to next provider")
                continue

            except (LLMPayloadTooLargeError, LLMAuthError) as exc:
                errors.append(f"{provider.name}: {exc}")
                log.warning("llm_provider_non_retryable",
                            provider=provider.name,
                            error=str(exc),
                            hint="Skipping to next provider (non-retryable)")
                continue

            except Exception as exc:
                errors.append(f"{provider.name}: {exc}")
                log.warning("llm_provider_error",
                            provider=provider.name,
                            error=str(exc),
                            hint="Falling through to next provider")
                continue

        raise LLMAllProvidersFailedError(
            f"All LLM providers failed: {'; '.join(errors)}"
        )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate long-form content (module drafts, expansions).

        Uses the generation-specific model from config. This model
        should be one with a large context window (e.g. Gemini Flash).
        Groq should NOT be the primary generation provider — its small
        context window (8k-128k) and strict rate limits make it a poor
        choice for 3,200+ word outputs.

        Falls through the provider stack if the primary fails.
        Each provider automatically resolves the generation model to
        its own equivalent via resolve_model().
        """
        return await self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self._generation_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def review(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
    ) -> str:
        """
        Run a review call (shorter output, lower temperature).

        Uses the review model if specified, otherwise falls through
        the provider stack with the default model.
        """
        return await self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            max_tokens=2048,
            temperature=0.5,  # Reviews should be more deterministic
        )

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        model: str | None = None,
    ) -> dict:
        """
        Send a chat completion request with tool-calling support.

        This is the method used by MATE's tool-calling agent. It sends
        the full conversation history (with tool call/response messages)
        along with tool definitions, and returns both the assistant's
        text content and any tool calls it wants to make.

        Falls through the provider stack on failures.

        Args:
            messages:  Full conversation history in OpenAI format:
                       [{"role": "system"|"user"|"assistant"|"tool", "content": ..., ...}]
            tools:     Tool definitions in OpenAI function-calling format:
                       [{"type": "function", "function": {"name": ..., "parameters": ...}}]
            max_tokens:  Maximum response tokens.
            temperature: Sampling temperature.
            model:       Override model (cross-provider resolution applies).

        Returns:
            Dict with:
              - content:   The assistant's text response (may be empty if tool_calls present)
              - tool_calls: List of tool call objects (may be empty):
                  [{"id": "...", "type": "function", "function": {"name": "...", "arguments": "..."}}]

        Raises:
            LLMAllProvidersFailedError: Every provider failed.
        """
        if not self._stack:
            raise LLMAllProvidersFailedError(
                "No LLM providers configured. Set at least one API key."
            )

        errors: list[str] = []

        for provider in self._stack:
            resolved_model = provider.resolve_model(model) or provider.default_model

            try:
                result = await provider.chat_with_tools(
                    messages=messages,
                    tools=tools,
                    model=resolved_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                log.info(
                    "llm_chat_with_tools_success",
                    provider=provider.name,
                    model=resolved_model,
                    has_tool_calls=bool(result.get("tool_calls")),
                    latency_ms=result.get("latency_ms", 0),
                )
                return result

            except LLMRateLimitError as exc:
                errors.append(f"{provider.name}: {exc}")
                log.warning(
                    "llm_tools_provider_rate_limited",
                    provider=provider.name,
                    error=str(exc),
                    hint="Falling through to next provider",
                )
                continue

            except (LLMPayloadTooLargeError, LLMAuthError) as exc:
                errors.append(f"{provider.name}: {exc}")
                log.warning(
                    "llm_tools_provider_non_retryable",
                    provider=provider.name,
                    error=str(exc),
                )
                continue

            except Exception as exc:
                errors.append(f"{provider.name}: {exc}")
                log.warning(
                    "llm_tools_provider_error",
                    provider=provider.name,
                    error=str(exc),
                    hint="Falling through to next provider",
                )
                continue

        raise LLMAllProvidersFailedError(
            f"All LLM providers failed for chat_with_tools: {'; '.join(errors)}"
        )


# ─── Module-level singleton ──────────────────────────────────────────────────

llm_provider = LLMProvider()
