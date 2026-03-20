"""Unit tests for the kg.n10s (Neosemantics) integration module.

Test Coverage:
- N10sConfig constants, graph config init/drop/get, namespace management (11 tests)
- N10sImporter default path, inline/URL/file import, setup pipeline, error handling (12 tests)
- OWLExporter Turtle generation: prefixes, header, classes, properties, type mapping (10 tests)
- ImportResult dataclass defaults and fields (3 tests)

All tests are marked with ``@pytest.mark.unit`` and run without a live Neo4j
instance. Neo4j driver interactions are replaced with ``unittest.mock`` mocks.

Usage::

    PYTHONPATH=. python -m pytest tests/test_n10s.py -v -m unit
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_driver() -> MagicMock:
    """Return a MagicMock Neo4j driver with a chainable session context manager."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver


def _get_mock_session(driver: MagicMock) -> MagicMock:
    """Extract the inner session mock from a mock driver."""
    return driver.session.return_value.__enter__.return_value


# =========================================================================
# TestN10sConfig
# =========================================================================


@pytest.mark.unit
class TestN10sConfig:
    """Unit tests for kg.n10s.config.N10sConfig."""

    # ------------------------------------------------------------------
    # Constants
    # ------------------------------------------------------------------

    def test_default_constants(self):
        """BASE_URI, S100_URI, DEFAULT_GRAPH_CONFIG 상수가 예상 값을 가져야 한다."""
        from kg.n10s.config import BASE_URI, DEFAULT_GRAPH_CONFIG, S100_URI

        assert BASE_URI == "https://kg.kriso.re.kr/maritime#"
        assert "registry.iho.int" in S100_URI
        assert isinstance(DEFAULT_GRAPH_CONFIG, dict)
        assert "handleVocabUris" in DEFAULT_GRAPH_CONFIG

    # ------------------------------------------------------------------
    # init_graph_config
    # ------------------------------------------------------------------

    def test_init_graph_config(self):
        """init_graph_config() 호출 시 n10s.graphconfig.init 프로시저를 실행해야 한다."""
        from kg.n10s.config import N10sConfig

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        session.run.return_value = []

        cfg = N10sConfig(driver)
        result = cfg.init_graph_config()

        assert result is True
        cypher_calls = str(session.run.call_args_list)
        assert "n10s.graphconfig.init" in cypher_calls

    def test_init_graph_config_custom(self):
        """init_graph_config()는 커스텀 설정 dict를 파라미터로 전달해야 한다."""
        from kg.n10s.config import N10sConfig

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        session.run.return_value = []
        custom = {"handleVocabUris": "IGNORE", "handleMultival": "ARRAY"}

        cfg = N10sConfig(driver)
        result = cfg.init_graph_config(config=custom)

        assert result is True
        # Verify custom config was passed in params
        call_args = session.run.call_args
        assert call_args is not None
        # params dict should contain the custom config
        params = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("parameters", {})
        assert "IGNORE" in str(params)

    # ------------------------------------------------------------------
    # drop_graph_config
    # ------------------------------------------------------------------

    def test_drop_graph_config(self):
        """drop_graph_config() 호출 시 n10s.graphconfig.drop 을 실행해야 한다."""
        from kg.n10s.config import N10sConfig

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        session.run.return_value = []

        cfg = N10sConfig(driver)
        result = cfg.drop_graph_config()

        assert result is True
        cypher_calls = str(session.run.call_args_list)
        assert "n10s.graphconfig.drop" in cypher_calls

    # ------------------------------------------------------------------
    # get_graph_config
    # ------------------------------------------------------------------

    def test_get_graph_config(self):
        """get_graph_config()는 Neo4j 레코드를 dict로 반환해야 한다."""
        from kg.n10s.config import N10sConfig

        driver = _make_mock_driver()
        session = _get_mock_session(driver)

        # Simulate Neo4j returning param/value rows
        rec1 = MagicMock()
        rec1.__getitem__ = lambda self, k: "handleVocabUris" if k == "param" else "MAP"
        rec2 = MagicMock()
        rec2.__getitem__ = lambda self, k: "handleMultival" if k == "param" else "ARRAY"
        session.run.return_value = [rec1, rec2]

        cfg = N10sConfig(driver)
        result = cfg.get_graph_config()

        assert isinstance(result, dict)
        cypher_calls = str(session.run.call_args_list)
        assert "n10s.graphconfig" in cypher_calls

    # ------------------------------------------------------------------
    # register_namespaces
    # ------------------------------------------------------------------

    def test_register_namespaces(self):
        """register_namespaces()는 8개 이상의 네임스페이스 프리픽스를 등록해야 한다."""
        from kg.n10s.config import N10sConfig

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        session.run.return_value = []

        cfg = N10sConfig(driver)
        count = cfg.register_namespaces()

        assert isinstance(count, int)
        assert count >= 8, f"Expected >= 8 namespace registrations, got {count}"
        assert session.run.call_count >= 8

    # ------------------------------------------------------------------
    # add_namespace
    # ------------------------------------------------------------------

    def test_add_namespace(self):
        """add_namespace()는 n10s.nsprefixes.add 프로시저를 단 한 번 호출해야 한다."""
        from kg.n10s.config import N10sConfig

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        session.run.return_value = []

        cfg = N10sConfig(driver)
        result = cfg.add_namespace("test", "https://example.org/test#")

        assert result is True
        assert session.run.call_count == 1
        cypher_calls = str(session.run.call_args_list)
        assert "n10s.nsprefixes.add" in cypher_calls

    # ------------------------------------------------------------------
    # list_namespaces
    # ------------------------------------------------------------------

    def test_list_namespaces(self):
        """list_namespaces()는 (prefix, uri) 튜플의 리스트를 반환해야 한다."""
        from kg.n10s.config import N10sConfig

        driver = _make_mock_driver()
        session = _get_mock_session(driver)

        # Simulate Neo4j returning two namespace records with prefix/namespace keys
        rec1 = MagicMock()
        rec1.__getitem__ = lambda self, k: "owl" if k == "prefix" else "http://www.w3.org/2002/07/owl#"
        rec2 = MagicMock()
        rec2.__getitem__ = lambda self, k: "maritime" if k == "prefix" else "https://kg.kriso.re.kr/maritime#"
        session.run.return_value = [rec1, rec2]

        cfg = N10sConfig(driver)
        result = cfg.list_namespaces()

        assert isinstance(result, list)
        cypher_calls = str(session.run.call_args_list)
        assert "n10s.nsprefixes" in cypher_calls

    # ------------------------------------------------------------------
    # add_mapping
    # ------------------------------------------------------------------

    def test_add_mapping(self):
        """add_mapping()은 n10s.mapping.add 프로시저를 호출해야 한다."""
        from kg.n10s.config import N10sConfig

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        session.run.return_value = []

        cfg = N10sConfig(driver)
        result = cfg.add_mapping("Vessel", "https://kg.kriso.re.kr/maritime#Vessel")

        assert result is True
        cypher_calls = str(session.run.call_args_list)
        assert "n10s.mapping.add" in cypher_calls

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_init_graph_config_error(self):
        """Neo4j 예외 시 init_graph_config()는 False를 반환해야 한다."""
        from kg.n10s.config import N10sConfig

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        session.run.side_effect = RuntimeError("Neo4j connection failed")

        cfg = N10sConfig(driver)
        result = cfg.init_graph_config()

        # N10sConfig catches exceptions and returns False
        assert result is False

    def test_register_namespaces_partial_failure(self):
        """register_namespaces()는 일부 실패 시에도 성공 카운트를 반환해야 한다."""
        from kg.n10s.config import N10sConfig

        driver = _make_mock_driver()
        session = _get_mock_session(driver)

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise RuntimeError("failed")
            return []

        session.run.side_effect = side_effect

        cfg = N10sConfig(driver)
        count = cfg.register_namespaces()

        assert isinstance(count, int)
        # At least some should succeed (odd-numbered calls)
        assert count >= 1
        # And count should be less than the total (some failed)
        from kg.n10s.config import NAMESPACE_PREFIXES
        assert count < len(NAMESPACE_PREFIXES)


# =========================================================================
# TestN10sImporter
# =========================================================================


@pytest.mark.unit
class TestN10sImporter:
    """Unit tests for kg.n10s.importer.N10sImporter."""

    # ------------------------------------------------------------------
    # DEFAULT_TTL_PATH
    # ------------------------------------------------------------------

    def test_default_ttl_path(self):
        """DEFAULT_TTL_PATH은 kg/ontology/maritime.ttl 을 가리켜야 한다."""
        from kg.n10s.importer import DEFAULT_TTL_PATH

        p = Path(DEFAULT_TTL_PATH)
        assert p.name == "maritime.ttl"
        assert "ontology" in p.parts
        assert "kg" in p.parts

    # ------------------------------------------------------------------
    # import_from_inline
    # ------------------------------------------------------------------

    def test_import_from_inline(self):
        """import_from_inline()은 n10s.rdf.import.inline 프로시저를 호출해야 한다."""
        from kg.n10s.importer import N10sImporter

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        mock_record = MagicMock()
        mock_record.get = lambda k, default=None: {"triplesLoaded": 42, "namespaces": 5, "extraInfo": ""}.get(k, default)
        session.run.return_value = [mock_record]

        importer = N10sImporter(driver)
        ttl = "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        result = importer.import_from_inline(ttl)

        cypher_calls = str(session.run.call_args_list)
        assert "n10s.rdf.import.inline" in cypher_calls
        assert result is not None
        assert result.success is True

    # ------------------------------------------------------------------
    # import_from_url
    # ------------------------------------------------------------------

    def test_import_from_url(self):
        """import_from_url()은 n10s.onto.import.fetch 프로시저를 호출해야 한다."""
        from kg.n10s.importer import N10sImporter

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        mock_record = MagicMock()
        mock_record.get = lambda k, default=None: {"triplesLoaded": 5, "namespaces": 2, "extraInfo": ""}.get(k, default)
        session.run.return_value = [mock_record]

        importer = N10sImporter(driver)
        result = importer.import_from_url("https://example.org/maritime.ttl")

        cypher_calls = str(session.run.call_args_list)
        assert "n10s.onto.import.fetch" in cypher_calls
        assert result is not None

    # ------------------------------------------------------------------
    # import_ontology (file path)
    # ------------------------------------------------------------------

    def test_import_ontology_with_file(self):
        """import_ontology()는 파일 경로가 주어지면 파일을 읽어 inline import해야 한다."""
        from kg.n10s.importer import N10sImporter

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        mock_record = MagicMock()
        mock_record.get = lambda k, default=None: {"triplesLoaded": 10, "namespaces": 3, "extraInfo": ""}.get(k, default)
        session.run.return_value = [mock_record]

        importer = N10sImporter(driver)

        # Write a temporary fake .ttl file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ttl", mode="w", delete=False) as f:
            f.write("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")
            tmp_path = f.name

        try:
            result = importer.import_ontology(source=tmp_path, setup=False)
        finally:
            import os
            os.unlink(tmp_path)

        assert result is not None
        assert result.success is True

    # ------------------------------------------------------------------
    # import_ontology (default path)
    # ------------------------------------------------------------------

    def test_import_ontology_default(self):
        """import_ontology() 경로 미지정 시 DEFAULT_TTL_PATH 를 사용해야 한다."""
        from kg.n10s import importer as importer_mod
        from kg.n10s.importer import N10sImporter

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        session.run.return_value = []

        # Patch DEFAULT_TTL_PATH to point to a non-existent file — expect FileNotFoundError handling
        with patch.object(importer_mod, "DEFAULT_TTL_PATH", Path("/nonexistent/maritime.ttl")):
            importer = N10sImporter(driver)
            result = importer.import_ontology(setup=False)

        # FileNotFoundError should be caught and returned as a failed ImportResult
        assert result is not None
        assert result.success is False
        assert len(result.errors) > 0

    # ------------------------------------------------------------------
    # import_ontology setup=True / setup=False
    # ------------------------------------------------------------------

    def test_import_ontology_with_setup(self):
        """setup=True 이면 init_graph_config + register_namespaces 를 먼저 호출해야 한다."""
        from kg.n10s.importer import N10sImporter

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        mock_record = MagicMock()
        mock_record.get = lambda k, default=None: {"triplesLoaded": 5, "namespaces": 2, "extraInfo": ""}.get(k, default)
        session.run.return_value = [mock_record]

        import os
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ttl", mode="w", delete=False) as f:
            f.write("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")
            tmp_path = f.name

        try:
            importer = N10sImporter(driver)
            result = importer.import_ontology(source=tmp_path, setup=True)
        finally:
            os.unlink(tmp_path)

        # setup=True means init_graph_config + 8+ namespace calls + import call
        # Total session.run calls should be > 1
        assert session.run.call_count > 1
        assert result is not None

    def test_import_ontology_without_setup(self):
        """setup=False 이면 init/namespace 단계를 건너뛰어야 한다."""
        from kg.n10s.importer import N10sImporter

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        mock_record = MagicMock()
        mock_record.get = lambda k, default=None: {"triplesLoaded": 5, "namespaces": 2, "extraInfo": ""}.get(k, default)
        session.run.return_value = [mock_record]

        import os
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ttl", mode="w", delete=False) as f:
            f.write("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")
            tmp_path = f.name

        try:
            importer = N10sImporter(driver)
            result = importer.import_ontology(source=tmp_path, setup=False)
        finally:
            os.unlink(tmp_path)

        # setup=False: only the import call → exactly 1 session.run call
        assert session.run.call_count == 1
        assert result is not None

    # ------------------------------------------------------------------
    # preview_import
    # ------------------------------------------------------------------

    def test_preview_import(self):
        """preview_import()은 실제 import 없이 미리보기 프로시저를 호출해야 한다."""
        from kg.n10s.importer import N10sImporter

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        mock_record = MagicMock()
        mock_record.get = lambda k, default=None: {"triplesLoaded": 3, "namespaces": 1, "extraInfo": ""}.get(k, default)
        session.run.return_value = [mock_record]

        import os
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ttl", mode="w", delete=False) as f:
            f.write("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")
            tmp_path = f.name

        try:
            importer = N10sImporter(driver)
            result = importer.preview_import(source=tmp_path)
        finally:
            os.unlink(tmp_path)

        assert session.run.called
        cypher_calls = str(session.run.call_args_list)
        assert "preview" in cypher_calls.lower()
        assert result is not None

    # ------------------------------------------------------------------
    # setup_and_import_full_pipeline
    # ------------------------------------------------------------------

    def test_setup_and_import_full_pipeline(self):
        """setup_and_import()는 5단계(drop→constraint→init→namespace→import)를 수행해야 한다."""
        from kg.n10s.importer import N10sImporter

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        mock_record = MagicMock()
        mock_record.get = lambda k, default=None: {"triplesLoaded": 20, "namespaces": 8, "extraInfo": ""}.get(k, default)
        session.run.return_value = [mock_record]

        import os
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ttl", mode="w", delete=False) as f:
            f.write("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")
            tmp_path = f.name

        try:
            importer = N10sImporter(driver)
            result = importer.setup_and_import(source=tmp_path)
        finally:
            os.unlink(tmp_path)

        # 5 steps: drop + constraint + init + 8+ namespaces + import
        assert session.run.call_count >= 5
        assert result is not None

    # ------------------------------------------------------------------
    # delete_imported_data
    # ------------------------------------------------------------------

    def test_delete_imported_data(self):
        """delete_imported_data()는 Resource 노드 정리 Cypher를 호출해야 한다."""
        from kg.n10s.importer import N10sImporter

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        session.run.return_value = []

        importer = N10sImporter(driver)
        result = importer.delete_imported_data()

        assert result is True
        assert session.run.called
        cypher_calls = str(session.run.call_args_list)
        assert "Resource" in cypher_calls or "DELETE" in cypher_calls

    # ------------------------------------------------------------------
    # import_error_handling
    # ------------------------------------------------------------------

    def test_import_error_handling(self):
        """Neo4j 예외는 ImportResult.errors 에 래핑되어 success=False 로 반환돼야 한다."""
        from kg.n10s.importer import N10sImporter

        driver = _make_mock_driver()
        session = _get_mock_session(driver)
        session.run.side_effect = RuntimeError("connection refused")

        importer = N10sImporter(driver)
        result = importer.import_from_inline("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")

        assert result is not None
        assert result.success is False
        assert len(result.errors) > 0


# =========================================================================
# TestOWLExporter
# =========================================================================


@pytest.mark.unit
class TestOWLExporter:
    """Unit tests for kg.n10s.owl_exporter.OWLExporter.

    OWLExporter already exists and is fully importable, so these tests
    verify its actual output without any mocking.
    """

    # ------------------------------------------------------------------
    # Turtle output structural tests
    # ------------------------------------------------------------------

    def test_export_turtle_has_prefixes(self):
        """export_turtle() 출력에는 @prefix owl:, maritime:, s100: 가 포함되어야 한다."""
        from kg.n10s.owl_exporter import OWLExporter

        exporter = OWLExporter()
        turtle = exporter.export_turtle()

        assert "@prefix owl:" in turtle
        assert "@prefix maritime:" in turtle
        assert "@prefix s100:" in turtle

    def test_export_turtle_has_ontology_header(self):
        """export_turtle() 출력에는 owl:Ontology 선언이 포함되어야 한다."""
        from kg.n10s.owl_exporter import OWLExporter

        exporter = OWLExporter()
        turtle = exporter.export_turtle()

        assert "owl:Ontology" in turtle

    def test_export_turtle_has_all_classes(self):
        """주요 클래스(Vessel, Port, Document, Experiment, TestFacility)가 출력에 있어야 한다."""
        from kg.n10s.owl_exporter import OWLExporter

        exporter = OWLExporter()
        turtle = exporter.export_turtle()

        for cls in ("Vessel", "Port", "Document", "Experiment", "TestFacility"):
            assert f"maritime:{cls}" in turtle, f"Missing class: {cls}"

    def test_export_turtle_has_superclass_hierarchy(self):
        """상위 클래스(PhysicalEntity, SpatialEntity 등)가 출력에 있어야 한다."""
        from kg.n10s.owl_exporter import OWLExporter

        exporter = OWLExporter()
        turtle = exporter.export_turtle()

        for superclass in (
            "PhysicalEntity",
            "SpatialEntity",
            "TemporalEntity",
            "InformationEntity",
            "KRISOEntity",
        ):
            assert f"maritime:{superclass}" in turtle, f"Missing superclass: {superclass}"

    def test_export_turtle_has_subclass_relations(self):
        """CargoShip 이 PhysicalEntity 의 하위 클래스임을 나타내는 triples 가 있어야 한다."""
        from kg.n10s.owl_exporter import OWLExporter

        exporter = OWLExporter()
        turtle = exporter.export_turtle()

        assert "maritime:CargoShip" in turtle
        assert "rdfs:subClassOf" in turtle
        assert "maritime:PhysicalEntity" in turtle

    def test_export_turtle_has_object_properties(self):
        """관계 타입이 ObjectProperty 로 선언되어야 한다."""
        from kg.n10s.owl_exporter import OWLExporter

        exporter = OWLExporter()
        turtle = exporter.export_turtle()

        assert "owl:ObjectProperty" in turtle
        # DOCKED_AT → dockedAt (camelCase conversion)
        assert "dockedAt" in turtle or "DOCKED_AT" in turtle

    def test_export_turtle_has_datatype_properties(self):
        """핵심 속성(mmsi, name 등)이 DatatypeProperty 로 선언되어야 한다."""
        from kg.n10s.owl_exporter import OWLExporter

        exporter = OWLExporter()
        turtle = exporter.export_turtle()

        assert "owl:DatatypeProperty" in turtle
        assert "mmsi" in turtle or "name" in turtle

    def test_map_neo4j_type_to_xsd(self):
        """_map_neo4j_type_to_xsd()는 Neo4j 타입을 올바른 XSD 타입으로 변환해야 한다."""
        from kg.n10s.owl_exporter import OWLExporter

        assert OWLExporter._map_neo4j_type_to_xsd("STRING") == "xsd:string"
        assert OWLExporter._map_neo4j_type_to_xsd("INTEGER") == "xsd:integer"
        assert OWLExporter._map_neo4j_type_to_xsd("POINT") == "geo:wktLiteral"
        assert OWLExporter._map_neo4j_type_to_xsd("FLOAT") == "xsd:float"
        assert OWLExporter._map_neo4j_type_to_xsd("BOOLEAN") == "xsd:boolean"
        assert OWLExporter._map_neo4j_type_to_xsd("DATE") == "xsd:date"
        assert OWLExporter._map_neo4j_type_to_xsd("DATETIME") == "xsd:dateTime"
        assert OWLExporter._map_neo4j_type_to_xsd("LIST<FLOAT>") == "rdf:List"
        assert OWLExporter._map_neo4j_type_to_xsd("LIST<STRING>") == "rdf:List"
        # Unknown type → xsd:string fallback
        assert OWLExporter._map_neo4j_type_to_xsd("UNKNOWN_XYZ") == "xsd:string"

    def test_export_to_file(self, tmp_path: Path):
        """export_to_file()은 Turtle 내용을 파일에 쓰고 Path를 반환해야 한다."""
        from kg.n10s.owl_exporter import OWLExporter

        exporter = OWLExporter()
        dest = tmp_path / "maritime.ttl"
        returned_path = exporter.export_to_file(str(dest))

        assert returned_path.exists()
        content = returned_path.read_text(encoding="utf-8")
        assert "@prefix owl:" in content
        assert len(content) > 100

    def test_generate_maritime_turtle_convenience(self):
        """모듈 레벨 generate_maritime_turtle() 함수가 Turtle 문자열을 반환해야 한다."""
        from kg.n10s.owl_exporter import generate_maritime_turtle

        result = generate_maritime_turtle()

        assert isinstance(result, str)
        assert "@prefix owl:" in result
        assert "owl:Ontology" in result
        assert len(result) > 500


# =========================================================================
# TestImportResult
# =========================================================================


@pytest.mark.unit
class TestImportResult:
    """Unit tests for the ImportResult dataclass from kg.n10s.importer."""

    def test_default_values(self):
        """ImportResult는 success 인자 필수이며 나머지는 기본값을 가져야 한다."""
        from kg.n10s.importer import ImportResult

        result = ImportResult(success=False)

        assert result.success is False
        assert result.triples_loaded == 0
        assert result.namespaces == 0
        assert result.extra_info == ""
        assert result.errors == []

    def test_success_result(self):
        """ImportResult는 성공 상태와 통계 필드를 수용해야 한다."""
        from kg.n10s.importer import ImportResult

        result = ImportResult(
            success=True,
            triples_loaded=42,
            namespaces=8,
            extra_info="import ok",
        )

        assert result.success is True
        assert result.triples_loaded == 42
        assert result.namespaces == 8
        assert result.extra_info == "import ok"

    def test_error_result(self):
        """ImportResult.errors 는 에러 메시지 리스트를 수용해야 한다."""
        from kg.n10s.importer import ImportResult

        result = ImportResult(
            success=False,
            errors=["Connection refused", "Timeout"],
        )

        assert result.success is False
        assert len(result.errors) == 2
        assert "Connection refused" in result.errors
