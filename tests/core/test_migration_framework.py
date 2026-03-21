"""Unit tests for the Neo4j migration framework."""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# The migrations package is under infra/, so we need to add it to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "infra"))

from migrations.models import MigrationFile, AppliedMigration
from migrations.runner import MigrationRunner


@pytest.mark.unit
class TestMigrationFile:
    """Tests for MigrationFile dataclass."""

    def test_frozen(self):
        """MigrationFile은 frozen dataclass."""
        m = MigrationFile(
            version="V001", sequence=1, description="test",
            path=Path("/tmp/V001__test.cypher"), checksum="sha256:abc",
        )
        with pytest.raises(AttributeError):
            m.version = "V002"  # type: ignore[misc]

    def test_compute_checksum(self, tmp_path: Path):
        """SHA-256 체크섬 계산."""
        f = tmp_path / "test.cypher"
        content = "CREATE (n:Node);"
        f.write_text(content, encoding="utf-8")
        result = MigrationFile.compute_checksum(f)
        expected = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert result == expected

    def test_statements_default_empty(self):
        """기본 statements는 빈 튜플."""
        m = MigrationFile(
            version="V001", sequence=1, description="test",
            path=Path("/tmp/test.cypher"), checksum="sha256:abc",
        )
        assert m.statements == ()


@pytest.mark.unit
class TestAppliedMigration:
    """Tests for AppliedMigration dataclass."""

    def test_frozen(self):
        a = AppliedMigration(
            version="V001", description="test",
            checksum="sha256:abc", applied_at="2026-01-01T00:00:00Z",
            execution_time_ms=100,
        )
        with pytest.raises(AttributeError):
            a.version = "V002"  # type: ignore[misc]

    def test_default_environment(self):
        a = AppliedMigration(
            version="V001", description="test",
            checksum="sha256:abc", applied_at="2026-01-01T00:00:00Z",
            execution_time_ms=100,
        )
        assert a.environment == ""


@pytest.mark.unit
class TestMigrationDiscovery:
    """Tests for MigrationRunner.discover_migrations()."""

    def _create_migration_files(self, tmp_path: Path, names: list[str]) -> None:
        for name in names:
            (tmp_path / name).write_text(f"// {name}\nCREATE (n:Test);", encoding="utf-8")

    def test_discovers_valid_files(self, tmp_path: Path):
        """V{NNN}__desc.cypher 패턴 파일 발견."""
        self._create_migration_files(tmp_path, [
            "V001__initial.cypher",
            "V002__add_indexes.cypher",
        ])
        runner = MigrationRunner(MagicMock(), "neo4j")
        migrations = runner.discover_migrations(tmp_path)
        assert len(migrations) == 2
        assert migrations[0].version == "V001"
        assert migrations[1].version == "V002"

    def test_sorted_by_sequence(self, tmp_path: Path):
        """시퀀스 번호 순으로 정렬."""
        self._create_migration_files(tmp_path, [
            "V003__third.cypher",
            "V001__first.cypher",
            "V002__second.cypher",
        ])
        runner = MigrationRunner(MagicMock(), "neo4j")
        migrations = runner.discover_migrations(tmp_path)
        assert [m.sequence for m in migrations] == [1, 2, 3]

    def test_skips_non_matching_files(self, tmp_path: Path):
        """패턴에 맞지 않는 파일은 무시."""
        self._create_migration_files(tmp_path, [
            "V001__valid.cypher",
            "not_a_migration.cypher",
            "README.md",
        ])
        runner = MigrationRunner(MagicMock(), "neo4j")
        migrations = runner.discover_migrations(tmp_path)
        assert len(migrations) == 1

    def test_parses_statements(self, tmp_path: Path):
        """마이그레이션 파일의 Cypher 문장이 파싱됨."""
        f = tmp_path / "V001__test.cypher"
        f.write_text("CREATE (a:A);\nCREATE (b:B);", encoding="utf-8")
        runner = MigrationRunner(MagicMock(), "neo4j")
        migrations = runner.discover_migrations(tmp_path)
        assert len(migrations[0].statements) == 2

    def test_empty_directory(self, tmp_path: Path):
        """빈 디렉토리는 빈 리스트."""
        runner = MigrationRunner(MagicMock(), "neo4j")
        migrations = runner.discover_migrations(tmp_path)
        assert migrations == []

    def test_computes_checksum(self, tmp_path: Path):
        """각 파일의 체크섬이 계산됨."""
        f = tmp_path / "V001__test.cypher"
        content = "CREATE (n:Test);"
        f.write_text(content, encoding="utf-8")
        runner = MigrationRunner(MagicMock(), "neo4j")
        migrations = runner.discover_migrations(tmp_path)
        expected = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert migrations[0].checksum == expected


@pytest.mark.unit
class TestMigrationValidation:
    """Tests for MigrationRunner.validate()."""

    def _create_migration_files(self, tmp_path: Path, names: list[str]) -> None:
        for name in names:
            (tmp_path / name).write_text("CREATE (n:Test);", encoding="utf-8")

    def test_valid_sequence(self, tmp_path: Path):
        """연속된 시퀀스는 에러 없음."""
        self._create_migration_files(tmp_path, [
            "V001__first.cypher",
            "V002__second.cypher",
            "V003__third.cypher",
        ])
        runner = MigrationRunner(MagicMock(), "neo4j")
        errors = runner.validate(tmp_path)
        assert errors == []

    def test_gap_in_sequence(self, tmp_path: Path):
        """시퀀스 갭 감지."""
        self._create_migration_files(tmp_path, [
            "V001__first.cypher",
            "V003__third.cypher",
        ])
        runner = MigrationRunner(MagicMock(), "neo4j")
        errors = runner.validate(tmp_path)
        assert len(errors) >= 1
        assert "Gap" in errors[0] or "gap" in errors[0].lower() or "expected" in errors[0].lower()

    def test_empty_migration_detected(self, tmp_path: Path):
        """빈 문장 마이그레이션 감지."""
        (tmp_path / "V001__empty.cypher").write_text("// only comments\n;", encoding="utf-8")
        runner = MigrationRunner(MagicMock(), "neo4j")
        errors = runner.validate(tmp_path)
        assert any("no executable" in e.lower() or "empty" in e.lower() for e in errors)


@pytest.mark.unit
class TestMigrationDryRun:
    """Tests for dry-run mode."""

    def test_dry_run_does_not_call_driver(self, tmp_path: Path):
        """Dry run은 드라이버를 호출하지 않음."""
        (tmp_path / "V001__test.cypher").write_text("CREATE (n:Test);", encoding="utf-8")
        mock_driver = MagicMock()
        runner = MigrationRunner(mock_driver, "neo4j")
        migration = runner.discover_migrations(tmp_path)[0]
        runner.apply(migration, dry_run=True)
        mock_driver.session.assert_not_called()
