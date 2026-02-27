"""Tests for structured reflection on stage failures."""
import pytest
from unittest.mock import AsyncMock, patch

from app.worker.failure import (
    FailureCategory,
    classify_failure,
    generate_structured_reflection,
    is_auto_retryable,
)


@pytest.mark.asyncio
async def test_generate_structured_reflection_success():
    """generate_structured_reflection returns structured dict when LLM succeeds."""
    mock_resp = AsyncMock()
    mock_resp.content = '{"root_cause": "API超时", "lesson": "增加超时配置", "suggestion": "设置更长的timeout"}'

    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(return_value=mock_resp)

    with patch(
        "app.integration.llm_client.get_llm_client", return_value=mock_client
    ):
        result = await generate_structured_reflection(
            error_message="TimeoutError: request timed out",
            stage_output="partial output here",
            stage_name="coding",
            agent_role="coding",
        )

    assert result["root_cause"] == "API超时"
    assert result["lesson"] == "增加超时配置"
    assert result["suggestion"] == "设置更长的timeout"


@pytest.mark.asyncio
async def test_generate_structured_reflection_fallback():
    """generate_structured_reflection falls back to raw error when LLM fails."""
    with patch(
        "app.integration.llm_client.get_llm_client",
        side_effect=Exception("LLM unavailable"),
    ):
        result = await generate_structured_reflection(
            error_message="Some error occurred",
            stage_output="",
            stage_name="review",
            agent_role="review",
        )

    assert result["root_cause"] == "Some error occurred"
    assert result["lesson"] == ""
    assert result["suggestion"] == "重新尝试"


@pytest.mark.asyncio
async def test_generate_structured_reflection_empty_error():
    """generate_structured_reflection returns fallback for empty error."""
    result = await generate_structured_reflection(
        error_message="",
        stage_output="",
        stage_name="test",
        agent_role="test",
    )

    assert result["root_cause"] == ""
    assert result["lesson"] == ""
    assert result["suggestion"] == "重新尝试"


@pytest.mark.asyncio
async def test_generate_structured_reflection_invalid_json():
    """generate_structured_reflection falls back when LLM returns invalid JSON."""
    mock_resp = AsyncMock()
    mock_resp.content = "This is not valid JSON"

    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(return_value=mock_resp)

    with patch(
        "app.integration.llm_client.get_llm_client", return_value=mock_client
    ):
        result = await generate_structured_reflection(
            error_message="Original error",
            stage_output="",
            stage_name="coding",
            agent_role="coding",
        )

    assert result["root_cause"] == "Original error"
    assert result["suggestion"] == "重新尝试"


def test_classify_failure_still_works():
    """Existing classify_failure function still works correctly."""
    assert classify_failure(error_message="timeout error") == FailureCategory.TRANSIENT
    assert classify_failure(error_message="circuit breaker tripped") == FailureCategory.RESOURCE
    assert classify_failure(error_message="invalid tool json") == FailureCategory.TOOL_ERROR
    assert classify_failure(error_message="something weird") == FailureCategory.UNKNOWN


def test_is_auto_retryable_still_works():
    """Existing is_auto_retryable function still works correctly."""
    assert is_auto_retryable(FailureCategory.TRANSIENT, "transient,tool_error") is True
    assert is_auto_retryable(FailureCategory.TOOL_ERROR, "transient,tool_error") is True
    assert is_auto_retryable(FailureCategory.RESOURCE, "transient,tool_error") is False
    assert is_auto_retryable(FailureCategory.SEMANTIC, "transient,tool_error") is False
