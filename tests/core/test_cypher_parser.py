"""Unit tests for the shared Cypher parser utility."""
from __future__ import annotations

import pytest
from pathlib import Path

from kg.utils.cypher_parser import parse_cypher_file


@pytest.mark.unit
class TestParseCypherFile:
    """Tests for parse_cypher_file()."""

    def test_single_statement(self, tmp_path: Path):
        """단일 문장 파싱."""
        f = tmp_path / "test.cypher"
        f.write_text("CREATE (n:Node {name: 'test'});", encoding="utf-8")
        result = parse_cypher_file(f)
        assert len(result) == 1
        assert result[0] == "CREATE (n:Node {name: 'test'})"

    def test_multiple_statements(self, tmp_path: Path):
        """세미콜론으로 구분된 다중 문장."""
        f = tmp_path / "test.cypher"
        f.write_text(
            "CREATE CONSTRAINT c1 FOR (n:A) REQUIRE n.id IS UNIQUE;\n"
            "CREATE INDEX i1 FOR (n:A) ON (n.name);",
            encoding="utf-8",
        )
        result = parse_cypher_file(f)
        assert len(result) == 2

    def test_comments_stripped(self, tmp_path: Path):
        """// 주석은 제거됨."""
        f = tmp_path / "test.cypher"
        f.write_text(
            "// This is a comment\n"
            "CREATE (n:Node);\n"
            "// Another comment\n"
            "MATCH (n) RETURN n;",
            encoding="utf-8",
        )
        result = parse_cypher_file(f)
        assert len(result) == 2
        assert not any(s.startswith("//") for s in result)

    def test_empty_statements_filtered(self, tmp_path: Path):
        """빈 문장은 필터링됨."""
        f = tmp_path / "test.cypher"
        f.write_text("CREATE (n:Node);\n;\n;\nMATCH (n) RETURN n;", encoding="utf-8")
        result = parse_cypher_file(f)
        assert len(result) == 2

    def test_multiline_statement(self, tmp_path: Path):
        """여러 줄에 걸친 문장이 한 줄로 조인됨."""
        f = tmp_path / "test.cypher"
        f.write_text(
            "CREATE CONSTRAINT\n"
            "  vessel_mmsi_unique\n"
            "FOR (v:Vessel)\n"
            "REQUIRE v.mmsi IS UNIQUE;",
            encoding="utf-8",
        )
        result = parse_cypher_file(f)
        assert len(result) == 1
        assert "vessel_mmsi_unique" in result[0]
        assert "\n" not in result[0]

    def test_empty_file(self, tmp_path: Path):
        """빈 파일은 빈 리스트 반환."""
        f = tmp_path / "test.cypher"
        f.write_text("", encoding="utf-8")
        result = parse_cypher_file(f)
        assert result == []

    def test_only_comments(self, tmp_path: Path):
        """주석만 있는 파일은 빈 리스트 반환."""
        f = tmp_path / "test.cypher"
        f.write_text("// comment 1\n// comment 2\n;", encoding="utf-8")
        result = parse_cypher_file(f)
        assert result == []

    def test_trailing_semicolon(self, tmp_path: Path):
        """마지막 세미콜론 뒤의 빈 문장은 무시."""
        f = tmp_path / "test.cypher"
        f.write_text("CREATE (n:Node);", encoding="utf-8")
        result = parse_cypher_file(f)
        assert len(result) == 1
