"""Conditional stage execution logic (Phase 2.1).

Evaluates conditions against structured outputs from prior stages
to determine whether a stage should execute or be skipped.

Example condition in template:
    {"source_stage": "code", "field": "status", "operator": "eq", "value": "pass"}
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Supported operators
_OPERATORS = {"eq", "ne", "gt", "lt", "gte", "lte", "contains", "not_contains", "exists", "not_exists"}


def evaluate_condition(
    condition: dict,
    structured_outputs: Dict[str, dict],
) -> bool:
    """Evaluate a stage condition against collected structured outputs.

    Args:
        condition: Condition dict with source_stage, field, operator, value.
        structured_outputs: {stage_name: output_structured_dict} from completed stages.

    Returns:
        True if condition is met (stage should execute), False to skip.
    """
    if not settings.CONDITIONS_ENABLED:
        return True

    source_stage = condition.get("source_stage")
    field = condition.get("field")
    operator = condition.get("operator", "eq")
    expected_value = condition.get("value")

    if not source_stage or not field:
        logger.warning("Invalid condition: missing source_stage or field: %s", condition)
        return True  # Default to execute on invalid conditions

    if operator not in _OPERATORS:
        logger.warning("Unknown condition operator: %s", operator)
        return True

    # Get the source stage's structured output
    source_output = structured_outputs.get(source_stage)
    if source_output is None:
        logger.info(
            "Condition source stage '%s' not found in outputs, skipping condition check",
            source_stage,
        )
        # Stage hasn't executed yet — default to execute
        return True

    # Extract the field value (supports dot notation for nested fields)
    actual_value = _get_nested_field(source_output, field)

    # Evaluate the operator
    return _apply_operator(operator, actual_value, expected_value)


def _get_nested_field(data: dict, field_path: str) -> Any:
    """Get a value from a nested dict using dot notation."""
    parts = field_path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _apply_operator(operator: str, actual: Any, expected: Any) -> bool:
    """Apply a comparison operator."""
    if operator == "exists":
        return actual is not None
    if operator == "not_exists":
        return actual is None

    if actual is None:
        return False

    if operator == "eq":
        return actual == expected
    elif operator == "ne":
        return actual != expected
    elif operator == "gt":
        return _numeric_compare(actual, expected, lambda a, b: a > b)
    elif operator == "lt":
        return _numeric_compare(actual, expected, lambda a, b: a < b)
    elif operator == "gte":
        return _numeric_compare(actual, expected, lambda a, b: a >= b)
    elif operator == "lte":
        return _numeric_compare(actual, expected, lambda a, b: a <= b)
    elif operator == "contains":
        if isinstance(actual, str):
            return str(expected) in actual
        if isinstance(actual, (list, tuple)):
            return expected in actual
        return False
    elif operator == "not_contains":
        if isinstance(actual, str):
            return str(expected) not in actual
        if isinstance(actual, (list, tuple)):
            return expected not in actual
        return True

    return True


def _numeric_compare(actual: Any, expected: Any, op) -> bool:
    """Safely compare values as numbers."""
    try:
        return op(float(actual), float(expected))
    except (TypeError, ValueError):
        return False
