# 15. 플랫폼 운영 기능 아키텍처

[← 디렉토리 구조](./14-directory-structure.md) | [다음: 아키텍처 리뷰 →](./16-architecture-review.md)

## 개요

IMSP 플랫폼은 KG 엔진 외에도 통합 리니지, 자산 관리, 서비스 Pool, 협업, 커스텀 노드 SDK 등 운영 계층 기능을 필요로 한다. 본 문서는 RFP 요구사항 점검 및 Suredata Lab 사전착수회의(2026-03-18) 결과 식별된 Gap을 보완하는 운영 기능 아키텍처를 기술한다.

> **구현 상태:** 본 섹션의 모든 기능은 설계 단계이며, Y2-Y3에 걸쳐 구현 예정이다.

---

## 15.1 통합 리니지 설계 (4종)

RFP는 데이터/모델/노드/워크플로우 4가지 대상에 대한 리니지를 요구한다. 기존 Section 4.7의 데이터 리니지(W3C PROV-O)를 기반으로 4종 통합 리니지를 설계한다.

```
통합 리니지 (W3C PROV-O 확장)
|
+-- 데이터 리니지 (Section 4.7 기존 설계)
|   RawAsset -> ProcessedAsset -> TransformActivity -> ProvenanceChain
|   추적 대상: 원천 데이터 수집 → 변환 → KG 적재 → 파생 분석
|
+-- 모델 리니지 (신규)
|   ModelVersion -> TrainingRun -> Dataset -> DeploymentRecord
|   추적 대상: 학습 데이터 → 하이퍼파라미터 → 모델 버전 → 배포 이력 → 성능 메트릭
|   저장: Neo4j (:ModelVersion)-[:TRAINED_ON]->(:Dataset)
|         (:ModelVersion)-[:DEPLOYED_AS]->(:DeploymentRecord)
|
+-- 노드 리니지 (신규)
|   NodeExecution -> InputArtifact -> OutputArtifact -> ErrorLog
|   추적 대상: 노드 실행 시각 → 입력/출력 데이터 → 실행 시간 → 오류 이력
|   저장: Neo4j (:NodeExecution)-[:CONSUMED]->(:Artifact)
|         (:NodeExecution)-[:PRODUCED]->(:Artifact)
|
+-- 워크플로우 리니지 (신규)
    WorkflowRun -> NodeExecution[] -> ServiceVersion -> ChangeLog
    추적 대상: 워크플로우 실행 DAG → 노드별 실행 결과 → 버전 변경 이력
    저장: Neo4j (:WorkflowRun)-[:EXECUTED]->(:NodeExecution)
          (:WorkflowRun)-[:VERSION_OF]->(:WorkflowDefinition)
    연동: Argo Workflow 실행 이벤트 → Webhook → 리니지 자동 기록
```

**통합 리니지 Neo4j 스키마 (추가 엔티티):**

| 엔티티 | 속성 | 관계 |
|--------|------|------|
| ModelVersion | modelId, version, framework, metrics, createdAt | TRAINED_ON, DEPLOYED_AS |
| TrainingRun | runId, hyperparams, duration, gpuHours | USED_DATASET, PRODUCED_MODEL |
| DeploymentRecord | deployId, endpoint, replicas, status | SERVES_MODEL |
| NodeExecution | execId, nodeType, startTime, endTime, status | CONSUMED, PRODUCED, PART_OF |
| WorkflowRun | runId, workflowId, trigger, status, duration | EXECUTED, VERSION_OF |
| WorkflowDefinition | workflowId, version, author, updatedAt | CONTAINS_NODE, DERIVED_FROM |

---

## 15.2 자산 관리 체계 (Asset Management)

플랫폼에 등록되는 모든 유무형 자산을 통합 관리하는 체계이다. 자산은 KG 노드로 메타데이터가 관리되며, W3C PROV-O 리니지로 이력이 추적된다.

```
자산 라이프사이클
|
+-- 등록 (Register)
|   자산 메타데이터 생성, KG 노드 생성, 버전 v1.0 할당
|
+-- 개발 (Develop)
|   버전 관리 (Git 기반), 변경 이력 추적
|
+-- 검증 (Validate)
|   단위 테스트, 통합 테스트, 품질 게이트 통과
|
+-- 배포 (Deploy)
|   컨테이너 빌드, K8s Deployment/Job 생성
|
+-- 운영 (Operate)
|   모니터링, 성능 메트릭 수집, 사용 통계
|
+-- 폐기 (Deprecate)
    사용 중지 알림, 의존성 분석, 아카이브
```

**자산 유형별 메타데이터:**

| 자산 유형 | 저장소 | 메타데이터 (Neo4j) | 원본 (Object Storage) |
|----------|--------|-------------------|---------------------|
| 데이터 자산 | Object Storage | 스키마, 크기, 포맷, 소유자, 접근 등급 | raw/{source}/{date}/ |
| 모델 자산 | Model Registry | 프레임워크, 버전, 메트릭, 입출력 스펙 | models/{name}/{version}/ |
| 노드 자산 | GitLab | 노드 타입, 입출력 스펙, 의존성, 컨테이너 이미지 | 소스코드 (Git) |
| 워크플로우 자산 | PostgreSQL + KG | DAG 구조, 노드 목록, 파라미터 스키마 | JSON 정의 |
| 서비스 자산 | K8s + KG | 엔드포인트, SLA, 접근 정책, 사용 통계 | Deployment YAML |

**API 엔드포인트 (계획):**

```
POST   /api/v1/assets                    자산 등록
GET    /api/v1/assets?type=&owner=       자산 목록 조회 (필터/검색)
GET    /api/v1/assets/{id}               자산 상세 조회
PUT    /api/v1/assets/{id}               자산 메타데이터 수정
DELETE /api/v1/assets/{id}               자산 폐기 (soft delete)
GET    /api/v1/assets/{id}/versions      자산 버전 이력
GET    /api/v1/assets/{id}/lineage       자산 리니지 그래프
POST   /api/v1/assets/{id}/deploy        자산 배포 (서비스화)
GET    /api/v1/assets/search?q=          자연어 기반 자산 검색 (KG + 벡터)
```

---

## 15.3 서비스 Pool 및 공개 관리

워크플로우를 개발한 후 "서비스"로 등록하고 외부에 공개하는 라이프사이클을 관리한다.

```
워크플로우 → 서비스 전환 라이프사이클

[워크플로우 저작]
     |
     v 기능 테스트 통과
[응용(App) 등록]  <- 1회성 실행, K8s Job
     |
     v 안정성 검증 (3회 이상 성공 실행)
[서비스(Service) 승격]  <- 지속 운용, K8s Deployment
     |
     v 관리자 심사/승인
[서비스 Pool 등록]  <- 카탈로그에 노출
     |
     v 접근 정책 설정
[서비스 공개]  <- 서비스 포털에서 이용 가능
     |
     v 사용 통계 수집
[서비스 운영/모니터링]
```

**워크플로우 서비스 GW:**

API Gateway(내부 개발자용)와 별도로, 등록된 서비스를 외부 사용자가 호출하는 전용 Gateway를 운영한다.

| Gateway | 대상 | 경로 Prefix | 인증 | Rate Limit |
|---------|------|-----------|------|-----------|
| Internal API GW | 개발자/연구자 | `/api/v1/` | Keycloak OIDC (JWT) | 1000 req/min |
| Service GW | 서비스 사용자 | `/service/v1/` | Keycloak OIDC 또는 API Key | 100 req/min (테넌트별) |

**서비스 Pool 관리 API (계획):**

```
POST   /api/v1/services                  서비스 등록 (워크플로우 → 서비스 전환)
GET    /api/v1/services                   서비스 카탈로그 조회
GET    /api/v1/services/{id}              서비스 상세 정보
PUT    /api/v1/services/{id}/publish      서비스 공개 (심사 후)
PUT    /api/v1/services/{id}/unpublish    서비스 비공개 전환
GET    /api/v1/services/{id}/stats        서비스 사용 통계
GET    /service/v1/{serviceId}/invoke     서비스 호출 (Service GW 경유)
```

---

## 15.4 협업 및 작업 공유 관리

멀티 연구자가 프로젝트 단위로 워크플로우/데이터/모델을 공유하고 협업하는 기능이다.

**프로젝트 작업 공간 (Project Workspace):**

```
프로젝트 (Project)
  |
  +-- 멤버 관리 (RBAC: Owner / Editor / Viewer)
  +-- 공유 자산 (데이터, 모델, 워크플로우)
  +-- 공유 KG 네임스페이스 (Neo4j 라벨 프리픽스 격리)
  +-- 활동 로그 (변경 이력, 댓글)
  +-- 환경 설정 (GPU 할당, 저장소 쿼터)
```

| 기능 | 설명 | K8s 구현 |
|------|------|---------|
| 프로젝트 생성 | 격리된 작업 공간 생성 | Namespace 또는 라벨 기반 격리 |
| 멤버 초대 | Keycloak 그룹 + RBAC 매핑 | Keycloak Group → K8s RoleBinding |
| 자산 공유 | 프로젝트 내 자산 공유 레벨 설정 | KG 접근 정책 (SecureCypherBuilder) |
| 워크플로우 공유 | 워크플로우 복제/포크/공동 편집 | PostgreSQL workflow_share 테이블 |
| 실시간 알림 | 변경/실행/오류 알림 | WebSocket + Redis Pub/Sub |

---

## 15.5 커스텀 노드 개발 SDK 및 Antigravity 연계

외부 개발자(연구자)가 자체 워크플로우 노드를 개발하고 플랫폼에 등록할 수 있는 도구 체인이다.

**노드 개발 프로시저 (Antigravity 연계):**

```
1. VS Code + Antigravity Extension 설치
     |
     v
2. 새 자산 프로젝트 생성 (IMSP 플랫폼 연계용 Extension)
   ├── 자산 개발 가이드.md (자동 생성)
   ├── 자산 개발 계획.md (AI Prompting으로 작성)
   ├── Dockerfile.default (자동 생성)
   └── src/ (소스 코드)
     |
     v AI Prompting (Antigravity)
3. 소스 코드 작성 (Python 또는 Node.js)
   ├── node_spec.yaml   # 노드 입출력 스펙 정의
   ├── main.py          # 노드 실행 로직
   ├── requirements.txt # 의존성
   └── test_node.py     # 단위 테스트
     |
     v
4. 자산 빌드 (Docker 이미지)
   docker build -t registry.kriso.re.kr/nodes/{node-name}:{version} .
     |
     v
5. 자산 등록 (IMSP 플랫폼 업로드)
   imsp-cli asset register --type node --spec node_spec.yaml --image ...
     |
     v
6. 노드 팔레트에 노출 (VueFlow 캔버스에서 사용 가능)
```

**노드 스펙 YAML 예시:**

```yaml
name: ais-anomaly-detector
version: 1.0.0
category: Transform
maritime_specific: true
description: AIS 데이터에서 항로 이탈 및 속도 이상을 탐지
inputs:
  - name: ais_data
    type: json_array
    description: AIS 메시지 배열
  - name: threshold
    type: float
    default: 2.0
    description: 이상 탐지 임계값 (표준편차 배수)
outputs:
  - name: anomalies
    type: json_array
    description: 탐지된 이상 항목
  - name: statistics
    type: json_object
    description: 탐지 통계
container:
  image: registry.kriso.re.kr/nodes/ais-anomaly-detector:1.0.0
  resources:
    memory: 512Mi
    cpu: "0.5"
```

---

## 15.6 민간 연구개발 지원 아키텍처

### 개요

IMSP는 5개년간 총 **29건**의 민간 연구개발 과제를 지원한다 (Y1: 3건, Y2: 5건, Y3: 5건, Y4: 8건, Y5: 8건). 이를 위한 셀프서비스 플랫폼 아키텍처를 설계한다.

### 지원 프로세스 (6단계)

```
신청 → 심사 → 온보딩 → 개발지원 → 검증 → 종료
 │       │       │         │        │      │
 ▼       ▼       ▼         ▼        ▼      ▼
서비스   심사    Keycloak   전용     성과   테넌트
포털    위원회   테넌트    워크스   리포트   정리
접수    API     생성      페이스   생성    아카이브
```

### 테넌트 온보딩 자동화

1. **신청 접수**: 서비스 포털 폼 → PostgreSQL 저장
2. **승인 후 자동 프로비저닝**:
   - Keycloak Organization 생성 (`civilian-{project_id}`)
   - Neo4j 테넌트 메타데이터 노드 생성
   - Ceph RGW 버킷 생성 (`imsp-civilian-{project_id}/`)
   - 리소스 쿼터 설정

### 리소스 쿼터 (과제당)

| 리소스 | 기본 할당 | 최대 |
|--------|----------|------|
| KG 노드 수 | 100,000 | 1,000,000 |
| Object Storage | 50 GB | 500 GB |
| GPU 시간/월 | 10시간 | 100시간 |
| API 호출/일 | 10,000 | 100,000 |
| 워크플로우 동시 실행 | 2 | 10 |

### Y5 셀프서비스 포털

- 민간 이용자 자체 가입 + 약관 동의
- 워크플로우 템플릿 마켓플레이스
- 사용량 대시보드 + 비용 추적
- API Key 자체 발급/관리

> **구현 상태:** 전체 기능 설계 단계. Y2에서 기초 테넌트 격리 구현, Y3에서 온보딩 자동화, Y5에서 셀프서비스 포털 완성 예정.

---

*관련 문서: [데이터 아키텍처](./04-data-architecture.md), [보안 아키텍처](./06-security-architecture.md), [아키텍처 리뷰](./16-architecture-review.md)*
