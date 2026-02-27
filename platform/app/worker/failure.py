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
from typing import Dict


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


async def generate_structured_reflection(
    error_message: str,
    stage_output: str,
    stage_name: str,
    agent_role: str,
) -> Dict[str, str]:
    """Use LLM to generate structured reflection on a stage failure.

    Returns {"root_cause": "...", "lesson": "...", "suggestion": "..."}.
    Falls back to raw error if LLM is unavailable.
    """
    fallback = {
        "root_cause": error_message,
        "lesson": "",
        "suggestion": "重新尝试",
    }
    if not error_message:
        return fallback

    try:
        from app.integration.llm_client import ChatMessage, get_llm_client

        from app.config import settings
        model_override = settings.SKILL_REFLECTION_MODEL or None
        client = get_llm_client()

        truncated_output = (stage_output or "")[:2000]
        prompt = (
            "你是一个任务失败分析助手。请分析以下阶段执行失败的情况，给出结构化反思。\n\n"
            f"**阶段名称:** {stage_name}\n"
            f"**执行角色:** {agent_role}\n"
            f"**错误信息:** {error_message}\n"
        )
        if truncated_output:
            prompt += f"**部分产出:**\n{truncated_output}\n"
        prompt += (
            "\n请严格按以下 JSON 格式回复（不要添加 markdown 代码块标记）：\n"
            '{"root_cause": "根因分析(一句话)", '
            '"lesson": "经验教训(一句话)", '
            '"suggestion": "改进建议(一句话)"}'
        )

        resp = await client.chat(
            messages=[ChatMessage(role="user", content=prompt)],
            model=model_override,
            temperature=0.3,
            max_tokens=300,
        )

        import json
        data = json.loads(resp.content.strip())
        if isinstance(data, dict):
            return {
                "root_cause": data.get("root_cause", error_message),
                "lesson": data.get("lesson", ""),
                "suggestion": data.get("suggestion", "重新尝试"),
            }
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Structured reflection failed, using fallback", exc_info=True
        )

    return fallback


def is_auto_retryable(category: FailureCategory, auto_retry_categories: str) -> bool:
    """Check if a failure category is configured for automatic retry.

    Args:
        category: The classified failure category.
        auto_retry_categories: Comma-separated list of retryable category names.
    """
    retryable = {c.strip() for c in auto_retry_categories.split(",") if c.strip()}
    return category.value in retryable
