"""Ontology-Query Bridge - Connect ontology schema to query builders.

Provides ontology-aware query building and validation, bridging the gap
between the domain ontology definitions and the Cypher/query generation layer.

Usage::

    from kg.ontology_bridge import OntologyAwareCypherBuilder, validate_structured_query
    from kg.ontology.maritime_loader import load_maritime_ontology

    ontology = load_maritime_ontology()

    # Ontology-aware CypherBuilder (soft validation with warnings)
    query, params = (
        OntologyAwareCypherBuilder(ontology=ontology)
        .match("(v:Vessel)")
        .where("v.vesselType = $type", {"type": "ContainerShip"})
        .return_("v")
        .build()
    )

    # Validate a StructuredQuery against the ontology
    warnings = validate_structured_query(structured_query, ontology)
"""

from __future__ import annotations

import re
import warnings
from typing import Any

from kg.cypher_builder import CypherBuilder
from kg.ontology.core import Ontology
from kg.query_generator import StructuredQuery

# 패턴: Cypher 노드 레이블 추출 (e.g., "(v:Vessel)" -> "Vessel")
_LABEL_PATTERN = re.compile(r"\(\s*\w*\s*:\s*(\w+)\s*\)")

# 패턴: WHERE 조건에서 속성 참조 추출 (e.g., "v.vesselType = $type" -> ("v", "vesselType"))
_PROPERTY_PATTERN = re.compile(r"(\w+)\.(\w+)")


def _extract_labels(pattern: str) -> list[str]:
    """Cypher 패턴 문자열에서 노드 레이블을 추출한다.

    Args:
        pattern: Cypher MATCH 패턴 (e.g., "(v:Vessel)-[:DOCKED_AT]->(b:Berth)")

    Returns:
        추출된 레이블 목록
    """
    return _LABEL_PATTERN.findall(pattern)


def _extract_property_refs(condition: str) -> list[tuple[str, str]]:
    """WHERE 조건 문자열에서 alias.property 참조를 추출한다.

    Args:
        condition: Cypher WHERE 조건 (e.g., "v.vesselType = $type")

    Returns:
        (alias, property_name) 튜플 목록
    """
    return _PROPERTY_PATTERN.findall(condition)


class OntologyAwareCypherBuilder(CypherBuilder):
    """온톨로지 기반 검증 기능이 포함된 CypherBuilder.

    ontology가 설정되면 match()와 where() 호출 시 노드 레이블과
    속성 이름을 온톨로지에 대해 검증한다. 검증 실패 시 warnings.warn()을
    통해 경고를 발생시키지만, 쿼리 빌드는 정상적으로 진행된다 (소프트 검증).

    ontology가 None이면 일반 CypherBuilder와 동일하게 동작한다.
    """

    def __init__(self, ontology: Ontology | None = None) -> None:
        super().__init__()
        self._ontology = ontology
        # alias -> label 매핑 (where 검증용)
        self._alias_to_label: dict[str, str] = {}

    def match(self, pattern: str) -> OntologyAwareCypherBuilder:
        """MATCH 절을 추가하고, 온톨로지 설정 시 노드 레이블을 검증한다.

        Args:
            pattern: Cypher 패턴 (e.g., "(v:Vessel)", "(a)-[:REL]->(b)")

        Returns:
            Self for chaining
        """
        if self._ontology is not None:
            labels = _extract_labels(pattern)
            for label in labels:
                if self._ontology.get_object_type(label) is None:
                    warnings.warn(
                        f"Label '{label}' not found in ontology '{self._ontology.name}'",
                        UserWarning,
                        stacklevel=2,
                    )
            # alias -> label 매핑 저장
            alias_label_pairs = re.findall(r"\(\s*(\w+)\s*:\s*(\w+)\s*\)", pattern)
            for alias, label in alias_label_pairs:
                self._alias_to_label[alias] = label

        super().match(pattern)
        return self

    def where(
        self, condition: str, params: dict[str, Any] | None = None
    ) -> OntologyAwareCypherBuilder:
        """WHERE 조건을 추가하고, 온톨로지 설정 시 속성 이름을 검증한다.

        Args:
            condition: Cypher 조건 (e.g., "v.vesselType = $type")
            params: 바인딩할 파라미터

        Returns:
            Self for chaining
        """
        if self._ontology is not None:
            refs = _extract_property_refs(condition)
            for alias, prop_name in refs:
                # $ 접두사가 있으면 파라미터 참조이므로 무시
                if alias.startswith("$"):
                    continue
                label = self._alias_to_label.get(alias)
                if label is not None:
                    obj_type = self._ontology.get_object_type(label)
                    if obj_type is not None and obj_type.get_property(prop_name) is None:
                        warnings.warn(
                            f"Property '{prop_name}' not found in ontology for label '{label}'",
                            UserWarning,
                            stacklevel=2,
                        )

        super().where(condition, params)
        return self


def validate_structured_query(query: StructuredQuery, ontology: Ontology) -> list[str]:
    """StructuredQuery를 온톨로지에 대해 검증한다.

    Args:
        query: 검증할 구조화된 쿼리
        ontology: 검증 기준 온톨로지

    Returns:
        검증 경고 메시지 목록 (빈 리스트 = 유효)
    """
    validation_warnings: list[str] = []

    # 엔티티 레이블 검증
    for label in query.object_types:
        obj_type = ontology.get_object_type(label)
        if obj_type is None:
            validation_warnings.append(f"Entity label '{label}' not found in ontology")
            continue

        # 요청된 속성 검증
        for prop in query.properties:
            if obj_type.get_property(prop) is None:
                validation_warnings.append(f"Property '{prop}' not found for entity '{label}'")

        # 필터 속성 검증
        for filter_ in query.filters:
            if obj_type.get_property(filter_.field) is None:
                validation_warnings.append(
                    f"Filter property '{filter_.field}' not found for entity '{label}'"
                )

    # 관계 타입 검증
    for rel in query.relationships:
        if ontology.get_link_type(rel.type) is None:
            validation_warnings.append(f"Relationship type '{rel.type}' not found in ontology")

    return validation_warnings


def get_ontology_context_for_query(ontology: Ontology) -> dict[str, Any]:
    """쿼리 생성 컨텍스트용 온톨로지 요약 정보를 반환한다.

    LLM 프롬프트 생성이나 쿼리 자동완성 등에 활용할 수 있는
    온톨로지의 구조화된 요약 딕셔너리를 생성한다.

    Args:
        ontology: 요약할 온톨로지

    Returns:
        dict with keys:
            - "labels": 유효한 노드 레이블 목록
            - "relationships": 유효한 관계 타입 목록
            - "properties": 레이블별 속성 이름 매핑
    """
    labels: list[str] = []
    properties: dict[str, list[str]] = {}

    for obj_type in ontology.get_all_object_types():
        labels.append(obj_type.name)
        prop_names = list(obj_type.properties.keys())
        if prop_names:
            properties[obj_type.name] = prop_names

    relationships: list[str] = [lt.name for lt in ontology.get_all_link_types()]

    return {
        "labels": sorted(labels),
        "relationships": sorted(relationships),
        "properties": properties,
    }
