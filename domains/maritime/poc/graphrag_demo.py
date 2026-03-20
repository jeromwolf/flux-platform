"""Integrated Agentic GraphRAG demo for the Maritime KG.

Demonstrates the full pipeline:
1. Initialize embedder + LLM
2. Generate embeddings for Document nodes (if missing)
3. Create and test each of 5 retrievers
4. Run Agentic (ToolsRetriever) with GraphRAG

Usage::

    # Full demo (requires Ollama + Neo4j)
    PYTHONPATH=. python -m poc.graphrag_demo

    # Skip embedding generation (assumes embeddings exist)
    PYTHONPATH=. python -m poc.graphrag_demo --skip-embeddings

    # Agentic mode only
    PYTHONPATH=. python -m poc.graphrag_demo --agentic-only
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Any

logger = logging.getLogger(__name__)

# -- Demo query sets (Korean) --

VECTOR_QUERIES = [
    "선박 저항 성능 최적화 연구",
    "빙해 환경에서의 선박 안전",
    "자율운항선박 기술 동향",
]

VECTOR_CYPHER_QUERIES = [
    "빙해수조 관련 논문과 발행 기관",
    "KRISO 연구 논문과 관련 시험시설",
]

TEXT2CYPHER_QUERIES = [
    "KRISO 시험시설 목록을 보여줘",
    "부산항 근처 선박 알려줘",
    "최근 해양사고 이력을 알려줘",
]

HYBRID_QUERIES = [
    "KVLCC2 저항시험 관련 연구",
    "캐비테이션터널 실험 논문",
]

AGENTIC_QUERIES = [
    "KRISO 시험시설 목록 보여줘",                  # -> text2cypher
    "선박 저항 관련 최신 연구 동향은?",              # -> vector_search
    "빙해수조에서 수행된 논문과 발행 기관 알려줘",    # -> vector_cypher
    "KVLCC2 저항시험 관련 논문 있어?",              # -> hybrid_search
]


def _print_header(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def _print_query(query: str) -> None:
    """Print a query label."""
    print(f"\n  Q: {query}")


def _print_results(results: Any, max_items: int = 3) -> None:
    """Print retriever results in a formatted manner."""
    if not hasattr(results, "items") or not results.items:
        print("  -> 결과 없음")
        return

    items = results.items[:max_items]
    print(f"  -> {len(results.items)}건 (상위 {len(items)}건 표시)")
    for i, item in enumerate(items, 1):
        content = str(item.content)[:200] if hasattr(item, "content") else str(item)[:200]
        print(f"     [{i}] {content}")
        if hasattr(item, "metadata") and item.metadata:
            score = item.metadata.get("score", "N/A")
            print(f"         score: {score}")


def _check_prerequisites() -> bool:
    """Check if Neo4j and Ollama are available."""
    errors = []

    # Check Neo4j
    try:
        from kg.config import get_driver
        driver = get_driver()
        with driver.session() as session:
            session.run("RETURN 1").single()
        print("  [OK] Neo4j 연결 성공")
    except Exception as exc:
        errors.append(f"Neo4j 연결 실패: {exc}")
        print(f"  [FAIL] Neo4j 연결 실패: {exc}")

    # Check Ollama
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            print(f"  [OK] Ollama 연결 성공 (모델: {len(models)}개)")
        else:
            errors.append("Ollama 응답 오류")
            print("  [FAIL] Ollama 응답 오류")
    except Exception as exc:
        errors.append(f"Ollama 연결 실패: {exc}")
        print(f"  [FAIL] Ollama 연결 실패: {exc}")

    if errors:
        print("\n  === 필수 서비스가 실행되지 않고 있습니다 ===")
        print("  시작 방법:")
        print("    docker compose up -d          # Neo4j")
        print("    ollama serve                   # Ollama")
        print("    ollama pull nomic-embed-text   # 임베딩 모델")
        print("    ollama pull qwen2.5:7b         # LLM 모델")
        return False
    return True


def run_demo(
    skip_embeddings: bool = False,
    agentic_only: bool = False,
) -> None:
    """Run the full Maritime GraphRAG demo."""
    from neo4j_graphrag.llm import OllamaLLM

    from kg.config import get_config, get_driver
    from kg.embeddings import OllamaEmbedder, generate_embeddings_batch
    from poc.graphrag_retrievers import (
        create_hybrid_retriever,
        create_text2cypher_retriever,
        create_tools_retriever,
        create_vector_cypher_retriever,
        create_vector_retriever,
    )

    _print_header("Maritime GraphRAG Demo - 해사 지식그래프 RAG 시연")
    print("  이 데모는 5가지 검색 방식을 순차적으로 시연합니다.\n")

    # Prerequisites check
    _print_header("Step 0: 환경 확인")
    if not _check_prerequisites():
        sys.exit(1)

    cfg = get_config()
    driver = get_driver()
    db = cfg.neo4j.database

    # Initialize embedder and LLM
    embedder_wrapper = OllamaEmbedder()
    embedder = embedder_wrapper.get_neo4j_graphrag_embedder()
    llm = OllamaLLM(model_name="qwen2.5:7b")

    # Step 1: Generate embeddings
    if not skip_embeddings and not agentic_only:
        _print_header("Step 1: 문서 임베딩 생성 (nomic-embed-text, 768차원)")
        start = time.time()
        result = generate_embeddings_batch(
            driver=driver, database=db, embedder=embedder_wrapper
        )
        elapsed = time.time() - start
        print(f"  처리: {result.total_processed}건")
        print(f"  성공: {result.total_success}건")
        print(f"  건너뜀: {result.total_skipped}건")
        print(f"  실패: {result.total_failed}건")
        print(f"  소요 시간: {elapsed:.1f}초")
        if result.errors:
            for doc_id, err in result.errors[:3]:
                print(f"  [오류] {doc_id}: {err}")
    else:
        print("\n  임베딩 생성 건너뜀 (--skip-embeddings)")

    if not agentic_only:
        # Step 2: VectorRetriever
        _print_header("Step 2: VectorRetriever - 의미 유사도 검색")
        print("  Document 노드의 textEmbedding 벡터 인덱스를 활용합니다.")
        vector_ret = create_vector_retriever(driver, embedder, neo4j_database=db)
        for query in VECTOR_QUERIES:
            _print_query(query)
            try:
                results = vector_ret.search(query_text=query, top_k=3)
                _print_results(results)
            except Exception as exc:
                print(f"  -> 오류: {type(exc).__name__}: {exc}")

        # Step 3: VectorCypherRetriever
        _print_header("Step 3: VectorCypherRetriever - 벡터 + 그래프 순회")
        print("  유사 문서를 찾은 후 ISSUED_BY, HAS_FACILITY 관계를 확장합니다.")
        vc_ret = create_vector_cypher_retriever(driver, embedder, neo4j_database=db)
        for query in VECTOR_CYPHER_QUERIES:
            _print_query(query)
            try:
                results = vc_ret.search(query_text=query, top_k=3)
                _print_results(results)
            except Exception as exc:
                print(f"  -> 오류: {type(exc).__name__}: {exc}")

        # Step 4: Text2CypherRetriever
        _print_header("Step 4: Text2CypherRetriever - 한국어 → Cypher")
        print("  LLM(qwen2.5:7b)이 자연어를 Cypher 쿼리로 변환합니다.")
        t2c_ret = create_text2cypher_retriever(driver, llm, neo4j_database=db)
        for query in TEXT2CYPHER_QUERIES:
            _print_query(query)
            try:
                results = t2c_ret.search(query_text=query)
                _print_results(results)
            except Exception as exc:
                print(f"  -> 오류: {type(exc).__name__}: {exc}")

        # Step 5: HybridRetriever
        _print_header("Step 5: HybridRetriever - 풀텍스트 + 벡터 결합")
        print("  document_search 풀텍스트 인덱스와 text_embedding 벡터를 결합합니다.")
        hybrid_ret = create_hybrid_retriever(driver, embedder, neo4j_database=db)
        for query in HYBRID_QUERIES:
            _print_query(query)
            try:
                results = hybrid_ret.search(query_text=query, top_k=3)
                _print_results(results)
            except Exception as exc:
                print(f"  -> 오류: {type(exc).__name__}: {exc}")

    # Step 6: Agentic GraphRAG
    _print_header("Step 6: Agentic GraphRAG - ToolsRetriever + GraphRAG")
    print("  LLM이 질문 유형에 따라 최적의 검색 전략을 자동 선택합니다.")
    print("  등록된 도구: vector_search, vector_cypher, text2cypher, hybrid_search\n")

    try:
        from neo4j_graphrag.generation import GraphRAG

        tools_retriever = create_tools_retriever(
            driver, embedder, llm, neo4j_database=db
        )
        rag = GraphRAG(retriever=tools_retriever, llm=llm)

        for query in AGENTIC_QUERIES:
            _print_query(query)
            try:
                start = time.time()
                response = rag.search(query_text=query)
                elapsed = time.time() - start
                answer = response.answer if hasattr(response, "answer") else str(response)
                print(f"  A: {answer[:500]}")
                print(f"     ({elapsed:.1f}초)")
            except Exception as exc:
                print(f"  -> 오류: {type(exc).__name__}: {exc}")

    except ImportError:
        print("  [WARN] neo4j_graphrag.generation 모듈을 가져올 수 없습니다.")
        print("         pip install neo4j-graphrag[ollama] 을 실행하세요.")

    # Summary
    _print_header("Demo 완료")
    print("  5가지 GraphRAG 검색 방식을 시연했습니다:")
    print("  1. VectorRetriever        - 의미 유사도 검색")
    print("  2. VectorCypherRetriever  - 벡터 + 그래프 순회")
    print("  3. Text2CypherRetriever   - 자연어 → Cypher")
    print("  4. HybridRetriever        - 풀텍스트 + 벡터 결합")
    print("  5. ToolsRetriever         - Agentic (LLM 자동 선택)")
    print("\n  비교: poc/langchain_qa.py (기존 LangChain 방식)도 참조하세요.")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Maritime GraphRAG Demo - 해사 지식그래프 RAG 시연"
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="임베딩 생성 단계를 건너뜁니다 (이미 생성된 경우)",
    )
    parser.add_argument(
        "--agentic-only",
        action="store_true",
        help="Agentic (ToolsRetriever) 모드만 실행합니다",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 로그 출력",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run_demo(
        skip_embeddings=args.skip_embeddings,
        agentic_only=args.agentic_only,
    )


if __name__ == "__main__":
    main()
