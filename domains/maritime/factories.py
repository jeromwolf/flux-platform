"""Maritime domain factory functions for core KG components.

Provides convenience constructors that bind core (domain-independent)
classes to the maritime ontology and term dictionary.  These will move
to the ``maritime/`` package during the Phase-2 directory split.

Usage::

    from kg.maritime_factories import (
        create_maritime_validator,
        create_maritime_corrector,
        create_maritime_detector,
    )

    validator = create_maritime_validator()
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def create_maritime_validator():
    """Create a CypherValidator bound to the maritime ontology.

    Returns:
        CypherValidator with all maritime labels and relationship types.
    """
    from kg.cypher_validator import CypherValidator
    from kg.ontology.maritime_loader import load_maritime_ontology

    ontology = load_maritime_ontology()
    return CypherValidator(ontology=ontology)


def create_maritime_corrector():
    """Create a CypherCorrector bound to the maritime ontology.

    Returns:
        CypherCorrector with all maritime labels and relationship types.
    """
    from kg.cypher_corrector import CypherCorrector
    from kg.ontology.maritime_loader import load_maritime_ontology

    ontology = load_maritime_ontology()
    labels = {ot.name for ot in ontology.get_all_object_types()}
    rel_types = {lt.name for lt in ontology.get_all_link_types()}
    return CypherCorrector(valid_labels=labels, valid_rel_types=rel_types)


def create_maritime_detector():
    """Create a HallucinationDetector bound to the maritime ontology and terms.

    Loads:
    - All entity type labels from maritime ontology
    - Named entities from ``maritime_terms.py``
    - Known entity names from sample data references
    - Entity synonym map for Korean term resolution

    Returns:
        HallucinationDetector configured for the maritime domain.
    """
    from kg.hallucination_detector import HallucinationDetector
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

    return HallucinationDetector(
        known_labels=known_labels,
        known_entities=NAMED_ENTITIES,
        known_names=known_names,
        synonym_map=ENTITY_SYNONYMS,
    )
