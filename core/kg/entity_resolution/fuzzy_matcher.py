"""Fuzzy string matcher for maritime entity resolution.

Uses only Python standard library (``difflib.SequenceMatcher`` and a manual
Jaro-Winkler implementation) -- no external dependencies required.

Handles:
- Case-insensitive comparison
- Korean + English mixed names
- Maritime-specific suffix/prefix patterns
- Common corporate suffixes (Co., Ltd., Inc., (주), 주식회사)

Also provides:
- EmbeddingMatcher: Pure Python n-gram embedding with cosine similarity
- HybridMatcher: MAKG 논문 기반 가중 조합 (Levenshtein + Cosine)
"""

from __future__ import annotations

import logging
import math
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

from kg.entity_resolution.models import ERCandidate, MatchMethod

# ---------------------------------------------------------------------------
# Normalization patterns
# ---------------------------------------------------------------------------

# 회사 관련 접미사 (corporate suffixes)
_CORPORATE_SUFFIXES = re.compile(
    r"\s*("
    r"co\.?\s*,?\s*ltd\.?"
    r"|ltd\.?"
    r"|inc\.?"
    r"|corp\.?"
    r"|corporation"
    r"|company"
    r"|주식회사"
    r"|㈜"
    r"|\(주\)"
    r")"
    r"\s*$",
    re.IGNORECASE,
)

# 반복 공백 정리
_MULTI_SPACE = re.compile(r"\s+")


class FuzzyMatcher:
    """String-similarity based entity matcher.

    Combines ``difflib.SequenceMatcher`` ratio and Jaro-Winkler distance,
    returning the higher of the two scores for each comparison. All
    comparisons are performed on *normalized* forms.

    Args:
        default_threshold: Minimum similarity to consider a match.
            Used by :meth:`find_matches` when no explicit threshold is given.
    """

    def __init__(self, default_threshold: float = 0.8) -> None:
        self.default_threshold = default_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def normalize(name: str) -> str:
        """Normalize an entity name for comparison.

        Steps:
        1. Strip leading/trailing whitespace
        2. Lowercase
        3. Remove common corporate suffixes (Co., Ltd., 주식회사, (주), ...)
        4. Collapse multiple spaces into one
        5. Strip again

        Args:
            name: Raw entity surface form.

        Returns:
            Cleaned, lowercased string suitable for comparison.
        """
        text = name.strip().lower()
        text = _CORPORATE_SUFFIXES.sub("", text)
        text = _MULTI_SPACE.sub(" ", text)
        return text.strip()

    def similarity(self, a: str, b: str) -> float:
        """Compute similarity between two entity names.

        Returns the **maximum** of SequenceMatcher ratio and Jaro-Winkler
        distance, both computed on normalized forms.

        Args:
            a: First entity name.
            b: Second entity name.

        Returns:
            Similarity score in [0.0, 1.0].
        """
        na = self.normalize(a)
        nb = self.normalize(b)

        if na == nb:
            return 1.0

        seq_ratio = SequenceMatcher(None, na, nb).ratio()
        jw = self._jaro_winkler(na, nb)

        return max(seq_ratio, jw)

    def levenshtein_similarity(self, a: str, b: str) -> float:
        """Compute normalized Levenshtein similarity between two entity names.

        Wagner-Fischer 동적 프로그래밍 알고리즘을 사용하며,
        롤링 배열로 O(min(m,n)) 공간을 사용합니다.

        Args:
            a: First entity name.
            b: Second entity name.

        Returns:
            Normalized similarity score in [0.0, 1.0]:
            ``1.0 - edit_distance / max(len(na), len(nb))``.
            Returns 1.0 if both strings are empty.
        """
        na = self.normalize(a)
        nb = self.normalize(b)

        if na == nb:
            return 1.0
        if not na or not nb:
            return 0.0

        # Wagner-Fischer DP (롤링 배열, O(min(m,n)) 공간)
        len_a, len_b = len(na), len(nb)

        # 짧은 문자열을 행(row)으로 사용하여 공간 최적화
        if len_a < len_b:
            na, nb = nb, na
            len_a, len_b = len_b, len_a

        # 이전 행 초기화 (삭제 비용)
        prev = list(range(len_b + 1))
        curr = [0] * (len_b + 1)

        for i in range(1, len_a + 1):
            curr[0] = i
            for j in range(1, len_b + 1):
                if na[i - 1] == nb[j - 1]:
                    curr[j] = prev[j - 1]  # 문자 일치: 비용 없음
                else:
                    curr[j] = 1 + min(
                        prev[j],      # 삭제 (deletion)
                        curr[j - 1],  # 삽입 (insertion)
                        prev[j - 1],  # 대체 (substitution)
                    )
            prev, curr = curr, prev  # 행 교환

        edit_distance = prev[len_b]
        return 1.0 - edit_distance / max(len_a, len_b)

    def find_matches(
        self,
        entity: str,
        candidates: list[str],
        threshold: float | None = None,
    ) -> list[ERCandidate]:
        """Find all candidate matches above the similarity threshold.

        Args:
            entity: The entity name to match against.
            candidates: Pool of candidate entity names.
            threshold: Minimum similarity score. Falls back to
                ``self.default_threshold`` when ``None``.

        Returns:
            List of :class:`ERCandidate` objects sorted by descending
            similarity, containing only matches >= *threshold*.
        """
        if threshold is None:
            threshold = self.default_threshold

        results: list[ERCandidate] = []
        for candidate in candidates:
            score = self.similarity(entity, candidate)
            if score >= threshold:
                na = self.normalize(entity)
                nc = self.normalize(candidate)
                method = MatchMethod.EXACT if na == nc else MatchMethod.FUZZY
                results.append(
                    ERCandidate(
                        entity_a=entity,
                        entity_b=candidate,
                        similarity=score,
                        method=method,
                        context={"normalized_a": na, "normalized_b": nc},
                    )
                )

        results.sort(key=lambda c: c.similarity, reverse=True)
        return results

    # ------------------------------------------------------------------
    # Jaro-Winkler (manual implementation)
    # ------------------------------------------------------------------

    @staticmethod
    def _jaro_similarity(s1: str, s2: str) -> float:
        """Compute Jaro similarity between two strings.

        Args:
            s1: First string.
            s2: Second string.

        Returns:
            Jaro similarity in [0.0, 1.0].
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        len1, len2 = len(s1), len(s2)
        # 매칭 윈도우 (matching window)
        match_distance = max(len1, len2) // 2 - 1
        if match_distance < 0:
            match_distance = 0

        s1_matches = [False] * len1
        s2_matches = [False] * len2

        matches = 0
        transpositions = 0

        # 매칭 문자 찾기 (find matching characters)
        for i in range(len1):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len2)
            for j in range(start, end):
                if s2_matches[j] or s1[i] != s2[j]:
                    continue
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

        if matches == 0:
            return 0.0

        # 전위 계산 (count transpositions)
        k = 0
        for i in range(len1):
            if not s1_matches[i]:
                continue
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

        jaro = (
            matches / len1
            + matches / len2
            + (matches - transpositions / 2) / matches
        ) / 3

        return jaro

    @classmethod
    def _jaro_winkler(cls, s1: str, s2: str, prefix_weight: float = 0.1) -> float:
        """Compute Jaro-Winkler similarity.

        Extends Jaro similarity by boosting the score for strings that share
        a common prefix (up to 4 characters).

        Args:
            s1: First string (should be normalized).
            s2: Second string (should be normalized).
            prefix_weight: Scaling factor for the common prefix bonus
                (standard value is 0.1).

        Returns:
            Jaro-Winkler similarity in [0.0, 1.0].
        """
        jaro = cls._jaro_similarity(s1, s2)

        # 공통 접두사 길이 (common prefix length, max 4)
        prefix_len = 0
        for i in range(min(len(s1), len(s2), 4)):
            if s1[i] == s2[i]:
                prefix_len += 1
            else:
                break

        return jaro + prefix_len * prefix_weight * (1 - jaro)


class EmbeddingMatcher:
    """Character n-gram embedding matcher with cosine similarity.

    Uses pure Python implementation without external dependencies.
    Converts strings into character n-gram frequency vectors and computes
    cosine similarity.

    Args:
        default_threshold: Minimum similarity to consider a match.
            Used by :meth:`find_matches` when no explicit threshold is given.
        n: n-gram size (default: 3 for trigrams).
    """

    def __init__(self, default_threshold: float = 0.85, n: int = 3) -> None:
        self.default_threshold = default_threshold
        self.n = n

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def similarity(self, a: str, b: str) -> float:
        """Compute embedding-based similarity between two strings.

        Converts both strings to normalized n-gram frequency vectors
        and computes cosine similarity.

        Args:
            a: First entity name.
            b: Second entity name.

        Returns:
            Cosine similarity score in [0.0, 1.0].
        """
        # 정규화 (FuzzyMatcher 재사용)
        na = FuzzyMatcher.normalize(a)
        nb = FuzzyMatcher.normalize(b)

        if na == nb:
            return 1.0

        # n-gram 벡터 생성
        vec_a = self._char_ngram_vector(na)
        vec_b = self._char_ngram_vector(nb)

        # 코사인 유사도 계산
        return self._cosine_similarity(vec_a, vec_b)

    def find_matches(
        self,
        entity: str,
        candidates: list[str],
        threshold: float | None = None,
    ) -> list[ERCandidate]:
        """Find all candidate matches above the similarity threshold.

        Args:
            entity: The entity name to match against.
            candidates: Pool of candidate entity names.
            threshold: Minimum similarity score. Falls back to
                ``self.default_threshold`` when ``None``.

        Returns:
            List of :class:`ERCandidate` objects sorted by descending
            similarity, containing only matches >= *threshold*.
        """
        if threshold is None:
            threshold = self.default_threshold

        results: list[ERCandidate] = []
        for candidate in candidates:
            score = self.similarity(entity, candidate)
            if score >= threshold:
                na = FuzzyMatcher.normalize(entity)
                nc = FuzzyMatcher.normalize(candidate)
                method = MatchMethod.EXACT if na == nc else MatchMethod.EMBEDDING
                results.append(
                    ERCandidate(
                        entity_a=entity,
                        entity_b=candidate,
                        similarity=score,
                        method=method,
                        context={
                            "normalized_a": na,
                            "normalized_b": nc,
                            "ngram_size": self.n,
                        },
                    )
                )

        results.sort(key=lambda c: c.similarity, reverse=True)
        return results

    # ------------------------------------------------------------------
    # Internal: n-gram vectorization
    # ------------------------------------------------------------------

    def _char_ngram_vector(self, text: str) -> dict[str, int]:
        """Convert text to character n-gram frequency vector.

        Args:
            text: Input text (should be normalized).

        Returns:
            Dictionary mapping n-gram to frequency count.
        """
        if not text:
            return {}

        ngrams: dict[str, int] = {}
        for i in range(len(text) - self.n + 1):
            gram = text[i : i + self.n]
            ngrams[gram] = ngrams.get(gram, 0) + 1

        return ngrams

    # ------------------------------------------------------------------
    # Internal: cosine similarity
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity(vec_a: dict[str, int], vec_b: dict[str, int]) -> float:
        """Compute cosine similarity between two frequency vectors.

        Args:
            vec_a: First n-gram frequency vector.
            vec_b: Second n-gram frequency vector.

        Returns:
            Cosine similarity in [0.0, 1.0].
        """
        if not vec_a or not vec_b:
            return 0.0

        # 내적 (dot product)
        dot_product = 0.0
        for gram in vec_a:
            if gram in vec_b:
                dot_product += vec_a[gram] * vec_b[gram]

        # 벡터 크기 (magnitude)
        mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
        mag_b = math.sqrt(sum(v * v for v in vec_b.values()))

        if mag_a == 0.0 or mag_b == 0.0:
            return 0.0

        return dot_product / (mag_a * mag_b)


class HybridMatcher:
    """MAKG 논문 기반 가중 조합 매처.

    Levenshtein(문자열 편집 거리) + Cosine(n-gram 의미 유사도)를
    가중 평균하여 최종 유사도를 계산합니다.

    Reference: Liu & Cheng (2024), "MAKG: A Maritime Accident Knowledge Graph"
    - Entity alignment: sim = α × levenshtein_sim + β × cosine_sim
    - Default weights: α=0.6, β=0.4

    Args:
        levenshtein_weight: Weight for Levenshtein similarity (default: 0.6).
        cosine_weight: Weight for cosine similarity (default: 0.4).
        default_threshold: Minimum hybrid similarity to consider a match.
        ngram_size: Character n-gram size for cosine component (default: 3).
    """

    def __init__(
        self,
        levenshtein_weight: float = 0.6,
        cosine_weight: float = 0.4,
        default_threshold: float = 0.8,
        ngram_size: int = 3,
    ) -> None:
        # 가중치 합 검증 (weight sum validation)
        if abs(levenshtein_weight + cosine_weight - 1.0) > 1e-6:
            raise ValueError(
                f"levenshtein_weight + cosine_weight must equal 1.0, "
                f"got {levenshtein_weight} + {cosine_weight} = "
                f"{levenshtein_weight + cosine_weight}"
            )
        self.levenshtein_weight = levenshtein_weight
        self.cosine_weight = cosine_weight
        self.default_threshold = default_threshold
        self.ngram_size = ngram_size

        # 내부 매처 인스턴스 생성
        self._fuzzy = FuzzyMatcher(default_threshold=default_threshold)
        self._embedding = EmbeddingMatcher(
            default_threshold=default_threshold, n=ngram_size
        )

    def similarity(self, a: str, b: str) -> float:
        """Compute hybrid similarity: α × levenshtein + β × cosine.

        Args:
            a: First entity name.
            b: Second entity name.

        Returns:
            Weighted similarity score in [0.0, 1.0].
        """
        lev_score = self._fuzzy.levenshtein_similarity(a, b)
        cos_score = self._embedding.similarity(a, b)

        hybrid = self.levenshtein_weight * lev_score + self.cosine_weight * cos_score

        logger.debug(
            "HybridMatcher: '%s' vs '%s' → lev=%.4f, cos=%.4f, hybrid=%.4f",
            a,
            b,
            lev_score,
            cos_score,
            hybrid,
        )

        return hybrid

    def find_matches(
        self,
        entity: str,
        candidates: list[str],
        threshold: float | None = None,
    ) -> list[ERCandidate]:
        """Find all candidate matches above the hybrid similarity threshold.

        Args:
            entity: The entity name to match against.
            candidates: Pool of candidate entity names.
            threshold: Minimum similarity score. Falls back to
                ``self.default_threshold`` when ``None``.

        Returns:
            List of :class:`ERCandidate` objects (method=HYBRID) sorted by
            descending similarity, containing only matches >= *threshold*.
        """
        if threshold is None:
            threshold = self.default_threshold

        results: list[ERCandidate] = []
        for candidate in candidates:
            na = FuzzyMatcher.normalize(entity)
            nc = FuzzyMatcher.normalize(candidate)

            # EXACT 단락 (short-circuit)
            if na == nc:
                results.append(
                    ERCandidate(
                        entity_a=entity,
                        entity_b=candidate,
                        similarity=1.0,
                        method=MatchMethod.EXACT,
                        context={"normalized_a": na, "normalized_b": nc},
                    )
                )
                continue

            lev_score = self._fuzzy.levenshtein_similarity(entity, candidate)
            cos_score = self._embedding.similarity(entity, candidate)
            hybrid = self.levenshtein_weight * lev_score + self.cosine_weight * cos_score

            logger.debug(
                "HybridMatcher.find_matches: '%s' vs '%s' → lev=%.4f, cos=%.4f, hybrid=%.4f",
                entity,
                candidate,
                lev_score,
                cos_score,
                hybrid,
            )

            if hybrid >= threshold:
                results.append(
                    ERCandidate(
                        entity_a=entity,
                        entity_b=candidate,
                        similarity=hybrid,
                        method=MatchMethod.HYBRID,
                        context={
                            "normalized_a": na,
                            "normalized_b": nc,
                            "levenshtein_score": lev_score,
                            "cosine_score": cos_score,
                            "weights": {
                                "levenshtein": self.levenshtein_weight,
                                "cosine": self.cosine_weight,
                            },
                        },
                    )
                )

        results.sort(key=lambda c: c.similarity, reverse=True)
        return results
