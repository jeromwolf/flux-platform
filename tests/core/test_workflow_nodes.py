"""Tests for built-in workflow nodes."""
import importlib
import pytest

from core.workflow.registry import NodeRegistry
import core.workflow.nodes as _nodes_pkg
import core.workflow.nodes.data_input as _data_input_mod
import core.workflow.nodes.http_request as _http_request_mod
import core.workflow.nodes.crawler as _crawler_mod
import core.workflow.nodes.transform as _transform_mod
import core.workflow.nodes.llm as _llm_mod
import core.workflow.nodes.neo4j_output as _neo4j_output_mod


@pytest.fixture(autouse=True)
def load_nodes():
    NodeRegistry.clear()
    # Re-register all built-in nodes by reloading their modules
    importlib.reload(_data_input_mod)
    importlib.reload(_http_request_mod)
    importlib.reload(_crawler_mod)
    importlib.reload(_transform_mod)
    importlib.reload(_llm_mod)
    importlib.reload(_neo4j_output_mod)
    yield
    NodeRegistry.clear()


class TestDataInputNode:
    @pytest.mark.asyncio
    async def test_text_mode(self):
        node = NodeRegistry.get("input")
        result = await node.execute([], {"mode": "text", "value": "hello"})
        assert result == [{"text": "hello"}]

    @pytest.mark.asyncio
    async def test_json_mode_dict(self):
        node = NodeRegistry.get("input")
        result = await node.execute([], {"mode": "json", "value": {"key": "val"}})
        assert result == [{"key": "val"}]

    @pytest.mark.asyncio
    async def test_json_mode_string(self):
        node = NodeRegistry.get("input")
        result = await node.execute([], {"mode": "json", "value": '{"key": "val"}'})
        assert result == [{"key": "val"}]

    @pytest.mark.asyncio
    async def test_json_mode_list_value(self):
        node = NodeRegistry.get("input")
        result = await node.execute([], {"mode": "json", "value": [{"a": 1}, {"b": 2}]})
        assert len(result) == 2
        assert result[0] == {"a": 1}

    @pytest.mark.asyncio
    async def test_list_mode(self):
        node = NodeRegistry.get("input")
        result = await node.execute([], {"mode": "list", "value": "a\nb\nc"})
        assert len(result) == 3
        assert result[0]["item"] == "a"
        assert result[0]["index"] == 0

    @pytest.mark.asyncio
    async def test_list_mode_skips_empty_lines(self):
        node = NodeRegistry.get("input")
        result = await node.execute([], {"mode": "list", "value": "a\n\nb"})
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_default_mode(self):
        node = NodeRegistry.get("input")
        result = await node.execute([], {"value": "test"})
        assert result == [{"text": "test"}]

    def test_parameter_schema(self):
        node = NodeRegistry.get("input")
        schema = node.get_parameter_schema()
        assert "properties" in schema
        assert "mode" in schema["properties"]


class TestTransformNode:
    @pytest.mark.asyncio
    async def test_extract_field(self):
        node = NodeRegistry.get("process")
        result = await node.execute(
            [{"a": {"b": 42}}],
            {"operation": "extract_field", "config": {"field": "a.b", "output_key": "value"}},
        )
        assert result == [{"value": 42}]

    @pytest.mark.asyncio
    async def test_rename_fields(self):
        node = NodeRegistry.get("process")
        result = await node.execute(
            [{"old_name": "val"}],
            {"operation": "rename_fields", "config": {"mapping": {"old_name": "new_name"}}},
        )
        assert result == [{"new_name": "val"}]

    @pytest.mark.asyncio
    async def test_filter_by_value(self):
        node = NodeRegistry.get("process")
        result = await node.execute(
            [{"x": 1}, {"x": 2}, {"x": 3}],
            {"operation": "filter_by_value", "config": {"field": "x", "value": 2, "operator": "gt"}},
        )
        assert len(result) == 1
        assert result[0]["x"] == 3

    @pytest.mark.asyncio
    async def test_filter_by_value_eq(self):
        node = NodeRegistry.get("process")
        result = await node.execute(
            [{"x": 1}, {"x": 2}],
            {"operation": "filter_by_value", "config": {"field": "x", "value": 2, "operator": "eq"}},
        )
        assert len(result) == 1
        assert result[0]["x"] == 2

    @pytest.mark.asyncio
    async def test_filter_by_value_lt(self):
        node = NodeRegistry.get("process")
        result = await node.execute(
            [{"x": 1}, {"x": 5}],
            {"operation": "filter_by_value", "config": {"field": "x", "value": 3, "operator": "lt"}},
        )
        assert len(result) == 1
        assert result[0]["x"] == 1

    @pytest.mark.asyncio
    async def test_template(self):
        node = NodeRegistry.get("process")
        result = await node.execute(
            [{"name": "World"}],
            {"operation": "template", "config": {"template": "Hello {{name}}!", "output_key": "text"}},
        )
        assert result[0]["text"] == "Hello World!"

    @pytest.mark.asyncio
    async def test_select_fields(self):
        node = NodeRegistry.get("process")
        result = await node.execute(
            [{"a": 1, "b": 2, "c": 3}],
            {"operation": "select_fields", "config": {"fields": ["a", "c"]}},
        )
        assert result == [{"a": 1, "c": 3}]

    @pytest.mark.asyncio
    async def test_merge(self):
        node = NodeRegistry.get("process")
        result = await node.execute(
            [{"a": 1}, {"b": 2}],
            {"operation": "merge", "config": {}},
        )
        assert result == [{"a": 1, "b": 2}]

    @pytest.mark.asyncio
    async def test_merge_empty(self):
        node = NodeRegistry.get("process")
        result = await node.execute(
            [],
            {"operation": "merge", "config": {}},
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_split_text(self):
        node = NodeRegistry.get("process")
        result = await node.execute(
            [{"text": "a\nb\nc"}],
            {"operation": "split_text", "config": {"field": "text", "delimiter": "\n"}},
        )
        assert len(result) == 3
        assert result[0]["text"] == "a"

    @pytest.mark.asyncio
    async def test_unknown_operation_raises(self):
        node = NodeRegistry.get("process")
        with pytest.raises(ValueError, match="Unknown operation"):
            await node.execute([], {"operation": "evil_exec"})

    def test_parameter_schema(self):
        node = NodeRegistry.get("process")
        schema = node.get_parameter_schema()
        assert "operation" in schema["properties"]


class TestNeo4jOutputNode:
    @pytest.mark.asyncio
    async def test_merge_mode(self):
        node = NodeRegistry.get("output")
        result = await node.execute(
            [{"name": "TestEntity", "type": "Ship"}],
            {"mode": "merge", "label": "Vessel"},
        )
        assert len(result) == 1
        assert "cypher" in result[0]
        assert "MERGE" in result[0]["cypher"]
        assert result[0]["label"] == "Vessel"

    @pytest.mark.asyncio
    async def test_create_mode(self):
        node = NodeRegistry.get("output")
        result = await node.execute(
            [{"name": "Ship1"}],
            {"mode": "create", "label": "Vessel"},
        )
        assert "CREATE" in result[0]["cypher"]

    @pytest.mark.asyncio
    async def test_custom_mode(self):
        node = NodeRegistry.get("output")
        result = await node.execute(
            [{"name": "Ship1"}],
            {"mode": "custom", "cypher": "CREATE (n:Ship {name: '{{name}}'})"},
        )
        assert "Ship1" in result[0]["cypher"]

    @pytest.mark.asyncio
    async def test_custom_no_cypher_raises(self):
        node = NodeRegistry.get("output")
        with pytest.raises(ValueError, match="requires 'cypher'"):
            await node.execute([{}], {"mode": "custom"})

    @pytest.mark.asyncio
    async def test_merge_mode_no_properties_skips(self):
        """Items with no scalar properties are skipped."""
        node = NodeRegistry.get("output")
        result = await node.execute(
            [{"nested": {"a": 1}}],  # no scalar values at top level
            {"mode": "merge", "label": "Vessel"},
        )
        assert result[0]["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_create_mode_with_properties_filter(self):
        node = NodeRegistry.get("output")
        result = await node.execute(
            [{"name": "Ship1", "tonnage": 5000, "extra": "ignored"}],
            {"mode": "create", "label": "Vessel", "properties": ["name", "tonnage"]},
        )
        assert "tonnage" in result[0]["cypher"]

    def test_parameter_schema(self):
        node = NodeRegistry.get("output")
        schema = node.get_parameter_schema()
        assert "mode" in schema["properties"]


class TestNodeRegistration:
    def test_all_six_nodes_registered(self):
        expected = {"input", "api", "crawler", "process", "ai", "output"}
        registered = {t["name"] for t in NodeRegistry.list_types()}
        assert expected.issubset(registered)

    def test_each_node_has_schema(self):
        for info in NodeRegistry.list_types():
            assert isinstance(info["parameter_schema"], dict)

    def test_each_node_has_category(self):
        for info in NodeRegistry.list_types():
            assert info["category"] != ""
