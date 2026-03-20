"""n10s graph configuration and namespace management.

Manages Neo4j Neosemantics (n10s) plugin configuration:
- Graph config initialization (n10s.graphconfig.init)
- Namespace prefix registration
- Mapping rules for Neo4j label/property naming

Usage::

    from kg.n10s.config import N10sConfig
    from kg.config import get_driver

    driver = get_driver()
    config = N10sConfig(driver)
    config.init_graph_config()
    config.register_namespaces()
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 네임스페이스 및 그래프 설정 상수
# ---------------------------------------------------------------------------

BASE_URI = "https://kg.kriso.re.kr/maritime#"
S100_URI = "https://registry.iho.int/s100#"

# n10s handleVocabUris 옵션: "SHORTEN", "IGNORE", "MAP", "KEEP"
DEFAULT_GRAPH_CONFIG: dict[str, Any] = {
    "handleVocabUris": "MAP",       # MAP allows custom prefix mapping
    "handleMultival": "ARRAY",      # 다중값 속성을 배열로 저장
    "handleRDFTypes": "LABELS",     # RDF types → Neo4j labels
    "keepLangTag": False,
    "keepCustomDataTypes": False,
    "applyNeo4jNaming": True,       # PascalCase/camelCase 변환
}

# (prefix, uri) 튜플 목록 — 해사 도메인 표준 네임스페이스
NAMESPACE_PREFIXES: list[tuple[str, str]] = [
    ("maritime", BASE_URI),
    ("s100", S100_URI),
    ("owl", "http://www.w3.org/2002/07/owl#"),
    ("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
    ("xsd", "http://www.w3.org/2001/XMLSchema#"),
    ("dc", "http://purl.org/dc/elements/1.1/"),
    ("dcterms", "http://purl.org/dc/terms/"),
    ("geo", "http://www.opengis.net/ont/geosparql#"),
]


class N10sConfig:
    """n10s 플러그인 그래프 설정 및 네임스페이스 관리.

    Neo4j Neosemantics 플러그인의 그래프 설정 초기화, 네임스페이스 등록,
    OWL URI → Neo4j 레이블/속성 매핑 규칙 관리를 담당합니다.

    Args:
        driver: Neo4j Python 드라이버 인스턴스.
        database: 대상 데이터베이스명. None이면 드라이버 기본값 사용.
    """

    def __init__(self, driver: Any, database: str | None = None) -> None:
        self._driver = driver
        self._database = database

    # ------------------------------------------------------------------
    # 그래프 설정 초기화
    # ------------------------------------------------------------------

    def init_graph_config(self, config: dict[str, Any] | None = None) -> bool:
        """n10s 그래프 설정을 초기화합니다.

        ``CALL n10s.graphconfig.init($config)`` 프로시저를 실행합니다.
        이미 설정이 존재하면 Neo4j가 오류를 반환하므로, 재설정 시
        :meth:`drop_graph_config` 를 먼저 호출하세요.

        Args:
            config: n10s graphconfig 파라미터 딕셔너리.
                None이면 :data:`DEFAULT_GRAPH_CONFIG` 를 사용합니다.

        Returns:
            성공 시 True, 실패 시 False.
        """
        effective_config = config if config is not None else DEFAULT_GRAPH_CONFIG
        cypher = "CALL n10s.graphconfig.init($config)"
        try:
            self._run_procedure(cypher, {"config": effective_config})
            logger.info("n10s 그래프 설정 초기화 완료: %s", effective_config)
            return True
        except Exception as exc:
            logger.error("n10s 그래프 설정 초기화 실패: %s", exc)
            return False

    def drop_graph_config(self) -> bool:
        """n10s 그래프 설정을 삭제합니다.

        ``CALL n10s.graphconfig.drop`` 프로시저를 실행합니다.
        재설정이 필요할 때 :meth:`init_graph_config` 전에 호출하세요.

        Returns:
            성공 시 True, 실패 시 False.
        """
        cypher = "CALL n10s.graphconfig.drop"
        try:
            self._run_procedure(cypher)
            logger.info("n10s 그래프 설정 삭제 완료")
            return True
        except Exception as exc:
            logger.error("n10s 그래프 설정 삭제 실패: %s", exc)
            return False

    def get_graph_config(self) -> dict[str, Any] | None:
        """현재 n10s 그래프 설정을 조회합니다.

        ``CALL n10s.graphconfig.show()`` 프로시저를 실행합니다.

        Returns:
            설정 파라미터 딕셔너리. 설정이 없거나 오류 시 None.
        """
        cypher = (
            "CALL n10s.graphconfig.show() YIELD param, value RETURN param, value"
        )
        try:
            result = self._run_procedure(cypher)
            return {row["param"]: row["value"] for row in result}
        except Exception as exc:
            logger.error("n10s 그래프 설정 조회 실패: %s", exc)
            return None

    # ------------------------------------------------------------------
    # 네임스페이스 관리
    # ------------------------------------------------------------------

    def register_namespaces(self) -> int:
        """모든 표준 해사 네임스페이스 프리픽스를 등록합니다.

        :data:`NAMESPACE_PREFIXES` 목록의 모든 항목을 등록합니다.

        Returns:
            성공적으로 등록된 네임스페이스 수.
        """
        registered = 0
        for prefix, uri in NAMESPACE_PREFIXES:
            if self.add_namespace(prefix, uri):
                registered += 1
        logger.info("네임스페이스 %d/%d 개 등록 완료", registered, len(NAMESPACE_PREFIXES))
        return registered

    def add_namespace(self, prefix: str, uri: str) -> bool:
        """단일 네임스페이스 프리픽스를 등록합니다.

        ``CALL n10s.nsprefixes.add(prefix, uri)`` 프로시저를 실행합니다.

        Args:
            prefix: 네임스페이스 단축 프리픽스 (예: "maritime").
            uri: 전체 네임스페이스 URI (예: "https://kg.kriso.re.kr/maritime#").

        Returns:
            성공 시 True, 실패 시 False.
        """
        cypher = "CALL n10s.nsprefixes.add($prefix, $uri)"
        try:
            self._run_procedure(cypher, {"prefix": prefix, "uri": uri})
            logger.debug("네임스페이스 등록: %s → %s", prefix, uri)
            return True
        except Exception as exc:
            logger.error("네임스페이스 등록 실패 (%s=%s): %s", prefix, uri, exc)
            return False

    def list_namespaces(self) -> list[tuple[str, str]]:
        """등록된 모든 네임스페이스 프리픽스를 조회합니다.

        ``CALL n10s.nsprefixes.list()`` 프로시저를 실행합니다.

        Returns:
            (prefix, namespace_uri) 튜플 목록.
        """
        cypher = (
            "CALL n10s.nsprefixes.list() YIELD prefix, namespace "
            "RETURN prefix, namespace"
        )
        try:
            result = self._run_procedure(cypher)
            return [(row["prefix"], row["namespace"]) for row in result]
        except Exception as exc:
            logger.error("네임스페이스 목록 조회 실패: %s", exc)
            return []

    # ------------------------------------------------------------------
    # 매핑 규칙
    # ------------------------------------------------------------------

    def add_mapping(self, graph_elem_name: str, schema_elem_name: str) -> bool:
        """OWL URI → Neo4j 레이블/속성명 매핑 규칙을 추가합니다.

        ``CALL n10s.mapping.add(schema_elem_name, graph_elem_name)`` 프로시저를
        실행합니다.

        Args:
            graph_elem_name: Neo4j 레이블 또는 속성명 (예: "Vessel").
            schema_elem_name: OWL 클래스/속성 URI
                (예: "https://kg.kriso.re.kr/maritime#Vessel").

        Returns:
            성공 시 True, 실패 시 False.
        """
        cypher = "CALL n10s.mapping.add($schemaElem, $graphElem)"
        try:
            self._run_procedure(
                cypher,
                {"schemaElem": schema_elem_name, "graphElem": graph_elem_name},
            )
            logger.debug("매핑 추가: %s → %s", schema_elem_name, graph_elem_name)
            return True
        except Exception as exc:
            logger.error(
                "매핑 추가 실패 (%s → %s): %s", schema_elem_name, graph_elem_name, exc
            )
            return False

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _run_procedure(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> Any:
        """Cypher 프로시저를 실행하고 결과를 반환합니다.

        Args:
            cypher: 실행할 Cypher 쿼리 문자열.
            params: 쿼리 파라미터 딕셔너리. None이면 빈 딕셔너리 사용.

        Returns:
            쿼리 결과 레코드 목록.

        Raises:
            Exception: Neo4j 드라이버 또는 프로시저 실행 오류.
        """
        params = params or {}
        with self._driver.session(database=self._database) as session:
            result = session.run(cypher, params)
            return list(result)
