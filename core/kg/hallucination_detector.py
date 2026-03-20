"""KG-based hallucination detection for generated answers.

Validates that entities mentioned in LLM-generated answers actually exist
in the knowledge graph ontology or known entity registry. Per GraphRAG
Part 10 -- Agentic GraphRAG hallucination prevention pattern.

Usage::

    detector = HallucinationDetector.from_maritime_ontology()
    result = detector.validate("HMM 알헤시라스가 부산항에 정박중입니다")
    if not result.is_valid:
        print(f"Hallucinated entities: {result.hallucinated_entities}")
"""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Result of hallucination detection.

    Attributes:
        is_valid: True if no hallucinated entities detected.
        mentioned_entities: All entities found in the text.
        verified_entities: Entities confirmed in KG.
        hallucinated_entities: Entities not found in KG.
        confidence: Confidence score (0.0-1.0).
        details: Additional validation details.
    """

    is_valid: bool = True
    mentioned_entities: list[str] = field(default_factory=list)
    verified_entities: list[str] = field(default_factory=list)
    hallucinated_entities: list[str] = field(default_factory=list)
    confidence: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)


class HallucinationDetector:
    """Detects hallucinated entities in generated text using KG validation.

    Validation strategy:
    1. Extract entity-like terms from text using maritime terms dictionary.
    2. Check against ontology (valid entity types/labels).
    3. Check against known named entities (KRISO facilities, ports, etc.).
    4. Flag unknown entities as potential hallucinations.

    Conservative policy: Only flag entities that look like specific proper
    nouns but don't match any known entity.  Generic terms are allowed.
    """

    def __init__(
        self,
        known_labels: set[str] | None = None,
        known_entities: dict[str, dict[str, str]] | None = None,
        known_names: set[str] | None = None,
        synonym_map: dict[str, str] | None = None,
    ) -> None:
        """Initialize with known KG entities.

        Args:
            known_labels: Valid ontology labels (e.g., ``{'Vessel', 'Port'}``).
            known_entities: Named entity registry from maritime_terms.
            known_names: Set of known entity names from sample data.
            synonym_map: Korean term -> Neo4j label synonym map.
        """
        self._known_labels = known_labels or set()
        self._known_entities = known_entities or {}
        self._known_names = known_names or set()
        self._synonym_map = synonym_map or {}

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_maritime_ontology(cls) -> HallucinationDetector:
        """Create detector from maritime ontology and terms dictionary.

        Loads:
        - All entity type labels from maritime ontology
        - Named entities from ``maritime_terms.py``
        - Known entity names from sample data references
        - Entity synonym map for Korean term resolution

        .. deprecated::
            Use ``kg.maritime_factories.create_maritime_detector()`` instead.
            This method will be removed in the next major version.
        """
        warnings.warn(
            "from_maritime_ontology() is deprecated. "
            "Use kg.maritime_factories.create_maritime_detector() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from kg.nlp.maritime_terms import ENTITY_SYNONYMS, NAMED_ENTITIES

        # Collect ontology labels via the loader
        known_labels: set[str] = set()
        try:
            from kg.ontology.maritime_loader import load_maritime_ontology

            ontology = load_maritime_ontology()
            known_labels = {ot.name for ot in ontology.get_all_object_types()}
        except Exception:
            logger.debug("Could not load maritime ontology for labels", exc_info=True)

        # Also add labels from ENTITY_SYNONYMS values
        known_labels.update(ENTITY_SYNONYMS.values())

        # Build known names from NAMED_ENTITIES + common proper nouns
        known_names: set[str] = set(NAMED_ENTITIES.keys())
        known_names.update(
            {
                "KRISO",
                "한국선박해양플랫폼연구소",
                "부산항",
                "인천항",
                "울산항",
                "여수광양항",
                "평택당진항",
                "HMM",
                "HMM 알헤시라스",
                "팬오션 드림",
                "해양수산부",
                "한국선급",
                "대형예인수조",
                "빙해수조",
                "캐비테이션터널",
                "심해공학수조",
                "해양공학수조",
                "해양경찰청",
                "부산항만공사",
                "남해",
                "동해",
                "서해",
                "대한해협",
            }
        )

        return cls(
            known_labels=known_labels,
            known_entities=NAMED_ENTITIES,
            known_names=known_names,
            synonym_map=ENTITY_SYNONYMS,
        )

    # ------------------------------------------------------------------
    # Entity extraction
    # ------------------------------------------------------------------

    def extract_entities_from_text(self, text: str) -> list[str]:
        """Extract potential entity names from text.

        Uses patterns to identify:
        - Known named entities from the maritime terms dictionary
        - Korean proper nouns (consecutive Korean chars with domain suffixes)
        - English proper nouns (capitalized words)

        Args:
            text: Input text to scan for entities.

        Returns:
            List of potential entity name strings (no duplicates,
            longest matches first).
        """
        if not text or not text.strip():
            return []

        entities: list[str] = []
        seen: set[str] = set()

        def _add(name: str) -> None:
            if name not in seen:
                seen.add(name)
                entities.append(name)

        # 1. Check against known named entities (longest first to avoid
        #    partial overlaps like "부산" matching before "부산항")
        from kg.nlp.maritime_terms import NAMED_ENTITIES

        for name in sorted(NAMED_ENTITIES.keys(), key=len, reverse=True):
            if name in text:
                _add(name)

        # 2. Check against known multi-word entity names (e.g. "HMM 알헤시라스")
        for name in sorted(self._known_names, key=len, reverse=True):
            if name in text and name not in seen:
                _add(name)

        # 3. Extract Korean proper noun patterns (domain suffixes)
        korean_patterns = [
            r"[가-힣]+항",  # ports: ~항
            r"[가-힣]+호",  # vessels: ~호
            r"[가-힣]+선",  # ships: ~선
            r"[가-힣]+소",  # institutes: ~소
            r"[가-힣]+부",  # ministries: ~부
            r"[가-힣]+청",  # agencies: ~청
            r"[가-힣]+사",  # companies: ~사
            r"[가-힣]+수조",  # basins: ~수조
            r"[가-힣]+터널",  # tunnels: ~터널
        ]
        for pattern in korean_patterns:
            for match in re.finditer(pattern, text):
                name = match.group()
                if len(name) >= 3 and name not in seen:
                    _add(name)

        # 4. Extract English proper nouns (sequences of capitalized words)
        eng_pattern = r"\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*\b"
        for match in re.finditer(eng_pattern, text):
            name = match.group()
            if len(name) >= 2 and name not in seen:
                _add(name)

        return entities

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, text: str) -> DetectionResult:
        """Validate text against KG for hallucinated entities.

        Args:
            text: Generated text to validate.

        Returns:
            DetectionResult with validation status and details.
        """
        if not text or not text.strip():
            return DetectionResult(is_valid=True, confidence=1.0)

        mentioned = self.extract_entities_from_text(text)
        if not mentioned:
            return DetectionResult(is_valid=True, confidence=1.0)

        verified: list[str] = []
        hallucinated: list[str] = []

        for entity in mentioned:
            if self._is_known_entity(entity):
                verified.append(entity)
            else:
                hallucinated.append(entity)

        # Calculate confidence: ratio of verified to total
        confidence = len(verified) / len(mentioned) if mentioned else 1.0

        return DetectionResult(
            is_valid=len(hallucinated) == 0,
            mentioned_entities=mentioned,
            verified_entities=verified,
            hallucinated_entities=hallucinated,
            confidence=confidence,
            details={
                "total_entities": len(mentioned),
                "verified_count": len(verified),
                "hallucinated_count": len(hallucinated),
            },
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_known_entity(self, entity: str) -> bool:
        """Check if entity is known in the KG.

        Checks against (in order):
        1. Exact match in known names
        2. Match in ontology labels
        3. Match in named entity registry keys
        4. Match in synonym map keys or values
        5. Case-insensitive match in known names
        """
        # 1. Exact match in known names
        if entity in self._known_names:
            return True

        # 2. Known ontology label
        if entity in self._known_labels:
            return True

        # 3. Named entity registry
        if entity in self._known_entities:
            return True

        # 4. Synonym map (Korean term or English label)
        if entity in self._synonym_map:
            return True
        if entity in self._synonym_map.values():
            return True

        # 5. Case-insensitive match in known names
        entity_lower = entity.lower()
        if any(n.lower() == entity_lower for n in self._known_names):
            return True

        # 6. Case-insensitive match in known labels
        if any(l.lower() == entity_lower for l in self._known_labels):
            return True

        return False
