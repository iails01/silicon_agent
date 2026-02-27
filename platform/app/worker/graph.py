"""Graph-based stage execution engine (Phase 3.1).

Replaces linear order-based execution with a DAG-driven ready-set model.
When templates use `depends_on`, stages execute as soon as their dependencies
are satisfied — enabling arbitrary parallelism and failure-redirect loops.

Backward compatibility: When `depends_on` is absent, dependencies are inferred
from `order` values (identical to current linear behavior).
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class StageNode:
    """A node in the stage execution graph."""
    name: str
    agent_role: str
    depends_on: List[str] = field(default_factory=list)
    condition: Optional[dict] = None
    on_failure: Optional[str] = None
    max_executions: int = 1
    order: int = 0  # For backward compat ordering


@dataclass
class StageGraph:
    """Execution graph for stage dependencies.

    Provides ready-set computation: given completed/running/failed sets,
    determines which stages are ready to execute next.
    """
    nodes: Dict[str, StageNode] = field(default_factory=dict)

    @classmethod
    def from_template_stages(cls, stages_json: str | list | None) -> StageGraph:
        """Build a StageGraph from template stage definitions.

        If stages use `depends_on`, builds explicit dependency graph.
        Otherwise, infers linear dependencies from `order` values.
        """
        graph = cls()

        if stages_json is None:
            return graph

        if isinstance(stages_json, str):
            try:
                stage_defs = json.loads(stages_json) if stages_json else []
            except (json.JSONDecodeError, TypeError):
                return graph
        else:
            stage_defs = stages_json

        if not stage_defs:
            return graph

        has_depends_on = any(sd.get("depends_on") for sd in stage_defs)

        if has_depends_on:
            # Explicit dependency graph
            for sd in stage_defs:
                node = StageNode(
                    name=sd["name"],
                    agent_role=sd.get("agent_role", "orchestrator"),
                    depends_on=sd.get("depends_on", []),
                    condition=sd.get("condition"),
                    on_failure=sd.get("on_failure"),
                    max_executions=sd.get("max_executions", 1),
                    order=sd.get("order", 0),
                )
                graph.nodes[node.name] = node
        else:
            # Infer linear dependencies from order values
            sorted_defs = sorted(stage_defs, key=lambda sd: sd.get("order", 0))

            # Group by order for parallel stages
            order_groups: Dict[int, List[dict]] = defaultdict(list)
            for sd in sorted_defs:
                order_groups[sd.get("order", 0)].append(sd)

            prev_group_names: List[str] = []
            for order in sorted(order_groups.keys()):
                current_group = order_groups[order]
                for sd in current_group:
                    node = StageNode(
                        name=sd["name"],
                        agent_role=sd.get("agent_role", "orchestrator"),
                        depends_on=list(prev_group_names),
                        condition=sd.get("condition"),
                        on_failure=sd.get("on_failure"),
                        max_executions=sd.get("max_executions", 1),
                        order=order,
                    )
                    graph.nodes[node.name] = node
                prev_group_names = [sd["name"] for sd in current_group]

        return graph

    def get_ready_stages(
        self,
        completed: Set[str],
        running: Set[str],
        failed: Set[str],
        skipped: Set[str],
        execution_counts: Dict[str, int] | None = None,
    ) -> List[StageNode]:
        """Get stages that are ready to execute.

        A stage is ready when:
        - All its dependencies are in completed or skipped
        - It's not already running
        - It hasn't exceeded max_executions
        """
        counts = execution_counts or {}
        done = completed | skipped
        ready = []

        for name, node in self.nodes.items():
            if name in completed or name in running or name in skipped:
                continue
            if name in failed:
                # Check if we can re-execute
                exec_count = counts.get(name, 0)
                if exec_count >= node.max_executions:
                    continue
                # Allow re-execution if all deps are still satisfied
            # Check all dependencies
            deps_satisfied = all(dep in done for dep in node.depends_on)
            if deps_satisfied:
                ready.append(node)

        return ready

    def get_failure_redirect(self, failed_stage: str) -> str | None:
        """Get the redirect target when a stage fails."""
        node = self.nodes.get(failed_stage)
        if node and node.on_failure:
            return node.on_failure
        return None

    def get_all_stage_names(self) -> List[str]:
        """Get all stage names in topological order (for display)."""
        visited: Set[str] = set()
        result: List[str] = []

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            node = self.nodes.get(name)
            if node:
                for dep in node.depends_on:
                    visit(dep)
            result.append(name)

        for name in self.nodes:
            visit(name)

        return result

    def validate(self) -> List[str]:
        """Validate the graph for cycles and missing dependencies.

        Returns list of error messages (empty if valid).
        """
        errors = []

        # Check for missing dependency references
        for name, node in self.nodes.items():
            for dep in node.depends_on:
                if dep not in self.nodes:
                    errors.append(f"Stage '{name}' depends on unknown stage '{dep}'")
            if node.on_failure and node.on_failure not in self.nodes:
                errors.append(f"Stage '{name}' failure redirect to unknown stage '{node.on_failure}'")

        # Cycle detection via DFS
        WHITE, GRAY, BLACK = 0, 1, 2
        colors: Dict[str, int] = {name: WHITE for name in self.nodes}

        def has_cycle(name: str) -> bool:
            colors[name] = GRAY
            node = self.nodes[name]
            for dep in node.depends_on:
                if dep not in colors:
                    continue
                if colors[dep] == GRAY:
                    errors.append(f"Cycle detected involving stage '{dep}'")
                    return True
                if colors[dep] == WHITE and has_cycle(dep):
                    return True
            colors[name] = BLACK
            return False

        for name in self.nodes:
            if colors[name] == WHITE:
                has_cycle(name)

        return errors
