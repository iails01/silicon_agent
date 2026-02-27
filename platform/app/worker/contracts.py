"""Structured stage output contracts for pipeline observability.

Defines per-stage JSON schemas for extracting structured data from raw LLM output.
After each stage completes, a lightweight LLM call extracts structured fields
which are stored alongside the raw text in output_structured.

This enables:
- Compressor to use structured data instead of lossy text truncation
- Conditions to evaluate structured fields (Phase 2.1)
- Confidence-based dynamic gates (Phase 2.3)
- Better signoff stage with parseable prior results
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base contract (all stages produce at minimum these fields)
# ---------------------------------------------------------------------------

class StageOutputContract(BaseModel):
    """Base structured output extracted from any stage."""
    summary: str = Field(description="一句话总结该阶段产出")
    status: Literal["pass", "fail", "partial"] = Field(
        default="pass", description="阶段执行结果状态"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="自评信心分数 0.0-1.0"
    )
    artifacts: List[str] = Field(
        default_factory=list, description="创建或修改的文件列表"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="阶段特定的结构化数据"
    )


# ---------------------------------------------------------------------------
# Per-stage contract extensions
# ---------------------------------------------------------------------------

class ParseOutputContract(StageOutputContract):
    """Structured output from the parse (orchestrator) stage."""
    requirements: List[str] = Field(default_factory=list, description="提炼的需求要点")
    risks: List[str] = Field(default_factory=list, description="识别的风险点")
    suggested_stages: List[str] = Field(default_factory=list, description="建议跳过的阶段")


class SpecOutputContract(StageOutputContract):
    """Structured output from the spec stage."""
    interfaces: List[str] = Field(default_factory=list, description="定义的接口列表")
    data_models: List[str] = Field(default_factory=list, description="数据模型列表")
    tech_choices: List[str] = Field(default_factory=list, description="技术选型")


class CodeOutputContract(StageOutputContract):
    """Structured output from the coding stage."""
    files_modified: List[str] = Field(default_factory=list, description="修改的文件列表")
    lines_changed: int = Field(default=0, description="变更行数")
    language: str = Field(default="", description="主要编程语言")


class TestOutputContract(StageOutputContract):
    """Structured output from the test stage."""
    tests_passed: int = Field(default=0, description="通过的测试数")
    tests_failed: int = Field(default=0, description="失败的测试数")
    coverage: Optional[float] = Field(default=None, description="测试覆盖率百分比")
    test_framework: str = Field(default="", description="测试框架")


class ReviewOutputContract(StageOutputContract):
    """Structured output from the review stage."""
    issues_critical: int = Field(default=0, description="Critical级别问题数")
    issues_major: int = Field(default=0, description="Major级别问题数")
    issues_minor: int = Field(default=0, description="Minor级别问题数")
    blocking_issues: List[str] = Field(default_factory=list, description="阻塞性问题列表")


class SmokeOutputContract(StageOutputContract):
    """Structured output from the smoke test stage."""
    scenarios_passed: int = Field(default=0, description="通过的场景数")
    scenarios_failed: int = Field(default=0, description="失败的场景数")


class DocOutputContract(StageOutputContract):
    """Structured output from the doc stage."""
    doc_types: List[str] = Field(default_factory=list, description="生成的文档类型")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

STAGE_CONTRACTS: Dict[str, type[StageOutputContract]] = {
    "parse": ParseOutputContract,
    "spec": SpecOutputContract,
    "code": CodeOutputContract,
    "test": TestOutputContract,
    "review": ReviewOutputContract,
    "smoke": SmokeOutputContract,
    "doc": DocOutputContract,
    "signoff": StageOutputContract,
    "approve": StageOutputContract,
}


def _get_schema_hint(stage_name: str) -> str:
    """Build a JSON schema hint for the extraction prompt."""
    contract_cls = STAGE_CONTRACTS.get(stage_name, StageOutputContract)
    fields = contract_cls.model_fields
    hints = {}
    for name, field_info in fields.items():
        desc = field_info.description or name
        if field_info.annotation is float or field_info.annotation is Optional[float]:
            hints[name] = f"<{desc}>"
        elif field_info.annotation is int:
            hints[name] = f"<{desc}>"
        elif field_info.annotation is list or str(field_info.annotation).startswith("list"):
            hints[name] = [f"<{desc}>"]
        elif field_info.annotation is dict or str(field_info.annotation).startswith("dict"):
            hints[name] = {}
        else:
            hints[name] = f"<{desc}>"
    return json.dumps(hints, ensure_ascii=False, indent=2)


async def extract_structured_output(
    stage_name: str,
    raw_output: str,
) -> Optional[Dict[str, Any]]:
    """Extract structured data from raw stage output via LLM.

    Returns a dict conforming to the stage's contract, or None on failure.
    Uses a lightweight LLM call with low temperature for consistency.
    """
    if not settings.STAGE_CONTRACTS_ENABLED:
        return None

    contract_cls = STAGE_CONTRACTS.get(stage_name, StageOutputContract)
    schema_hint = _get_schema_hint(stage_name)

    try:
        from app.integration.llm_client import ChatMessage, get_llm_client

        client = get_llm_client()
        prompt = (
            f"你是一个结构化数据提取助手。请从以下【{stage_name}】阶段的产出中提取结构化信息。\n\n"
            f"---\n{raw_output[:8000]}\n---\n\n"
            f"请严格按以下 JSON 格式回复（不要添加 markdown 代码块标记）：\n{schema_hint}"
        )
        resp = await client.chat(
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=0.2,
            max_tokens=1000,
        )

        # Parse and validate
        content = resp.content.strip()
        # Handle potential markdown code blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        data = json.loads(content)
        # Validate against contract
        validated = contract_cls.model_validate(data)
        return validated.model_dump()
    except Exception:
        logger.warning(
            "Failed to extract structured output for stage %s",
            stage_name, exc_info=True,
        )
        # Return a minimal contract with just the summary
        try:
            return StageOutputContract(
                summary=raw_output[:200].split("\n", 1)[0].strip(),
                status="pass",
            ).model_dump()
        except Exception:
            return None
