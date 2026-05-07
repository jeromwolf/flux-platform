"""Tests for WorkflowExecutor — DAG execution, cycle detection, data flow."""
import pytest
import asyncio

from core.workflow.base_node import BaseNode
from core.workflow.registry import NodeRegistry
from core.workflow.executor import WorkflowExecutor, CycleDetectedError
from core.workflow.models import ExecutionStatus, NodeStatus


# --- Test Nodes ---


class EchoNode(BaseNode):
    name = "echo"
    display_name = "Echo"
    description = "Returns input + params"

    async def execute(self, input_data, params):
        return [{"echo": True, "input": input_data, **params}]


class DoubleNode(BaseNode):
    name = "double"
    display_name = "Double"
    description = "Doubles input count"

    async def execute(self, input_data, params):
        return input_data + input_data if input_data else [{"doubled": True}]


class SlowNode(BaseNode):
    name = "slow"
    display_name = "Slow"
    description = "Takes time"

    async def execute(self, input_data, params):
        await asyncio.sleep(params.get("delay", 0.1))
        return [{"slow": True}]


class ErrorNode(BaseNode):
    name = "error_node"
    display_name = "Error"
    description = "Always fails"

    async def execute(self, input_data, params):
        raise RuntimeError("Boom!")


@pytest.fixture(autouse=True)
def register_test_nodes():
    NodeRegistry.clear()
    NodeRegistry.register(EchoNode)
    NodeRegistry.register(DoubleNode)
    NodeRegistry.register(SlowNode)
    NodeRegistry.register(ErrorNode)
    yield
    NodeRegistry.clear()


# --- Helper ---


def make_workflow(nodes_def, edges_def, wf_id="test-wf"):
    """Build a workflow dict from simplified definitions."""
    nodes = []
    for nid, ntype in nodes_def:
        nodes.append({
            "id": nid,
            "type": "custom",
            "data": {"type": ntype, "label": nid, "params": {}},
            "position": {"x": 0, "y": 0},
        })
    edges = []
    for i, (src, tgt) in enumerate(edges_def):
        edges.append({"id": f"e{i}", "source": src, "target": tgt})
    return {"id": wf_id, "nodes": nodes, "edges": edges}


# --- Tests ---


class TestWorkflowExecutor:

    @pytest.mark.asyncio
    async def test_empty_workflow(self):
        executor = WorkflowExecutor()
        result = await executor.execute({"id": "w1", "nodes": [], "edges": []})
        assert result.status == ExecutionStatus.ERROR
        assert "no nodes" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_single_node(self):
        wf = make_workflow([("n1", "echo")], [])
        executor = WorkflowExecutor()
        result = await executor.execute(wf)
        assert result.status == ExecutionStatus.SUCCESS
        assert "n1" in result.node_results
        assert result.node_results["n1"].status == NodeStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_linear_chain(self):
        wf = make_workflow(
            [("n1", "echo"), ("n2", "echo"), ("n3", "echo")],
            [("n1", "n2"), ("n2", "n3")],
        )
        executor = WorkflowExecutor()
        result = await executor.execute(wf)
        assert result.status == ExecutionStatus.SUCCESS
        assert all(
            nr.status == NodeStatus.SUCCESS for nr in result.node_results.values()
        )

    @pytest.mark.asyncio
    async def test_diamond_dag(self):
        """A -> B, A -> C, B -> D, C -> D"""
        wf = make_workflow(
            [("a", "echo"), ("b", "echo"), ("c", "echo"), ("d", "echo")],
            [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
        )
        executor = WorkflowExecutor()
        result = await executor.execute(wf)
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_cycle_detection(self):
        wf = make_workflow(
            [("a", "echo"), ("b", "echo"), ("c", "echo")],
            [("a", "b"), ("b", "c"), ("c", "a")],
        )
        executor = WorkflowExecutor()
        with pytest.raises(CycleDetectedError, match="cycle"):
            await executor.execute(wf)

    @pytest.mark.asyncio
    async def test_node_error_stops_execution(self):
        wf = make_workflow(
            [("n1", "echo"), ("n2", "error_node"), ("n3", "echo")],
            [("n1", "n2"), ("n2", "n3")],
        )
        executor = WorkflowExecutor()
        result = await executor.execute(wf)
        assert result.status == ExecutionStatus.ERROR
        assert result.node_results["n1"].status == NodeStatus.SUCCESS
        assert result.node_results["n2"].status == NodeStatus.ERROR
        assert result.node_results["n3"].status == NodeStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_unknown_node_type(self):
        wf = make_workflow([("n1", "nonexistent")], [])
        executor = WorkflowExecutor()
        result = await executor.execute(wf)
        assert result.status == ExecutionStatus.ERROR
        assert "unknown" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_cancellation(self):
        """Verify cancel() method adds to _cancelled set."""
        executor = WorkflowExecutor()
        executor.cancel("test-exec-id")
        assert "test-exec-id" in executor._cancelled

    @pytest.mark.asyncio
    async def test_timeout(self):
        wf = make_workflow([("n1", "slow")], [])
        # Set very short timeout and add delay param
        wf["nodes"][0]["data"]["params"] = {"delay": 5}
        executor = WorkflowExecutor(node_timeout=0.1)
        result = await executor.execute(wf)
        assert result.status == ExecutionStatus.ERROR
        assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_status_callback(self):
        statuses = []

        async def on_status(exec_id, node_id, status, extra):
            statuses.append((node_id, status.value))

        wf = make_workflow([("n1", "echo")], [])
        executor = WorkflowExecutor(on_status_change=on_status)
        await executor.execute(wf)

        # Should have: workflow running, n1 running, n1 success, workflow done
        node_statuses = [(nid, s) for nid, s in statuses if nid == "n1"]
        assert ("n1", "running") in node_statuses
        assert ("n1", "success") in node_statuses

    @pytest.mark.asyncio
    async def test_data_flow(self):
        """Test that output of node A flows to input of node B."""
        wf = make_workflow(
            [("n1", "echo"), ("n2", "echo")],
            [("n1", "n2")],
        )
        executor = WorkflowExecutor()
        result = await executor.execute(wf)

        n2_input = result.node_results["n2"].input_data
        n1_output = result.node_results["n1"].output_data
        assert n2_input == n1_output

    @pytest.mark.asyncio
    async def test_initial_data(self):
        """Test initial_data passed to source nodes."""
        wf = make_workflow([("n1", "echo")], [])
        executor = WorkflowExecutor()
        result = await executor.execute(wf, initial_data=[{"key": "value"}])

        n1_input = result.node_results["n1"].input_data
        assert n1_input == [{"key": "value"}]

    @pytest.mark.asyncio
    async def test_multiple_source_nodes(self):
        """Multiple nodes with no upstream all run."""
        wf = make_workflow(
            [("a", "echo"), ("b", "echo"), ("c", "echo")],
            [],  # No edges — all independent
        )
        executor = WorkflowExecutor()
        result = await executor.execute(wf)
        assert result.status == ExecutionStatus.SUCCESS
        assert len(result.node_results) == 3

    @pytest.mark.asyncio
    async def test_workflow_id_propagated(self):
        """Execution result has the correct workflow_id."""
        wf = make_workflow([("n1", "echo")], [], wf_id="my-wf-42")
        executor = WorkflowExecutor()
        result = await executor.execute(wf)
        assert result.workflow_id == "my-wf-42"

    @pytest.mark.asyncio
    async def test_node_duration_tracked(self):
        """Node execution duration is recorded."""
        wf = make_workflow([("n1", "slow")], [])
        wf["nodes"][0]["data"]["params"] = {"delay": 0.05}
        executor = WorkflowExecutor()
        result = await executor.execute(wf)
        assert result.node_results["n1"].duration_ms >= 40  # at least ~50ms

    @pytest.mark.asyncio
    async def test_double_node_data_doubling(self):
        """DoubleNode doubles the input list."""
        wf = make_workflow(
            [("n1", "echo"), ("n2", "double")],
            [("n1", "n2")],
        )
        executor = WorkflowExecutor()
        result = await executor.execute(wf)
        # echo produces 1 item, double should produce 2
        assert len(result.node_results["n2"].output_data) == 2

    @pytest.mark.asyncio
    async def test_error_message_contains_node_id(self):
        """Error message includes which node failed."""
        wf = make_workflow([("broken", "error_node")], [])
        executor = WorkflowExecutor()
        result = await executor.execute(wf)
        assert "broken" in result.error_message

    @pytest.mark.asyncio
    async def test_finished_at_set_on_success(self):
        """Execution result finished_at is set when done."""
        wf = make_workflow([("n1", "echo")], [])
        executor = WorkflowExecutor()
        result = await executor.execute(wf)
        assert result.finished_at is not None
