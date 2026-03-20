"""n10s OWL/Turtle ontology import into Neo4j.

Imports OWL ontology definitions into Neo4j as a Property Graph
using the Neosemantics (n10s) plugin procedures.

Usage::

    from kg.n10s.importer import N10sImporter
    from kg.config import get_driver

    driver = get_driver()
    importer = N10sImporter(driver)
    result = importer.import_ontology()  # Imports default maritime.ttl
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kg.n10s.config import N10sConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 기본 경로 및 포맷 상수
# ---------------------------------------------------------------------------

# 해사 온톨로지 Turtle 파일 기본 경로
DEFAULT_TTL_PATH = Path(__file__).parent.parent / "ontology" / "maritime.ttl"
DEFAULT_FORMAT = "Turtle"  # n10s format 파라미터


# ---------------------------------------------------------------------------
# 결과 데이터클래스
# ---------------------------------------------------------------------------


@dataclass
class ImportResult:
    """n10s 임포트 작업 결과.

    Attributes:
        success: 임포트 성공 여부.
        triples_loaded: 적재된 RDF 트리플 수.
        namespaces: 처리된 네임스페이스 수.
        extra_info: 추가 상태 메시지.
        errors: 오류 메시지 목록.
    """

    success: bool
    triples_loaded: int = 0
    namespaces: int = 0
    extra_info: str = ""
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# N10sImporter
# ---------------------------------------------------------------------------


class N10sImporter:
    """n10s 플러그인을 통한 OWL/Turtle 온톨로지 Neo4j 임포트.

    Neosemantics (n10s) 플러그인 프로시저를 사용하여 OWL/Turtle 형식의
    온톨로지를 Neo4j Property Graph로 임포트합니다.

    Args:
        driver: Neo4j Python 드라이버 인스턴스.
        database: 대상 데이터베이스명. None이면 드라이버 기본값 사용.
    """

    def __init__(self, driver: Any, database: str | None = None) -> None:
        self._driver = driver
        self._database = database
        # 내부적으로 N10sConfig 인스턴스를 생성하여 설정 관리
        self._config = N10sConfig(driver, database)

    # ------------------------------------------------------------------
    # 공개 임포트 메서드
    # ------------------------------------------------------------------

    def import_ontology(
        self,
        source: str | Path | None = None,
        format: str = DEFAULT_FORMAT,
        *,
        setup: bool = True,
    ) -> ImportResult:
        """메인 임포트 메서드.

        온톨로지 소스를 Neo4j에 임포트합니다. ``setup=True`` 이면
        임포트 전에 그래프 설정 초기화 및 네임스페이스 등록을 수행합니다.

        Args:
            source: 임포트 소스.
                - None → :data:`DEFAULT_TTL_PATH` 파일 내용 사용
                - Path 또는 로컬 파일 경로 문자열 → 파일 내용 읽기
                - "http://..." 로 시작하는 문자열 → URL 임포트
            format: n10s RDF 포맷 파라미터. 기본값은 "Turtle".
            setup: True이면 임포트 전에 그래프 설정 및 네임스페이스를
                초기화합니다.

        Returns:
            :class:`ImportResult` 인스턴스.
        """
        # 설정 초기화 (요청된 경우)
        if setup:
            self._config.init_graph_config()
            self._config.register_namespaces()

        # URL 임포트 분기
        if isinstance(source, str) and source.startswith("http"):
            return self.import_from_url(source, format)

        # 로컬 파일 읽기
        file_path = Path(source) if source is not None else DEFAULT_TTL_PATH
        try:
            rdf_content = file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            msg = f"온톨로지 파일을 찾을 수 없습니다: {file_path}"
            logger.error(msg)
            return ImportResult(success=False, errors=[msg])
        except OSError as exc:
            msg = f"온톨로지 파일 읽기 실패 ({file_path}): {exc}"
            logger.error(msg)
            return ImportResult(success=False, errors=[msg])

        return self.import_from_inline(rdf_content, format)

    def import_from_url(self, url: str, format: str = DEFAULT_FORMAT) -> ImportResult:
        """URL에서 온톨로지를 가져와 임포트합니다.

        ``CALL n10s.onto.import.fetch(url, format)`` 프로시저를 실행합니다.

        Args:
            url: RDF/OWL 온톨로지 URL.
            format: n10s RDF 포맷 파라미터.

        Returns:
            :class:`ImportResult` 인스턴스.
        """
        cypher = "CALL n10s.onto.import.fetch($url, $format)"
        try:
            records = self._run_procedure(cypher, {"url": url, "format": format})
            return self._parse_import_records(records)
        except Exception as exc:
            msg = f"URL 임포트 실패 ({url}): {exc}"
            logger.error(msg)
            return ImportResult(success=False, errors=[msg])

    def import_from_inline(
        self, rdf_content: str, format: str = DEFAULT_FORMAT
    ) -> ImportResult:
        """인라인 RDF/Turtle 콘텐츠를 임포트합니다.

        ``CALL n10s.rdf.import.inline(rdf_content, format)`` 프로시저를
        실행합니다. 로컬 파일 임포트의 핵심 메서드입니다.

        Args:
            rdf_content: Turtle/RDF 형식의 온톨로지 문자열.
            format: n10s RDF 포맷 파라미터.

        Returns:
            :class:`ImportResult` 인스턴스.
        """
        cypher = "CALL n10s.rdf.import.inline($rdfContent, $format)"
        try:
            records = self._run_procedure(
                cypher, {"rdfContent": rdf_content, "format": format}
            )
            result = self._parse_import_records(records)
            logger.info(
                "인라인 임포트 완료: %d 트리플 적재", result.triples_loaded
            )
            return result
        except Exception as exc:
            msg = f"인라인 임포트 실패: {exc}"
            logger.error(msg)
            return ImportResult(success=False, errors=[msg])

    def preview_import(
        self,
        source: str | Path | None = None,
        format: str = DEFAULT_FORMAT,
    ) -> ImportResult:
        """실제 임포트 없이 임포트 결과를 미리 봅니다.

        ``CALL n10s.onto.preview.inline(content, format)`` 프로시저를
        실행합니다. 데이터베이스에 변경사항을 저장하지 않습니다.

        Args:
            source: 미리 볼 소스 (None이면 기본 maritime.ttl 사용).
            format: n10s RDF 포맷 파라미터.

        Returns:
            :class:`ImportResult` 인스턴스 (triples_loaded는 미리보기 수).
        """
        file_path = Path(source) if source is not None else DEFAULT_TTL_PATH
        try:
            rdf_content = file_path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError) as exc:
            msg = f"미리보기용 파일 읽기 실패 ({file_path}): {exc}"
            logger.error(msg)
            return ImportResult(success=False, errors=[msg])

        cypher = "CALL n10s.onto.preview.inline($rdfContent, $format)"
        try:
            records = self._run_procedure(
                cypher, {"rdfContent": rdf_content, "format": format}
            )
            return self._parse_import_records(records)
        except Exception as exc:
            msg = f"임포트 미리보기 실패: {exc}"
            logger.error(msg)
            return ImportResult(success=False, errors=[msg])

    def get_import_status(self) -> dict[str, Any]:
        """임포트된 트리플 수 및 메타데이터를 조회합니다.

        Returns:
            Resource 노드 수, 관계 수 등 임포트 상태 딕셔너리.
        """
        cypher = (
            "MATCH (r:Resource) "
            "RETURN count(r) AS resource_count, "
            "size([(r)-[rel]->() | rel]) AS relationship_count"
        )
        try:
            records = self._run_procedure(cypher)
            if records:
                row = records[0]
                return {
                    "resource_count": row.get("resource_count", 0),
                    "relationship_count": row.get("relationship_count", 0),
                }
            return {"resource_count": 0, "relationship_count": 0}
        except Exception as exc:
            logger.error("임포트 상태 조회 실패: %s", exc)
            return {"error": str(exc)}

    def delete_imported_data(self) -> bool:
        """임포트된 Resource 노드 및 관계를 모두 삭제합니다.

        Warning:
            이 작업은 되돌릴 수 없습니다. :meth:`Resource` 레이블을 가진
            모든 노드와 연결된 관계가 삭제됩니다.

        Returns:
            성공 시 True, 실패 시 False.
        """
        cypher = "MATCH (n:Resource) DETACH DELETE n"
        try:
            self._run_procedure(cypher)
            logger.info("임포트된 Resource 데이터 삭제 완료")
            return True
        except Exception as exc:
            logger.error("임포트 데이터 삭제 실패: %s", exc)
            return False

    # ------------------------------------------------------------------
    # 완전한 파이프라인
    # ------------------------------------------------------------------

    def setup_and_import(
        self, source: str | Path | None = None
    ) -> ImportResult:
        """완전한 n10s 설정 및 임포트 파이프라인을 실행합니다.

        다음 순서로 작업을 수행합니다:

        1. 기존 그래프 설정 삭제 (오류 무시)
        2. Resource(uri) 유니크 제약조건 생성
        3. 그래프 설정 초기화
        4. 네임스페이스 등록
        5. 온톨로지 임포트

        Args:
            source: 임포트 소스 (None이면 기본 maritime.ttl 사용).

        Returns:
            :class:`ImportResult` 인스턴스.
        """
        # 1단계: 기존 설정 정리 (오류 무시)
        self._config.drop_graph_config()
        logger.info("[1/5] 기존 n10s 그래프 설정 정리")

        # 2단계: Resource(uri) 유니크 제약조건 생성
        constraint_cypher = (
            "CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS "
            "FOR (r:Resource) ON (r.uri)"
        )
        try:
            self._run_procedure(constraint_cypher)
            logger.info("[2/5] Resource(uri) 유니크 제약조건 생성 완료")
        except Exception as exc:
            logger.warning("제약조건 생성 경고 (이미 존재할 수 있음): %s", exc)

        # 3단계: 그래프 설정 초기화
        if not self._config.init_graph_config():
            return ImportResult(
                success=False, errors=["n10s 그래프 설정 초기화 실패"]
            )
        logger.info("[3/5] n10s 그래프 설정 초기화 완료")

        # 4단계: 네임스페이스 등록
        registered = self._config.register_namespaces()
        logger.info("[4/5] 네임스페이스 %d개 등록 완료", registered)

        # 5단계: 온톨로지 임포트 (setup=False — 이미 위에서 완료)
        result = self.import_ontology(source=source, setup=False)
        logger.info(
            "[5/5] 임포트 %s: %d 트리플",
            "성공" if result.success else "실패",
            result.triples_loaded,
        )
        return result

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _run_procedure(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[Any]:
        """Cypher 프로시저를 실행하고 결과 레코드 목록을 반환합니다.

        Args:
            cypher: 실행할 Cypher 쿼리 문자열.
            params: 쿼리 파라미터 딕셔너리.

        Returns:
            쿼리 결과 레코드 목록.

        Raises:
            Exception: Neo4j 드라이버 또는 프로시저 실행 오류.
        """
        params = params or {}
        with self._driver.session(database=self._database) as session:
            result = session.run(cypher, params)
            return list(result)

    @staticmethod
    def _parse_import_records(records: list[Any]) -> ImportResult:
        """n10s 임포트 프로시저 결과 레코드를 파싱합니다.

        n10s 프로시저는 일반적으로 ``triplesLoaded``, ``namespaces``,
        ``extraInfo`` 필드를 반환합니다.

        Args:
            records: ``session.run()`` 결과 레코드 목록.

        Returns:
            파싱된 :class:`ImportResult` 인스턴스.
        """
        if not records:
            return ImportResult(success=True, extra_info="결과 레코드 없음")

        row = records[0]
        # n10s 프로시저 반환 필드 이름 처리 (버전별 차이 대응)
        triples = int(row.get("triplesLoaded", row.get("triples_loaded", 0)))
        namespaces = int(row.get("namespaces", 0))
        extra_info = str(row.get("extraInfo", row.get("extra_info", "")))

        return ImportResult(
            success=True,
            triples_loaded=triples,
            namespaces=namespaces,
            extra_info=extra_info,
        )
