"""NER pipeline that composes multiple taggers and merges their outputs.

The pipeline collects tags from every registered NERTagger, then
deduplicates overlapping spans using a deterministic priority rule:

1. Longer span wins (more specific match).
2. Higher confidence wins when spans are the same length.
3. The tagger added first wins when confidence is also equal.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from kg.nlp.ner.models import NERResult, NERTag

if TYPE_CHECKING:
    from kg.nlp.ner.protocol import NERTagger


class NERPipeline:
    """Composable pipeline for named entity recognition.

    Example::

        pipeline = (
            NERPipeline()
            .add_tagger(DictionaryTagger.from_maritime_terms())
        )
        result = pipeline.process("부산항에서 컨테이너선이 출항했다.")

    Attributes:
        _taggers: Ordered list of registered NERTagger instances.
    """

    def __init__(self, taggers: list[NERTagger] | None = None) -> None:
        """Initialise the pipeline with an optional list of taggers.

        Args:
            taggers: Pre-registered taggers.  If *None* an empty pipeline
                is created; use :meth:`add_tagger` to register taggers.
        """
        self._taggers: list[NERTagger] = list(taggers) if taggers else []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_tagger(self, tagger: NERTagger) -> NERPipeline:
        """Register a tagger and return *self* for fluent chaining.

        Args:
            tagger: Any object that satisfies the NERTagger protocol.

        Returns:
            This NERPipeline instance (enables method chaining).
        """
        self._taggers.append(tagger)
        return self

    def process(self, text: str) -> NERResult:
        """Run all registered taggers over *text* and return merged results.

        Tags from all taggers are collected, deduplicated (overlapping spans
        resolved by the priority rules described in the module docstring),
        and sorted by start offset before being returned.

        Args:
            text: Raw input string to process.

        Returns:
            NERResult containing deduplicated, sorted tags.
        """
        start_ns = time.perf_counter_ns()

        raw_tags: list[NERTag] = []
        for tagger in self._taggers:
            raw_tags.extend(tagger.tag(text))

        deduped = self._deduplicate(raw_tags)
        deduped.sort(key=lambda t: t.start)

        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

        return NERResult(
            text=text,
            tags=tuple(deduped),
            processing_time_ms=elapsed_ms,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _deduplicate(self, tags: list[NERTag]) -> list[NERTag]:
        """Resolve overlapping spans using the module-level priority rules.

        Two tags *overlap* when their character spans intersect, i.e.
        ``tag_a.start < tag_b.end and tag_b.start < tag_a.end``.

        For each group of mutually overlapping tags, the winner is chosen
        by:

        1. Longest span (``end - start``).
        2. Highest confidence (``NERTag.confidence``).
        3. Lower index in *tags* list (earlier tagger registration order).

        Args:
            tags: Unsorted list of raw tags that may contain overlaps.

        Returns:
            Deduplicated list of non-overlapping tags.
        """
        if not tags:
            return []

        # Sort by start offset, then by descending span length so that
        # longer (higher-priority) spans come first for each position.
        sorted_tags = sorted(
            tags,
            key=lambda t: (t.start, -(t.end - t.start), -t.confidence),
        )

        kept: list[NERTag] = []
        for candidate in sorted_tags:
            overlaps = False
            for accepted in kept:
                if candidate.start < accepted.end and accepted.start < candidate.end:
                    # Overlap detected — resolve by priority.
                    cand_len = candidate.end - candidate.start
                    acc_len = accepted.end - accepted.start

                    if cand_len > acc_len:
                        # Candidate is longer: replace accepted.
                        kept.remove(accepted)
                        kept.append(candidate)
                    elif cand_len == acc_len and candidate.confidence > accepted.confidence:
                        # Same length but higher confidence: replace.
                        kept.remove(accepted)
                        kept.append(candidate)
                    # Otherwise accepted wins; skip candidate.
                    overlaps = True
                    break

            if not overlaps:
                kept.append(candidate)

        return kept
