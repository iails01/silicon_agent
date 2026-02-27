"""Failure classification for stage execution errors.

Categorizes failures to enable different recovery strategies:
- transient: timeout/network errors → auto-retry
- tool_error: invalid tool JSON → text-only fallback retry
- resource: circuit breaker / quota exceeded → terminal
- semantic: wrong output / quality issues → retry with enhanced context
- gate_rejected: human rejected stage output → feedback loop (Phase 1.3)
- unknown: unclassifiable errors
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Optional


class FailureCategory(str, Enum):
    TRANSIENT = "transient"
    TOOL_ERROR = "tool_error"
    RESOURCE = "resource"
    SEMANTIC = "semantic"
    GATE_REJECTED = "gate_rejected"
    UNKNOWN = "unknown"


# Patterns for transient errors (timeouts, network issues)
_TRANSIENT_PATTERNS = [
    re.compile(r"timeout", re.IGNORECASE),
    re.compile(r"timed?\s*out", re.IGNORECASE),
    re.compile(r"connection\s*(refused|reset|error)", re.IGNORECASE),
    re.compile(r"network\s*(error|unreachable)", re.IGNORECASE),
    re.compile(r"(502|503|504)\s*(bad gateway|service unavailable|gateway timeout)", re.IGNORECASE),
    re.compile(r"rate\s*limit", re.IGNORECASE),
    re.compile(r"ECONNREFUSED|ECONNRESET|ETIMEDOUT", re.IGNORECASE),
    re.compile(r"asyncio\.TimeoutError", re.IGNORECASE),
]

# Patterns for tool errors (invalid JSON, tool call failures)
_TOOL_ERROR_PATTERNS = [
    re.compile(r"invalid\s*tool\s*(call|json|response)", re.IGNORECASE),
    re.compile(r"json\s*decode\s*error", re.IGNORECASE),
    re.compile(r"tool_use.*failed", re.IGNORECASE),
    re.compile(r"unknown\s*tool", re.IGNORECASE),
    re.compile(r"MiniMax.*tool", re.IGNORECASE),
]

# Patterns for resource exhaustion
_RESOURCE_PATTERNS = [
    re.compile(r"circuit\s*breaker", re.IGNORECASE),
    re.compile(r"quota\s*(exceeded|limit)", re.IGNORECASE),
    re.compile(r"(token|cost)\s*limit", re.IGNORECASE),
    re.compile(r"out\s*of\s*memory", re.IGNORECASE),
    re.compile(r"(429|insufficient_quota)", re.IGNORECASE),
]


def classify_failure(
    error: Exception | None = None,
    error_message: str | None = None,
    output: str | None = None,
) -> FailureCategory:
    """Classify a failure into a recovery category.

    Args:
        error: The exception that caused the failure (if available).
        error_message: The error message string.
        output: The stage output text (if any partial output was produced).

    Returns:
        FailureCategory indicating the type of failure.
    """
    # Build the text to match against
    texts = []
    if error is not None:
        texts.append(str(error))
        texts.append(type(error).__name__)
    if error_message:
        texts.append(error_message)
    combined = " ".join(texts)

    if not combined.strip():
        return FailureCategory.UNKNOWN

    # Check patterns in priority order
    for pattern in _RESOURCE_PATTERNS:
        if pattern.search(combined):
            return FailureCategory.RESOURCE

    for pattern in _TOOL_ERROR_PATTERNS:
        if pattern.search(combined):
            return FailureCategory.TOOL_ERROR

    for pattern in _TRANSIENT_PATTERNS:
        if pattern.search(combined):
            return FailureCategory.TRANSIENT

    # Check for specific exception types
    if error is not None:
        error_type = type(error).__name__
        if error_type in ("TimeoutError", "asyncio.TimeoutError", "ReadTimeout", "ConnectTimeout"):
            return FailureCategory.TRANSIENT
        if "ConnectionError" in error_type or "OSError" in error_type:
            return FailureCategory.TRANSIENT

    return FailureCategory.UNKNOWN


def is_auto_retryable(category: FailureCategory, auto_retry_categories: str) -> bool:
    """Check if a failure category is configured for automatic retry.

    Args:
        category: The classified failure category.
        auto_retry_categories: Comma-separated list of retryable category names.
    """
    retryable = {c.strip() for c in auto_retry_categories.split(",") if c.strip()}
    return category.value in retryable
