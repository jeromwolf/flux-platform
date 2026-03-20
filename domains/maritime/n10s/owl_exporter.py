"""OWL/Turtle exporter for the Maritime Knowledge Graph ontology.

Converts Python ontology definitions from ``kg.ontology.maritime_ontology``
into OWL/Turtle format suitable for Neosemantics (n10s) import into Neo4j.

Usage::

    from kg.n10s.owl_exporter import OWLExporter

    exporter = OWLExporter()
    turtle_str = exporter.export_turtle()
    exporter.export_to_file("kg/ontology/maritime.ttl")

CLI::

    python -m kg.n10s.owl_exporter            # writes to kg/ontology/maritime.ttl
    python -m kg.n10s.owl_exporter -o out.ttl  # writes to custom path
"""

from __future__ import annotations

import logging
import textwrap
from collections import OrderedDict
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entity group hierarchy mapping
# ---------------------------------------------------------------------------
# 각 그룹은 maritime_ontology.py 의 주석 구간("# ----- XxxGroup -----")에
# 대응하며, 그룹 이름(superclass)과 소속 엔티티 레이블 목록으로 구성한다.
# 순서는 원본 파일의 선언 순서를 그대로 유지한다.
# ---------------------------------------------------------------------------

_ENTITY_GROUPS: OrderedDict[str, list[str]] = OrderedDict([
    ("PhysicalEntity", [
        "Vessel", "CargoShip", "Tanker", "FishingVessel", "PassengerShip",
        "NavalVessel", "AutonomousVessel", "Port", "TradePort", "CoastalPort",
        "FishingPort", "PortFacility", "Berth", "Anchorage", "Terminal",
        "Waterway", "TSS", "Channel", "Cargo", "DangerousGoods", "BulkCargo",
        "ContainerCargo", "Sensor", "AISTransceiver", "Radar", "CCTVCamera",
        "WeatherStation",
    ]),
    ("SpatialEntity", [
        "SeaArea", "EEZ", "TerritorialSea", "CoastalRegion", "GeoPoint",
    ]),
    ("TemporalEntity", [
        "Voyage", "PortCall", "TrackSegment", "Incident", "Collision",
        "Grounding", "Pollution", "Distress", "IllegalFishing",
        "WeatherCondition", "Activity", "Loading", "Unloading", "Bunkering",
        "Anchoring", "Loitering",
    ]),
    ("InformationEntity", [
        "Regulation", "COLREG", "SOLAS", "MARPOL", "IMDGCode", "Document",
        "AccidentReport", "InspectionReport", "NavigationalWarning",
        "CargoManifest", "DataSource", "APIEndpoint", "StreamSource",
        "FileSource", "Service", "QueryService", "AnalysisService",
        "AlertService", "PredictionService",
    ]),
    ("ObservationEntity", [
        "Observation", "SARObservation", "OpticalObservation",
        "CCTVObservation", "AISObservation", "RadarObservation",
        "WeatherObservation",
    ]),
    ("AgentEntity", [
        "Organization", "GovernmentAgency", "ShippingCompany",
        "ResearchInstitute", "ClassificationSociety", "Person",
        "CrewMember", "Inspector",
    ]),
    ("PlatformResource", [
        "Workflow", "WorkflowNode", "WorkflowExecution", "AIModel",
        "DataPipeline", "AIAgent", "MCPTool", "MCPResource",
    ]),
    ("MultimodalData", [
        "AISData", "SatelliteImage", "RadarImage", "SensorReading",
        "MaritimeChart", "VideoClip",
    ]),
    ("MultimodalRepresentation", [
        "VisualEmbedding", "TrajectoryEmbedding", "TextEmbedding",
        "FusedEmbedding",
    ]),
    ("KRISOEntity", [
        "Experiment", "TestFacility", "TowingTank", "OceanEngineeringBasin",
        "IceTank", "DeepOceanBasin", "WaveEnergyTestSite",
        "HyperbaricChamber", "CavitationTunnel", "LargeCavitationTunnel",
        "MediumCavitationTunnel", "HighSpeedCavitationTunnel",
        "BridgeSimulator", "ExperimentalDataset", "TestCondition",
        "ModelShip", "Measurement", "Resistance", "Propulsion",
        "Maneuvering", "Seakeeping", "IcePerformance", "StructuralResponse",
    ]),
    ("RBACEntity", [
        "User", "Role", "DataClass", "Permission",
    ]),
])

# 역인덱스: 엔티티 레이블 -> 소속 그룹명
_LABEL_TO_GROUP: dict[str, str] = {}
for _grp, _labels in _ENTITY_GROUPS.items():
    for _lbl in _labels:
        _LABEL_TO_GROUP[_lbl] = _grp

# Neo4j 타입 -> XSD 데이터타입 매핑
_NEO4J_TO_XSD: dict[str, str] = {
    "STRING": "xsd:string",
    "INTEGER": "xsd:integer",
    "FLOAT": "xsd:float",
    "BOOLEAN": "xsd:boolean",
    "DATE": "xsd:date",
    "DATETIME": "xsd:dateTime",
    "POINT": "geo:wktLiteral",
    "LIST<FLOAT>": "rdf:List",
    "LIST<STRING>": "rdf:List",
}


class OWLExporter:
    """Maritime 온톨로지를 OWL/Turtle 형식으로 변환하는 익스포터.

    ``kg.ontology.maritime_ontology`` 모듈의 ``ENTITY_LABELS``,
    ``RELATIONSHIP_TYPES``, ``PROPERTY_DEFINITIONS`` 를 읽어
    W3C OWL 2 Turtle 시리얼라이제이션을 생성한다.

    Args:
        base_uri: 온톨로지 기본 네임스페이스 URI.
        ontology_name: 온톨로지 식별 이름.

    Example::

        exporter = OWLExporter()
        print(exporter.export_turtle())
    """

    def __init__(
        self,
        base_uri: str = "https://kg.kriso.re.kr/maritime#",
        ontology_name: str = "maritime",
    ) -> None:
        self.base_uri = base_uri
        self.ontology_name = ontology_name

        # 온톨로지 URI (# 제거)
        self.ontology_uri = base_uri.rstrip("#")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export_turtle(self) -> str:
        """Generate complete OWL/Turtle string from maritime ontology data.

        Returns:
            Turtle-formatted string containing the full OWL ontology.
        """
        sections = [
            self._build_prefixes(),
            self._build_ontology_header(),
            self._build_classes(),
            self._build_object_properties(),
            self._build_datatype_properties(),
        ]
        turtle = "\n".join(sections)
        logger.info(
            "Generated OWL/Turtle: %d characters, ontology=%s",
            len(turtle),
            self.ontology_name,
        )
        return turtle

    def export_to_file(self, path: str | Path) -> Path:
        """Write Turtle to file.

        Args:
            path: Destination file path.

        Returns:
            Resolved ``Path`` of the written file.
        """
        dest = Path(path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        turtle = self.export_turtle()
        dest.write_text(turtle, encoding="utf-8")
        logger.info("Wrote OWL/Turtle to %s (%d bytes)", dest, len(turtle))
        return dest

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_prefixes(self) -> str:
        """Standard Turtle prefix declarations.

        Includes owl, rdfs, rdf, xsd, dc, dcterms, geo, skos, s100,
        and the project-specific maritime namespace.

        Returns:
            Multi-line ``@prefix`` block.
        """
        return textwrap.dedent(f"""\
            @prefix owl:      <http://www.w3.org/2002/07/owl#> .
            @prefix rdfs:     <http://www.w3.org/2000/01/rdf-schema#> .
            @prefix rdf:      <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix xsd:      <http://www.w3.org/2001/XMLSchema#> .
            @prefix dc:       <http://purl.org/dc/elements/1.1/> .
            @prefix dcterms:  <http://purl.org/dc/terms/> .
            @prefix geo:      <http://www.opengis.net/ont/geosparql#> .
            @prefix skos:     <http://www.w3.org/2004/02/skos/core#> .
            @prefix s100:     <https://registry.iho.int/s100/> .
            @prefix maritime: <{self.base_uri}> .
        """)

    def _build_ontology_header(self) -> str:
        """OWL Ontology declaration with metadata.

        Returns:
            Turtle block declaring the ontology resource with Dublin Core
            metadata annotations.
        """
        return textwrap.dedent(f"""\
            # =====================================================================
            # Ontology Declaration
            # =====================================================================

            <{self.ontology_uri}> a owl:Ontology ;
                dc:title "KRISO Maritime Knowledge Graph Ontology"@en ;
                dc:title "KRISO 해사 지식그래프 온톨로지"@ko ;
                dc:description "OWL ontology for the Conversational Maritime Service Platform knowledge graph. Auto-generated from Python ontology definitions."@en ;
                dcterms:creator "KRISO Maritime KG Team" ;
                dcterms:license <https://creativecommons.org/licenses/by/4.0/> ;
                owl:versionInfo "1.0.0" ;
                rdfs:comment "Generated by kg.n10s.owl_exporter from kg.ontology.maritime_ontology" .
        """)

    def _build_classes(self) -> str:
        """Convert ENTITY_LABELS to owl:Class declarations.

        Entity groups are declared as superclasses, and each entity label
        within a group becomes a subclass of its group class.

        Returns:
            Turtle block with all owl:Class declarations.
        """
        from kg.ontology.maritime_ontology import ENTITY_LABELS

        lines: list[str] = [
            "# =====================================================================",
            "# Classes",
            "# =====================================================================",
            "",
        ]

        # -- 그룹 상위 클래스 선언 --
        lines.append("# ----- Superclass Hierarchy (Entity Groups) -----")
        lines.append("")
        for group_name in _ENTITY_GROUPS:
            lines.append(f"maritime:{group_name} a owl:Class ;")
            lines.append(f'    rdfs:label "{_camel_to_label(group_name)}"@en ;')
            lines.append(
                f'    rdfs:comment "Superclass for {_camel_to_label(group_name).lower()} entities in the maritime domain"@en .'
            )
            lines.append("")

        # -- 개별 엔티티 클래스 선언 --
        lines.append("# ----- Entity Classes -----")
        lines.append("")

        for group_name, labels in _ENTITY_GROUPS.items():
            lines.append(f"# --- {group_name} ---")
            lines.append("")
            for label in labels:
                description = ENTITY_LABELS.get(label, "")
                lines.append(f"maritime:{label} a owl:Class ;")
                lines.append(f"    rdfs:subClassOf maritime:{group_name} ;")
                lines.append(f'    rdfs:label "{label}"@en ;')
                if description:
                    # 이스케이프 처리: Turtle 문자열 내 쌍따옴표 보호
                    safe_desc = description.replace("\\", "\\\\").replace('"', '\\"')
                    lines.append(f'    rdfs:comment "{safe_desc}"@en .')
                else:
                    lines.append(f'    rdfs:comment "{label}"@en .')
                lines.append("")

        # ENTITY_LABELS 에 있지만 그룹에 없는 엔티티가 있으면 경고 + 출력
        grouped_labels = set(_LABEL_TO_GROUP.keys())
        all_labels = set(ENTITY_LABELS.keys())
        ungrouped = all_labels - grouped_labels
        if ungrouped:
            logger.warning(
                "Ungrouped entity labels (no superclass assigned): %s",
                sorted(ungrouped),
            )
            lines.append("# --- Ungrouped ---")
            lines.append("")
            for label in sorted(ungrouped):
                description = ENTITY_LABELS.get(label, "")
                safe_desc = description.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f"maritime:{label} a owl:Class ;")
                lines.append(f'    rdfs:label "{label}"@en ;')
                lines.append(f'    rdfs:comment "{safe_desc}"@en .')
                lines.append("")

        return "\n".join(lines)

    def _build_object_properties(self) -> str:
        """Convert RELATIONSHIP_TYPES to owl:ObjectProperty declarations.

        Each relationship gets ``rdfs:domain`` and ``rdfs:range`` from
        ``from_label`` and ``to_label`` respectively.

        Returns:
            Turtle block with all owl:ObjectProperty declarations.
        """
        from kg.ontology.maritime_ontology import RELATIONSHIP_TYPES

        lines: list[str] = [
            "# =====================================================================",
            "# Object Properties (Relationships)",
            "# =====================================================================",
            "",
        ]

        for rel in RELATIONSHIP_TYPES:
            rel_type: str = rel["type"]
            from_label: str = rel["from_label"]
            to_label: str = rel["to_label"]
            description: str = rel.get("description", "")
            properties: list[str] = rel.get("properties", [])

            # Turtle local name: 관계 타입을 camelCase 로 변환
            # SCREAMING_SNAKE_CASE -> camelCase
            prop_name = _snake_to_camel(rel_type)

            safe_desc = description.replace("\\", "\\\\").replace('"', '\\"')

            lines.append(f"maritime:{prop_name} a owl:ObjectProperty ;")
            lines.append(f'    rdfs:label "{rel_type}"@en ;')
            lines.append(f"    rdfs:domain maritime:{from_label} ;")
            lines.append(f"    rdfs:range maritime:{to_label} ;")
            if safe_desc:
                lines.append(f'    rdfs:comment "{safe_desc}"@en ;')
            if properties:
                # 관계 속성 목록을 skos:note 로 기록
                prop_list = ", ".join(properties)
                lines.append(
                    f'    skos:note "Relationship properties: {prop_list}"@en ;'
                )
            # 마지막 세미콜론을 마침표로 교체
            if lines[-1].endswith(" ;"):
                lines[-1] = lines[-1][:-2] + " ."
            else:
                lines.append("    .")
            lines.append("")

        return "\n".join(lines)

    def _build_datatype_properties(self) -> str:
        """Convert PROPERTY_DEFINITIONS to owl:DatatypeProperty declarations.

        Each property is scoped to its owning entity class via ``rdfs:domain``
        and typed with the XSD equivalent via ``rdfs:range``.

        Returns:
            Turtle block with all owl:DatatypeProperty declarations.
        """
        from kg.ontology.maritime_ontology import PROPERTY_DEFINITIONS

        lines: list[str] = [
            "# =====================================================================",
            "# Datatype Properties",
            "# =====================================================================",
            "",
        ]

        # 중복 방지를 위해 이미 선언된 (property_name, domain, range) 추적
        declared: set[tuple[str, str, str]] = set()

        for entity_label, props in PROPERTY_DEFINITIONS.items():
            lines.append(f"# --- {entity_label} properties ---")
            lines.append("")
            for prop_name, neo4j_type in props.items():
                xsd_type = self._map_neo4j_type_to_xsd(neo4j_type)
                key = (prop_name, entity_label, xsd_type)
                if key in declared:
                    continue
                declared.add(key)

                # 속성 로컬 이름: "EntityLabel_propertyName" 형식으로
                # 같은 이름의 속성이 다른 엔티티에서 다른 타입으로 쓰일 수 있으므로
                # 엔티티별로 구분한다.
                local_name = f"{entity_label}_{prop_name}"

                lines.append(f"maritime:{local_name} a owl:DatatypeProperty ;")
                lines.append(f'    rdfs:label "{prop_name}"@en ;')
                lines.append(f"    rdfs:domain maritime:{entity_label} ;")
                lines.append(f"    rdfs:range {xsd_type} ;")
                lines.append(
                    f'    rdfs:comment "Property {prop_name} of {entity_label} (Neo4j type: {neo4j_type})"@en .'
                )
                lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Type mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_neo4j_type_to_xsd(neo4j_type: str) -> str:
        """Map a Neo4j type string to the corresponding XSD datatype.

        Args:
            neo4j_type: Neo4j property type, e.g. ``"STRING"``, ``"POINT"``,
                ``"LIST<FLOAT>"``.

        Returns:
            Prefixed XSD type string such as ``"xsd:string"``,
            ``"geo:wktLiteral"``, or ``"rdf:List"``.

        Examples:
            >>> OWLExporter._map_neo4j_type_to_xsd("STRING")
            'xsd:string'
            >>> OWLExporter._map_neo4j_type_to_xsd("POINT")
            'geo:wktLiteral'
            >>> OWLExporter._map_neo4j_type_to_xsd("LIST<FLOAT>")
            'rdf:List'
        """
        mapped = _NEO4J_TO_XSD.get(neo4j_type)
        if mapped is not None:
            return mapped
        # LIST<...> 패턴 일반 매칭
        if neo4j_type.startswith("LIST<"):
            return "rdf:List"
        logger.warning("Unknown Neo4j type '%s', defaulting to xsd:string", neo4j_type)
        return "xsd:string"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _snake_to_camel(screaming_snake: str) -> str:
    """Convert SCREAMING_SNAKE_CASE to camelCase.

    Args:
        screaming_snake: e.g. ``"DOCKED_AT"``.

    Returns:
        camelCase string, e.g. ``"dockedAt"``.

    Examples:
        >>> _snake_to_camel("DOCKED_AT")
        'dockedAt'
        >>> _snake_to_camel("AIS_TRACK_OF")
        'aisTrackOf'
    """
    parts = screaming_snake.lower().split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _camel_to_label(camel: str) -> str:
    """Convert PascalCase to a human-readable label with spaces.

    Args:
        camel: e.g. ``"PhysicalEntity"``.

    Returns:
        Spaced label, e.g. ``"Physical Entity"``.

    Examples:
        >>> _camel_to_label("PhysicalEntity")
        'Physical Entity'
        >>> _camel_to_label("KRISOEntity")
        'KRISO Entity'
    """
    result: list[str] = []
    buf: list[str] = []
    for ch in camel:
        if ch.isupper():
            if buf:
                # 연속 대문자(KRISO 같은 약어) 처리
                if len(buf) > 1 and buf[-1].isupper():
                    # 이전까지 약어, 현재 대문자는 새 단어 시작일 수도 있음
                    pass
                # 소문자 다음 대문자면 단어 경계
                if buf[-1].islower():
                    result.append("".join(buf))
                    buf = []
                # 대문자 연속 중 다음 문자를 봐야 하지만, 간이 처리
                elif len(buf) >= 2 and buf[-1].isupper():
                    # 약어 끝 판별은 다음 문자가 소문자인지로 (여기서는 ch 가 대문자)
                    pass
            buf.append(ch)
        else:
            # 소문자: 약어 종료 지점 감지
            if len(buf) >= 2 and buf[-1].isupper() and buf[-2].isupper():
                # 마지막 대문자를 떼어서 새 단어로
                prefix = "".join(buf[:-1])
                result.append(prefix)
                buf = [buf[-1], ch]
            else:
                buf.append(ch)
    if buf:
        result.append("".join(buf))
    return " ".join(result)


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def generate_maritime_turtle() -> str:
    """Generate OWL/Turtle for the maritime ontology using default settings.

    Returns:
        Complete Turtle-formatted ontology string.
    """
    return OWLExporter().export_turtle()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point: ``python -m kg.n10s.owl_exporter``.

    Writes the maritime OWL ontology to ``kg/ontology/maritime.ttl``
    by default. Use ``-o`` to specify a custom output path.
    """
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Export Maritime ontology as OWL/Turtle for n10s import",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="kg/ontology/maritime.ttl",
        help="Output file path (default: kg/ontology/maritime.ttl)",
    )
    parser.add_argument(
        "--base-uri",
        type=str,
        default="https://kg.kriso.re.kr/maritime#",
        help="Base URI for the ontology namespace",
    )
    args = parser.parse_args()

    exporter = OWLExporter(base_uri=args.base_uri)
    dest = exporter.export_to_file(args.output)

    print(f"OWL/Turtle written to {dest}", file=sys.stdout)


if __name__ == "__main__":
    main()
