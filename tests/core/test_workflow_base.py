"""Tests for workflow engine core: BaseNode, NodeRegistry, models."""
import pytest

from core.workflow.base_node import BaseNode
from core.workflow.registry import NodeRegistry
from core.workflow.models import (
    ExecutionStatus,
    NodeStatus,
    TriggerType,
    NodeExecutionResult,
    ExecutionResult,
)


# --- Test Fixtures ---


class MockNode(BaseNode):
    name = "mock"
    display_name = "Mock Node"
    description = "Test node"
    category = "test"

    async def execute(self, input_data, params):
        return [{"result": "mock", **params}]

    def get_parameter_schema(self):
        return {"type": "object", "properties": {"key": {"type": "string"}}}


class FailNode(BaseNode):
    name = "fail"
    display_name = "Fail Node"
    description = "Always fails"
    category = "test"

    async def execute(self, input_data, params):
        raise RuntimeError("Intentional failure")


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear NodeRegistry before each test."""
    NodeRegistry.clear()
    yield
    NodeRegistry.clear()


# --- BaseNode Tests ---


class TestBaseNode:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseNode()

    def test_mock_node_attributes(self):
        node = MockNode()
        assert node.name == "mock"
        assert node.display_name == "Mock Node"
        assert node.category == "test"

    @pytest.mark.asyncio
    async def test_mock_node_execute(self):
        node = MockNode()
        result = await node.execute([], {"key": "value"})
        assert result == [{"result": "mock", "key": "value"}]

    def test_parameter_schema(self):
        node = MockNode()
        schema = node.get_parameter_schema()
        assert "properties" in schema

    def test_validate_params_default(self):
        node = MockNode()
        errors = node.validate_params({"key": "val"})
        assert errors == []

    @pytest.mark.asyncio
    async def test_fail_node_raises(self):
        node = FailNode()
        with pytest.raises(RuntimeError, match="Intentional failure"):
            await node.execute([], {})

    def test_default_parameter_schema_empty(self):
        """BaseNode subclass without override returns empty dict."""
        node = FailNode()
        schema = node.get_parameter_schema()
        assert schema == {}


# --- NodeRegistry Tests ---


class TestNodeRegistry:
    def test_register_and_get(self):
        NodeRegistry.register(MockNode)
        node = NodeRegistry.get("mock")
        assert isinstance(node, MockNode)

    def test_register_as_decorator(self):
        @NodeRegistry.register
        class DecoratedNode(BaseNode):
            name = "decorated"
            display_name = "Decorated"
            description = ""

            async def execute(self, input_data, params):
                return []

        assert NodeRegistry.has("decorated")

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown node type"):
            NodeRegistry.get("nonexistent")

    def test_register_empty_name_raises(self):
        class EmptyNameNode(BaseNode):
            name = ""

            async def execute(self, input_data, params):
                return []

        with pytest.raises(ValueError, match="no 'name'"):
            NodeRegistry.register(EmptyNameNode)

    def test_has(self):
        assert not NodeRegistry.has("mock")
        NodeRegistry.register(MockNode)
        assert NodeRegistry.has("mock")

    def test_list_types(self):
        NodeRegistry.register(MockNode)
        types = NodeRegistry.list_types()
        assert len(types) == 1
        assert types[0]["name"] == "mock"
        assert "parameter_schema" in types[0]

    def test_clear(self):
        NodeRegistry.register(MockNode)
        assert NodeRegistry.has("mock")
        NodeRegistry.clear()
        assert not NodeRegistry.has("mock")

    def test_list_types_includes_all_metadata(self):
        NodeRegistry.register(MockNode)
        types = NodeRegistry.list_types()
        entry = types[0]
        assert entry["display_name"] == "Mock Node"
        assert entry["description"] == "Test node"
        assert entry["category"] == "test"

    def test_overwrite_existing_logs_warning(self):
        """Registering same name twice replaces it (with log warning)."""
        NodeRegistry.register(MockNode)

        class MockNode2(BaseNode):
            name = "mock"
            display_name = "Mock2"
            description = ""

            async def execute(self, input_data, params):
                return [{"v": 2}]

        NodeRegistry.register(MockNode2)
        node = NodeRegistry.get("mock")
        assert node.display_name == "Mock2"


# --- Model Tests ---


class TestModels:
    def test_execution_status_values(self):
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.SUCCESS.value == "success"
        assert ExecutionStatus.ERROR.value == "error"
        assert ExecutionStatus.CANCELLED.value == "cancelled"

    def test_node_status_values(self):
        assert NodeStatus.IDLE.value == "idle"
        assert NodeStatus.RUNNING.value == "running"
        assert NodeStatus.SUCCESS.value == "success"
        assert NodeStatus.ERROR.value == "error"
        assert NodeStatus.SKIPPED.value == "skipped"

    def test_trigger_type_values(self):
        assert TriggerType.MANUAL.value == "manual"
        assert TriggerType.SCHEDULE.value == "schedule"
        assert TriggerType.WEBHOOK.value == "webhook"
        assert TriggerType.EVENT.value == "event"

    def test_node_execution_result_to_dict(self):
        nr = NodeExecutionResult(node_id="n1", node_type="mock")
        d = nr.to_dict()
        assert d["node_id"] == "n1"
        assert d["status"] == "idle"
        assert d["output_data"] == []
        assert d["input_data"] == []
        assert d["error_message"] == ""
        assert d["started_at"] is None
        assert d["finished_at"] is None
        assert d["duration_ms"] == 0.0

    def test_execution_result_to_dict(self):
        er = ExecutionResult(workflow_id="wf1")
        d = er.to_dict()
        assert d["workflow_id"] == "wf1"
        assert d["status"] == "pending"
        assert d["trigger_type"] == "manual"
        assert isinstance(d["id"], str)
        assert len(d["id"]) == 12

    def test_execution_result_default_fields(self):
        er = ExecutionResult()
        assert er.workflow_id == ""
        assert er.status == ExecutionStatus.PENDING
        assert er.trigger_type == TriggerType.MANUAL
        assert er.node_results == {}
        assert er.error_message == ""
        assert er.finished_at is None

    def test_node_execution_result_defaults(self):
        nr = NodeExecutionResult(node_id="x", node_type="y")
        assert nr.status == NodeStatus.IDLE
        assert nr.input_data == []
        assert nr.output_data == []

    def test_execution_status_is_str_enum(self):
        """ExecutionStatus values are usable as strings."""
        assert ExecutionStatus.SUCCESS == "success"
        assert str(ExecutionStatus.ERROR) == "ExecutionStatus.ERROR"
