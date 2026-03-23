"""LightRAG-style graph-based retrieval engine.

Implements the core LightRAG pattern: entity extraction -> KG indexing ->
dual-level (entity + topic) graph retrieval. Operates on top of the existing
Neo4j KG and RAG infrastructure.

Reference: "LightRAG: Simple and Fast Retrieval-Augmented Generation"
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from rag.engines.models import RetrievalMode, RetrievedChunk
from rag.documents.models import DocumentChunk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entity extraction models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractedEntity:
    """An entity extracted from text.

    Attributes:
        name: Canonical entity name.
        entity_type: Category label (e.g. Vessel, Port, Organization).
        description: Short contextual snippet around the entity mention.
        source_chunk_id: Chunk from which this entity was extracted.
    """

    name: str
    entity_type: str
    description: str = ""
    source_chunk_id: str = ""


@dataclass(frozen=True)
class ExtractedRelationship:
    """A relationship extracted between two entities.

    Attributes:
        source: Source entity name.
        target: Target entity name.
        relationship_type: Relationship label (e.g. RELATED_TO, DOCKED_AT).
        description: Short contextual snippet describing the relationship.
        weight: Confidence or strength weight in (0, 1].
    """

    source: str
    target: str
    relationship_type: str
    description: str = ""
    weight: float = 1.0


@dataclass(frozen=True)
class EntityExtractionResult:
    """Result of entity extraction from a text chunk.

    Attributes:
        entities: Extracted entities as an immutable tuple.
        relationships: Extracted relationships as an immutable tuple.
    """

    entities: tuple[ExtractedEntity, ...] = ()
    relationships: tuple[ExtractedRelationship, ...] = ()


# ---------------------------------------------------------------------------
# Extractor protocol and regex implementation
# ---------------------------------------------------------------------------


@runtime_checkable
class EntityExtractor(Protocol):
    """Protocol for extracting entities and relationships from text."""

    def extract(self, text: str) -> EntityExtractionResult: ...


@dataclass
class RegexEntityExtractor:
    """Simple regex-based entity extractor for Korean maritime domain.

    Uses pattern matching to extract entities. For production, replace with
    LLM-based extraction (GPT/Claude) or a dedicated NER model.

    Default patterns cover five maritime entity types:
    - Vessel: ship names ending in -함/-호, vessel class keywords
    - Port: names ending in -항/-포구
    - Organization: known acronyms and Korean institute patterns
    - Regulation: IMO codes, SOLAS/MARPOL/COLREG, Korean safety laws
    - SeaArea: names ending in -해협/-해/-만
    """

    # NOTE: Korean \b word-boundary does not work with Hangul in Python re.
    # Patterns omit \b and rely on the character class [가-힣] plus suffix
    # specificity.  Processing order matters: SeaArea patterns (해협) are
    # checked before (해) via ordered iteration.  Overlap detection in
    # extract() prevents shorter patterns from re-matching consumed spans.
    patterns: dict[str, list[str]] = field(default_factory=lambda: {
        "Vessel": [
            r"([가-힣]{2,}함)",
            r"([가-힣]{2,}호)",
            r"(VLCC|LNG선|컨테이너선|유조선|벌크선)",
        ],
        "Port": [
            # Negative lookbehind excludes verb forms like 입항, 출항, 기항, 반항
            r"(?<!입)(?<!출)(?<!기)(?<!반)([가-힣]{2,}항)",
            r"([가-힣]{2,}포구)",
        ],
        "Organization": [
            r"(KRISO|한국해양과학기술원|IMO|해양수산부|선급)",
            r"([가-힣]{2,}연구[소원])",
        ],
        "Regulation": [
            r"(IMO\s*규정\s*[A-Z]?\.\d+)",
            r"(SOLAS|MARPOL|COLREG)",
            r"([가-힣]*안전법[가-힣]*)",
        ],
        "SeaArea": [
            # 해협 before 해 to prevent overlap (대한해협 vs 대한해)
            r"([가-힣]{2,}해협)",
            r"([가-힣]{2,}해)",
            r"([가-힣]{2,}만)",
        ],
    })

    def extract(self, text: str) -> EntityExtractionResult:
        """Extract entities and co-occurrence relationships from *text*.

        Entity extraction proceeds by scanning *text* against every compiled
        regex pattern.  Relationships are inferred from co-occurrence: two
        entities appearing in the same sentence are linked with a
        ``RELATED_TO`` relationship.

        Args:
            text: Raw input text (may be Korean, English, or mixed).

        Returns:
            Extraction result containing entities and relationships.
        """
        entities: list[ExtractedEntity] = []
        seen_names: set[str] = set()
        # Track matched character spans to prevent overlapping shorter matches
        # (e.g. "대한해" should not match if "대한해협" already consumed that span)
        consumed_spans: list[tuple[int, int]] = []

        for entity_type, type_patterns in self.patterns.items():
            for pattern in type_patterns:
                for match in re.finditer(pattern, text):
                    name = match.group(1) if match.lastindex else match.group(0)
                    name = name.strip()
                    if not name or name in seen_names or len(name) < 2:
                        continue
                    # Check overlap with already-consumed spans
                    m_start = match.start(1) if match.lastindex else match.start(0)
                    m_end = match.end(1) if match.lastindex else match.end(0)
                    if any(s <= m_start < e or s < m_end <= e for s, e in consumed_spans):
                        continue
                    seen_names.add(name)
                    consumed_spans.append((m_start, m_end))
                    # Grab surrounding context (up to 20 chars each side)
                    ctx_start = max(0, m_start - 20)
                    ctx_end = min(len(text), m_end + 20)
                    entities.append(ExtractedEntity(
                        name=name,
                        entity_type=entity_type,
                        description=text[ctx_start:ctx_end].strip(),
                    ))

        # Infer relationships via sentence-level co-occurrence
        relationships: list[ExtractedRelationship] = []
        sentences = re.split(r"[.!?\n]", text)
        for sentence in sentences:
            sentence_entities = [e for e in entities if e.name in sentence]
            for i, e1 in enumerate(sentence_entities):
                for e2 in sentence_entities[i + 1:]:
                    relationships.append(ExtractedRelationship(
                        source=e1.name,
                        target=e2.name,
                        relationship_type="RELATED_TO",
                        description=sentence.strip()[:100],
                    ))

        return EntityExtractionResult(
            entities=tuple(entities),
            relationships=tuple(relationships),
        )


# ---------------------------------------------------------------------------
# LightRAG engine
# ---------------------------------------------------------------------------


@dataclass
class LightRAGEngine:
    """Graph-based RAG engine inspired by LightRAG.

    Dual-level retrieval:
    - **Low-level:** Direct entity matching followed by 1-hop neighbor
      expansion in the in-memory entity graph.
    - **High-level:** Topic/theme clustering via entity type grouping.

    Results from both levels are fused using Reciprocal Rank Fusion (RRF).

    Works entirely in-memory without Neo4j.  For production, a Neo4j-backed
    variant can be introduced in Y2 that persists the entity graph and uses
    Cypher traversals for neighbor expansion.

    Example::

        engine = LightRAGEngine()
        engine.index_chunks(chunks)
        results = engine.retrieve("부산항 컨테이너선 안전 규정")
    """

    extractor: EntityExtractor = field(default_factory=RegexEntityExtractor)

    # Internal indices (not part of public API)
    _entity_index: dict[str, ExtractedEntity] = field(
        default_factory=dict, init=False,
    )
    _relationship_index: list[ExtractedRelationship] = field(
        default_factory=list, init=False,
    )
    _chunk_entities: dict[str, list[str]] = field(
        default_factory=dict, init=False,
    )  # chunk_id -> entity names
    _entity_chunks: dict[str, list[str]] = field(
        default_factory=dict, init=False,
    )  # entity name -> chunk_ids
    _chunks: dict[str, DocumentChunk] = field(
        default_factory=dict, init=False,
    )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_chunk(self, chunk: DocumentChunk) -> EntityExtractionResult:
        """Extract entities from *chunk* and update the graph index.

        Args:
            chunk: A document chunk to index.

        Returns:
            The extraction result for this chunk.
        """
        result = self.extractor.extract(chunk.content)

        self._chunks[chunk.chunk_id] = chunk
        self._chunk_entities[chunk.chunk_id] = []

        for entity in result.entities:
            self._entity_index[entity.name] = entity
            self._chunk_entities[chunk.chunk_id].append(entity.name)

            if entity.name not in self._entity_chunks:
                self._entity_chunks[entity.name] = []
            self._entity_chunks[entity.name].append(chunk.chunk_id)

        for rel in result.relationships:
            self._relationship_index.append(rel)

        return result

    def index_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Index multiple chunks.

        Args:
            chunks: Chunks to index.

        Returns:
            Total number of entities extracted across all chunks.
        """
        total_entities = 0
        for chunk in chunks:
            result = self.index_chunk(chunk)
            total_entities += len(result.entities)
        return total_entities

    # ------------------------------------------------------------------
    # Low-level retrieval (entity-centric)
    # ------------------------------------------------------------------

    def retrieve_low_level(
        self, query: str, top_k: int = 10,
    ) -> list[RetrievedChunk]:
        """Low-level retrieval: chunks containing query entities + 1-hop neighbors.

        1. Extract entities from the query.
        2. Also match any indexed entity whose name appears in the query text.
        3. Collect chunks containing those entities (score 1.0 each).
        4. Expand via relationships to neighbor entities (score 0.5 * weight).
        5. Normalize scores and return top-k.

        Args:
            query: User query string.
            top_k: Maximum results.

        Returns:
            Ranked list of retrieved chunks.
        """
        # Extract entities from query
        query_result = self.extractor.extract(query)
        query_entity_names = {e.name for e in query_result.entities}

        # Fuzzy: also match any indexed entity whose name appears in query
        for entity_name in list(self._entity_index.keys()):
            if entity_name in query:
                query_entity_names.add(entity_name)

        # Score chunks by direct entity match
        chunk_scores: dict[str, float] = {}
        for entity_name in query_entity_names:
            for chunk_id in self._entity_chunks.get(entity_name, []):
                chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + 1.0

        # Expand via 1-hop relationships
        for rel in self._relationship_index:
            if rel.source in query_entity_names or rel.target in query_entity_names:
                neighbor = rel.target if rel.source in query_entity_names else rel.source
                for chunk_id in self._entity_chunks.get(neighbor, []):
                    chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + 0.5 * rel.weight

        # Normalize and collect
        max_score = max(chunk_scores.values()) if chunk_scores else 1.0
        results: list[RetrievedChunk] = []
        for chunk_id, score in sorted(chunk_scores.items(), key=lambda x: -x[1])[:top_k]:
            chunk = self._chunks.get(chunk_id)
            if chunk:
                results.append(RetrievedChunk(
                    chunk=chunk,
                    score=score / max_score,
                    retrieval_mode=RetrievalMode.HYBRID,
                ))

        return results

    # ------------------------------------------------------------------
    # High-level retrieval (topic/type-centric)
    # ------------------------------------------------------------------

    def retrieve_high_level(
        self, query: str, top_k: int = 10,
    ) -> list[RetrievedChunk]:
        """High-level retrieval: chunks related to query themes/topics.

        Uses entity type clustering as a proxy for community/topic detection.
        Matches query keywords against predefined type-keyword mappings to
        determine relevant entity types, then collects chunks containing
        entities of those types.

        Args:
            query: User query string.
            top_k: Maximum results.

        Returns:
            Ranked list of retrieved chunks.
        """
        # Determine relevant entity types from query
        query_result = self.extractor.extract(query)
        query_types = {e.entity_type for e in query_result.entities}

        # Keyword-based type detection
        type_keywords: dict[str, list[str]] = {
            "Vessel": ["선박", "함", "호", "vessel", "ship"],
            "Port": ["항", "항만", "port", "포구"],
            "Organization": ["기관", "연구", "organization"],
            "Regulation": ["규정", "법", "regulation", "안전"],
            "SeaArea": ["해", "해협", "만", "sea"],
        }
        for etype, keywords in type_keywords.items():
            if any(kw in query.lower() for kw in keywords):
                query_types.add(etype)

        # Collect entities matching the inferred types
        matching_entities = [
            e for e in self._entity_index.values()
            if e.entity_type in query_types
        ]

        # Score chunks containing those entities
        chunk_scores: dict[str, float] = {}
        for entity in matching_entities:
            for chunk_id in self._entity_chunks.get(entity.name, []):
                chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + 0.3

        max_score = max(chunk_scores.values()) if chunk_scores else 1.0
        results: list[RetrievedChunk] = []
        for chunk_id, score in sorted(chunk_scores.items(), key=lambda x: -x[1])[:top_k]:
            chunk = self._chunks.get(chunk_id)
            if chunk:
                results.append(RetrievedChunk(
                    chunk=chunk,
                    score=score / max_score,
                    retrieval_mode=RetrievalMode.HYBRID,
                ))

        return results

    # ------------------------------------------------------------------
    # Dual-level retrieval (main entry point)
    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 10) -> list[RetrievedChunk]:
        """Dual-level retrieval combining low-level and high-level results.

        Merges results from both retrieval levels using Reciprocal Rank
        Fusion (RRF) with constant k=60.

        Args:
            query: User query string.
            top_k: Maximum results to return.

        Returns:
            Fused ranked list of retrieved chunks.
        """
        low = self.retrieve_low_level(query, top_k=top_k * 2)
        high = self.retrieve_high_level(query, top_k=top_k * 2)

        # RRF fusion
        k = 60  # RRF constant
        chunk_scores: dict[str, float] = {}
        chunk_map: dict[str, RetrievedChunk] = {}

        for rank, result in enumerate(low):
            cid = result.chunk.chunk_id
            chunk_scores[cid] = chunk_scores.get(cid, 0) + 1.0 / (k + rank + 1)
            chunk_map[cid] = result

        for rank, result in enumerate(high):
            cid = result.chunk.chunk_id
            chunk_scores[cid] = chunk_scores.get(cid, 0) + 1.0 / (k + rank + 1)
            if cid not in chunk_map:
                chunk_map[cid] = result

        # Normalize
        max_score = max(chunk_scores.values()) if chunk_scores else 1.0
        results: list[RetrievedChunk] = []
        for cid, score in sorted(chunk_scores.items(), key=lambda x: -x[1])[:top_k]:
            rc = chunk_map[cid]
            results.append(RetrievedChunk(
                chunk=rc.chunk,
                score=score / max_score,
                retrieval_mode=RetrievalMode.HYBRID,
            ))

        return results

    # ------------------------------------------------------------------
    # Inspection / visualization helpers
    # ------------------------------------------------------------------

    def get_entity_graph(self) -> dict[str, Any]:
        """Return the current entity graph for visualization.

        Returns:
            Dictionary with ``nodes``, ``edges``, ``entity_count``,
            ``relationship_count``, and ``chunk_count`` keys.
        """
        nodes = [
            {
                "id": name,
                "label": name,
                "type": entity.entity_type,
                "description": entity.description,
            }
            for name, entity in self._entity_index.items()
        ]
        edges = [
            {
                "source": rel.source,
                "target": rel.target,
                "label": rel.relationship_type,
                "weight": rel.weight,
            }
            for rel in self._relationship_index
        ]
        return {
            "nodes": nodes,
            "edges": edges,
            "entity_count": len(nodes),
            "relationship_count": len(edges),
            "chunk_count": len(self._chunks),
        }

    @property
    def entity_count(self) -> int:
        """Number of unique entities in the index."""
        return len(self._entity_index)

    @property
    def relationship_count(self) -> int:
        """Number of relationships in the index."""
        return len(self._relationship_index)

    @property
    def chunk_count(self) -> int:
        """Number of indexed chunks."""
        return len(self._chunks)
