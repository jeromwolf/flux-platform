"""LangChain GraphCypherQAChain PoC -- Natural Language -> Cypher -> Neo4j.

Demonstrates text-to-Cypher query generation using:
- LLM: Qwen 2.5 7B via Ollama (local, on-premise)
- Graph: Neo4j Maritime Knowledge Graph
- Chain: GraphCypherQAChain from langchain-neo4j

Usage::
    python poc/langchain_qa.py
    python poc/langchain_qa.py "부산항 근처 선박 알려줘"
"""

from __future__ import annotations

import sys

from langchain_core.prompts import PromptTemplate
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from langchain_ollama import ChatOllama

from kg.config import get_config

_cfg = get_config()

# =========================================================================
# 1. Custom Cypher Generation Prompt
# =========================================================================

CYPHER_GENERATION_TEMPLATE = """You are a Neo4j Cypher expert working with a Korean Maritime Knowledge Graph.
The graph contains data about vessels, ports, sea areas, voyages, incidents,
KRISO test facilities, regulations, sensors, weather conditions,
and KRISO research papers (Document nodes crawled from ScholarWorks).

IMPORTANT: Always answer in Korean (한국어).

Schema:
{schema}

Important Cypher syntax rules:
- Property names are in English (name, vesselType, currentLocation, etc.)
  but property VALUES can be in Korean (e.g. name: '부산항', name: 'HMM 알헤시라스').
- Spatial data uses Neo4j point() and point.distance().
  Vessel positions: vessel.currentLocation  /  Port positions: port.location
  Distance is in meters, so 50 km = 50000.
- Use MATCH and OPTIONAL MATCH. Always RETURN meaningful fields.
- CONTAINS is used in WHERE clauses: WHERE node.prop CONTAINS 'text'
  NEVER put CONTAINS inside curly braces {{}}.
  Correct:   MATCH (n:Label) WHERE n.name CONTAINS 'text'
  INCORRECT: MATCH (n:Label {{name: CONTAINS('text')}})
- For exact matches use MATCH (n:Label {{name: 'exact value'}})
- For partial/fuzzy matches use WHERE n.name CONTAINS 'partial'
- For fulltext search use: CALL db.index.fulltext.queryNodes('index_name', 'search term')
  Available fulltext indexes: document_search (Document: title, content, summary),
  vessel_search, port_search, regulation_search, experiment_search

Document (research paper) search rules:
- Document nodes include crawled KRISO research papers.
- Papers have: title, content (abstract), authors (list), docType, language,
  issueDate, journal, keywords, source, doi, sourceUrl
- Papers are linked to KRISO: (doc:Document)-[:ISSUED_BY]->(org:Organization)
- source='scholarworks_crawl' means crawled from ScholarWorks
- To search papers by keyword, use CONTAINS on title or content, or use fulltext index.
- Do NOT assume Document nodes have DESCRIBES relationship to Incident.
  Most papers are standalone, linked only via ISSUED_BY to Organization.

Key entity examples (Korean):
  Ports:  부산항, 인천항, 울산항, 여수광양항, 평택당진항
  Vessels: HMM 알헤시라스, 팬오션 드림, 한라, 새마을호, 무궁화 10호
  Sea areas: 남해, 동해, 서해, 대한해협
  Organizations (orgId -> name):
    ORG-KRISO -> 한국해양과학기술원 부설 선박해양플랜트연구소 (KRISO)
    ORG-MOF   -> 해양수산부
    ORG-BPA   -> 부산항만공사
    ORG-KR    -> 한국선급
    ORG-HMM   -> HMM (현대상선)
    ORG-KCG   -> 해양경찰청
  IMPORTANT: "KRISO" is commonly used but the stored name is
  '한국해양과학기술원 부설 선박해양플랜트연구소'. Use orgId = 'ORG-KRISO'.
  Facilities: 대형 예인수조, 해양공학수조, 빙해수조, 심해공학수조

Few-shot examples:

Question: 부산항 반경 50km 이내 선박을 알려줘
Cypher:
MATCH (p:Port {{name: '부산항'}})
MATCH (v:Vessel)
WHERE point.distance(v.currentLocation, p.location) < 50000
RETURN v.name AS vessel, v.vesselType AS type,
       round(point.distance(v.currentLocation, p.location) / 1000.0, 1) AS distance_km
ORDER BY distance_km

Question: HMM 알헤시라스는 어디로 항해 중이야?
Cypher:
MATCH (v:Vessel)-[:ON_VOYAGE]->(voy:Voyage)-[:TO_PORT]->(dest:Port)
WHERE v.name CONTAINS 'HMM 알헤시라스'
OPTIONAL MATCH (voy)-[:FROM_PORT]->(orig:Port)
RETURN v.name AS vessel, orig.name AS origin, dest.name AS destination,
       v.currentStatus AS status, v.speed AS speed_knots

Question: KRISO 시험설비 목록을 보여줘
Cypher:
MATCH (org:Organization {{orgId: 'ORG-KRISO'}})-[:HAS_FACILITY]->(tf:TestFacility)
RETURN tf.name AS facility, tf.nameEn AS facility_en,
       tf.facilityType AS type, tf.length AS length_m,
       tf.width AS width_m, tf.depth AS depth_m

Question: 최근 해양사고 이력을 알려줘
Cypher:
MATCH (inc:Incident)
OPTIONAL MATCH (inc)-[:INVOLVES]->(v:Vessel)
OPTIONAL MATCH (inc)-[:VIOLATED]->(reg:Regulation)
RETURN inc.incidentId AS id, inc.incidentType AS type,
       inc.severity AS severity, inc.description AS description,
       v.name AS involved_vessel, reg.title AS violated_regulation
ORDER BY inc.date DESC

Question: 남해 기상 상태는 어때?
Cypher:
MATCH (w:WeatherCondition)-[:AFFECTS]->(sa:SeaArea {{name: '남해'}})
RETURN sa.name AS sea_area, w.windSpeed AS wind_speed_ms,
       w.waveHeight AS wave_height_m, w.visibility AS visibility_km,
       w.seaState AS sea_state, w.temperature AS temp_c, w.riskLevel AS risk

Question: 자율운항선박 관련 논문을 찾아줘
Cypher:
MATCH (doc:Document)
WHERE doc.title CONTAINS '자율운항'
OPTIONAL MATCH (doc)-[:ISSUED_BY]->(org:Organization)
RETURN doc.docId AS id, doc.title AS title, doc.authors AS authors,
       doc.issueDate AS date, doc.docType AS type, org.name AS publisher
ORDER BY doc.issueDate DESC

Question: 해양오염 관련 연구 논문 있어?
Cypher:
CALL db.index.fulltext.queryNodes('document_search', '해양오염') YIELD node AS doc, score
OPTIONAL MATCH (doc)-[:ISSUED_BY]->(org:Organization)
RETURN doc.docId AS id, doc.title AS title, doc.authors AS authors,
       doc.issueDate AS date, score
ORDER BY score DESC
LIMIT 10

Question: KRISO 연구 논문 몇 편이야?
Cypher:
MATCH (doc:Document)-[:ISSUED_BY]->(org:Organization {{orgId: 'ORG-KRISO'}})
RETURN count(doc) AS paper_count, collect(DISTINCT doc.docType) AS types

Question: KVLCC2 저항시험 결과를 보여줘
Cypher:
MATCH (exp:Experiment)-[:PRODUCED]->(ds:ExperimentalDataset)-[:CONTAINS]->(m:Measurement)
WHERE exp.title CONTAINS 'KVLCC2'
RETURN exp.title AS experiment, ds.title AS dataset,
       m.measurementType AS type, m.value AS value, m.unit AS unit,
       m.description AS description
ORDER BY m.testSpeed

Question: 해양공학수조에서 진행된 실험은?
Cypher:
MATCH (exp:Experiment)-[:CONDUCTED_AT]->(tf:TestFacility {{facilityId: 'TF-OEB'}})
OPTIONAL MATCH (exp)-[:PRODUCED]->(ds:ExperimentalDataset)
RETURN exp.experimentId AS id, exp.title AS title, exp.date AS date,
       exp.status AS status, ds.title AS dataset
ORDER BY exp.date DESC

Question: 빙해수조 시험 조건을 알려줘
Cypher:
MATCH (exp:Experiment)-[:CONDUCTED_AT]->(tf:TestFacility {{facilityId: 'TF-ICE'}})
MATCH (exp)-[:HAS_CONDITION]->(tc:TestCondition)
RETURN exp.title AS experiment, tc.description AS condition,
       tc.iceThickness AS ice_thickness_m, tc.iceStrength AS ice_strength_kPa,
       tc.testSpeed AS speed, tc.testSpeedUnit AS speed_unit

Question: 사용자 역할별 접근 권한을 보여줘
Cypher:
MATCH (r:Role)-[:CAN_ACCESS]->(dc:DataClass)
RETURN r.name AS role, r.level AS role_level,
       collect(dc.name) AS accessible_data, r.description AS description
ORDER BY r.level DESC

Now generate a Cypher statement for the following question.
Do not include any explanations or apologies.
Do not include any text except the generated Cypher statement.

Question: {question}
Cypher:
"""

CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question"],
    template=CYPHER_GENERATION_TEMPLATE,
)

# Custom QA prompt to force Korean answers
QA_TEMPLATE = """You are a Korean maritime data assistant. ALWAYS answer in Korean (한국어).
Based on the query results below, provide a clear and helpful answer.

Question: {question}
Query Results: {context}

If the results are empty, say you couldn't find matching data in Korean.
Answer in Korean:"""

QA_PROMPT = PromptTemplate(
    input_variables=["question", "context"],
    template=QA_TEMPLATE,
)

# =========================================================================
# 2. Graph & LLM Setup (Lazy Singleton)
# =========================================================================

# Module-level variables (initialized lazily)
_graph = None
_chain = None


def _get_chain():
    """Lazily initialize and return the GraphCypherQAChain."""
    global _graph, _chain
    if _chain is not None:
        return _chain

    print(f"[config] Neo4j: {_cfg.neo4j.uri}  database={_cfg.neo4j.database}")
    print("[config] LLM:   Ollama qwen2.5:7b (local)")
    print()

    _graph = Neo4jGraph(
        url=_cfg.neo4j.uri,
        username=_cfg.neo4j.user,
        password=_cfg.neo4j.password,
        database=_cfg.neo4j.database,
        enhanced_schema=False,
    )

    llm = ChatOllama(model="qwen2.5:7b", temperature=0)

    _chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=_graph,
        cypher_prompt=CYPHER_GENERATION_PROMPT,
        qa_prompt=QA_PROMPT,
        verbose=True,
        return_intermediate_steps=True,
        validate_cypher=True,
        allow_dangerous_requests=True,
        top_k=10,
    )
    return _chain


# =========================================================================
# 3. Helper: ask a single question
# =========================================================================


def ask(question: str) -> None:
    """Run a single question through the chain and print results."""
    print(f"\n{'=' * 70}")
    print(f"  Q: {question}")
    print(f"{'=' * 70}")
    try:
        chain = _get_chain()
        result = chain.invoke({"query": question})

        # Extract generated Cypher from intermediate steps
        steps = result.get("intermediate_steps", [])
        if steps:
            cypher_query = steps[0].get("query", "") if isinstance(steps[0], dict) else steps[0]
            print(f"\n  [Cypher]\n  {cypher_query}")
            if len(steps) > 1:
                context = steps[1].get("context", "") if isinstance(steps[1], dict) else steps[1]
                print(f"\n  [Context]\n  {context}")

        answer = result.get("result", "(no answer)")
        print(f"\n  [Answer]\n  {answer}")

    except Exception as exc:
        print(f"\n  [Error] {type(exc).__name__}: {exc}")

    print(f"\n{'-' * 70}")


# =========================================================================
# 4. Demo queries
# =========================================================================

DEMO_QUESTIONS = [
    "부산항 반경 50km 이내 선박을 알려줘",
    "HMM 알헤시라스는 어디로 항해 중이야?",
    "KRISO 시험설비 목록을 보여줘",
    "최근 해양사고 이력을 알려줘",
    "남해 기상 상태는 어때?",
    "KRISO 실험 데이터셋을 보여줘",
    "캐비테이션터널 시설 정보를 알려줘",
]


def run_demo() -> None:
    """Run all demo questions sequentially."""
    print("\n" + "=" * 70)
    print("  Maritime KG - LangChain GraphCypherQAChain Demo")
    print("  LLM: qwen2.5:7b (Ollama)  |  Graph: Neo4j")
    print("=" * 70)

    for question in DEMO_QUESTIONS:
        ask(question)

    print("\n[Demo complete]")


# =========================================================================
# 5. Main
# =========================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Single question mode
        question = " ".join(sys.argv[1:])
        ask(question)
    else:
        # Demo + interactive
        run_demo()
        print("\n[Interactive Mode] 질문을 입력하세요 (종료: q)")
        while True:
            try:
                q = input("\n질문> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if q.lower() in ("q", "quit", "exit", "종료"):
                break
            if q:
                ask(q)

    # Cleanup
    if _graph is not None:
        if hasattr(_graph, "close"):
            _graph.close()
        elif hasattr(_graph, "_driver"):
            _graph._driver.close()

    print("[Done]")
