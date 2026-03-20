"""Demonstration of embedding-based entity resolution.

Shows the difference between fuzzy and embedding matching for maritime entities.
"""

from kg.entity_resolution import EmbeddingMatcher, EntityResolver, FuzzyMatcher

# Example entities with typos and variations
entities = [
    "Samsung Heavy Industries",
    "Samsyng Heavy Industries",  # 타이포
    "HMM",
    "Hyundai Merchant Marine",
    "KRISO",
    "kriso",
    "Korea Research Institute",
    "부산항",
    "Busan Port",
]


def demo_fuzzy_vs_embedding() -> None:
    """Compare fuzzy and embedding similarity scores."""
    print("=" * 60)
    print("Fuzzy vs Embedding Similarity Comparison")
    print("=" * 60)

    fuzzy = FuzzyMatcher()
    embedding = EmbeddingMatcher()

    pairs = [
        ("Samsung Heavy Industries", "Samsyng Heavy Industries"),
        ("HMM", "Hyundai Merchant Marine"),
        ("KRISO", "kriso"),
        ("KRISO", "Korea Research Institute"),
        ("부산항", "Busan Port"),
    ]

    for a, b in pairs:
        fuzzy_score = fuzzy.similarity(a, b)
        emb_score = embedding.similarity(a, b)
        print(f"\n'{a}' vs '{b}'")
        print(f"  Fuzzy:     {fuzzy_score:.3f}")
        print(f"  Embedding: {emb_score:.3f}")
        print(f"  Winner:    {'EMBEDDING' if emb_score > fuzzy_score else 'FUZZY'}")


def demo_resolver_without_embedding() -> None:
    """Resolve entities using only fuzzy matching."""
    print("\n\n" + "=" * 60)
    print("Entity Resolution: Fuzzy Only (use_embedding=False)")
    print("=" * 60)

    resolver = EntityResolver(fuzzy_threshold=0.8, use_embedding=False)
    results = resolver.resolve(entities)

    print(f"\nFound {len(results)} entity groups:\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. Canonical: '{result.canonical}'")
        if result.merged:
            print(f"   Merged from: {result.aliases}")
            print(f"   Evidence: {len(result.candidates)} candidate(s)")
            for cand in result.candidates:
                if cand.similarity >= 0.8:
                    print(
                        f"     - {cand.entity_a} ↔ {cand.entity_b}: "
                        f"{cand.similarity:.3f} ({cand.method.value})"
                    )
        print()


def demo_resolver_with_embedding() -> None:
    """Resolve entities using fuzzy + embedding matching."""
    print("=" * 60)
    print("Entity Resolution: Fuzzy + Embedding (use_embedding=True)")
    print("=" * 60)

    resolver = EntityResolver(
        fuzzy_threshold=0.8,
        embedding_threshold=0.85,
        use_embedding=True,
    )
    results = resolver.resolve(entities)

    print(f"\nFound {len(results)} entity groups:\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. Canonical: '{result.canonical}'")
        if result.merged:
            print(f"   Merged from: {result.aliases}")
            print(f"   Evidence: {len(result.candidates)} candidate(s)")
            for cand in result.candidates:
                threshold = (
                    0.85 if cand.method.value == "EMBEDDING" else 0.8
                )
                if cand.similarity >= threshold:
                    print(
                        f"     - {cand.entity_a} ↔ {cand.entity_b}: "
                        f"{cand.similarity:.3f} ({cand.method.value})"
                    )
        print()


if __name__ == "__main__":
    demo_fuzzy_vs_embedding()
    demo_resolver_without_embedding()
    demo_resolver_with_embedding()
