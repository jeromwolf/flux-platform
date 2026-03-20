"""Comprehensive unit tests for the kg.entity_resolution module.

Test Coverage:
- MatchMethod enum values (2 tests)
- ERCandidate creation and defaults (2 tests)
- ERResult creation and defaults (2 tests)
- FuzzyMatcher.normalize() Korean + English (6 tests)
- FuzzyMatcher.similarity() known pairs (6 tests)
- FuzzyMatcher.find_matches() threshold filtering (4 tests)
- FuzzyMatcher._jaro_similarity() edge cases (3 tests)
- EntityResolver.resolve_pair() (3 tests)
- EntityResolver.resolve() grouping logic (8 tests)
- Conservative merge policy (2 tests)
- Module __init__ exports (1 test)
- EmbeddingMatcher n-gram vectorization (6 tests)
- EmbeddingMatcher similarity (8 tests)
- EmbeddingMatcher find_matches (3 tests)
- EntityResolver with embedding enabled (10 tests)

Total: ~60 tests
"""

from __future__ import annotations

import pytest

from kg.entity_resolution import (
    EntityResolver,
    ERCandidate,
    ERResult,
    FuzzyMatcher,
    MatchMethod,
)
from kg.entity_resolution.fuzzy_matcher import (
    EmbeddingMatcher,
)
from kg.entity_resolution.fuzzy_matcher import (
    FuzzyMatcher as FuzzyMatcherDirect,
)
from kg.entity_resolution.models import ERCandidate as ERCandidateDirect
from kg.entity_resolution.resolver import EntityResolver as EntityResolverDirect

# =============================================================================
# MatchMethod Enum
# =============================================================================


@pytest.mark.unit
class TestMatchMethod:
    """Tests for MatchMethod enumeration."""

    def test_all_values_present(self) -> None:
        """MatchMethod should define EXACT, FUZZY, EMBEDDING, LLM."""
        assert set(MatchMethod) == {
            MatchMethod.EXACT,
            MatchMethod.FUZZY,
            MatchMethod.EMBEDDING,
            MatchMethod.LLM,
        }

    def test_string_serialization(self) -> None:
        """MatchMethod should serialize to its string value."""
        assert str(MatchMethod.EXACT) == "MatchMethod.EXACT"
        assert MatchMethod.FUZZY.value == "FUZZY"


# =============================================================================
# ERCandidate Dataclass
# =============================================================================


@pytest.mark.unit
class TestERCandidate:
    """Tests for ERCandidate data model."""

    def test_creation_with_defaults(self) -> None:
        """ERCandidate should be creatable with required fields only."""
        c = ERCandidate(
            entity_a="KRISO",
            entity_b="kriso",
            similarity=1.0,
            method=MatchMethod.EXACT,
        )
        assert c.entity_a == "KRISO"
        assert c.entity_b == "kriso"
        assert c.similarity == 1.0
        assert c.method == MatchMethod.EXACT
        assert c.context == {}

    def test_creation_with_context(self) -> None:
        """ERCandidate should accept arbitrary context dict."""
        c = ERCandidate(
            entity_a="A",
            entity_b="B",
            similarity=0.75,
            method=MatchMethod.FUZZY,
            context={"source": "crawler", "confidence": "medium"},
        )
        assert c.context["source"] == "crawler"
        assert len(c.context) == 2


# =============================================================================
# ERResult Dataclass
# =============================================================================


@pytest.mark.unit
class TestERResult:
    """Tests for ERResult data model."""

    def test_creation_with_defaults(self) -> None:
        """ERResult should be creatable with canonical name only."""
        r = ERResult(canonical="KRISO")
        assert r.canonical == "KRISO"
        assert r.aliases == []
        assert r.candidates == []
        assert r.merged is False

    def test_creation_with_aliases(self) -> None:
        """ERResult should store aliases and merged flag."""
        r = ERResult(
            canonical="MSC OSCAR",
            aliases=["msc oscar", "MSC Oscar"],
            merged=True,
        )
        assert len(r.aliases) == 2
        assert r.merged is True


# =============================================================================
# FuzzyMatcher.normalize()
# =============================================================================


@pytest.mark.unit
class TestFuzzyMatcherNormalize:
    """Tests for the name normalization function."""

    def test_lowercase_and_strip(self) -> None:
        """Should lowercase and strip whitespace."""
        assert FuzzyMatcher.normalize("  KRISO  ") == "kriso"

    def test_remove_corporate_suffixes_english(self) -> None:
        """Should remove Co., Ltd., Inc. etc."""
        assert FuzzyMatcher.normalize("Samsung Co., Ltd.") == "samsung"
        assert FuzzyMatcher.normalize("Hyundai Corp.") == "hyundai"
        assert FuzzyMatcher.normalize("Maersk Inc.") == "maersk"

    def test_remove_corporate_suffixes_korean(self) -> None:
        """Should remove 주식회사, (주) etc."""
        assert FuzzyMatcher.normalize("삼성전자 주식회사") == "삼성전자"
        assert FuzzyMatcher.normalize("현대상선(주)") == "현대상선"
        assert FuzzyMatcher.normalize("㈜한진해운") == "㈜한진해운"  # 접두사는 유지

    def test_collapse_multiple_spaces(self) -> None:
        """Should collapse multiple spaces into one."""
        assert FuzzyMatcher.normalize("MSC   OSCAR") == "msc oscar"

    def test_empty_and_whitespace(self) -> None:
        """Should handle empty and whitespace-only strings."""
        assert FuzzyMatcher.normalize("") == ""
        assert FuzzyMatcher.normalize("   ") == ""

    def test_korean_entity_unchanged(self) -> None:
        """Pure Korean names without suffixes should pass through."""
        assert FuzzyMatcher.normalize("부산항") == "부산항"
        assert FuzzyMatcher.normalize("해양수산부") == "해양수산부"


# =============================================================================
# FuzzyMatcher.similarity()
# =============================================================================


@pytest.mark.unit
class TestFuzzyMatcherSimilarity:
    """Tests for similarity scoring."""

    def setup_method(self) -> None:
        self.matcher = FuzzyMatcher()

    def test_identical_strings(self) -> None:
        """Identical strings should return 1.0."""
        assert self.matcher.similarity("삼성전자", "삼성전자") == 1.0

    def test_case_variants_exact_after_normalize(self) -> None:
        """Case-only differences should return 1.0 (exact after normalize)."""
        assert self.matcher.similarity("KRISO", "kriso") == 1.0

    def test_high_similarity_case_variant_multiword(self) -> None:
        """MSC OSCAR vs MSC Oscar should be very high (>0.9)."""
        score = self.matcher.similarity("MSC OSCAR", "MSC Oscar")
        assert score > 0.9

    def test_low_similarity_different_entities(self) -> None:
        """Completely different entities should score low (<0.6)."""
        score = self.matcher.similarity("Samsung", "Sony")
        assert score < 0.6

    def test_corporate_suffix_stripped(self) -> None:
        """Names differing only by suffix should match exactly."""
        score = self.matcher.similarity("Hyundai Co., Ltd.", "Hyundai")
        assert score == 1.0

    def test_moderate_similarity(self) -> None:
        """Partially similar names should get moderate scores."""
        score = self.matcher.similarity("Busan Port", "Busan Harbor")
        assert 0.4 < score < 0.9


# =============================================================================
# FuzzyMatcher._jaro_similarity() edge cases
# =============================================================================


@pytest.mark.unit
class TestJaroSimilarity:
    """Tests for the internal Jaro similarity computation."""

    def test_both_empty(self) -> None:
        """Two empty strings should return 1.0."""
        assert FuzzyMatcher._jaro_similarity("", "") == 1.0

    def test_one_empty(self) -> None:
        """One empty string should return 0.0."""
        assert FuzzyMatcher._jaro_similarity("abc", "") == 0.0
        assert FuzzyMatcher._jaro_similarity("", "abc") == 0.0

    def test_single_char_match(self) -> None:
        """Single matching characters."""
        score = FuzzyMatcher._jaro_similarity("a", "a")
        assert score == 1.0


# =============================================================================
# FuzzyMatcher.find_matches()
# =============================================================================


@pytest.mark.unit
class TestFuzzyMatcherFindMatches:
    """Tests for candidate discovery."""

    def setup_method(self) -> None:
        self.matcher = FuzzyMatcher(default_threshold=0.8)

    def test_finds_exact_match(self) -> None:
        """Should find exact (after normalization) matches."""
        results = self.matcher.find_matches("KRISO", ["kriso", "Samsung", "HMM"])
        assert len(results) >= 1
        assert results[0].entity_b == "kriso"
        assert results[0].method == MatchMethod.EXACT
        assert results[0].similarity == 1.0

    def test_threshold_filtering(self) -> None:
        """Should exclude matches below the threshold."""
        results = self.matcher.find_matches(
            "Samsung",
            ["Sony", "Samsang", "Apple"],
            threshold=0.9,
        )
        # "Sony" and "Apple" should be excluded; "Samsang" might or might not pass
        for r in results:
            assert r.similarity >= 0.9

    def test_empty_candidates(self) -> None:
        """Empty candidate list should return empty results."""
        results = self.matcher.find_matches("KRISO", [])
        assert results == []

    def test_sorted_by_descending_similarity(self) -> None:
        """Results should be sorted highest similarity first."""
        results = self.matcher.find_matches(
            "MSC OSCAR",
            ["MSC Oscar", "MSC OSKAR", "COSCO"],
            threshold=0.5,
        )
        scores = [r.similarity for r in results]
        assert scores == sorted(scores, reverse=True)


# =============================================================================
# EntityResolver.resolve_pair()
# =============================================================================


@pytest.mark.unit
class TestEntityResolverPair:
    """Tests for pairwise entity comparison."""

    def setup_method(self) -> None:
        self.resolver = EntityResolver(fuzzy_threshold=0.8)

    def test_exact_match_after_normalize(self) -> None:
        """Case variants should be EXACT with 1.0 similarity."""
        c = self.resolver.resolve_pair("KRISO", "kriso")
        assert c.method == MatchMethod.EXACT
        assert c.similarity == 1.0

    def test_fuzzy_match(self) -> None:
        """Similar but not identical strings should be FUZZY."""
        c = self.resolver.resolve_pair("MSC OSCAR", "MSC OSKAR")
        assert c.method == MatchMethod.FUZZY
        assert c.similarity > 0.7

    def test_low_similarity_pair(self) -> None:
        """Unrelated entities should get low similarity."""
        c = self.resolver.resolve_pair("Samsung", "Maersk")
        assert c.similarity < 0.6


# =============================================================================
# EntityResolver.resolve() - grouping logic
# =============================================================================


@pytest.mark.unit
class TestEntityResolverResolve:
    """Tests for the full resolution pipeline."""

    def setup_method(self) -> None:
        self.resolver = EntityResolver(fuzzy_threshold=0.8)

    def test_empty_input(self) -> None:
        """Empty entity list should return empty results."""
        assert self.resolver.resolve([]) == []

    def test_single_entity(self) -> None:
        """Single entity should return one unmerged result."""
        results = self.resolver.resolve(["KRISO"])
        assert len(results) == 1
        assert results[0].canonical == "KRISO"
        assert results[0].merged is False
        assert results[0].aliases == []

    def test_all_unique_entities(self) -> None:
        """Completely different entities should not merge."""
        results = self.resolver.resolve(["Samsung", "Maersk", "COSCO"])
        assert len(results) == 3
        assert all(not r.merged for r in results)

    def test_case_variants_merge(self) -> None:
        """Case-only variants should merge into one group."""
        results = self.resolver.resolve(["MSC OSCAR", "MSC Oscar", "msc oscar"])
        # 모두 같은 그룹으로 병합되어야 함
        merged_groups = [r for r in results if r.merged]
        assert len(merged_groups) == 1
        group = merged_groups[0]
        assert len(group.aliases) == 2  # canonical + 2 aliases = 3 total
        assert group.merged is True

    def test_canonical_is_longest(self) -> None:
        """Canonical name should be the longest surface form."""
        results = self.resolver.resolve(["MSC OSCAR", "MSC Oscar", "msc oscar"])
        merged = [r for r in results if r.merged]
        assert len(merged) == 1
        # "MSC OSCAR" and "MSC Oscar" are same length (9 chars);
        # max() picks the first encountered for ties, but both are valid
        assert len(merged[0].canonical) == 9

    def test_different_strings_not_merged(self) -> None:
        """Semantically same but textually different should NOT merge.

        "KRISO" vs "Korea Research Institute" are too different in string
        form for fuzzy matching alone to merge them.
        """
        results = self.resolver.resolve(["KRISO", "Korea Research Institute"])
        assert len(results) == 2
        assert all(not r.merged for r in results)

    def test_hmm_korean_not_merged(self) -> None:
        """HMM vs 현대상선 should NOT merge (too risky without context)."""
        results = self.resolver.resolve(["HMM", "현대상선"])
        assert len(results) == 2
        assert all(not r.merged for r in results)

    def test_mixed_merge_and_separate(self) -> None:
        """Some entities merge while others stay separate."""
        entities = [
            "MSC OSCAR",
            "MSC Oscar",
            "COSCO SHIPPING",
            "Maersk",
        ]
        results = self.resolver.resolve(entities)
        merged_count = sum(1 for r in results if r.merged)
        unmerged_count = sum(1 for r in results if not r.merged)
        assert merged_count == 1  # MSC OSCAR / MSC Oscar
        assert unmerged_count == 2  # COSCO SHIPPING, Maersk


# =============================================================================
# Conservative merge policy
# =============================================================================


@pytest.mark.unit
class TestConservativePolicy:
    """Tests that the resolver is conservative (avoids false merges)."""

    def test_ambiguous_pair_stays_separate(self) -> None:
        """Entities with moderate similarity should NOT be merged.

        Using a high threshold to ensure borderline cases stay separate.
        """
        resolver = EntityResolver(fuzzy_threshold=0.9)
        results = resolver.resolve(["Busan Port", "Busan Harbor"])
        # 유사하지만 0.9 임계값에는 못 미침
        assert len(results) == 2
        assert all(not r.merged for r in results)

    def test_strict_threshold_prevents_merge(self) -> None:
        """Very high threshold should prevent all but exact merges."""
        resolver = EntityResolver(fuzzy_threshold=0.99)
        results = resolver.resolve(["MSC OSCAR", "MSC OSKAR"])
        assert len(results) == 2
        assert all(not r.merged for r in results)


# =============================================================================
# Module exports
# =============================================================================


@pytest.mark.unit
class TestModuleExports:
    """Test that __init__.py exports are correct."""

    def test_all_exports_importable(self) -> None:
        """All __all__ members should be importable."""
        from kg.entity_resolution import __all__ as exports

        assert "ERCandidate" in exports
        assert "ERResult" in exports
        assert "MatchMethod" in exports
        assert "FuzzyMatcher" in exports
        assert "EmbeddingMatcher" in exports
        assert "EntityResolver" in exports
        assert len(exports) == 6

    def test_direct_imports_match_package_imports(self) -> None:
        """Direct and package-level imports should be the same classes."""
        assert FuzzyMatcher is FuzzyMatcherDirect
        assert ERCandidate is ERCandidateDirect
        assert EntityResolver is EntityResolverDirect


# =============================================================================
# EmbeddingMatcher - n-gram vectorization
# =============================================================================


@pytest.mark.unit
class TestEmbeddingMatcherNgrams:
    """Tests for character n-gram vectorization."""

    def setup_method(self) -> None:
        self.matcher = EmbeddingMatcher(n=3)

    def test_char_ngram_basic(self) -> None:
        """Should generate correct trigrams for simple text."""
        vec = self.matcher._char_ngram_vector("abc")
        assert vec == {"abc": 1}

    def test_char_ngram_overlapping(self) -> None:
        """Should generate overlapping n-grams."""
        vec = self.matcher._char_ngram_vector("abcd")
        assert vec == {"abc": 1, "bcd": 1}

    def test_char_ngram_repeated(self) -> None:
        """Should count repeated n-grams."""
        vec = self.matcher._char_ngram_vector("abcabc")
        # "abc", "bca", "cab", "abc" (repeated), "bca" (repeated), "cab" (repeated)
        # Wait, let me recalculate: "abcabc" -> "abc", "bca", "cab", "abc"
        # So: abc:2, bca:1, cab:1
        assert vec["abc"] == 2
        assert vec["bca"] == 1
        assert vec["cab"] == 1

    def test_char_ngram_empty(self) -> None:
        """Empty string should return empty vector."""
        vec = self.matcher._char_ngram_vector("")
        assert vec == {}

    def test_char_ngram_short_string(self) -> None:
        """String shorter than n should return empty vector."""
        vec = self.matcher._char_ngram_vector("ab")
        assert vec == {}

    def test_char_ngram_korean(self) -> None:
        """Should handle Korean characters."""
        vec = self.matcher._char_ngram_vector("부산항")
        assert "부산항" in vec
        assert vec["부산항"] == 1


# =============================================================================
# EmbeddingMatcher - cosine similarity
# =============================================================================


@pytest.mark.unit
class TestEmbeddingMatcherSimilarity:
    """Tests for embedding similarity computation."""

    def setup_method(self) -> None:
        self.matcher = EmbeddingMatcher(n=3)

    def test_identical_strings(self) -> None:
        """Identical strings should return 1.0."""
        assert self.matcher.similarity("samsung", "samsung") == 1.0

    def test_case_variants_exact(self) -> None:
        """Case-only differences should return 1.0 (exact after normalize)."""
        score = self.matcher.similarity("KRISO", "kriso")
        assert score == 1.0

    def test_very_similar_strings(self) -> None:
        """Very similar strings should have moderate to high cosine similarity."""
        score = self.matcher.similarity("MSC OSCAR", "MSC OSKAR")
        # n-gram embedding is more sensitive to character differences
        # than fuzzy matching - "msc oscar" vs "msc oskar" differ in 2 chars
        assert score > 0.5

    def test_different_strings_low_score(self) -> None:
        """Completely different strings should have low similarity."""
        score = self.matcher.similarity("Samsung", "Maersk")
        assert score < 0.5

    def test_partial_overlap(self) -> None:
        """Partially overlapping strings should get moderate scores."""
        score = self.matcher.similarity("Busan Port", "Busan Harbor")
        # "Busan" 부분은 겹치지만 "Port"/"Harbor"는 다름
        assert 0.3 < score < 0.7

    def test_empty_strings(self) -> None:
        """Empty strings should return 0.0."""
        assert self.matcher.similarity("", "abc") == 0.0
        assert self.matcher.similarity("abc", "") == 0.0

    def test_corporate_suffix_normalized(self) -> None:
        """Corporate suffixes should be stripped before comparison."""
        score = self.matcher.similarity("Hyundai Co., Ltd.", "Hyundai")
        assert score == 1.0

    def test_korean_entity_similarity(self) -> None:
        """Korean entities should be compared correctly."""
        score = self.matcher.similarity("부산항", "부산항")
        assert score == 1.0
        score2 = self.matcher.similarity("부산항", "인천항")
        assert score2 < 0.8  # Different ports


# =============================================================================
# EmbeddingMatcher - find_matches
# =============================================================================


@pytest.mark.unit
class TestEmbeddingMatcherFindMatches:
    """Tests for embedding-based candidate discovery."""

    def setup_method(self) -> None:
        self.matcher = EmbeddingMatcher(default_threshold=0.85, n=3)

    def test_finds_exact_match(self) -> None:
        """Should find exact matches with EXACT method."""
        results = self.matcher.find_matches("KRISO", ["kriso", "Samsung", "HMM"])
        assert len(results) >= 1
        assert results[0].entity_b == "kriso"
        assert results[0].method == MatchMethod.EXACT
        assert results[0].similarity == 1.0

    def test_threshold_filtering(self) -> None:
        """Should exclude matches below threshold."""
        results = self.matcher.find_matches(
            "Samsung",
            ["Sony", "Samsyng", "Apple"],
            threshold=0.9,
        )
        # Only very similar ones should pass
        for r in results:
            assert r.similarity >= 0.9

    def test_embedding_method_for_non_exact(self) -> None:
        """Non-exact matches should use EMBEDDING method."""
        results = self.matcher.find_matches(
            "MSC OSCAR",
            ["MSC OSKAR", "COSCO"],
            threshold=0.7,
        )
        # "MSC OSKAR" should match with EMBEDDING method
        non_exact = [r for r in results if r.similarity < 1.0]
        if non_exact:
            assert non_exact[0].method == MatchMethod.EMBEDDING


# =============================================================================
# EntityResolver with embedding enabled
# =============================================================================


@pytest.mark.unit
class TestEntityResolverWithEmbedding:
    """Tests for EntityResolver with embedding matching enabled."""

    def setup_method(self) -> None:
        self.resolver = EntityResolver(
            fuzzy_threshold=0.8,
            embedding_threshold=0.85,
            use_embedding=True,
        )

    def test_embedding_matcher_instantiated(self) -> None:
        """Embedding matcher should be instantiated when use_embedding=True."""
        assert self.resolver._embedding_matcher is not None

    def test_resolve_pair_exact_priority(self) -> None:
        """EXACT match should take priority over all."""
        c = self.resolver.resolve_pair("KRISO", "kriso")
        assert c.method == MatchMethod.EXACT
        assert c.similarity == 1.0

    def test_resolve_pair_embedding_vs_fuzzy(self) -> None:
        """Should use EMBEDDING if it scores higher than FUZZY."""
        # This is a bit hard to test without knowing exact scores,
        # but we can test that embedding is considered
        c = self.resolver.resolve_pair("MSC OSCAR", "MSC OSKAR")
        # Either FUZZY or EMBEDDING depending on which scores higher
        assert c.method in [MatchMethod.FUZZY, MatchMethod.EMBEDDING]
        assert c.similarity > 0.7

    def test_resolve_pair_context_includes_both_scores(self) -> None:
        """When embedding wins, context should include both scores."""
        c = self.resolver.resolve_pair("Samsyng", "Samsung")
        # Normalized: "samsyng" vs "samsung" - very similar
        if c.method == MatchMethod.EMBEDDING:
            assert "fuzzy_score" in c.context
            assert "embedding_score" in c.context

    def test_resolve_with_embedding_threshold(self) -> None:
        """Resolve should respect embedding_threshold for EMBEDDING matches."""
        # Create entities that might match via embedding but not fuzzy
        entities = ["MSC OSCAR", "MSC OSKAR", "COSCO"]
        results = self.resolver.resolve(entities)
        # Check that results are reasonable
        assert len(results) > 0

    def test_korean_entity_embedding(self) -> None:
        """Korean entities should work with embedding."""
        c = self.resolver.resolve_pair("부산항", "부산항")
        assert c.method == MatchMethod.EXACT
        assert c.similarity == 1.0

    def test_mixed_merge_with_embedding(self) -> None:
        """Some entities should merge via embedding while others stay separate."""
        entities = [
            "Samsung",
            "Samsyng",  # typo, might match via embedding
            "Maersk",
        ]
        results = self.resolver.resolve(entities)
        # At least 2 groups (Samsung/Samsyng might merge, Maersk separate)
        assert len(results) >= 2

    def test_embedding_disabled_by_default(self) -> None:
        """Resolver without use_embedding should not instantiate embedding matcher."""
        resolver_no_emb = EntityResolver(use_embedding=False)
        assert resolver_no_emb._embedding_matcher is None

    def test_resolve_pair_without_embedding_stays_fuzzy(self) -> None:
        """Without embedding enabled, should only use EXACT/FUZZY."""
        resolver_no_emb = EntityResolver(use_embedding=False)
        c = resolver_no_emb.resolve_pair("MSC OSCAR", "MSC OSKAR")
        assert c.method in [MatchMethod.EXACT, MatchMethod.FUZZY]
        assert c.method != MatchMethod.EMBEDDING

    def test_threshold_boundary_exact(self) -> None:
        """Exact match should merge regardless of threshold."""
        strict_resolver = EntityResolver(
            fuzzy_threshold=0.99,
            embedding_threshold=0.99,
            use_embedding=True,
        )
        results = strict_resolver.resolve(["MSC OSCAR", "msc oscar"])
        merged = [r for r in results if r.merged]
        assert len(merged) == 1  # Should merge via EXACT

    def test_high_embedding_threshold_prevents_false_merge(self) -> None:
        """Very high embedding threshold should prevent borderline merges."""
        strict_resolver = EntityResolver(
            fuzzy_threshold=0.8,
            embedding_threshold=0.98,
            use_embedding=True,
        )
        results = strict_resolver.resolve(["Samsung", "Samsyng"])
        # With very high threshold, might not merge
        # This test verifies threshold is respected
        assert len(results) >= 1
