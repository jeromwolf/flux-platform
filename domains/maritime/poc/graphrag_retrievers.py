"""5 GraphRAG retriever implementations for the Maritime KG.

Provides factory functions for each retriever type:
1. create_vector_retriever       -- Pure vector similarity on Document.textEmbedding
2. create_vector_cypher_retriever -- Vector + graph traversal (org/facility)
3. create_text2cypher_retriever  -- Natural language to Cypher via LLM
4. create_hybrid_retriever       -- Vector + fulltext combined
5. create_tools_retriever        -- Agentic: LLM selects optimal retriever

Each factory returns a configured retriever instance. All require a
running Neo4j instance and Ollama for embedding/LLM operations.

Usage::

    from kg.config import get_driver
    from kg.embeddings import OllamaEmbedder
    from poc.graphrag_retrievers import create_vector_retriever

    driver = get_driver()
    embedder = OllamaEmbedder()
    retriever = create_vector_retriever(
        driver, embedder.get_neo4j_graphrag_embedder()
    )
    results = retriever.search(query_text="선박 저항 성능", top_k=5)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# -- Constants matching kg/schema/indexes.cypher --
VECTOR_INDEX_NAME = "text_embedding"         # indexes.cypher line 9
FULLTEXT_INDEX_NAME = "document_search"      # indexes.cypher line 23
DEFAULT_LLM_MODEL = "qwen2.5:7b"

# -- Neo4j schema excerpt for Text2Cypher context --
# Built from kg/ontology/maritime_ontology.py ENTITY_LABELS + RELATIONSHIP_TYPES
NEO4J_SCHEMA_TEXT = """
Node labels: Vessel, Port, SeaArea, Voyage, Incident, WeatherCondition,
Document, Regulation, Organization, Person, Experiment, TestFacility,
ModelShip, ExperimentalDataset, Measurement, TestCondition, Sensor,
Observation, DataSource, User, Role, DataClass

Key relationships:
(:Vessel)-[:DOCKED_AT]->(:Berth)
(:Vessel)-[:ON_VOYAGE]->(:Voyage)
(:Voyage)-[:FROM_PORT]->(:Port)
(:Voyage)-[:TO_PORT]->(:Port)
(:Vessel)-[:LOCATED_AT]->(:SeaArea)
(:Incident)-[:INVOLVES]->(:Vessel)
(:Incident)-[:OCCURRED_AT]->(:GeoPoint)
(:WeatherCondition)-[:AFFECTS]->(:SeaArea)
(:Document)-[:ISSUED_BY]->(:Organization)
(:Experiment)-[:CONDUCTED_AT]->(:TestFacility)
(:Experiment)-[:TESTED]->(:ModelShip)
(:Experiment)-[:PRODUCED]->(:ExperimentalDataset)
(:Organization {orgId: 'ORG-KRISO'})-[:HAS_FACILITY]->(:TestFacility)
(:User)-[:HAS_ROLE]->(:Role)-[:CAN_ACCESS]->(:DataClass)

Key properties:
Vessel: vesselId, name, vesselType, flag, grossTonnage, currentLocation (POINT)
Port: portId, name, nameEn, location (POINT), portType
Document: docId, title, content, summary, authors, issueDate, textEmbedding
TestFacility: facilityId, name, nameEn, facilityType
Experiment: experimentId, title, objective, date, status
"""

# -- Korean few-shot examples for Text2Cypher --
TEXT2CYPHER_EXAMPLES = [
    "USER: KRISO 시험시설 목록 보여줘\n"
    "CYPHER: MATCH (tf:TestFacility) RETURN tf.name AS 시설명, tf.facilityType AS 유형",
    "USER: 부산항에 정박 중인 선박은?\n"
    "CYPHER: MATCH (v:Vessel)-[:DOCKED_AT]->(:Berth)<-[:HAS_BERTH]-(p:Port {name: '부산항'}) "
    "RETURN v.name AS 선박명, v.vesselType AS 선종",
    "USER: 최근 해양사고 목록\n"
    "CYPHER: MATCH (i:Incident) RETURN i.incidentId AS 사고ID, i.title AS 제목, "
    "i.date AS 일시 ORDER BY i.date DESC LIMIT 10",
    "USER: 빙해수조에서 수행된 실험\n"
    "CYPHER: MATCH (e:Experiment)-[:CONDUCTED_AT]->(tf:TestFacility {facilityType: 'IceTank'}) "
    "RETURN e.title AS 실험명, e.date AS 일시",
]

DOCUMENT_RETURN_PROPERTIES = [
    "docId", "title", "content", "summary", "authors",
    "issueDate", "docType", "source",
]


def create_vector_retriever(
    driver: Any,
    embedder: Any,
    *,
    index_name: str = VECTOR_INDEX_NAME,
    return_properties: list[str] | None = None,
    neo4j_database: str | None = None,
) -> Any:
    """Create a VectorRetriever for semantic Document search.

    Performs pure vector similarity search against the text_embedding index.

    Args:
        driver: Neo4j driver instance.
        embedder: neo4j_graphrag Embedder instance.
        index_name: Vector index name (default: "text_embedding").
        return_properties: Node properties to return.
        neo4j_database: Database name override.

    Returns:
        Configured VectorRetriever instance.
    """
    from neo4j_graphrag.retrievers import VectorRetriever

    return VectorRetriever(
        driver=driver,
        index_name=index_name,
        embedder=embedder,
        return_properties=return_properties or DOCUMENT_RETURN_PROPERTIES,
        neo4j_database=neo4j_database,
    )


def create_vector_cypher_retriever(
    driver: Any,
    embedder: Any,
    *,
    index_name: str = VECTOR_INDEX_NAME,
    retrieval_query: str | None = None,
    neo4j_database: str | None = None,
) -> Any:
    """Create a VectorCypherRetriever for vector + graph traversal.

    After vector similarity finds Document nodes, the retrieval_query
    traverses ISSUED_BY -> Organization and links to experiments/facilities.

    Args:
        driver: Neo4j driver instance.
        embedder: neo4j_graphrag Embedder instance.
        index_name: Vector index name.
        retrieval_query: Custom Cypher traversal query. Uses default if None.
        neo4j_database: Database name override.

    Returns:
        Configured VectorCypherRetriever instance.
    """
    from neo4j_graphrag.retrievers import VectorCypherRetriever

    default_query = """
        OPTIONAL MATCH (node)-[:ISSUED_BY]->(org:Organization)
        OPTIONAL MATCH (org)-[:HAS_FACILITY]->(tf:TestFacility)
        OPTIONAL MATCH (node)-[:DESCRIBES]->(inc:Incident)

        RETURN node.docId        AS docId,
               node.title        AS title,
               node.content      AS content,
               node.authors      AS authors,
               node.issueDate    AS issueDate,
               collect(DISTINCT org.name)  AS organizations,
               collect(DISTINCT tf.name)   AS facilities,
               collect(DISTINCT inc.incidentId) AS relatedIncidents,
               score
        ORDER BY score DESC
    """

    return VectorCypherRetriever(
        driver=driver,
        index_name=index_name,
        embedder=embedder,
        retrieval_query=retrieval_query or default_query,
        neo4j_database=neo4j_database,
    )


def create_text2cypher_retriever(
    driver: Any,
    llm: Any | None = None,
    *,
    neo4j_schema: str | None = None,
    examples: list[str] | None = None,
    neo4j_database: str | None = None,
) -> Any:
    """Create a Text2CypherRetriever for natural language to Cypher.

    Uses the LLM to translate Korean/English questions into Cypher queries.
    No embedder is needed -- purely LLM-based generation.

    Args:
        driver: Neo4j driver instance.
        llm: neo4j_graphrag LLM instance. Creates OllamaLLM if None.
        neo4j_schema: Schema description text. Uses default if None.
        examples: Few-shot Cypher examples. Uses Korean maritime examples if None.
        neo4j_database: Database name override.

    Returns:
        Configured Text2CypherRetriever instance.
    """
    from neo4j_graphrag.retrievers import Text2CypherRetriever

    if llm is None:
        from neo4j_graphrag.llm import OllamaLLM
        llm = OllamaLLM(model_name=DEFAULT_LLM_MODEL)

    return Text2CypherRetriever(
        driver=driver,
        llm=llm,
        neo4j_schema=neo4j_schema or NEO4J_SCHEMA_TEXT,
        examples=examples or TEXT2CYPHER_EXAMPLES,
        neo4j_database=neo4j_database,
    )


def create_hybrid_retriever(
    driver: Any,
    embedder: Any,
    *,
    vector_index_name: str = VECTOR_INDEX_NAME,
    fulltext_index_name: str = FULLTEXT_INDEX_NAME,
    return_properties: list[str] | None = None,
    neo4j_database: str | None = None,
) -> Any:
    """Create a HybridRetriever combining vector + fulltext search.

    Searches both the vector index (semantic similarity) and fulltext index
    (keyword matching) on Document nodes, then merges and ranks results.

    Args:
        driver: Neo4j driver instance.
        embedder: neo4j_graphrag Embedder instance.
        vector_index_name: Vector index name.
        fulltext_index_name: Fulltext index name.
        return_properties: Node properties to return.
        neo4j_database: Database name override.

    Returns:
        Configured HybridRetriever instance.
    """
    from neo4j_graphrag.retrievers import HybridRetriever

    return HybridRetriever(
        driver=driver,
        vector_index_name=vector_index_name,
        fulltext_index_name=fulltext_index_name,
        embedder=embedder,
        return_properties=return_properties or DOCUMENT_RETURN_PROPERTIES,
        neo4j_database=neo4j_database,
    )


def create_tools_retriever(
    driver: Any,
    embedder: Any,
    llm: Any | None = None,
    *,
    neo4j_database: str | None = None,
) -> Any:
    """Create a ToolsRetriever (Agentic) that selects optimal retriever per query.

    Registers 4 tools:
    - vector_search: semantic document similarity
    - vector_cypher: semantic + graph traversal for related entities
    - text2cypher: structured Cypher queries for exact lookups
    - hybrid_search: keyword + semantic combined search

    The LLM analyzes each query and selects the most appropriate tool(s).

    Args:
        driver: Neo4j driver instance.
        embedder: neo4j_graphrag Embedder instance.
        llm: neo4j_graphrag LLM instance. Creates OllamaLLM if None.
        neo4j_database: Database name override.

    Returns:
        Configured ToolsRetriever instance.
    """
    from neo4j_graphrag.retrievers import ToolsRetriever

    if llm is None:
        from neo4j_graphrag.llm import OllamaLLM
        llm = OllamaLLM(model_name=DEFAULT_LLM_MODEL)

    # Build the 4 sub-retrievers
    vector_ret = create_vector_retriever(
        driver, embedder, neo4j_database=neo4j_database
    )
    vector_cypher_ret = create_vector_cypher_retriever(
        driver, embedder, neo4j_database=neo4j_database
    )
    text2cypher_ret = create_text2cypher_retriever(
        driver, llm, neo4j_database=neo4j_database
    )
    hybrid_ret = create_hybrid_retriever(
        driver, embedder, neo4j_database=neo4j_database
    )

    # Convert each retriever to a tool with Korean descriptions
    tools = [
        vector_ret.convert_to_tool(
            name="vector_search",
            description=(
                "의미적으로 유사한 해사 문서/논문 검색. "
                "예: '선박 저항 관련 연구', '빙해 환경 논문'"
            ),
        ),
        vector_cypher_ret.convert_to_tool(
            name="vector_cypher",
            description=(
                "유사 문서 검색 후 관련 기관/시설/사고까지 그래프 확장. "
                "예: '빙해수조 관련 논문과 발행 기관', '논문 저자의 소속 기관'"
            ),
        ),
        text2cypher_ret.convert_to_tool(
            name="text2cypher",
            description=(
                "정확한 구조적 데이터 검색. 선박 목록, 통계, 필터링, 집계. "
                "예: '항구별 선박 수', '컨테이너선 목록', 'KRISO 시험시설'"
            ),
        ),
        hybrid_ret.convert_to_tool(
            name="hybrid_search",
            description=(
                "키워드 + 의미 결합 검색. 특정 용어가 포함된 유사 문서 찾기. "
                "예: 'KVLCC2 저항시험', '캐비테이션 관련 연구'"
            ),
        ),
    ]

    return ToolsRetriever(llm=llm, tools=tools)
