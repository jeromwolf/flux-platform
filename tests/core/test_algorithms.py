"""Unit tests for core/kg/algorithms/ package.

All tests are marked @pytest.mark.unit and require no external dependencies.
PYTHONPATH: core:domains
"""

from __future__ import annotations

import dataclasses

import pytest

from kg.algorithms import AlgorithmResult, GraphAlgorithmRunner, ProjectionConfig, ProjectionManager
from kg.algorithms.models import AlgorithmResult, ProjectionConfig
from kg.algorithms.projections import ProjectionManager
from kg.algorithms.runner import GraphAlgorithmRunner, GDSAvailability
from kg.algorithms.centrality import generate_pagerank_cypher, generate_betweenness_cypher
from kg.algorithms.community import generate_louvain_cypher, generate_label_propagation_cypher
from kg.algorithms.pathfinding import generate_shortest_path_cypher, generate_dijkstra_cypher
from kg.algorithms.similarity import generate_node_similarity_cypher


# ---------------------------------------------------------------------------
# ProjectionConfig
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProjectionConfig:
    """Tests for ProjectionConfig frozen dataclass."""

    @pytest.mark.unit
    def test_defaults(self):
        """ProjectionConfig must default orientation to NATURAL and optional fields to None."""
        config = ProjectionConfig(name="test_graph")
        assert config.name == "test_graph"
        assert config.orientation == "NATURAL"
        assert config.node_labels is None
        assert config.relationship_types is None
        assert config.properties is None

    @pytest.mark.unit
    def test_frozen(self):
        """Assignment to any field must raise FrozenInstanceError."""
        config = ProjectionConfig(name="immutable")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            config.name = "changed"  # type: ignore[misc]

    @pytest.mark.unit
    def test_custom_values(self):
        """Custom labels, relationship types, and orientation must be stored."""
        config = ProjectionConfig(
            name="vessel_graph",
            node_labels=["Vessel", "Port"],
            relationship_types=["DOCKED_AT", "SAILED_TO"],
            orientation="UNDIRECTED",
            properties=["name", "capacity"],
        )
        assert config.node_labels == ["Vessel", "Port"]
        assert config.relationship_types == ["DOCKED_AT", "SAILED_TO"]
        assert config.orientation == "UNDIRECTED"
        assert config.properties == ["name", "capacity"]


# ---------------------------------------------------------------------------
# AlgorithmResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAlgorithmResult:
    """Tests for AlgorithmResult frozen dataclass."""

    @pytest.mark.unit
    def test_success_no_errors(self):
        """success must be True when errors list is empty."""
        result = AlgorithmResult(algorithm="pageRank", projection_name="g")
        assert result.success is True
        assert result.errors == []

    @pytest.mark.unit
    def test_failure_with_errors(self):
        """success must be False when errors contains at least one entry."""
        result = AlgorithmResult(
            algorithm="louvain",
            projection_name="g",
            errors=["GDS plugin not found"],
        )
        assert result.success is False
        assert len(result.errors) == 1

    @pytest.mark.unit
    def test_frozen(self):
        """Assignment to any field must raise FrozenInstanceError."""
        result = AlgorithmResult(algorithm="betweenness", projection_name="g")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            result.algorithm = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ProjectionManager
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProjectionManager:
    """Tests for ProjectionManager Cypher generators."""

    @pytest.fixture
    def manager(self) -> ProjectionManager:
        return ProjectionManager()

    @pytest.fixture
    def basic_config(self) -> ProjectionConfig:
        return ProjectionConfig(name="test_graph")

    @pytest.mark.unit
    def test_generate_create_cypher(self, manager, basic_config):
        """generate_create_cypher must return a tuple and contain gds.graph.project."""
        result = manager.generate_create_cypher(basic_config)
        assert isinstance(result, tuple)
        cypher, params = result
        assert "gds.graph.project" in cypher
        assert "name" in params
        assert params["name"] == "test_graph"

    @pytest.mark.unit
    def test_generate_drop_cypher(self, manager):
        """generate_drop_cypher must contain gds.graph.drop."""
        cypher, params = manager.generate_drop_cypher("my_graph")
        assert "gds.graph.drop" in cypher
        assert params["name"] == "my_graph"

    @pytest.mark.unit
    def test_generate_exists_cypher(self, manager):
        """generate_exists_cypher must contain gds.graph.exists."""
        cypher, params = manager.generate_exists_cypher("my_graph")
        assert "gds.graph.exists" in cypher
        assert params["name"] == "my_graph"

    @pytest.mark.unit
    def test_generate_list_cypher(self, manager):
        """generate_list_cypher must contain gds.graph.list."""
        cypher, params = manager.generate_list_cypher()
        assert "gds.graph.list" in cypher
        assert isinstance(params, dict)

    @pytest.mark.unit
    def test_create_with_custom_config(self, manager):
        """Custom node labels and relationship types must appear in params."""
        config = ProjectionConfig(
            name="maritime_graph",
            node_labels=["Vessel", "Port"],
            relationship_types=["DOCKED_AT"],
            orientation="UNDIRECTED",
        )
        cypher, params = manager.generate_create_cypher(config)
        assert "Vessel" in params["nodeLabels"]
        assert "Port" in params["nodeLabels"]
        assert "DOCKED_AT" in params["relTypes"]
        assert params["orient"] == "UNDIRECTED"


# ---------------------------------------------------------------------------
# Centrality algorithms
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCentralityAlgorithms:
    """Tests for centrality Cypher generators."""

    @pytest.mark.unit
    def test_pagerank_cypher(self):
        """PageRank cypher must reference gds.pageRank.stream and include all params."""
        cypher, params = generate_pagerank_cypher(
            "vessel_graph",
            max_iterations=30,
            damping_factor=0.9,
            top_k=5,
        )
        assert "gds.pageRank.stream" in cypher
        assert params["projection"] == "vessel_graph"
        assert "max" in params
        assert "df" in params
        assert "topK" in params
        assert params["max"] == 30
        assert params["df"] == 0.9
        assert params["topK"] == 5

    @pytest.mark.unit
    def test_pagerank_defaults(self):
        """Default PageRank parameters must be maxIterations=20, dampingFactor=0.85."""
        _, params = generate_pagerank_cypher("g")
        assert params["max"] == 20
        assert params["df"] == 0.85

    @pytest.mark.unit
    def test_betweenness_cypher(self):
        """Betweenness cypher must reference gds.betweenness.stream."""
        cypher, params = generate_betweenness_cypher("vessel_graph", top_k=3)
        assert "gds.betweenness.stream" in cypher
        assert params["projection"] == "vessel_graph"
        assert params["topK"] == 3


# ---------------------------------------------------------------------------
# Community algorithms
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCommunityAlgorithms:
    """Tests for community detection Cypher generators."""

    @pytest.mark.unit
    def test_louvain_cypher(self):
        """Louvain cypher must reference gds.louvain.stream."""
        cypher, params = generate_louvain_cypher("vessel_graph", top_k=15)
        assert "gds.louvain.stream" in cypher
        assert params["projection"] == "vessel_graph"
        assert params["topK"] == 15

    @pytest.mark.unit
    def test_label_propagation_cypher(self):
        """Label Propagation cypher must reference gds.labelPropagation.stream."""
        cypher, params = generate_label_propagation_cypher("vessel_graph", top_k=20)
        assert "gds.labelPropagation.stream" in cypher
        assert params["projection"] == "vessel_graph"
        assert params["topK"] == 20


# ---------------------------------------------------------------------------
# Pathfinding algorithms
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPathfindingAlgorithms:
    """Tests for pathfinding Cypher generators."""

    @pytest.mark.unit
    def test_shortest_path_cypher(self):
        """Shortest path cypher must contain gds.shortestPath.dijkstra.stream and both IDs."""
        cypher, params = generate_shortest_path_cypher(
            "vessel_graph",
            source_id="VESSEL-001",
            target_id="PORT-BUS",
        )
        assert "gds.shortestPath.dijkstra.stream" in cypher
        assert params["sourceId"] == "VESSEL-001"
        assert params["targetId"] == "PORT-BUS"

    @pytest.mark.unit
    def test_dijkstra_cypher(self):
        """Dijkstra cypher must include the weight property parameter."""
        cypher, params = generate_dijkstra_cypher(
            "vessel_graph",
            source_id="VESSEL-001",
            target_id="PORT-BUS",
            weight_property="distance",
        )
        assert "gds.shortestPath.dijkstra.stream" in cypher
        assert params["weightProperty"] == "distance"
        assert params["sourceId"] == "VESSEL-001"
        assert params["targetId"] == "PORT-BUS"


# ---------------------------------------------------------------------------
# Similarity algorithms
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimilarityAlgorithms:
    """Tests for similarity Cypher generators."""

    @pytest.mark.unit
    def test_node_similarity_cypher(self):
        """Node Similarity cypher must reference gds.nodeSimilarity.stream and include cutoff."""
        cypher, params = generate_node_similarity_cypher(
            "vessel_graph",
            similarity_cutoff=0.7,
            top_k=5,
        )
        assert "gds.nodeSimilarity.stream" in cypher
        assert params["cutoff"] == 0.7
        assert params["topK"] == 5
        assert params["projection"] == "vessel_graph"


# ---------------------------------------------------------------------------
# GraphAlgorithmRunner
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGraphAlgorithmRunner:
    """Tests for the GraphAlgorithmRunner unified facade."""

    @pytest.fixture
    def runner(self) -> GraphAlgorithmRunner:
        return GraphAlgorithmRunner()

    @pytest.mark.unit
    def test_list_algorithms(self, runner):
        """list_algorithms must return all expected algorithm names."""
        algorithms = runner.list_algorithms()
        expected = {
            "pageRank",
            "betweenness",
            "louvain",
            "labelPropagation",
            "shortestPath",
            "dijkstra",
            "nodeSimilarity",
        }
        assert set(algorithms) == expected

    @pytest.mark.unit
    def test_generate_pagerank(self, runner):
        """generate_pagerank must return a (cypher, params) tuple."""
        cypher, params = runner.generate_pagerank("g", max_iterations=10, top_k=5)
        assert isinstance(cypher, str)
        assert isinstance(params, dict)
        assert "gds.pageRank.stream" in cypher
        assert params["topK"] == 5

    @pytest.mark.unit
    def test_generate_betweenness(self, runner):
        """generate_betweenness must delegate to betweenness cypher generator."""
        cypher, params = runner.generate_betweenness("g", top_k=7)
        assert "gds.betweenness.stream" in cypher
        assert params["topK"] == 7

    @pytest.mark.unit
    def test_generate_louvain(self, runner):
        """generate_louvain must delegate to louvain cypher generator."""
        cypher, params = runner.generate_louvain("g", top_k=12)
        assert "gds.louvain.stream" in cypher
        assert params["topK"] == 12

    @pytest.mark.unit
    def test_generate_shortest_path(self, runner):
        """generate_shortest_path must forward source and target IDs correctly."""
        cypher, params = runner.generate_shortest_path(
            "g", source_id="A", target_id="B"
        )
        assert "gds.shortestPath.dijkstra.stream" in cypher
        assert params["sourceId"] == "A"
        assert params["targetId"] == "B"

    @pytest.mark.unit
    def test_projection_manager_property(self, runner):
        """projection_manager property must return a ProjectionManager instance."""
        pm = runner.projection_manager
        assert isinstance(pm, ProjectionManager)


# ---------------------------------------------------------------------------
# GDSAvailability
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGDSAvailability:
    """Tests for GDSAvailability.generate_check_cypher."""

    @pytest.mark.unit
    def test_check_cypher(self):
        """The check cypher must contain gds.version()."""
        cypher, params = GDSAvailability.generate_check_cypher()
        assert "gds.version()" in cypher
        assert isinstance(params, dict)
