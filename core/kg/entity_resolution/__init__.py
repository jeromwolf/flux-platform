"""Entity Resolution module for maritime KG quality improvement.

Provides fuzzy and embedding-based entity resolution to detect and merge
duplicate entities in the maritime knowledge graph. Complements the
exact-match dictionary lookup in ``kg.nlp.maritime_terms`` with:

- **FuzzyMatcher**: String similarity using SequenceMatcher + Jaro-Winkler
- **EmbeddingMatcher**: Character n-gram embedding with cosine similarity
- **EntityResolver**: 3-tier pipeline (exact -> fuzzy -> embedding)
- Conservative merge policy to avoid false positives

Usage::

    from kg.entity_resolution import FuzzyMatcher, EmbeddingMatcher, EntityResolver

    matcher = FuzzyMatcher()
    candidates = matcher.find_matches("MSC Oscar", ["MSC OSCAR", "COSCO"])

    emb_matcher = EmbeddingMatcher()
    score = emb_matcher.similarity("Samsung", "Samsyng")

    resolver = EntityResolver(fuzzy_threshold=0.8, use_embedding=True)
    results = resolver.resolve(["KRISO", "kriso", "Samsung"])
"""

from kg.entity_resolution.fuzzy_matcher import EmbeddingMatcher, FuzzyMatcher
from kg.entity_resolution.models import (
    ERCandidate,
    ERResult,
    MatchMethod,
)
from kg.entity_resolution.resolver import EntityResolver

__all__ = [
    "ERCandidate",
    "ERResult",
    "MatchMethod",
    "FuzzyMatcher",
    "EmbeddingMatcher",
    "EntityResolver",
]
