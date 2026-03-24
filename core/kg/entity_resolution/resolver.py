"""Entity Resolver with 3-tier matching pipeline.

Provides the main :class:`EntityResolver` that combines exact, fuzzy, and
(optionally) embedding-based matching to group duplicate entity mentions
and select canonical names.

Design principles:
- **Conservative merge**: only merge when similarity clearly exceeds the
  threshold. Ambiguous pairs stay separate.
- **Longest-form canonical**: the longest surface form is chosen as the
  canonical name (usually the most informative).
- **Extensible**: ``use_embedding`` flag reserves room for a future
  embedding-based matcher without breaking the API.
"""

from __future__ import annotations

from kg.entity_resolution.fuzzy_matcher import EmbeddingMatcher, FuzzyMatcher, HybridMatcher
from kg.entity_resolution.models import ERCandidate, ERResult, MatchMethod


class EntityResolver:
    """4-tier entity resolution pipeline.

    Tiers:
    1. **Exact** -- normalized string equality (always on).
    2. **Hybrid** -- weighted Levenshtein + Cosine (off by default, MAKG 기반).
    3. **Fuzzy** -- SequenceMatcher + Jaro-Winkler (always on).
    4. **Embedding** -- vector cosine similarity (off by default, future).

    Args:
        fuzzy_threshold: Minimum fuzzy similarity to consider a merge.
        embedding_threshold: Minimum embedding similarity (future use).
        use_embedding: Enable embedding-based matching (not yet implemented).
        use_hybrid: Enable MAKG-inspired hybrid matching (Levenshtein + Cosine).
        hybrid_levenshtein_weight: Weight for Levenshtein component (default: 0.6).
        hybrid_cosine_weight: Weight for Cosine component (default: 0.4).
    """

    def __init__(
        self,
        fuzzy_threshold: float = 0.8,
        embedding_threshold: float = 0.85,
        use_embedding: bool = False,
        use_hybrid: bool = False,
        hybrid_levenshtein_weight: float = 0.6,
        hybrid_cosine_weight: float = 0.4,
    ) -> None:
        self.fuzzy_threshold = fuzzy_threshold
        self.embedding_threshold = embedding_threshold
        self.use_embedding = use_embedding
        self.use_hybrid = use_hybrid
        self.hybrid_levenshtein_weight = hybrid_levenshtein_weight
        self.hybrid_cosine_weight = hybrid_cosine_weight
        self._matcher = FuzzyMatcher(default_threshold=fuzzy_threshold)
        self._embedding_matcher = (
            EmbeddingMatcher(default_threshold=embedding_threshold)
            if use_embedding
            else None
        )
        self._hybrid_matcher = (
            HybridMatcher(
                levenshtein_weight=hybrid_levenshtein_weight,
                cosine_weight=hybrid_cosine_weight,
                default_threshold=fuzzy_threshold,
            )
            if use_hybrid
            else None
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_pair(self, a: str, b: str) -> ERCandidate:
        """Compare two entity mentions and return a match candidate.

        Args:
            a: First entity surface form.
            b: Second entity surface form.

        Returns:
            An :class:`ERCandidate` with the computed similarity and method.
        """
        na = self._matcher.normalize(a)
        nb = self._matcher.normalize(b)

        # Tier 1: EXACT
        if na == nb:
            return ERCandidate(
                entity_a=a,
                entity_b=b,
                similarity=1.0,
                method=MatchMethod.EXACT,
                context={"normalized_a": na, "normalized_b": nb},
            )

        # Tier 2: HYBRID (if enabled) — MAKG 기반 가중 조합 (Levenshtein + Cosine)
        if self.use_hybrid and self._hybrid_matcher is not None:
            hybrid_score = self._hybrid_matcher.similarity(a, b)
            if hybrid_score >= self.fuzzy_threshold:
                lev_score = self._hybrid_matcher._fuzzy.levenshtein_similarity(a, b)
                cos_score = self._hybrid_matcher._embedding.similarity(a, b)
                return ERCandidate(
                    entity_a=a,
                    entity_b=b,
                    similarity=hybrid_score,
                    method=MatchMethod.HYBRID,
                    context={
                        "normalized_a": na,
                        "normalized_b": nb,
                        "levenshtein_score": lev_score,
                        "cosine_score": cos_score,
                        "weights": {
                            "levenshtein": self.hybrid_levenshtein_weight,
                            "cosine": self.hybrid_cosine_weight,
                        },
                    },
                )

        # Tier 3: FUZZY
        fuzzy_score = self._matcher.similarity(a, b)

        # Tier 4: EMBEDDING (if enabled)
        if self.use_embedding and self._embedding_matcher is not None:
            embedding_score = self._embedding_matcher.similarity(a, b)

            # 두 점수 중 높은 것 사용
            if embedding_score > fuzzy_score:
                return ERCandidate(
                    entity_a=a,
                    entity_b=b,
                    similarity=embedding_score,
                    method=MatchMethod.EMBEDDING,
                    context={
                        "normalized_a": na,
                        "normalized_b": nb,
                        "fuzzy_score": fuzzy_score,
                        "embedding_score": embedding_score,
                    },
                )

        # FUZZY가 더 높거나 embedding 비활성화
        return ERCandidate(
            entity_a=a,
            entity_b=b,
            similarity=fuzzy_score,
            method=MatchMethod.FUZZY,
            context={"normalized_a": na, "normalized_b": nb},
        )

    def resolve(self, entities: list[str]) -> list[ERResult]:
        """Resolve a list of entity mentions into grouped results.

        Algorithm:
        1. For every pair, compute similarity via :meth:`resolve_pair`.
        2. Build connected components using Union-Find, merging pairs
           whose similarity >= ``fuzzy_threshold``.
        3. For each component, pick the *longest* surface form as canonical.

        Args:
            entities: List of entity surface forms to resolve.

        Returns:
            List of :class:`ERResult`, one per resolved group.  Singleton
            groups (no duplicates found) have ``merged=False``.
        """
        if not entities:
            return []

        n = len(entities)

        # Union-Find 구조
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]  # path compression
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # 모든 쌍 비교 및 후보 수집
        all_candidates: dict[tuple[int, int], ERCandidate] = {}
        for i in range(n):
            for j in range(i + 1, n):
                candidate = self.resolve_pair(entities[i], entities[j])
                all_candidates[(i, j)] = candidate

                # Merge threshold 결정: embedding이면 embedding_threshold,
                # HYBRID/FUZZY이면 fuzzy_threshold
                threshold = (
                    self.embedding_threshold
                    if candidate.method == MatchMethod.EMBEDDING
                    else self.fuzzy_threshold
                )

                if candidate.similarity >= threshold:
                    union(i, j)

        # 컴포넌트 그룹 구성
        groups: dict[int, list[int]] = {}
        for i in range(n):
            root = find(i)
            groups.setdefault(root, []).append(i)

        results: list[ERResult] = []
        for indices in groups.values():
            surface_forms = [entities[i] for i in indices]
            # 가장 긴 형태를 정식 이름(canonical)으로 선택
            canonical = max(surface_forms, key=len)
            aliases = [s for s in surface_forms if s != canonical]
            merged = len(surface_forms) > 1

            # 해당 그룹의 후보 증거 수집
            group_candidates: list[ERCandidate] = []
            index_set = set(indices)
            for (i, j), cand in all_candidates.items():
                if i in index_set and j in index_set:
                    group_candidates.append(cand)

            results.append(
                ERResult(
                    canonical=canonical,
                    aliases=aliases,
                    candidates=group_candidates,
                    merged=merged,
                )
            )

        return results
