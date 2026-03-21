"""Korean Natural Language to StructuredQuery parser.

Rule-based parser that converts Korean natural language queries into
StructuredQuery objects for the Maritime Knowledge Graph. No LLM dependency.

Usage::

    from kg.nlp.nl_parser import NLParser

    # Default: uses maritime terms
    parser = NLParser()
    result = parser.parse("부산항 근처 컨테이너선 5000톤 이상")
    print(result.query)
    print(result.confidence)

    # Custom domain: inject a TermDictionary implementation
    from kg.nlp.term_dictionary import TermDictionary
    parser = NLParser(terms=my_custom_terms)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from kg.nlp.term_dictionary import TermDictionary
from kg.query_generator import (
    AggregationSpec,
    ExtractedFilter,
    Pagination,
    QueryIntent,
    QueryIntentType,
    RelationshipSpec,
    StructuredQuery,
)
from kg.types import FilterOperator, ReasoningType

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ParseResult:
    """Result of parsing a Korean natural language query.

    Attributes:
        query: The structured query derived from the input text.
        confidence: A score in [0.0, 1.0] reflecting how many terms
            were successfully resolved.
        unresolved_terms: Korean terms that could not be mapped to
            any known entity, relationship, or property.
        parse_details: Debug information about extraction steps.
    """

    query: StructuredQuery
    confidence: float = 0.0
    unresolved_terms: list[str] = field(default_factory=list)
    parse_details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Comparison keyword mappings
# ---------------------------------------------------------------------------

_COMPARISON_KEYWORDS: dict[str, FilterOperator] = {
    "이상": FilterOperator.GREATER_THAN_OR_EQUALS,
    "이하": FilterOperator.LESS_THAN_OR_EQUALS,
    "초과": FilterOperator.GREATER_THAN,
    "미만": FilterOperator.LESS_THAN,
}

# ---------------------------------------------------------------------------
# Aggregation keyword mappings
# ---------------------------------------------------------------------------

_AGGREGATION_KEYWORDS: dict[str, str] = {
    "평균": "AVG",
    "합계": "SUM",
    "합산": "SUM",
    "최대": "MAX",
    "최소": "MIN",
    "최댓값": "MAX",
    "최솟값": "MIN",
}

# ---------------------------------------------------------------------------
# Numeric field heuristics: Korean unit suffix -> (property_name, multiplier)
# ---------------------------------------------------------------------------

_UNIT_TO_PROPERTY: dict[str, tuple[str, float]] = {
    "톤": ("tonnage", 1.0),
    "t": ("tonnage", 1.0),
    "미터": ("length", 1.0),
    "m": ("length", 1.0),
    "노트": ("speed", 1.0),
    "kt": ("speed", 1.0),
    "km": ("distance", 1000.0),  # stored in meters
}

# Pattern: digits followed by optional unit, then optional comparison keyword
_NUMBER_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*"  # number (group 1)
    r"(톤|t|미터|m|노트|kt|km)?\s*"  # unit (group 2)
    r"(이상|이하|초과|미만)?"  # comparison (group 3)
)

# Pattern: "상위 N개" or "N개만"
_PAGINATION_PATTERN = re.compile(
    r"(?:상위\s*(\d+)\s*개)|(?:(\d+)\s*개만)|(?:(\d+)\s*건만)|(?:상위\s*(\d+)\s*건)"
)

# Pattern for COUNT intent
_COUNT_KEYWORDS = ["몇", "개수", "건수", "척수", "총수"]
_COUNT_UNIT_PATTERN = re.compile(r"몇\s*(척|개|건|곳|대)")


class NLParser:
    """Parse Korean natural language into StructuredQuery.

    Uses an injected term dictionary for entity/property/relationship
    resolution. Rule-based parsing without LLM dependency.

    Args:
        terms: A TermDictionary implementation. Defaults to maritime terms.
    """

    def __init__(self, terms: TermDictionary | None = None) -> None:
        if terms is None:
            from maritime.nlp.maritime_terms import (
                ENTITY_SYNONYMS,
                NAMED_ENTITIES,
                PROPERTY_VALUE_MAP,
                RELATIONSHIP_KEYWORDS,
            )

            class _DefaultTerms:
                @property
                def entity_synonyms(self) -> dict[str, str]:
                    return ENTITY_SYNONYMS

                @property
                def named_entities(self) -> dict[str, dict[str, str]]:
                    return NAMED_ENTITIES

                @property
                def relationship_keywords(self) -> dict[str, str]:
                    return RELATIONSHIP_KEYWORDS

                @property
                def property_value_map(self) -> dict[str, dict]:
                    return PROPERTY_VALUE_MAP

            self._terms = _DefaultTerms()
        else:
            self._terms = terms

    def parse(self, text: str) -> ParseResult:
        """Parse Korean text into a structured query.

        Args:
            text: Korean natural language query string.

        Returns:
            A ParseResult containing the structured query, confidence
            score, unresolved terms, and debug details.
        """
        if not text or not text.strip():
            return ParseResult(
                query=StructuredQuery(
                    intent=QueryIntent(intent=QueryIntentType.FIND, confidence=0.0),
                ),
                confidence=0.0,
                unresolved_terms=[],
                parse_details={"error": "empty input"},
            )

        text = text.strip()

        intent = self._detect_intent(text)
        entities = self._extract_entities(text)
        filters = self._extract_filters(text, entities)
        relationships = self._extract_relationships(text)
        aggregations = self._extract_aggregations(text)
        pagination = self._extract_pagination(text)

        # Classify reasoning type
        reasoning_type = self._classify_reasoning_type(text, entities, relationships)

        # Build StructuredQuery
        query = StructuredQuery(
            intent=intent,
            object_types=entities,
            filters=filters,
            relationships=relationships,
            aggregations=aggregations if aggregations else None,
            pagination=pagination,
            reasoning_type=reasoning_type,
        )

        # Compute confidence and unresolved terms
        confidence, unresolved = self._compute_confidence(text, entities, filters, relationships)

        parse_details: dict[str, Any] = {
            "detected_intent": intent.intent.value if isinstance(intent.intent, QueryIntentType) else intent.intent,
            "entities": entities,
            "filters": [
                {"field": f.field, "operator": f.operator.value if isinstance(f.operator, FilterOperator) else f.operator, "value": f.value}
                for f in filters
            ],
            "relationships": [{"type": r.type, "direction": r.direction} for r in relationships],
            "aggregations": [
                {"function": a.function, "field": a.field}
                for a in (aggregations or [])
            ],
            "pagination": {"limit": pagination.limit} if pagination else None,
        }

        return ParseResult(
            query=query,
            confidence=confidence,
            unresolved_terms=unresolved,
            parse_details=parse_details,
        )

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------

    def _detect_intent(self, text: str) -> QueryIntent:
        """Detect query intent from Korean keywords.

        Args:
            text: Korean natural language text.

        Returns:
            QueryIntent with detected type and confidence.
        """
        # COUNT detection
        for kw in _COUNT_KEYWORDS:
            if kw in text:
                return QueryIntent(intent=QueryIntentType.COUNT, confidence=0.9)
        if re.search(r"수\b", text) and ("몇" in text or "총" in text):
            return QueryIntent(intent=QueryIntentType.COUNT, confidence=0.8)

        # AGGREGATE detection
        for kw in _AGGREGATION_KEYWORDS:
            if kw in text:
                return QueryIntent(intent=QueryIntentType.AGGREGATE, confidence=0.9)

        # Default: FIND
        return QueryIntent(intent=QueryIntentType.FIND, confidence=0.7)

    # ------------------------------------------------------------------
    # Entity extraction
    # ------------------------------------------------------------------

    def _extract_entities(self, text: str) -> list[str]:
        """Find entity labels from Korean text using the synonyms dictionary.

        Args:
            text: Korean natural language text.

        Returns:
            Deduplicated list of Neo4j entity labels found.
        """
        found_labels: list[str] = []
        seen: set[str] = set()

        # Check named entities first (longer, more specific matches)
        for name in sorted(self._terms.named_entities.keys(), key=len, reverse=True):
            if name in text:
                ne = self._terms.named_entities[name]
                label = ne["label"]
                if label not in seen:
                    found_labels.append(label)
                    seen.add(label)

        # Check entity synonyms (sort by key length descending for greedy match)
        for korean_term in sorted(self._terms.entity_synonyms.keys(), key=len, reverse=True):
            if korean_term in text:
                label = self._terms.entity_synonyms[korean_term]
                if label not in seen:
                    found_labels.append(label)
                    seen.add(label)

        return found_labels

    # ------------------------------------------------------------------
    # Filter extraction
    # ------------------------------------------------------------------

    def _extract_filters(
        self, text: str, entities: list[str]
    ) -> list[ExtractedFilter]:
        """Extract filters from text using property maps and named entities.

        Args:
            text: Korean natural language text.
            entities: Already-extracted entity labels for context.

        Returns:
            List of ExtractedFilter objects.
        """
        filters: list[ExtractedFilter] = []

        # 1. Named entity filters (e.g., "부산항" -> Port.unlocode = "KRPUS")
        for name in sorted(self._terms.named_entities.keys(), key=len, reverse=True):
            if name in text:
                ne = self._terms.named_entities[name]
                filters.append(
                    ExtractedFilter(
                        field=ne["key"],
                        operator=FilterOperator.EQUALS,
                        value=ne["value"],
                        confidence=0.95,
                    )
                )

        # 2. Property value filters (e.g., "컨테이너선" -> vesselType = ContainerShip)
        for prop_name, value_map in self._terms.property_value_map.items():
            for korean_val in sorted(value_map.keys(), key=len, reverse=True):
                if korean_val in text:
                    english_val = value_map[korean_val]
                    # Avoid duplicate filters for same property
                    if not any(f.field == prop_name and f.value == english_val for f in filters):
                        filters.append(
                            ExtractedFilter(
                                field=prop_name,
                                operator=FilterOperator.EQUALS,
                                value=english_val,
                                confidence=0.9,
                            )
                        )

        # 3. Numeric comparison filters (e.g., "5000톤 이상" -> tonnage >= 5000)
        for match in _NUMBER_PATTERN.finditer(text):
            num_str, unit, comparison = match.groups()
            if not unit and not comparison:
                # Bare number without unit or comparison -- skip
                continue

            num_val = float(num_str)
            if num_val == int(num_val):
                num_val = int(num_val)

            # Determine property from unit
            prop_name = "tonnage"  # default
            multiplier = 1.0
            if unit and unit in _UNIT_TO_PROPERTY:
                prop_name, multiplier = _UNIT_TO_PROPERTY[unit]

            actual_value = num_val * multiplier
            if actual_value == int(actual_value):
                actual_value = int(actual_value)

            # Determine operator from comparison keyword
            if comparison and comparison in _COMPARISON_KEYWORDS:
                op = _COMPARISON_KEYWORDS[comparison]
            elif unit and not comparison:
                # Just a number with unit, default to equals
                op = FilterOperator.EQUALS
            else:
                continue

            filters.append(
                ExtractedFilter(
                    field=prop_name,
                    operator=op,
                    value=actual_value,
                    confidence=0.85,
                )
            )

        return filters

    # ------------------------------------------------------------------
    # Relationship extraction
    # ------------------------------------------------------------------

    def _extract_relationships(self, text: str) -> list[RelationshipSpec]:
        """Detect relationships from Korean keywords.

        Args:
            text: Korean natural language text.

        Returns:
            List of RelationshipSpec objects.
        """
        relationships: list[RelationshipSpec] = []
        seen: set[str] = set()

        for korean_kw in sorted(self._terms.relationship_keywords.keys(), key=len, reverse=True):
            if korean_kw in text:
                rel_type = self._terms.relationship_keywords[korean_kw]
                if rel_type not in seen:
                    relationships.append(
                        RelationshipSpec(type=rel_type, direction="outgoing")
                    )
                    seen.add(rel_type)

        return relationships

    # ------------------------------------------------------------------
    # Aggregation extraction
    # ------------------------------------------------------------------

    def _extract_aggregations(self, text: str) -> list[AggregationSpec] | None:
        """Detect aggregation functions from Korean keywords.

        Args:
            text: Korean natural language text.

        Returns:
            List of AggregationSpec or None if no aggregations found.
        """
        aggregations: list[AggregationSpec] = []

        for korean_kw, func in _AGGREGATION_KEYWORDS.items():
            if korean_kw in text:
                # Try to detect what field the aggregation is on
                agg_field = self._guess_aggregation_field(text, korean_kw)
                aggregations.append(
                    AggregationSpec(
                        function=func,
                        field=agg_field,
                        alias=f"{func.lower()}_{agg_field}" if agg_field else func.lower(),
                    )
                )

        return aggregations if aggregations else None

    def _guess_aggregation_field(self, text: str, agg_keyword: str) -> str | None:
        """Heuristic to guess which field an aggregation applies to.

        Args:
            text: Full query text.
            agg_keyword: The Korean aggregation keyword found.

        Returns:
            Property name string or None.
        """
        # Common field hints in Korean
        field_hints: dict[str, str] = {
            "톤수": "tonnage",
            "톤": "tonnage",
            "속도": "speed",
            "길이": "length",
            "무게": "tonnage",
            "거리": "distance",
        }

        # Look for field hint near the aggregation keyword
        idx = text.find(agg_keyword)
        window_start = max(0, idx - 10)
        window_end = min(len(text), idx + len(agg_keyword) + 10)
        window = text[window_start:window_end]

        for hint_kr, prop in field_hints.items():
            if hint_kr in window or hint_kr in text:
                return prop

        return None

    # ------------------------------------------------------------------
    # Pagination extraction
    # ------------------------------------------------------------------

    def _extract_pagination(self, text: str) -> Pagination | None:
        """Detect pagination from patterns like '상위 N개' or 'N개만'.

        Args:
            text: Korean natural language text.

        Returns:
            Pagination object or None.
        """
        match = _PAGINATION_PATTERN.search(text)
        if match:
            # Groups: (상위N개, N개만, N건만, 상위N건)
            for group in match.groups():
                if group is not None:
                    return Pagination(limit=int(group))
        return None

    # ------------------------------------------------------------------
    # Reasoning type classification
    # ------------------------------------------------------------------

    # Keywords for multi-hop reasoning type detection
    _COMPARISON_REASONING_KEYWORDS: list[str] = [
        "비교", "차이", "어느 쪽", "더 많", "더 적", "vs", "대비",
    ]
    _INTERSECTION_REASONING_KEYWORDS: list[str] = [
        "공통", "겹치는", "둘 다", "모두", "동시에", "양쪽",
    ]
    _COMPOSITION_REASONING_KEYWORDS: list[str] = [
        "Top", "가장 많", "가장 적", "순위", "합계", "총", "평균",
    ]
    # Possessive chain patterns for BRIDGE detection:
    #   - "~의 ~의" (double possessive)
    #   - "~에 ~중인/~한 ~의" (locative + adjectival + possessive)
    _POSSESSIVE_CHAIN_PATTERN = re.compile(r"의\s+\S+.*의\b")
    _LOCATIVE_POSSESSIVE_PATTERN = re.compile(
        r"에\s+\S*(?:중인|하는|정박|위치|소속|운영)\S*\s+\S*의\s",
    )
    # Multi-relationship chain: entity + relationship + entity + relationship
    _MULTI_REL_PATTERN = re.compile(
        r"(?:가|이|에서|에)\s+\S*(?:운영|수행|실시|소유|소속|정박|위치)"
        r"\S*\s+\S*(?:에서|에|의|을|를)\s+\S*(?:수행|실시|운영|사용|진행|생성)",
    )

    def _classify_reasoning_type(
        self,
        text: str,
        entities: list[str],
        relationships: list[RelationshipSpec],
    ) -> ReasoningType:
        """Classify the multi-hop reasoning type from Korean text.

        Detection priority (first match wins):
            1. COMPARISON -- keywords like "비교", "vs", "차이" 등
            2. INTERSECTION -- keywords like "공통", "둘 다", "동시에" 등
            3. COMPOSITION -- keywords like "Top", "가장 많", "합계" 등
            4. BRIDGE -- possessive chains ("~의 ~의"), or multiple
               relationship keywords in sequence
            5. DIRECT -- default (single entity lookup)

        Args:
            text: Korean natural language text.
            entities: Entity labels extracted from the text.
            relationships: Relationship specs extracted from the text.

        Returns:
            The detected ReasoningType.
        """
        # 1. COMPARISON
        for kw in self._COMPARISON_REASONING_KEYWORDS:
            if kw in text:
                return ReasoningType.COMPARISON

        # 2. INTERSECTION
        for kw in self._INTERSECTION_REASONING_KEYWORDS:
            if kw in text:
                return ReasoningType.INTERSECTION

        # 3. COMPOSITION
        for kw in self._COMPOSITION_REASONING_KEYWORDS:
            if kw in text:
                return ReasoningType.COMPOSITION

        # 4. BRIDGE -- possessive chain, locative+possessive, multi-rel, or 3+ entities
        if self._POSSESSIVE_CHAIN_PATTERN.search(text):
            return ReasoningType.BRIDGE
        if self._LOCATIVE_POSSESSIVE_PATTERN.search(text):
            return ReasoningType.BRIDGE
        if self._MULTI_REL_PATTERN.search(text):
            return ReasoningType.BRIDGE
        if len(relationships) >= 2:
            return ReasoningType.BRIDGE
        # 3+ distinct entity types suggest multi-hop traversal
        if len(entities) >= 3:
            return ReasoningType.BRIDGE

        # 5. Default
        return ReasoningType.DIRECT

    # ------------------------------------------------------------------
    # Confidence computation
    # ------------------------------------------------------------------

    def _compute_confidence(
        self,
        text: str,
        entities: list[str],
        filters: list[ExtractedFilter],
        relationships: list[RelationshipSpec],
    ) -> tuple[float, list[str]]:
        """Compute confidence score and find unresolved terms.

        Confidence is based on how many meaningful terms in the input
        were successfully resolved to entities, filters, or relationships.

        Args:
            text: Original input text.
            entities: Extracted entity labels.
            filters: Extracted filters.
            relationships: Extracted relationships.

        Returns:
            Tuple of (confidence_score, unresolved_terms).
        """
        resolved_count = len(entities) + len(filters) + len(relationships)

        # Estimate total meaningful terms by counting Korean "words"
        # (simplified: split on spaces + common particles)
        words = re.split(r"[\s,을를이가은는의에서도로]+", text)
        meaningful_words = [w for w in words if len(w) >= 1 and w.strip()]
        total_words = max(len(meaningful_words), 1)

        # Find unresolved terms
        resolved_text = text
        # Remove known named entities
        for name in self._terms.named_entities:
            resolved_text = resolved_text.replace(name, "")
        # Remove known entity synonyms
        for term in sorted(self._terms.entity_synonyms.keys(), key=len, reverse=True):
            resolved_text = resolved_text.replace(term, "")
        # Remove known relationship keywords
        for kw in self._terms.relationship_keywords:
            resolved_text = resolved_text.replace(kw, "")
        # Remove numbers and units
        resolved_text = _NUMBER_PATTERN.sub("", resolved_text)
        # Remove pagination patterns
        resolved_text = _PAGINATION_PATTERN.sub("", resolved_text)
        # Remove common particles and punctuation
        resolved_text = re.sub(r"[을를이가은는의에서도로와과?!~\s,\.]+", " ", resolved_text)

        unresolved = [w.strip() for w in resolved_text.split() if len(w.strip()) >= 2]

        # Confidence: ratio of resolved items to total
        if resolved_count == 0:
            confidence = 0.1
        else:
            confidence = min(1.0, resolved_count / max(total_words, resolved_count))

        # Penalize for unresolved terms
        if unresolved:
            penalty = len(unresolved) * 0.1
            confidence = max(0.1, confidence - penalty)

        return round(confidence, 2), unresolved
