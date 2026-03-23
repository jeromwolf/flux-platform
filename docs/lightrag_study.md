# LightRAG Study

## Paper Reference

**"LightRAG: Simple and Fast Retrieval-Augmented Generation"**
Zirui Guo et al., 2024. Proposes a graph-based RAG framework that replaces flat
chunk retrieval with entity-level knowledge graph traversal.

## Core Concept

Standard RAG: `document -> chunk -> embed -> vector search -> context`
LightRAG:    `document -> chunk -> extract entities/rels -> build KG -> graph traversal -> context`

The key insight is that a knowledge graph captures **structural relationships**
between entities, enabling retrieval that follows semantic connections rather
than relying solely on embedding similarity.

## Dual-Level Retrieval

| Level | What it finds | How |
|-------|---------------|-----|
| Low-level | Specific entity mentions and their 1-hop neighbors | Entity matching + graph traversal |
| High-level | Topically related context via community/cluster | Entity type grouping (simplified) |

Results from both levels are merged using Reciprocal Rank Fusion (RRF).

## LightRAG vs Standard RAG vs Microsoft GraphRAG

| Feature | Standard RAG | LightRAG | MS GraphRAG |
|---------|-------------|----------|-------------|
| Index structure | Flat chunks + vectors | Entity KG + vectors | Entity KG + community summaries |
| Retrieval | Vector similarity / BM25 | Graph traversal + RRF | Community-level summarization |
| Incremental update | Re-embed new chunks | Add entities/rels to graph | Rebuild communities |
| Complexity | Low | Medium | High |
| LLM calls at index | 0 | 1 per chunk (extraction) | Many (extraction + summarization) |
| Best for | Simple Q&A | Entity-rich domains | Global summarization queries |

## Our Implementation (`rag/engines/lightrag.py`)

- **RegexEntityExtractor**: Pattern-based extraction for Korean maritime entities
  (Vessel, Port, Organization, Regulation, SeaArea). No LLM required.
- **LightRAGEngine**: In-memory entity graph with dual-level retrieval.
- **No Neo4j dependency**: Works entirely in-memory for Y1. Neo4j integration planned for Y2.
- **Incremental indexing**: `index_chunk()` adds entities without re-processing existing data.

## Comparison with HybridRAGEngine

| Aspect | HybridRAGEngine | LightRAGEngine |
|--------|----------------|----------------|
| Requires embeddings | Yes | No |
| Requires entity extraction | No | Yes |
| Structural relationships | None | 1-hop graph traversal |
| Korean domain awareness | Generic BM25 | Maritime regex patterns |
| Combine via | RRF (semantic + keyword) | RRF (entity + topic) |

The two engines are complementary. HybridRAGEngine excels at semantic similarity;
LightRAGEngine excels at entity-connected retrieval.

## Evaluation Framework (`rag/engines/evaluation.py`)

Provides `RAGEvaluator` with standard IR metrics (precision, recall, F1, MRR) and
a `compare()` method for head-to-head strategy comparison.

## Future Roadmap

| Phase | Enhancement |
|-------|-------------|
| Y1-Q3 | LLM-based entity extraction (replace regex) |
| Y1-Q4 | Combine LightRAG + HybridRAG in unified pipeline |
| Y2-Q1 | Neo4j persistence for entity graph |
| Y2-Q2 | Community detection (Louvain/Leiden) for true high-level retrieval |
| Y2-Q3 | Cross-encoder reranking on graph-retrieved results |
| Y2-Q4 | Evaluation on KRISO maritime benchmark dataset |
