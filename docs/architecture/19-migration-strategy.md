# 19. 데이터베이스 마이그레이션 전략

[← API 설계 표준](./18-api-standards.md) | [다음: NLP/NER 아키텍처 →](./20-nlp-ner.md)

## 개요

Neo4j Community Edition은 내장 마이그레이션 도구를 제공하지 않으므로, IMSP 플랫폼은 자체 마이그레이션 프레임워크를 구축하여 스키마 변경과 데이터 변환을 관리한다. 본 문서는 마이그레이션 파일 구조, 실행기(Runner), 온톨로지 연동, 롤백 절차, 환경별 전략, CI/CD 통합, 그리고 5개년에 걸친 온톨로지 진화 계획을 기술한다.

> 본 문서는 아키텍처 리뷰 C-6 (DB 마이그레이션 프레임워크 설계 — [16-architecture-review.md](./16-architecture-review.md) 참조)에서 식별된 CRITICAL 이슈에 대한 상세 설계이다.

---

## 19.1 설계 원칙

| 원칙 | 설명 |
|------|------|
| **Forward-Only** | Production 환경에서는 롤백 마이그레이션을 지원하지 않음. 백업 복원만 허용 |
| **멱등성** | 동일 마이그레이션을 중복 실행해도 부작용 없음 (MERGE 사용) |
| **원자성** | 각 마이그레이션 파일은 하나의 논리적 변경 단위. 실패 시 전체 롤백 |
| **추적성** | 적용된 마이그레이션을 Neo4j 메타데이터 노드로 추적 |
| **온톨로지 연동** | 온톨로지 변경이 자동으로 마이그레이션 스크립트를 트리거 |
| **Dry-Run** | 실행 전 예상 변경사항을 미리 확인할 수 있는 모의 실행 모드 |

---

## 19.2 마이그레이션 프레임워크

### 19.2.1 파일 구조

```
infra/migrations/
├── V001__initial_constraints.cypher          # 초기 제약조건 + 인덱스
├── V002__add_lineage_labels.cypher           # 리니지 레이블 + 관계
├── V003__add_rbac_metadata.cypher            # RBAC 메타데이터 노드
├── V004__ontology_maritime_v1.cypher         # 해사 온톨로지 v1 제약조건
├── V005__add_fulltext_index.cypher           # 전문 검색 인덱스
├── V006__etl_run_tracking.cypher             # ETL 실행 추적 노드
├── ...
├── V100__y1_q2_ontology_expansion.cypher     # Y1 Q2 온톨로지 확장
├── V101__y1_q2_temporal_properties.cypher    # 시간 속성 추가
├── ...
├── V200__y2_q1_agent_schema.cypher           # Y2 에이전트 스키마
├── ...
├── migrate.py                                # 마이그레이션 실행기
├── rollback_generator.py                     # 롤백 스크립트 생성기 (dev only)
└── README.md                                 # 사용 안내
```

### 19.2.2 명명 규칙

파일명: `V{NNN}__{description}.cypher`

| 규칙 | 설명 |
|------|------|
| 접두사 | `V` + 3자리 숫자 (001-999) |
| 구분자 | 이중 언더스코어 `__` |
| 설명 | snake_case, 영문 소문자 |
| 확장자 | `.cypher` |

### 19.2.3 버전 범위 배정

| 범위 | 용도 | 예시 |
|------|------|------|
| V001-V099 | 초기 설정 (제약조건, 인덱스, 기본 레이블) | `V001__initial_constraints.cypher` |
| V100-V199 | Y1 마이그레이션 | `V100__y1_q2_ontology_expansion.cypher` |
| V200-V299 | Y2 마이그레이션 | `V200__y2_q1_agent_schema.cypher` |
| V300-V399 | Y3 마이그레이션 | `V300__y3_clustering_prep.cypher` |
| V400-V499 | Y4 마이그레이션 | `V400__y4_multi_tenant.cypher` |
| V500-V599 | Y5 마이그레이션 | `V500__y5_stabilization.cypher` |
| V900-V999 | 핫픽스 (긴급 수정) | `V901__hotfix_index_missing.cypher` |

---

## 19.3 마이그레이션 실행기

### 19.3.1 메타데이터 노드

적용된 마이그레이션을 Neo4j 내부에 `:Migration` 노드로 추적한다.

```cypher
// 마이그레이션 메타데이터 노드 스키마
CREATE CONSTRAINT migration_version_unique IF NOT EXISTS
FOR (m:Migration) REQUIRE m.version IS UNIQUE;

// 마이그레이션 적용 시 생성되는 노드
CREATE (m:Migration {
  version: "V001",
  description: "initial_constraints",
  appliedAt: datetime(),
  checksum: "sha256:abc123...",
  executionTimeMs: 1250,
  appliedBy: "migrate.py",
  environment: "production"
})
```

### 19.3.2 실행기 구현 (migrate.py)

```python
# infra/migrations/migrate.py
"""
Neo4j 마이그레이션 실행기.

Usage:
    # 미적용 마이그레이션 모두 실행
    python migrate.py --uri bolt://localhost:7687 --user neo4j --password secret

    # Dry-run (실제 실행 없이 변경사항 미리 확인)
    python migrate.py --dry-run

    # 특정 버전까지만 실행
    python migrate.py --target V005

    # 상태 확인
    python migrate.py --status
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase


@dataclass
class MigrationFile:
    """마이그레이션 파일 메타데이터."""
    version: str           # "V001"
    description: str       # "initial_constraints"
    path: Path             # 파일 경로
    checksum: str          # SHA-256 해시
    statements: list[str]  # Cypher 문장 목록


class MigrationRunner:
    """Neo4j 마이그레이션 실행기."""

    def __init__(self, driver, database: str = "neo4j"):
        self._driver = driver
        self._database = database

    def get_applied_versions(self) -> set[str]:
        """이미 적용된 마이그레이션 버전 목록을 조회한다."""
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (m:Migration) RETURN m.version AS version"
            )
            return {record["version"] for record in result}

    def apply(self, migration: MigrationFile, dry_run: bool = False) -> None:
        """단일 마이그레이션을 적용한다."""
        if dry_run:
            print(f"[DRY-RUN] Would apply {migration.version}: {migration.description}")
            for stmt in migration.statements:
                print(f"  > {stmt[:80]}...")
            return

        start = datetime.now(timezone.utc)
        with self._driver.session(database=self._database) as session:
            with session.begin_transaction() as tx:
                for stmt in migration.statements:
                    tx.run(stmt)

                # 메타데이터 노드 생성
                elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                tx.run(
                    """
                    CREATE (m:Migration {
                        version: $version,
                        description: $description,
                        appliedAt: datetime(),
                        checksum: $checksum,
                        executionTimeMs: $elapsed,
                        appliedBy: 'migrate.py'
                    })
                    """,
                    version=migration.version,
                    description=migration.description,
                    checksum=migration.checksum,
                    elapsed=int(elapsed),
                )
                tx.commit()

    def run_pending(self, target: str | None = None, dry_run: bool = False) -> int:
        """미적용 마이그레이션을 순서대로 실행한다."""
        applied = self.get_applied_versions()
        pending = self._discover_migrations()

        count = 0
        for migration in pending:
            if migration.version in applied:
                continue
            if target and migration.version > target:
                break

            self._verify_checksum(migration, applied)
            self.apply(migration, dry_run=dry_run)
            count += 1

        return count

    def _discover_migrations(self) -> list[MigrationFile]:
        """migrations/ 디렉토리에서 .cypher 파일을 발견하고 정렬한다."""
        pattern = re.compile(r"^V(\d{3})__(.+)\.cypher$")
        migrations_dir = Path(__file__).parent
        files = []

        for path in sorted(migrations_dir.glob("V*.cypher")):
            match = pattern.match(path.name)
            if match:
                content = path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(content.encode()).hexdigest()
                statements = [s.strip() for s in content.split(";") if s.strip()]
                files.append(MigrationFile(
                    version=f"V{match.group(1)}",
                    description=match.group(2),
                    path=path,
                    checksum=f"sha256:{checksum}",
                    statements=statements,
                ))

        return files

    def _verify_checksum(self, migration: MigrationFile, applied: set[str]) -> None:
        """이전에 적용된 마이그레이션의 체크섬이 변경되지 않았는지 검증한다."""
        if migration.version not in applied:
            return
        # 이미 적용된 버전의 파일이 수정된 경우 경고
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (m:Migration {version: $version}) RETURN m.checksum AS checksum",
                version=migration.version,
            )
            record = result.single()
            if record and record["checksum"] != migration.checksum:
                raise ValueError(
                    f"Migration {migration.version} checksum mismatch! "
                    f"File was modified after being applied."
                )
```

### 19.3.3 CLI 사용법

```bash
# 전체 미적용 마이그레이션 실행
python infra/migrations/migrate.py \
    --uri bolt://localhost:7687 \
    --user neo4j \
    --password $NEO4J_PASSWORD

# Dry-run 모드 (변경 없이 확인만)
python infra/migrations/migrate.py --dry-run

# 특정 버전까지만 실행
python infra/migrations/migrate.py --target V005

# 현재 적용 상태 확인
python infra/migrations/migrate.py --status

# 특정 환경 지정
python infra/migrations/migrate.py --env staging
```

---

## 19.4 마이그레이션 파일 예시

### 19.4.1 V001 — 초기 제약조건

```cypher
// V001__initial_constraints.cypher
// 해사 KG 초기 제약조건 및 인덱스

// 유일성 제약조건
CREATE CONSTRAINT vessel_mmsi_unique IF NOT EXISTS
FOR (v:Vessel) REQUIRE v.mmsi IS UNIQUE;

CREATE CONSTRAINT port_unlocode_unique IF NOT EXISTS
FOR (p:Port) REQUIRE p.unlocode IS UNIQUE;

CREATE CONSTRAINT document_doi_unique IF NOT EXISTS
FOR (d:Document) REQUIRE d.doi IS UNIQUE;

// 존재성 제약조건 (Neo4j EE에서만 동작, CE에서는 무시)
// CREATE CONSTRAINT vessel_name_exists IF NOT EXISTS
// FOR (v:Vessel) REQUIRE v.name IS NOT NULL;

// 인덱스
CREATE INDEX vessel_name_idx IF NOT EXISTS FOR (v:Vessel) ON (v.name);
CREATE INDEX vessel_type_idx IF NOT EXISTS FOR (v:Vessel) ON (v.vesselType);
CREATE INDEX port_name_idx IF NOT EXISTS FOR (p:Port) ON (p.name);
CREATE INDEX document_title_idx IF NOT EXISTS FOR (d:Document) ON (d.title);

// 마이그레이션 메타데이터 제약조건
CREATE CONSTRAINT migration_version_unique IF NOT EXISTS
FOR (m:Migration) REQUIRE m.version IS UNIQUE;
```

### 19.4.2 V002 — 리니지 레이블

```cypher
// V002__add_lineage_labels.cypher
// W3C PROV-O 기반 리니지 레이블 및 관계

CREATE INDEX lineage_entity_idx IF NOT EXISTS
FOR (l:LineageNode) ON (l.entityId);

CREATE INDEX lineage_activity_idx IF NOT EXISTS
FOR (a:Activity) ON (a.activityId);

CREATE INDEX lineage_timestamp_idx IF NOT EXISTS
FOR (l:LineageNode) ON (l.createdAt);
```

### 19.4.3 V100 — Y1 Q2 온톨로지 확장

```cypher
// V100__y1_q2_ontology_expansion.cypher
// 해사 온톨로지 v1 확장: 연구시설 + 해양사고 엔티티 추가

// 새 레이블 제약조건
CREATE CONSTRAINT facility_id_unique IF NOT EXISTS
FOR (f:TestFacility) REQUIRE f.facilityId IS UNIQUE;

CREATE CONSTRAINT incident_id_unique IF NOT EXISTS
FOR (i:Incident) REQUIRE i.incidentId IS UNIQUE;

CREATE CONSTRAINT weather_station_id_unique IF NOT EXISTS
FOR (w:WeatherStation) REQUIRE w.stationId IS UNIQUE;

// 새 인덱스
CREATE INDEX facility_name_idx IF NOT EXISTS FOR (f:TestFacility) ON (f.name);
CREATE INDEX incident_date_idx IF NOT EXISTS FOR (i:Incident) ON (i.occurredAt);
CREATE INDEX weather_station_name_idx IF NOT EXISTS FOR (w:WeatherStation) ON (w.name);

// 기존 데이터에 새 속성 추가 (MERGE 패턴)
MATCH (v:Vessel) WHERE v.createdAt IS NULL
SET v.createdAt = datetime();

MATCH (p:Port) WHERE p.createdAt IS NULL
SET p.createdAt = datetime();
```

---

## 19.5 온톨로지 연동 마이그레이션

온톨로지 변경이 Neo4j 스키마에 자동으로 반영되도록 3-Layer Cascade를 구현한다.

### 19.5.1 3-Layer Cascade

```
Layer 1: Conceptual (OWL/TTL)
     │
     │  변경 감지 (diff)
     ▼
Layer 2: Mapping (Cypher DDL 생성)
     │
     │  자동 생성
     ▼
Layer 3: Physical (마이그레이션 파일)
```

### 19.5.2 변경 유형별 처리

| 변경 유형 | Conceptual (OWL) | Physical (Neo4j) | 데이터 마이그레이션 |
|----------|------------------|------------------|------------------|
| 엔티티 추가 | ObjectType 추가 | 레이블 생성 + 인덱스 | 불필요 |
| 엔티티 삭제 | ObjectType 제거 | 레이블 아카이브 (삭제하지 않음) | 아카이브 노드로 이동 |
| 속성 추가 | PropertyDefinition 추가 | 인덱스 추가 (선택) | 기본값 SET |
| 속성 삭제 | PropertyDefinition 제거 | 인덱스 제거 | 속성 REMOVE |
| 속성 이름 변경 | name 변경 | 기존 속성 → 새 속성 복사 | SET + REMOVE |
| 관계 추가 | LinkType 추가 | 관계 생성 | 불필요 |
| 관계 삭제 | LinkType 제거 | 관계 아카이브 | 아카이브 관계로 이동 |
| 타입 변경 | data_type 변경 | 제약조건 재설정 | 타입 변환 스크립트 |

### 19.5.3 자동 마이그레이션 생성기

```python
# infra/migrations/ontology_differ.py
"""온톨로지 변경사항을 감지하여 마이그레이션 스크립트를 자동 생성한다."""

class OntologyDiffer:
    """두 온톨로지 버전을 비교하여 차이점을 추출한다."""

    def diff(self, old_ontology, new_ontology) -> list[Change]:
        """변경사항 목록을 반환한다."""
        changes = []
        # 추가된 ObjectType
        for obj_type in new_ontology.object_types - old_ontology.object_types:
            changes.append(AddObjectType(obj_type))
        # 삭제된 ObjectType
        for obj_type in old_ontology.object_types - new_ontology.object_types:
            changes.append(RemoveObjectType(obj_type))
        # 속성 변경 비교
        # ...
        return changes

    def generate_cypher(self, changes: list[Change]) -> str:
        """변경사항을 Cypher 마이그레이션 스크립트로 변환한다."""
        statements = []
        for change in changes:
            statements.extend(change.to_cypher())
        return ";\n".join(statements)
```

---

## 19.6 롤백 절차

### 19.6.1 환경별 롤백 정책

| 환경 | 롤백 방식 | 자동화 수준 |
|------|----------|-----------|
| **Development** | 자동 롤백 스크립트 생성 + 실행 | 완전 자동 |
| **Staging** | 스냅샷 복원 + 수동 검증 | 반자동 |
| **Production** | 백업 복원 only (forward-only 정책) | 수동 |

### 19.6.2 Development 롤백

개발 환경에서는 각 마이그레이션에 대한 역방향 스크립트를 자동 생성한다.

```python
# infra/migrations/rollback_generator.py
"""마이그레이션 파일에서 롤백 스크립트를 자동 생성한다."""

class RollbackGenerator:
    """각 Cypher DDL 문에 대한 역방향 문을 생성한다."""

    ROLLBACK_MAP = {
        "CREATE CONSTRAINT": "DROP CONSTRAINT",
        "CREATE INDEX": "DROP INDEX",
        "SET": "REMOVE",
        # MERGE로 생성된 노드는 DELETE로 역전
    }

    def generate(self, migration_file: Path) -> str:
        """마이그레이션 파일을 분석하여 롤백 Cypher를 생성한다."""
        content = migration_file.read_text()
        rollback_statements = []
        for stmt in content.split(";"):
            reverse = self._reverse_statement(stmt.strip())
            if reverse:
                rollback_statements.append(reverse)
        # 역순으로 실행해야 의존성이 올바름
        return ";\n".join(reversed(rollback_statements))
```

### 19.6.3 Production 롤백 절차

Production에서는 마이그레이션 롤백을 하지 않고, 백업에서 복원한다.

```
1. 문제 감지 → 즉시 서비스 중단 (Maintenance Mode)
2. 최근 백업 확인:
   - neo4j-admin database dump neo4j → /backup/neo4j-YYYYMMDD-HHmmss.dump
   - 백업은 매일 03:00 자동 생성 (CronJob)
3. 백업 복원:
   - neo4j stop
   - neo4j-admin database load neo4j --from-path=/backup/neo4j-latest.dump --overwrite-destination
   - neo4j start
4. :Migration 노드 확인 → 적용된 마이그레이션 상태 검증
5. 서비스 재개
```

---

## 19.7 환경별 전략

### 19.7.1 Development

```
개발자 로컬 → 마이그레이션 수동 실행
     │
     ├── python infra/migrations/migrate.py --dry-run    (확인)
     ├── python infra/migrations/migrate.py              (적용)
     └── python infra/migrations/migrate.py --rollback V005  (롤백, dev only)
```

| 항목 | 설정 |
|------|------|
| 실행 방식 | 수동 (`python migrate.py`) |
| 롤백 | 자동 생성 롤백 스크립트 허용 |
| 백업 | 불필요 (Docker 볼륨 재생성 가능) |
| 데이터 | Docker Compose의 Neo4j 컨테이너 |

### 19.7.2 Staging

```
GitLab MR → CI Pipeline → 자동 마이그레이션
     │
     ├── Stage 1: Dry-run + 예상 변경 리뷰
     ├── Stage 2: 스냅샷 생성
     ├── Stage 3: 마이그레이션 적용
     └── Stage 4: 통합 테스트 실행
```

| 항목 | 설정 |
|------|------|
| 실행 방식 | GitLab CI 자동 (MR merge 시) |
| 롤백 | 스냅샷 복원 (자동 백업 후 적용) |
| 백업 | 마이그레이션 전 자동 스냅샷 |
| 데이터 | K8s Staging 클러스터의 Neo4j |

### 19.7.3 Production

```
Release Tag → CI Pipeline → 수동 승인 → 마이그레이션
     │
     ├── Stage 1: Dry-run 결과 리뷰
     ├── Stage 2: DBA/운영팀 수동 승인 (GitLab Manual Job)
     ├── Stage 3: 자동 백업 (neo4j-admin dump)
     ├── Stage 4: 마이그레이션 적용 (Maintenance Mode)
     └── Stage 5: Health Check + Smoke Test
```

| 항목 | 설정 |
|------|------|
| 실행 방식 | GitLab CI + 수동 승인 (Manual Job) |
| 롤백 | 백업 복원 only (forward-only) |
| 백업 | 적용 직전 자동 백업 + 일일 CronJob |
| 데이터 | K8s Production 클러스터의 Neo4j |
| 윈도우 | 점검 시간 (02:00-04:00 KST) |

---

## 19.8 CI/CD 통합

### 19.8.1 GitLab CI 파이프라인

```yaml
# .gitlab-ci.yml (마이그레이션 관련 부분)

stages:
  - validate
  - migrate-staging
  - migrate-production

# 마이그레이션 파일 검증 (모든 MR에서 실행)
validate-migrations:
  stage: validate
  script:
    - python infra/migrations/migrate.py --validate
    # 파일명 규칙 검증, Cypher 문법 검사, 체크섬 일관성
  rules:
    - changes:
      - infra/migrations/*.cypher

# Staging 자동 마이그레이션
migrate-staging:
  stage: migrate-staging
  script:
    - python infra/migrations/migrate.py --dry-run --env staging
    - python infra/migrations/migrate.py --env staging
    - python -m pytest tests/ -m integration -v
  environment:
    name: staging
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      changes:
        - infra/migrations/*.cypher

# Production 수동 승인 마이그레이션
migrate-production:
  stage: migrate-production
  script:
    - python infra/migrations/migrate.py --dry-run --env production
    - neo4j-admin database dump neo4j --to-path=/backup/pre-migration-$(date +%Y%m%d).dump
    - python infra/migrations/migrate.py --env production
    - python -m pytest tests/ -m smoke -v
  environment:
    name: production
  when: manual  # 수동 승인 필요
  rules:
    - if: $CI_COMMIT_TAG
```

### 19.8.2 마이그레이션 검증 규칙

CI에서 자동으로 검증하는 항목:

| 검증 | 설명 |
|------|------|
| 파일명 패턴 | `V{NNN}__{description}.cypher` 형식 준수 |
| 버전 순서 | 새 파일의 버전이 기존 최대 버전보다 크야 함 |
| 체크섬 불변 | 이미 적용된 마이그레이션 파일이 수정되지 않았는지 확인 |
| Cypher 문법 | 기본적인 구문 검사 (세미콜론 구분, 빈 문장 없음) |
| 금지 명령어 | Production 마이그레이션에서 `DROP CONSTRAINT`, `DELETE` 등 위험 명령어 경고 |
| 멱등성 | `IF NOT EXISTS`, `MERGE` 패턴 사용 권장 경고 |

---

## 19.9 데이터 마이그레이션 패턴

### 19.9.1 MERGE vs CREATE 선택 기준

| 상황 | 사용 패턴 | 이유 |
|------|----------|------|
| 제약조건/인덱스 | `CREATE ... IF NOT EXISTS` | 멱등성 보장 |
| 기존 노드에 속성 추가 | `MATCH ... SET` | 기존 데이터 보존 |
| 새 노드 생성 (기존 가능성 있음) | `MERGE` | 중복 방지 |
| 새 노드 생성 (확실히 신규) | `CREATE` | 성능 우수 |
| 대량 데이터 변환 | `UNWIND + MERGE` | 배치 처리 |

### 19.9.2 대량 데이터 마이그레이션

10만 건 이상의 데이터를 변환할 때는 배치 처리를 사용한다.

```cypher
// 대량 속성 변환 예시: vesselType 정규화
// APOC 없이 순수 Cypher로 배치 처리

// Step 1: 변환 대상 조회
MATCH (v:Vessel) WHERE v.vesselType IS NOT NULL
WITH v, v.vesselType AS oldType
LIMIT 10000
SET v.vesselTypeNormalized = CASE
  WHEN oldType IN ['tanker', 'Tanker', 'TANKER'] THEN 'Tanker'
  WHEN oldType IN ['container', 'Container'] THEN 'ContainerShip'
  WHEN oldType IN ['bulk', 'BulkCarrier'] THEN 'BulkCarrier'
  ELSE oldType
END
RETURN count(v) AS processed;

// Step 2: 남은 데이터가 있으면 반복 실행
// migrate.py에서 processed > 0인 동안 반복
```

### 19.9.3 APOC 활용 배치 (Neo4j APOC 플러그인 설치 시)

```cypher
// APOC periodic.iterate로 대량 처리
CALL apoc.periodic.iterate(
  "MATCH (v:Vessel) WHERE v.createdAt IS NULL RETURN v",
  "SET v.createdAt = datetime()",
  {batchSize: 5000, parallel: false}
) YIELD batches, total, errorMessages
RETURN batches, total, errorMessages;
```

### 19.9.4 스키마 변경 + 데이터 변환 동시 실행

하나의 마이그레이션 파일에서 스키마와 데이터를 함께 변경하는 패턴:

```cypher
// V101__y1_q2_temporal_properties.cypher

// Phase 1: 스키마 변경 (인덱스 추가)
CREATE INDEX vessel_valid_from_idx IF NOT EXISTS FOR (v:Vessel) ON (v.validFrom);
CREATE INDEX vessel_valid_to_idx IF NOT EXISTS FOR (v:Vessel) ON (v.validTo);

// Phase 2: 기존 데이터에 기본 시간 속성 추가
MATCH (v:Vessel) WHERE v.validFrom IS NULL
SET v.validFrom = datetime('2026-01-01T00:00:00Z');

MATCH (v:Vessel) WHERE v.validTo IS NULL
SET v.validTo = datetime('9999-12-31T23:59:59Z');

// Phase 3: 관계에도 시간 속성 추가
MATCH ()-[r:DOCKED_AT]->() WHERE r.validFrom IS NULL
SET r.validFrom = datetime('2026-01-01T00:00:00Z'),
    r.validTo = datetime('9999-12-31T23:59:59Z');
```

---

## 19.10 온톨로지 진화 계획 (40 -> 150 타입)

### 19.10.1 연차별 타입 확장 계획

| 연차 | 목표 타입 수 | 증분 | 주요 추가 엔티티 |
|------|------------|------|---------------|
| Y1 | ~40 | 초기 구축 | Vessel, Port, Route, Document, Incident, TestFacility, WeatherCondition, Researcher, Organization |
| Y2 | ~70 | +30 | Agent, Workflow, Model, Service, Dataset, Experiment, Sensor, MaritimeZone, Regulation |
| Y3 | ~100 | +30 | DigitalTwin, Simulation, Scenario, Alert, AISRecord, SatelliteImage, Chart(S-100) |
| Y4 | ~130 | +30 | Collaboration, Publication, Standard, Certificate, InspectionReport, RiskAssessment |
| Y5 | ~150 | +20 | 안정화 및 최적화, 커뮤니티 기여 타입 |

### 19.10.2 마이그레이션 예상 일정

```
Y1 Q1: V001-V010  초기 제약조건 + 인덱스 (~40 타입)
Y1 Q2: V100-V110  시간 속성 + 연구시설 확장
Y1 Q3: V111-V120  fulltext 인덱스 + ELT 메타데이터
Y1 Q4: V121-V130  온톨로지 v1 최종 정리

Y2 Q1: V200-V210  에이전트/워크플로우 스키마 (~70 타입)
Y2 Q2: V211-V220  RAG 문서 스키마 + 임베딩 인덱스
Y2 Q3: V221-V230  서비스 Pool + 자산 관리 스키마
Y2 Q4: V231-V240  멀티테넌시 속성 추가

Y3 Q1: V300-V310  S-100 전자해도 스키마 (~100 타입)
Y3 Q2: V311-V320  3D 모델 + 시뮬레이션 스키마
...
```

### 19.10.3 대규모 온톨로지 변경 시 절차

대규모 변경 (10개 이상 타입 추가/수정)에는 특별 절차를 적용한다.

```
1. OWL/TTL 변경 → ontology_differ.py 실행 → 차이점 확인
2. 마이그레이션 스크립트 자동 생성 → 수동 리뷰
3. Development에서 테스트 → 통합 테스트 확인
4. Staging에서 적용 → 성능 벤치마크 (쿼리 지연 측정)
5. Production 적용 (점검 시간 내, 수동 승인)
6. :Migration 노드 확인 + 온톨로지 버전 메타데이터 갱신
```

---

## 19.11 코드 매핑

| 파일/디렉토리 | 역할 | 상태 |
|--------------|------|------|
| `infra/migrations/` | 마이그레이션 파일 디렉토리 | **Y1 Q1 신규** |
| `infra/migrations/migrate.py` | 마이그레이션 실행기 | **Y1 Q1 신규** |
| `infra/migrations/rollback_generator.py` | 롤백 스크립트 생성기 | **Y1 Q1 신규** |
| `infra/migrations/ontology_differ.py` | 온톨로지 변경 감지기 | **Y1 Q2 신규** |
| `core/kg/config.py` | Neo4j 연결 설정 (마이그레이션 시 활용) | 현재 구현 |
| `core/kg/ontology/core.py` | 온톨로지 프레임워크 (Conceptual 레이어) | 현재 구현 |
| `core/kg/ontology_bridge.py` | 온톨로지 → KG 변환 (Mapping 레이어) | 현재 구현 |
| `infra/docker-compose.yml` | 로컬 Neo4j 컨테이너 설정 | 현재 구현 |
| `.gitlab-ci.yml` | CI/CD 파이프라인 (마이그레이션 스테이지 추가) | **Y1 Q1 추가** |

---

## 19.12 구현 로드맵

| 시점 | 작업 | 상세 |
|------|------|------|
| Y1 Q1 | 마이그레이션 프레임워크 구축 | `migrate.py` 실행기 + V001-V006 초기 마이그레이션 파일 |
| Y1 Q1 | CI/CD 통합 | GitLab CI에 마이그레이션 검증 + 자동 적용 스테이지 추가 |
| Y1 Q2 | 온톨로지 연동 | `ontology_differ.py` 구현. OWL 변경 → Cypher 자동 생성 |
| Y1 Q2 | 시간 속성 마이그레이션 | V100-V110: `validFrom`/`validTo` 전체 적용 |
| Y1 Q3 | 백업 자동화 | CronJob으로 일일 `neo4j-admin dump` + Ceph 저장 |
| Y2 Q1 | 대규모 마이그레이션 도구 | APOC 활용 배치 처리 + 진행률 모니터링 |
| Y3 | 스키마 버전 관리 UI | 관리 대시보드에서 마이그레이션 이력/상태 시각화 |
| Y4 | EE 전환 시 마이그레이션 | Neo4j EE 전환 시 CE → EE 데이터 마이그레이션 절차 |

---

*관련 문서: [아키텍처 리뷰 C-6](./16-architecture-review.md), [데이터 아키텍처](./04-data-architecture.md), [배포 아키텍처](./05-deployment-architecture.md), [연차별 로드맵](./13-roadmap.md)*
