"""Unit tests for core/kg/utils/verification.py.

TC-VU01 ~ TC-VU03: verify_graph_summary, verify_schema, verify_rbac.
All tests use mocked sessions — no live Neo4j connection required.
"""

from __future__ import annotations

from typing import Any

import pytest

from kg.utils.verification import verify_graph_summary, verify_rbac, verify_schema


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockRecord:
    """Minimal dict-like record object."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class MockResult:
    """Iterable result that also supports list() conversion."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = [MockRecord(r) for r in records]

    def __iter__(self):
        return iter(self._records)

    def single(self) -> MockRecord | None:
        return self._records[0] if self._records else None


class ScriptedSession:
    """Session that returns predefined results for successive .run() calls.

    Each call to .run() pops the next result from the queue. If the queue
    is exhausted it returns an empty MockResult.
    """

    def __init__(self, results: list[list[dict[str, Any]]]) -> None:
        self._queue: list[list[dict[str, Any]]] = list(results)
        self.calls: list[str] = []

    def run(self, cypher: str, *args, **kwargs) -> MockResult:
        self.calls.append(cypher)
        if self._queue:
            return MockResult(self._queue.pop(0))
        return MockResult([])

    def single_run(self, cypher: str, *args, **kwargs) -> MockResult:
        """Alias so code that calls session.run(...).single() works."""
        return self.run(cypher)


# =============================================================================
# TC-VU01: verify_graph_summary
# =============================================================================


@pytest.mark.unit
class TestVerifyGraphSummary:
    """verify_graph_summary() unit tests."""

    def _session(
        self,
        node_records: list[dict],
        rel_records: list[dict],
    ) -> ScriptedSession:
        """Build a session that serves node records then rel records."""
        return ScriptedSession([node_records, rel_records])

    def test_returns_tuple_of_ints(self) -> None:
        """Return type is (int, int)."""
        session = self._session(
            [{"label": "Vessel", "count": 10}],
            [{"type": "DOCKED_AT", "count": 5}],
        )
        result = verify_graph_summary(session)
        assert isinstance(result, tuple)
        assert len(result) == 2
        nodes, rels = result
        assert isinstance(nodes, int)
        assert isinstance(rels, int)

    def test_correct_node_total(self) -> None:
        """Total nodes = sum of all label counts."""
        session = self._session(
            [
                {"label": "Vessel", "count": 7},
                {"label": "Port", "count": 3},
            ],
            [],
        )
        total_nodes, _ = verify_graph_summary(session)
        assert total_nodes == 10

    def test_correct_rel_total(self) -> None:
        """Total rels = sum of all type counts."""
        session = self._session(
            [],
            [
                {"type": "DOCKED_AT", "count": 4},
                {"type": "OPERATED_BY", "count": 6},
            ],
        )
        _, total_rels = verify_graph_summary(session)
        assert total_rels == 10

    def test_empty_graph_returns_zeros(self) -> None:
        """No nodes or rels → (0, 0)."""
        session = self._session([], [])
        result = verify_graph_summary(session)
        assert result == (0, 0)

    def test_null_label_handled(self, capsys) -> None:
        """label=None is displayed as '(unlabeled)'."""
        session = self._session(
            [{"label": None, "count": 2}],
            [],
        )
        verify_graph_summary(session)
        captured = capsys.readouterr()
        assert "(unlabeled)" in captured.out

    def test_output_contains_summary_line(self, capsys) -> None:
        """Output includes a summary line with node and rel counts."""
        session = self._session(
            [{"label": "Vessel", "count": 5}],
            [{"type": "DOCKED_AT", "count": 3}],
        )
        verify_graph_summary(session)
        captured = capsys.readouterr()
        assert "5" in captured.out
        assert "3" in captured.out
        assert "SUMMARY" in captured.out

    def test_single_label_correct(self) -> None:
        """Single label: total_nodes equals that label's count."""
        session = self._session(
            [{"label": "Vessel", "count": 42}],
            [{"type": "DOCKED_AT", "count": 0}],
        )
        nodes, rels = verify_graph_summary(session)
        assert nodes == 42
        assert rels == 0

    def test_two_queries_issued(self) -> None:
        """Exactly two session.run() calls are made."""
        session = self._session([], [])
        verify_graph_summary(session)
        assert len(session.calls) == 2

    def test_output_contains_label_name(self, capsys) -> None:
        """Output contains the label name 'Vessel'."""
        session = self._session(
            [{"label": "Vessel", "count": 1}],
            [],
        )
        verify_graph_summary(session)
        captured = capsys.readouterr()
        assert "Vessel" in captured.out


# =============================================================================
# TC-VU02: verify_schema
# =============================================================================


@pytest.mark.unit
class TestVerifySchema:
    """verify_schema() unit tests."""

    def _session(
        self,
        constraints: list[dict],
        indexes: list[dict],
    ) -> ScriptedSession:
        return ScriptedSession([constraints, indexes])

    def test_returns_tuple_of_ints(self) -> None:
        """Return type is (int, int)."""
        session = self._session([{}], [{}, {}])
        result = verify_schema(session)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_correct_constraint_count(self) -> None:
        """First return value = number of constraints."""
        session = self._session([{}, {}, {}], [])
        constraints, _ = verify_schema(session)
        assert constraints == 3

    def test_correct_index_count(self) -> None:
        """Second return value = number of indexes."""
        session = self._session([], [{}, {}, {}, {}])
        _, indexes = verify_schema(session)
        assert indexes == 4

    def test_empty_schema_returns_zeros(self) -> None:
        """No constraints or indexes → (0, 0)."""
        session = self._session([], [])
        result = verify_schema(session)
        assert result == (0, 0)

    def test_output_contains_counts(self, capsys) -> None:
        """Output line mentions constraint and index counts."""
        session = self._session([{}], [{}, {}])
        verify_schema(session)
        captured = capsys.readouterr()
        assert "1" in captured.out  # 1 constraint
        assert "2" in captured.out  # 2 indexes

    def test_two_queries_issued(self) -> None:
        """Exactly two session.run() calls are made."""
        session = self._session([], [])
        verify_schema(session)
        assert len(session.calls) == 2

    def test_show_constraints_query_issued(self) -> None:
        """First query contains SHOW CONSTRAINTS."""
        session = self._session([], [])
        verify_schema(session)
        assert "SHOW CONSTRAINTS" in session.calls[0]

    def test_show_indexes_query_issued(self) -> None:
        """Second query contains SHOW INDEXES."""
        session = self._session([], [])
        verify_schema(session)
        assert "SHOW INDEXES" in session.calls[1]


# =============================================================================
# TC-VU03: verify_rbac
# =============================================================================


@pytest.mark.unit
class TestVerifyRbac:
    """verify_rbac() unit tests."""

    def _rbac_session(
        self,
        node_cnts: list[int] | None = None,
        rel_cnts: list[int] | None = None,
        access_matrix: list[dict] | None = None,
        user_assignments: list[dict] | None = None,
    ) -> ScriptedSession:
        """Build a scripted session for the RBAC verification queries.

        verify_rbac() issues:
        - 4 node count queries  (User, Role, DataClass, Permission)
        - 4 rel count queries   (HAS_ROLE, CAN_ACCESS, GRANTS, BELONGS_TO)
        - 1 access matrix query
        - 1 user assignments query
        """
        node_counts = node_cnts or [0, 0, 0, 0]
        rel_counts = rel_cnts or [0, 0, 0, 0]

        results: list[list[dict]] = []
        for cnt in node_counts:
            results.append([{"cnt": cnt}])
        for cnt in rel_counts:
            results.append([{"cnt": cnt}])
        results.append(access_matrix or [])
        results.append(user_assignments or [])

        return ScriptedSession(results)

    def test_returns_none(self) -> None:
        """verify_rbac() returns None."""
        session = self._rbac_session()
        result = verify_rbac(session)
        assert result is None

    def test_issues_ten_queries(self) -> None:
        """Exactly 10 session.run() calls: 4 node + 4 rel + 1 matrix + 1 users."""
        session = self._rbac_session()
        verify_rbac(session)
        assert len(session.calls) == 10

    def test_output_contains_rbac_header(self, capsys) -> None:
        """Output contains 'RBAC' somewhere."""
        session = self._rbac_session()
        verify_rbac(session)
        captured = capsys.readouterr()
        assert "RBAC" in captured.out

    def test_node_counts_printed(self, capsys) -> None:
        """Output contains node labels: User, Role, DataClass, Permission."""
        session = self._rbac_session(node_cnts=[5, 3, 8, 12])
        verify_rbac(session)
        captured = capsys.readouterr()
        for label in ("User", "Role", "DataClass", "Permission"):
            assert label in captured.out

    def test_rel_counts_printed(self, capsys) -> None:
        """Output contains rel types: HAS_ROLE, CAN_ACCESS, GRANTS, BELONGS_TO."""
        session = self._rbac_session(rel_cnts=[2, 4, 6, 8])
        verify_rbac(session)
        captured = capsys.readouterr()
        for rel_type in ("HAS_ROLE", "CAN_ACCESS", "GRANTS", "BELONGS_TO"):
            assert rel_type in captured.out

    def test_access_matrix_printed(self, capsys) -> None:
        """Access matrix rows are printed with role name and classes."""
        matrix = [
            {"roleName": "Admin", "level": 3, "classes": ["VesselData", "PortData"]},
        ]
        session = self._rbac_session(access_matrix=matrix)
        verify_rbac(session)
        captured = capsys.readouterr()
        assert "Admin" in captured.out
        assert "VesselData" in captured.out

    def test_access_matrix_empty_classes(self, capsys) -> None:
        """Role with no accessible classes shows '(none)'."""
        matrix = [
            {"roleName": "Guest", "level": 1, "classes": []},
        ]
        session = self._rbac_session(access_matrix=matrix)
        verify_rbac(session)
        captured = capsys.readouterr()
        assert "(none)" in captured.out

    def test_user_assignments_printed(self, capsys) -> None:
        """User assignment rows are printed."""
        assignments = [
            {"userName": "alice", "roleName": "Admin", "maxLevel": 5},
        ]
        session = self._rbac_session(user_assignments=assignments)
        verify_rbac(session)
        captured = capsys.readouterr()
        assert "alice" in captured.out
        assert "Admin" in captured.out

    def test_null_max_level_prints_zero(self, capsys) -> None:
        """maxLevel=None in user assignment is printed as 0."""
        assignments = [
            {"userName": "bob", "roleName": "Viewer", "maxLevel": None},
        ]
        session = self._rbac_session(user_assignments=assignments)
        verify_rbac(session)
        captured = capsys.readouterr()
        assert "bob" in captured.out
        # maxLevel None → printed as 0
        assert "0" in captured.out

    def test_done_message_printed(self, capsys) -> None:
        """Output ends with DONE message."""
        session = self._rbac_session()
        verify_rbac(session)
        captured = capsys.readouterr()
        assert "DONE" in captured.out

    def test_non_zero_node_counts_printed(self, capsys) -> None:
        """Non-zero node counts appear in the output."""
        session = self._rbac_session(node_cnts=[10, 5, 3, 2])
        verify_rbac(session)
        captured = capsys.readouterr()
        assert "10" in captured.out

    def test_empty_access_matrix_no_crash(self) -> None:
        """Empty access matrix → no exception raised."""
        session = self._rbac_session(access_matrix=[])
        verify_rbac(session)  # should not raise

    def test_empty_user_assignments_no_crash(self) -> None:
        """Empty user assignments → no exception raised."""
        session = self._rbac_session(user_assignments=[])
        verify_rbac(session)  # should not raise
