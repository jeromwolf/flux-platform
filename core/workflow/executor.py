"""DAG-based workflow executor (n8n WorkflowExecute pattern)."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from core.workflow.base_node import BaseNode
from core.workflow.models import (
    ExecutionResult,
    ExecutionStatus,
    NodeExecutionResult,
    NodeStatus,
    TriggerType,
)
from core.workflow.registry import NodeRegistry

logger = logging.getLogger(__name__)

# Type for optional WebSocket status callback
StatusCallback = Callable[[str, str, NodeStatus, dict[str, Any]], Awaitable[None]]


class CycleDetectedError(Exception):
    """Raised when the workflow graph contains a cycle."""

    pass


class WorkflowExecutor:
    """DAG-based workflow executor.

    Loads workflow definition (nodes + edges), validates the graph,
    performs topological sort, and executes nodes sequentially in
    dependency order. Each node's output feeds into its downstream
    nodes' inputs.

    Args:
        on_status_change: Optional async callback fired when node status changes.
            Signature: (execution_id, node_id, new_status, extra_data)
            Used for WebSocket push.
        node_timeout: Max seconds per node execution (default 300 = 5 min).
        max_output_size: Max bytes for node output data (default 10MB).
    """

    def __init__(
        self,
        on_status_change: StatusCallback | None = None,
        node_timeout: float = 300.0,
        max_output_size: int = 10 * 1024 * 1024,
    ) -> None:
        self._on_status_change = on_status_change
        self._node_timeout = node_timeout
        self._max_output_size = max_output_size
        self._cancelled: set[str] = set()  # execution IDs to cancel

    def cancel(self, execution_id: str) -> None:
        """Request cancellation of a running execution."""
        self._cancelled.add(execution_id)

    async def execute(
        self,
        workflow: dict[str, Any],
        trigger_type: TriggerType = TriggerType.MANUAL,
        initial_data: list[dict[str, Any]] | None = None,
    ) -> ExecutionResult:
        """Execute a workflow.

        Args:
            workflow: Dict with "id", "nodes" (list), "edges" (list).
            trigger_type: How execution was triggered.
            initial_data: Optional input data for source nodes (webhook payload, etc.).

        Returns:
            ExecutionResult with per-node results.

        Raises:
            CycleDetectedError: If the graph contains cycles.
            ValueError: If workflow has no nodes.
        """
        result = ExecutionResult(
            workflow_id=workflow.get("id", ""),
            trigger_type=trigger_type,
        )

        nodes_raw = workflow.get("nodes", [])
        edges_raw = workflow.get("edges", [])

        if not nodes_raw:
            result.status = ExecutionStatus.ERROR
            result.error_message = "Workflow has no nodes"
            result.finished_at = datetime.now(timezone.utc)
            return result

        # Build adjacency + in-degree maps
        # node_id -> node definition
        node_map: dict[str, dict[str, Any]] = {}
        for n in nodes_raw:
            nid = n.get("id", "")
            node_map[nid] = n

        # adjacency: source -> [targets]
        adjacency: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {nid: 0 for nid in node_map}

        for edge in edges_raw:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            if src in node_map and tgt in node_map:
                adjacency[src].append(tgt)
                in_degree[tgt] = in_degree.get(tgt, 0) + 1

        # Topological sort (Kahn's algorithm) with cycle detection
        sorted_ids = self._topological_sort(node_map, adjacency, in_degree)

        # Initialize node results
        for nid, node_def in node_map.items():
            node_type = self._get_node_type(node_def)
            result.node_results[nid] = NodeExecutionResult(
                node_id=nid,
                node_type=node_type,
            )

        # Execute
        result.status = ExecutionStatus.RUNNING
        await self._notify(
            result.execution_id,
            "__workflow__",
            NodeStatus.RUNNING,
            {
                "status": ExecutionStatus.RUNNING.value,
                "workflow_id": result.workflow_id,
            },
        )

        # Track node outputs for data flow
        node_outputs: dict[str, list[dict[str, Any]]] = {}

        try:
            for nid in sorted_ids:
                # Check cancellation
                if result.execution_id in self._cancelled:
                    self._cancelled.discard(result.execution_id)
                    result.status = ExecutionStatus.CANCELLED
                    result.error_message = "Execution cancelled by user"
                    break

                node_def = node_map[nid]
                node_type = self._get_node_type(node_def)
                node_result = result.node_results[nid]

                # Resolve node class from registry
                if not NodeRegistry.has(node_type):
                    node_result.status = NodeStatus.ERROR
                    node_result.error_message = f"Unknown node type: {node_type}"
                    result.status = ExecutionStatus.ERROR
                    result.error_message = (
                        f"Node '{nid}' has unknown type: {node_type}"
                    )
                    await self._notify(
                        result.execution_id,
                        nid,
                        NodeStatus.ERROR,
                        {"error": node_result.error_message},
                    )
                    break

                # Gather input data from upstream nodes
                input_data = self._gather_inputs(
                    nid, adjacency, node_outputs, initial_data
                )
                node_result.input_data = input_data

                # Get node params from definition
                params = self._get_node_params(node_def)

                # Mark running
                node_result.status = NodeStatus.RUNNING
                node_result.started_at = datetime.now(timezone.utc)
                await self._notify(
                    result.execution_id, nid, NodeStatus.RUNNING, {}
                )

                # Execute with timeout
                try:
                    node_instance = NodeRegistry.get(node_type)
                    output = await asyncio.wait_for(
                        node_instance.execute(input_data, params),
                        timeout=self._node_timeout,
                    )

                    node_result.output_data = output
                    node_result.status = NodeStatus.SUCCESS
                    node_result.finished_at = datetime.now(timezone.utc)
                    node_result.duration_ms = (
                        node_result.finished_at - node_result.started_at
                    ).total_seconds() * 1000

                    node_outputs[nid] = output

                    await self._notify(
                        result.execution_id,
                        nid,
                        NodeStatus.SUCCESS,
                        {
                            "duration_ms": node_result.duration_ms,
                            "output_count": len(output),
                        },
                    )

                except asyncio.TimeoutError:
                    node_result.status = NodeStatus.ERROR
                    node_result.error_message = (
                        f"Node execution timed out after {self._node_timeout}s"
                    )
                    node_result.finished_at = datetime.now(timezone.utc)
                    result.status = ExecutionStatus.ERROR
                    result.error_message = f"Node '{nid}' timed out"
                    await self._notify(
                        result.execution_id,
                        nid,
                        NodeStatus.ERROR,
                        {"error": node_result.error_message},
                    )
                    break

                except Exception as exc:
                    node_result.status = NodeStatus.ERROR
                    node_result.error_message = str(exc)
                    node_result.finished_at = datetime.now(timezone.utc)
                    result.status = ExecutionStatus.ERROR
                    result.error_message = f"Node '{nid}' failed: {exc}"
                    await self._notify(
                        result.execution_id,
                        nid,
                        NodeStatus.ERROR,
                        {"error": str(exc)},
                    )
                    break

            else:
                # All nodes completed — only set SUCCESS if not already
                # set to CANCELLED/ERROR
                if result.status == ExecutionStatus.RUNNING:
                    result.status = ExecutionStatus.SUCCESS

        except Exception as exc:
            result.status = ExecutionStatus.ERROR
            result.error_message = f"Executor error: {exc}"
            logger.exception(
                "Unexpected executor error for workflow %s", result.workflow_id
            )

        finally:
            result.finished_at = datetime.now(timezone.utc)
            # Mark remaining idle nodes as skipped
            for nr in result.node_results.values():
                if nr.status == NodeStatus.IDLE:
                    nr.status = NodeStatus.SKIPPED

            await self._notify(
                result.execution_id,
                "__workflow__",
                NodeStatus.IDLE,
                {
                    "status": result.status.value,
                    "error_message": result.error_message,
                },
            )

        return result

    def _topological_sort(
        self,
        node_map: dict[str, dict[str, Any]],
        adjacency: dict[str, list[str]],
        in_degree: dict[str, int],
    ) -> list[str]:
        """Kahn's algorithm with cycle detection.

        Returns:
            Topologically sorted list of node IDs.

        Raises:
            CycleDetectedError: If the graph contains a cycle.
        """
        queue: deque[str] = deque()
        for nid, deg in in_degree.items():
            if deg == 0:
                queue.append(nid)

        sorted_ids: list[str] = []
        while queue:
            nid = queue.popleft()
            sorted_ids.append(nid)
            for downstream in adjacency.get(nid, []):
                in_degree[downstream] -= 1
                if in_degree[downstream] == 0:
                    queue.append(downstream)

        if len(sorted_ids) != len(node_map):
            # Find cycle participants
            cycle_nodes = [nid for nid in node_map if nid not in sorted_ids]
            raise CycleDetectedError(
                f"Workflow contains a cycle involving nodes: {cycle_nodes}"
            )

        return sorted_ids

    def _get_node_type(self, node_def: dict[str, Any]) -> str:
        """Extract node type from VueFlow node definition.

        VueFlow stores type in node_def["data"]["type"] or node_def["type"].
        """
        data = node_def.get("data", {})
        return data.get("type", node_def.get("type", "unknown"))

    def _get_node_params(self, node_def: dict[str, Any]) -> dict[str, Any]:
        """Extract user-configured params from node definition."""
        data = node_def.get("data", {})
        return data.get("params", {})

    def _gather_inputs(
        self,
        node_id: str,
        adjacency: dict[str, list[str]],
        node_outputs: dict[str, list[dict[str, Any]]],
        initial_data: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """Gather input data from all upstream nodes.

        For source nodes (no upstream), returns initial_data if provided,
        otherwise empty list.
        """
        # Find all upstream nodes (reverse adjacency lookup)
        upstream_ids = [
            src for src, targets in adjacency.items() if node_id in targets
        ]

        if not upstream_ids:
            return initial_data or []

        # Merge all upstream outputs
        merged: list[dict[str, Any]] = []
        for uid in upstream_ids:
            merged.extend(node_outputs.get(uid, []))
        return merged

    async def _notify(
        self,
        execution_id: str,
        node_id: str,
        status: NodeStatus,
        extra: dict[str, Any],
    ) -> None:
        """Fire the status change callback if registered."""
        if self._on_status_change:
            try:
                await self._on_status_change(
                    execution_id, node_id, status, extra
                )
            except Exception:
                logger.warning("Status callback failed", exc_info=True)
