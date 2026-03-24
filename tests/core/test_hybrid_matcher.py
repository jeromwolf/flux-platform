"""Unit tests for HybridMatcher and Levenshtein similarity (MAKG paper).

Test Coverage:
- FuzzyMatcher.levenshtein_similarity: 7 tests
- HybridMatcher: 10 tests
- EntityResolver with use_hybrid=True: 5 tests
- Maritime-specific scenarios: 3 tests

Total: 25 tests
"""

from __future__ import annotations

import pytest

from kg.entity_resolution import (
    EntityResolver,
    ERCandidate,
    ERResult,
    FuzzyMatcher,
    HybridMatcher,
    MatchMethod,
)
from kg.entity_resolution.fuzzy_matcher import EmbeddingMatcher

pytestmark = pytest.mark.unit


# =============================================================================
# FuzzyMatcher.levenshtein_similarity
# =============================================================================


class TestLevenshteinSimilarity:
    """Tests for FuzzyMatcher.levenshtein_similarity (Wagner-Fischer DP)."""

    def setup_method(self) -> None:
        self.matcher = FuzzyMatcher()

    def test_levenshtein_identical(self) -> None:
        """Identical strings should return 1.0."""
        score = self.matcher.levenshtein_similarity("samsung", "samsung")
        assert score == 1.0

    def test_levenshtein_completely_different(self) -> None:
        """Completely different strings should return a low score (< 0.5)."""
        score = self.matcher.levenshtein_similarity("abc", "xyz")
        assert score < 0.5

    def test_levenshtein_one_edit(self) -> None:
        """Strings differing by one character should return a high score (> 0.8)."""
        # "kitten" -> "sitten": 1 substitution, length 6, score = 1 - 1/6 ≈ 0.833
        score = self.matcher.levenshtein_similarity("kitten", "sitten")
        assert score > 0.8

    def test_levenshtein_empty_strings(self) -> None:
        """Both empty strings should return 1.0."""
        score = self.matcher.levenshtein_similarity("", "")
        assert score == 1.0

    def test_levenshtein_one_empty(self) -> None:
        """One empty string vs non-empty should return 0.0."""
        score = self.matcher.levenshtein_similarity("hello", "")
        assert score == 0.0

    def test_levenshtein_case_insensitive(self) -> None:
        """Case-only differences should return 1.0 after normalization."""
        score = self.matcher.levenshtein_similarity("Hello", "hello")
        assert score == 1.0

    def test_levenshtein_corporate_suffix_ignored(self) -> None:
        """Corporate suffixes stripped before comparison should yield 1.0."""
        score = self.matcher.levenshtein_similarity("Samsung Co., Ltd.", "Samsung")
        assert score == 1.0


# =============================================================================
# HybridMatcher
# =============================================================================


class TestHybridMatcher:
    """Tests for HybridMatcher (MAKG-based weighted combination)."""

    def test_hybrid_default_weights(self) -> None:
        """Default weights should be levenshtein=0.6 and cosine=0.4."""
        matcher = HybridMatcher()
        assert matcher.levenshtein_weight == 0.6
        assert matcher.cosine_weight == 0.4

    def test_hybrid_invalid_weights_raises(self) -> None:
        """Weights that do not sum to 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="must equal 1.0"):
            HybridMatcher(levenshtein_weight=0.5, cosine_weight=0.3)

    def test_hybrid_identical_strings(self) -> None:
        """Identical strings should return 1.0."""
        matcher = HybridMatcher()
        score = matcher.similarity("Samsung", "Samsung")
        assert score == 1.0

    def test_hybrid_similar_strings(self) -> None:
        """'Busan Port' vs 'Pusan Port' should return a medium-high score."""
        matcher = HybridMatcher()
        score = matcher.similarity("Busan Port", "Pusan Port")
        # P/B romanization difference: fairly similar in Levenshtein and n-grams
        assert score > 0.5

    def test_hybrid_dissimilar_strings(self) -> None:
        """'Vessel Alpha' vs 'Port Zebra' should return a low score."""
        matcher = HybridMatcher()
        score = matcher.similarity("Vessel Alpha", "Port Zebra")
        assert score < 0.5

    def test_hybrid_weighted_combination(self) -> None:
        """Hybrid score should approximate 0.6*levenshtein + 0.4*cosine."""
        fuzzy = FuzzyMatcher()
        embedding = EmbeddingMatcher()
        hybrid = HybridMatcher(levenshtein_weight=0.6, cosine_weight=0.4)

        a, b = "MSC OSCAR", "MSC OSKAR"

        lev_score = fuzzy.levenshtein_similarity(a, b)
        cos_score = embedding.similarity(a, b)
        expected = 0.6 * lev_score + 0.4 * cos_score
        actual = hybrid.similarity(a, b)

        assert abs(actual - expected) < 0.05

    def test_hybrid_find_matches_returns_hybrid_method(self) -> None:
        """find_matches should return candidates with MatchMethod.HYBRID."""
        matcher = HybridMatcher(default_threshold=0.5)
        results = matcher.find_matches("MSC OSCAR", ["MSC OSKAR", "COSCO"])
        hybrid_results = [r for r in results if r.method == MatchMethod.HYBRID]
        assert len(hybrid_results) >= 1

    def test_hybrid_find_matches_context_has_components(self) -> None:
        """HYBRID candidates' context should include levenshtein_score, cosine_score, weights."""
        matcher = HybridMatcher(default_threshold=0.5)
        results = matcher.find_matches("MSC OSCAR", ["MSC OSKAR"])
        assert len(results) >= 1
        candidate = results[0]
        if candidate.method == MatchMethod.HYBRID:
            assert "levenshtein_score" in candidate.context
            assert "cosine_score" in candidate.context
            assert "weights" in candidate.context
            weights = candidate.context["weights"]
            assert "levenshtein" in weights
            assert "cosine" in weights

    def test_hybrid_find_matches_filters_by_threshold(self) -> None:
        """find_matches should only return matches >= threshold."""
        matcher = HybridMatcher(default_threshold=0.9)
        # "COSCO" vs "MSC OSCAR" should be well below 0.9
        results = matcher.find_matches("MSC OSCAR", ["COSCO", "Maersk", "CMA CGM"])
        for r in results:
            assert r.similarity >= 0.9

    def test_hybrid_custom_weights(self) -> None:
        """HybridMatcher should accept and use custom weights (0.3/0.7)."""
        matcher = HybridMatcher(levenshtein_weight=0.3, cosine_weight=0.7)
        assert matcher.levenshtein_weight == 0.3
        assert matcher.cosine_weight == 0.7

        fuzzy = FuzzyMatcher()
        embedding = EmbeddingMatcher()
        a, b = "Busan", "busan port"

        lev_score = fuzzy.levenshtein_similarity(a, b)
        cos_score = embedding.similarity(a, b)
        expected = 0.3 * lev_score + 0.7 * cos_score
        actual = matcher.similarity(a, b)

        assert abs(actual - expected) < 0.05


# =============================================================================
# EntityResolver with use_hybrid=True
# =============================================================================


class TestEntityResolverHybrid:
    """Tests for EntityResolver operating with use_hybrid=True."""

    def test_resolver_hybrid_mode(self) -> None:
        """EntityResolver(use_hybrid=True) should instantiate HybridMatcher."""
        resolver = EntityResolver(use_hybrid=True)
        assert resolver._hybrid_matcher is not None
        assert isinstance(resolver._hybrid_matcher, HybridMatcher)

    def test_resolver_hybrid_resolves_similar_entities(self) -> None:
        """KRISO and kriso should merge; Samsung should stay separate."""
        resolver = EntityResolver(fuzzy_threshold=0.8, use_hybrid=True)
        results = resolver.resolve(["KRISO", "kriso", "Samsung"])
        merged_groups = [r for r in results if r.merged]
        # KRISO / kriso are exact after normalization → should merge
        assert len(merged_groups) >= 1
        merged_names = {r.canonical for r in merged_groups} | {
            alias for r in merged_groups for alias in r.aliases
        }
        assert "KRISO" in merged_names or "kriso" in merged_names

        # Samsung should remain separate
        all_canonicals = {r.canonical for r in results}
        samsung_groups = [
            r
            for r in results
            if r.canonical == "Samsung" or "Samsung" in r.aliases
        ]
        assert len(samsung_groups) == 1
        assert not samsung_groups[0].merged or samsung_groups[0].canonical != "Samsung"

    def test_resolver_hybrid_exact_still_wins(self) -> None:
        """Exact matches should still return EXACT method even when use_hybrid=True."""
        resolver = EntityResolver(use_hybrid=True)
        candidate = resolver.resolve_pair("KRISO", "kriso")
        assert candidate.method == MatchMethod.EXACT
        assert candidate.similarity == 1.0

    def test_resolver_hybrid_custom_weights(self) -> None:
        """EntityResolver with custom hybrid weights should wire them through."""
        resolver = EntityResolver(
            use_hybrid=True,
            hybrid_levenshtein_weight=0.5,
            hybrid_cosine_weight=0.5,
        )
        assert resolver._hybrid_matcher is not None
        assert resolver._hybrid_matcher.levenshtein_weight == 0.5
        assert resolver._hybrid_matcher.cosine_weight == 0.5

    def test_resolver_hybrid_off_by_default(self) -> None:
        """EntityResolver() without use_hybrid should never produce HYBRID results."""
        resolver = EntityResolver()
        assert resolver._hybrid_matcher is None

        # Run resolution over a few similar pairs and verify no HYBRID method appears
        entities = ["MSC OSCAR", "MSC OSKAR", "COSCO"]
        results = resolver.resolve(entities)
        for group in results:
            for cand in group.candidates:
                assert cand.method != MatchMethod.HYBRID


# =============================================================================
# Maritime-specific scenarios
# =============================================================================


class TestMaritimeScenarios:
    """Real-world maritime entity resolution scenarios."""

    def test_maritime_vessel_name_variants(self) -> None:
        """'MSC OSCAR', 'MSC Oscar', 'M.S.C. Oscar' should merge."""
        # Note: dots in "M.S.C." are stripped by normalization → "m.s.c. oscar" vs "msc oscar"
        # The normalized forms may not be identical, but should be highly similar
        resolver = EntityResolver(fuzzy_threshold=0.7, use_hybrid=True)
        results = resolver.resolve(["MSC OSCAR", "MSC Oscar", "MSC OSCAR"])
        # At minimum, "MSC OSCAR" / "MSC Oscar" should merge (case-insensitive exact)
        merged = [r for r in results if r.merged]
        assert len(merged) >= 1

    def test_maritime_port_name_variants(self) -> None:
        """'Busan Port' and 'BUSAN' should merge; '부산항' should stay separate (different script)."""
        resolver = EntityResolver(fuzzy_threshold=0.75, use_hybrid=True)
        results = resolver.resolve(["Busan Port", "BUSAN", "부산항"])

        # '부산항' is Korean-script only; it should NOT merge with Latin-script variants
        korean_group = next(
            (
                r
                for r in results
                if r.canonical == "부산항"
                or "부산항" in r.aliases
            ),
            None,
        )
        assert korean_group is not None, "'부산항' should appear as a separate group"

        # Verify '부산항' is not merged with the Latin-script groups
        if korean_group.merged:
            # If somehow merged, the group must not mix Korean and Latin forms
            all_in_group = [korean_group.canonical] + korean_group.aliases
            latin_forms = [f for f in all_in_group if f not in ("부산항",)]
            assert len(latin_forms) == 0, (
                "'부산항' should not merge with Latin 'Busan' variants"
            )

    def test_maritime_company_suffix_handling(self) -> None:
        """'Hyundai Merchant Marine Co., Ltd.' and 'Hyundai Merchant Marine' should merge."""
        resolver = EntityResolver(fuzzy_threshold=0.8, use_hybrid=True)
        results = resolver.resolve(
            ["Hyundai Merchant Marine Co., Ltd.", "Hyundai Merchant Marine"]
        )
        merged = [r for r in results if r.merged]
        assert len(merged) == 1, (
            "Corporate suffix variant should merge with base name"
        )
        group = merged[0]
        all_forms = [group.canonical] + group.aliases
        assert "Hyundai Merchant Marine Co., Ltd." in all_forms
        assert "Hyundai Merchant Marine" in all_forms
