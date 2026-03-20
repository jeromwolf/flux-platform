"""Shared types and enums for the Maritime KG platform.

This module provides canonical definitions used across multiple kg modules,
preventing duplication and ensuring interoperability.
"""

from __future__ import annotations

from enum import Enum


class ReasoningType(str, Enum):
    """Multi-hop reasoning type classification per GraphRAG Part 7.

    Classifies the reasoning pattern required to answer a natural language
    query over the knowledge graph.

    Members:
        DIRECT: 1-hop lookup -- 단순 조회 (e.g., "부산항 정보").
        BRIDGE: Sequential traversal A->B->C -- 순차 이동
            (e.g., "부산항에 정박중인 선박의 소유 기관").
        COMPARISON: Compare two or more entities -- A와 B 비교
            (e.g., "예인수조 vs 빙해수조 실험 비교").
        INTERSECTION: Find overlap between sets -- A∩B 교집합
            (e.g., "부산항과 인천항에 공통으로 입항한 선박").
        COMPOSITION: Multi-relation aggregation -- 여러 관계 조합
            (e.g., "가장 많은 실험을 수행한 시험시설 Top 3").
    """

    DIRECT = "direct"
    BRIDGE = "bridge"
    COMPARISON = "comparison"
    INTERSECTION = "intersection"
    COMPOSITION = "composition"


class FilterOperator(str, Enum):
    """Unified filter operators for query building.

    Supports both canonical long-form values (e.g., ``greater_than``) and
    short-form aliases (e.g., ``gt``) via _missing_.
    """

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUALS = "greater_than_or_equals"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUALS = "less_than_or_equals"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    MATCHES_REGEX = "matches_regex"

    @classmethod
    def _missing_(cls, value: object) -> FilterOperator | None:
        """Accept short-form aliases for backward compatibility."""
        if not isinstance(value, str):
            return None
        _ALIASES = {
            "eq": cls.EQUALS,
            "neq": cls.NOT_EQUALS,
            "gt": cls.GREATER_THAN,
            "gte": cls.GREATER_THAN_OR_EQUALS,
            "lt": cls.LESS_THAN,
            "lte": cls.LESS_THAN_OR_EQUALS,
            "in_list": cls.IN,
            "not_in_list": cls.NOT_IN,
            "regex": cls.MATCHES_REGEX,
        }
        return _ALIASES.get(value.lower())
