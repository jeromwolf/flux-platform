# 6. 보안 아키텍처

[← 배포 아키텍처](./05-deployment-architecture.md) | [다음: 데이터 흐름도 →](./07-data-flow.md)

## 개요

IMSP 플랫폼의 보안 아키텍처는 **Defense in Depth(심층 방어)** 원칙에 따라 인증/인가, 네트워크, 데이터 접근, 감사 로깅의 다중 계층으로 설계된다. 이용자 유형(데이터 제공자, 내부 연구자, 외부 이용자)에 따라 3개 보안 계층을 적용하며, Keycloak SSO를 중심으로 K8s RBAC와 Application RBAC의 이중 접근 제어를 구현한다. 본 문서는 보안 모델, RBAC 시스템, 네트워크 보안, 감사 로깅, JWT에서 Keycloak으로의 전환 계획, 그리고 Cypher Injection 방어 전략을 기술한다.

---

## 6.1 인증/인가 3계층 모델

IMSP는 이용자 유형에 따라 3개 보안 계층을 적용한다. 외부 이용자일수록 더 강한 격리와 제한을 받는다.

```
+----------------------------------------------------------------------+
|                     보안 아키텍처 3계층 모델                           |
|                                                                      |
|  Layer 2: 2차 이용자 (External Researcher / Public)                  |
|  +------------------------------------------------------------------+ |
|  | Authentication : Keycloak OIDC (소셜 로그인 허용)                  | |
|  | Authorization  : Read-only, 공개 데이터 + 서비스 포털 접근만        | |
|  | Isolation      : 공유 환경, Rate Limit 100 req/min                | |
|  | Data Access    : PUBLIC, INTERNAL 등급만                          | |
|  +------------------------------------------------------------------+ |
|                                                                      |
|  Layer 1: KRISO 내부 연구자 (Internal Researcher / Developer)        |
|  +------------------------------------------------------------------+ |
|  | Authentication : Keycloak OIDC + MFA (TOTP 또는 WebAuthn)        | |
|  | Authorization  : Read/Write/Execute (팀/프로젝트 RBAC)             | |
|  | Isolation      : 팀별 K8s Namespace, 전용 KG 접근 범위            | |
|  | Data Access    : PUBLIC ~ CONFIDENTIAL 등급                       | |
|  +------------------------------------------------------------------+ |
|                                                                      |
|  Layer 0: 데이터 제공자 (Suredata Lab / 외부 기관)                   |
|  +------------------------------------------------------------------+ |
|  | Authentication : API Key + IP Whitelist (CIDR 화이트리스트)        | |
|  | Authorization  : Write-only, Ingest API (/api/v1/ingest/*) 한정   | |
|  | Isolation      : 기관별 Object Storage 버킷 + KG 네임스페이스 분리 | |
|  | Data Access    : 쓰기 전용, 자기 기관 데이터만                     | |
|  +------------------------------------------------------------------+ |
+----------------------------------------------------------------------+
```

### 코드 매핑

| 보안 구성요소 | 코드베이스 위치 | 비고 |
|-------------|---------------|------|
| JWT 인증 미들웨어 | `core/kg/api/middleware/auth.py` | `verify_jwt()`, `verify_api_key()` |
| RBAC 정책 엔진 | `core/kg/rbac/policy.py` | `RBACPolicy.check_access()`, `augment_cypher_with_access()` |
| SecureCypherBuilder | `core/kg/rbac/secure_builder.py` | RBAC WHERE 절 자동 주입 |
| Keycloak Realm 설정 | `infra/keycloak/` (예정) | Realm export JSON |

---

## 6.2 이중 RBAC 시스템

Keycloak SSO가 통합 인증 허브 역할을 하며, K8s RBAC와 Application RBAC가 병렬로 동작한다.

```
                    +---------------------------+
                    |     Keycloak SSO          |
                    |  (OIDC 토큰 발급 허브)     |
                    +------+----------+---------+
                           |          |
               +-----------+          +-----------+
               |                                  |
  +--------------------+            +-----------------------------+
  |   K8s RBAC          |            |   Application RBAC          |
  |   (인프라 접근 제어) |            |   (데이터 접근 제어)         |
  |                     |            |                             |
  | ServiceAccount      |            |  5 Roles:                   |
  | ClusterRole         |            |  - Admin (전체 접근)         |
  | RoleBinding         |            |  - InternalResearcher (R/W) |
  |                     |            |  - ExternalResearcher (R)   |
  | Pod / Service /     |            |  - Developer (API + Execute)|
  | Secret 접근 제어     |            |  - Public (공개 데이터만)   |
  |                     |            |                             |
  |                     |            |  5 Data Classifications:    |
  |                     |            |  1. PUBLIC                  |
  |                     |            |  2. INTERNAL                |
  |                     |            |  3. CONFIDENTIAL            |
  |                     |            |  4. RESTRICTED              |
  |                     |            |  5. TOP_SECRET              |
  +--------------------+            +-----------------------------+
```

### RBAC 강제 3개 지점 (Defense in Depth)

```
HTTP Request
    |
    v [1] RBACPolicy.check_access()
    |      binary allow/deny
    |      Neo4j 그래프 순회: User->Role->DataClass
    |      실패 시 403 즉시 반환
    |
    v [2] augment_cypher_with_access()
    |      생성된 Cypher에 WHERE 절 주입
    |      WHERE dc.level <= user.maxAccessLevel
    |      데이터 등급 필터링 자동화
    |
    v [3] SecureCypherBuilder (쿼리 생성 단계)
    |      EXISTS 서브쿼리 구조 주입
    |      MATCH (u:User)-[:HAS_ROLE]->(r:Role)-[:CAN_ACCESS]->(dc:DataClass)
    |      SQL Injection 유사 패턴 사전 차단
    |
    v Neo4j 실행 (3중 필터링된 결과 반환)
```

**코드 흐름 상세:**

| 지점 | 함수 | 파일 | 동작 |
|------|------|------|------|
| [1] 접근 제어 | `RBACPolicy.check_access()` | `core/kg/rbac/policy.py` | User-Role-DataClass 그래프 순회, 이진 판단 |
| [2] 쿼리 보강 | `augment_cypher_with_access()` | `core/kg/rbac/policy.py` | 기존 Cypher에 `AND` 절 주입 (`_inject_where_clause`) |
| [3] 보안 빌더 | `SecureCypherBuilder.build()` | `core/kg/rbac/secure_builder.py` | EXISTS 서브쿼리로 RBAC 필터 구조적 주입 |

---

## 6.3 네트워크 보안

| 보안 계층 | 기술 | 설명 |
|----------|------|------|
| NetworkPolicy | K8s NetworkPolicy | Neo4j는 maritime-api, etl-pipeline만 접근 허용 (Bolt 7687) |
| Service Mesh | Istio | mTLS 자동 적용, 트래픽 관리, Circuit Breaking, 서비스 간 인증 (2차년도 도입) |
| Pod Security | PodSecurityStandards `restricted` | root 실행 금지, 특권 컨테이너 금지, capability 제한 |
| TLS | cert-manager | Let's Encrypt (외부) 또는 KRISO 내부 CA (내부망) |
| Secret 관리 | External Secrets Operator | HashiCorp Vault 연동, GitOps 시크릿 관리 |
| 이미지 보안 | Trivy (CI 파이프라인) | CVE 자동 검출, CRITICAL 취약점 시 빌드 실패 |
| GitOps Secret | SOPS + age | 암호화된 시크릿을 Git에 안전하게 커밋 |
| Ingress | Kong Gateway / Nginx | TLS Termination, Rate Limiting, WAF 규칙 |

**NetworkPolicy 예시 (Neo4j 격리):**

```
Neo4j Pod (7687)
  |
  +-- ALLOW: maritime-api (label: app=maritime-api)
  +-- ALLOW: etl-pipeline (label: app=etl-pipeline)
  \-- DENY: 기타 모든 Pod 및 외부 접근
```

### Istio mTLS 상세 (2차년도 도입)

2차년도 K8s 전환과 함께 Istio Service Mesh를 도입하여 서비스 간 통신을 암호화하고 접근을 제어한다.

**PeerAuthentication (STRICT mode):**

```yaml
# Namespace 전체에 STRICT mTLS 적용
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: imsp
spec:
  mtls:
    mode: STRICT
```

`STRICT` 모드에서는 Namespace `imsp` 내의 모든 Pod 간 통신이 mTLS로 강제된다. Sidecar가 주입되지 않은 외부 클라이언트는 통신이 차단되므로, Ingress Gateway를 통해서만 외부 접근이 가능하다.

**AuthorizationPolicy (서비스 간 접근 제어):**

```yaml
# maritime-api만 Neo4j에 접근 허용
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: neo4j-access
  namespace: imsp
spec:
  selector:
    matchLabels:
      app: neo4j
  action: ALLOW
  rules:
    - from:
        - source:
            principals:
              - "cluster.local/ns/imsp/sa/maritime-api"
              - "cluster.local/ns/imsp/sa/etl-pipeline"
      to:
        - operation:
            ports: ["7687"]   # Bolt protocol만 허용
```

**VirtualService (트래픽 분배):**

| 배포 전략 | 적용 대상 | 설명 |
|----------|----------|------|
| Canary | `maritime-api` | 신규 버전 10% -> 50% -> 100% 점진 전환. 오류율 > 1% 시 자동 롤백 |
| Blue/Green | `maritime-frontend` | 구버전/신버전 독립 배포, DNS 전환으로 무중단 전환 |
| 고정 라우팅 | `neo4j`, `ollama-server` | StatefulSet/GPU 워크로드는 트래픽 분배 미적용 |

```yaml
# Canary 배포 예시: API 서버 신규 버전 10% 트래픽 할당
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: maritime-api
  namespace: imsp
spec:
  hosts:
    - maritime-api
  http:
    - route:
        - destination:
            host: maritime-api
            subset: stable
          weight: 90
        - destination:
            host: maritime-api
            subset: canary
          weight: 10
```

---

## 6.4 감사 로깅 (Dual Audit)

| 감사 계층 | 대상 이벤트 | 저장소 | 보존 기간 |
|----------|-----------|--------|---------|
| K8s Audit Log | API 서버 요청, Pod 생성/삭제, RBAC 변경 | 파일 (EFK 연동 예정) | 90일 |
| Application Lineage | KG 데이터 변경, Cypher 쿼리 실행, 데이터 출처 | Neo4j (LineageNode) | 영구 |
| Access Log | HTTP 요청/응답 (사용자, IP, 경로, 상태코드) | 구조화 JSON (stdout) | 30일 |
| ETL Audit | 수집 건수, 오류율, 데이터 품질 점수 | PostgreSQL (etl_audit 테이블) | 180일 |

4차년도 이후 EFK(Elasticsearch + Fluentd + Kibana) 스택으로 중앙 집중 로그 관리 전환 예정.

---

## 6.5 JWT -> Keycloak 전환 계획

### 현재 상태 (1차년도)

현재 IMSP API 서버는 **JWT (HS256) + API Key** 이중 인증을 사용한다. 코드베이스 `core/kg/api/middleware/auth.py`에 구현되어 있다.

| 인증 방식 | 헤더 | 검증 방식 | 대상 |
|----------|------|----------|------|
| API Key | `X-API-Key` | 환경변수 `APP_API_KEY`와 비교 | 외부 시스템 (Suredata Lab, ETL) |
| JWT | `Authorization: Bearer <token>` | `JWT_SECRET_KEY` (HS256) 서명 검증 | 내부 사용자 (연구자, 개발자) |

**현재 구현의 한계:**
- 대칭키(HS256) 사용으로 토큰 발급과 검증이 동일한 비밀키에 의존
- 사용자 관리, 역할 관리가 Application 내부에 하드코딩
- MFA, 소셜 로그인, 세션 관리 등 고급 기능 부재
- API Key 로테이션 시 전체 서비스 재배포 필요

### 전환 계획

| 시기 | 마일스톤 | 상세 |
|------|---------|------|
| Y1 Q1-Q2 | JWT 기반 운영 | 현재 상태 유지, Keycloak 평가 및 PoC |
| Y1 Q3 | Keycloak 도입 | `imsp` Realm 생성, OIDC 토큰 발급 시작 |
| Y1 Q4 | 병렬 운영 | JWT + Keycloak 동시 지원 (Dual Auth Middleware) |
| Y2 Q1 | JWT 완전 교체 | JWT HS256 폐기, Keycloak RS256 단독 운영 |
| Y2 Q2 | MFA 적용 | TOTP/WebAuthn MFA 강제 (Layer 1 이상) |

### Keycloak Realm 설정

```
Realm: imsp
|
+-- Clients
|   +-- imsp-api           # FastAPI 백엔드 (confidential client)
|   |   +-- Access Type: confidential
|   |   +-- Valid Redirect URIs: https://api.imsp.kriso.re.kr/*
|   |   +-- Service Account: enabled (machine-to-machine)
|   |   \-- Client Scope: roles, profile, email
|   |
|   +-- imsp-ui           # Vue 3 프론트엔드 (public client)
|   |   +-- Access Type: public
|   |   +-- Valid Redirect URIs: https://imsp.kriso.re.kr/*
|   |   +-- Web Origins: https://imsp.kriso.re.kr
|   |   \-- PKCE: enabled (S256)
|   |
|   \-- argo-workflow      # Argo Workflow (confidential client)
|       +-- Access Type: confidential
|       +-- Service Account: enabled
|       \-- Client Scope: roles
|
+-- Roles
|   +-- Admin              # 전체 접근 (access_level: 5)
|   +-- InternalResearcher  # R/W, CONFIDENTIAL까지 (access_level: 3)
|   +-- ExternalResearcher  # Read-only, INTERNAL까지 (access_level: 2)
|   +-- Developer           # API + Execute (access_level: 3)
|   \-- Public              # 공개 데이터만 (access_level: 1)
|
+-- Identity Providers
|   +-- KRISO LDAP          # 내부 직원 SSO
|   \-- Google OIDC          # 외부 연구자 소셜 로그인 (Layer 2)
|
+-- Authentication Flows
|   +-- Browser Flow         # MFA 포함 (Layer 1)
|   \-- Direct Grant Flow    # API Key 대체 (machine-to-machine)
|
\-- Token Settings
    +-- Access Token Lifespan: 15분
    +-- Refresh Token Lifespan: 8시간
    +-- SSO Session Max: 24시간
    \-- Signing Algorithm: RS256 (비대칭키)
```

### 롤백 계획 (Keycloak 장애 시)

Keycloak 장애 발생 시 JWT fallback 모드로 자동 전환하여 서비스 중단을 방지한다.

```
HTTP Request
    |
    v Auth Middleware (Dual Mode)
    |
    +-- Keycloak Token 검증 시도
    |   |
    |   +-- 성공 -> 정상 처리
    |   |
    |   +-- Keycloak 연결 실패 (timeout 3s)
    |       |
    |       v JWT Fallback Mode 활성화
    |       |   +-- 기존 JWT_SECRET_KEY로 HS256 검증
    |       |   +-- AlertManager 알림 발송 (Keycloak 장애)
    |       |   +-- Prometheus 메트릭: auth_fallback_count++
    |       |   \-- 관리자에게 Slack/이메일 알림
    |       |
    |       v 제한된 기능으로 운영
    |           +-- 신규 토큰 발급 불가 (기존 토큰만 유효)
    |           +-- MFA 우회 (보안 등급 일시 하향)
    |           \-- 감사 로그에 "FALLBACK_MODE" 태그 기록
```

---

## 6.6 Cypher Injection 방어

Neo4j Cypher 쿼리는 SQL과 유사한 Injection 공격에 노출될 수 있다. IMSP는 CypherBuilder의 구조적 설계와 SecureCypherBuilder의 RBAC 필터를 통해 다층 방어를 구현한다.

### 파라미터화된 쿼리 강제

CypherBuilder(`core/kg/cypher_builder.py`)는 **Fluent API** 패턴으로 설계되어, 사용자 입력이 절대로 쿼리 문자열에 직접 연결(concatenation)되지 않는다. 모든 사용자 값은 `$paramName` 형태의 파라미터로 바인딩된다.

```python
# 안전한 쿼리 생성 (CypherBuilder 사용)
query, params = (
    CypherBuilder()
    .match("(v:Vessel)")
    .where("v.name = $name", {"name": user_input})  # 파라미터 바인딩
    .return_("v")
    .build()
)
# 결과: MATCH (v:Vessel) WHERE v.name = $name RETURN v
# params: {"name": "부산호"}
# -> user_input이 쿼리 문자열에 절대 포함되지 않음
```

**설계 원칙:**
- `where()` 메서드는 조건 문자열과 파라미터를 분리하여 수신
- 자동 생성된 파라미터명 (`_p0`, `_p1`, ...) 으로 충돌 방지
- `filter_node()` 메서드는 `FilterSpec` 객체를 통해 타입 안전한 필터 생성
- 모든 파라미터는 Neo4j Driver의 파라미터 바인딩을 통해 전달 (`driver.run(query, params)`)

### SecureCypherBuilder의 RBAC 필터 적용 과정

`SecureCypherBuilder`(`core/kg/rbac/secure_builder.py`)는 CypherBuilder를 확장하여 RBAC 접근 제어를 쿼리 레벨에서 강제한다.

```
사용자 쿼리 요청
    |
    v SecureCypherBuilder(user_id="USER-001", access_level=2)
    |
    +-- .match("(v:Vessel)")
    +-- .with_access_control("v", data_class_level=1)
    +-- .where("v.vesselType = $type", {"type": "ContainerShip"})
    +-- .return_("v")
    |
    v .build() 호출
    |
    +-- access_level >= 5 (Admin)?
    |   +-- Yes -> RBAC 절 생략 (bypass)
    |   +-- No  -> EXISTS 서브쿼리 주입
    |
    v 최종 쿼리:
        MATCH (v:Vessel)
        WHERE v.vesselType = $type
        AND EXISTS {
            MATCH (u:User {userId: $__rbac_user_id})
                  -[:HAS_ROLE]->(r:Role)-[:CAN_ACCESS]->(dc:DataClass)
            WHERE dc.level <= $__rbac_dc_level_v
        }
        RETURN v
    |
    v 파라미터:
        {"type": "ContainerShip",
         "__rbac_user_id": "USER-001",
         "__rbac_dc_level_v": 1}
```

### 금지 패턴 목록

아래 Cypher 패턴은 보안상 위험하므로, 프로덕션 환경에서 사용자 입력에 의해 실행되어서는 안 된다. CypherValidator(`core/kg/cypher_validator.py`)의 보안 검증(Stage 5)에서 차단한다.

| 금지 패턴 | 위험도 | 이유 |
|----------|--------|------|
| `DETACH DELETE` | CRITICAL | 노드와 모든 관계 일괄 삭제, 데이터 손실 |
| `DELETE` (조건 없음) | CRITICAL | 무조건 삭제, 데이터 손실 |
| `CALL apoc.periodic.iterate` | HIGH | 대량 배치 처리, 서버 리소스 고갈 |
| `CALL apoc.cypher.run` | HIGH | 동적 Cypher 실행 (2차 Injection 벡터) |
| `CALL apoc.export.*` | HIGH | 데이터 유출 (파일시스템 접근) |
| `LOAD CSV` | HIGH | 외부 URL에서 데이터 로드 (SSRF 벡터) |
| `CALL dbms.*` | MEDIUM | DB 관리 명령 (shutdown, config 변경 등) |
| `CALL apoc.trigger.*` | MEDIUM | 트리거 생성/삭제 (지속적 사이드이펙트) |
| `CREATE CONSTRAINT` / `DROP CONSTRAINT` | MEDIUM | 스키마 변경 (DDL 조작) |
| `CREATE INDEX` / `DROP INDEX` | MEDIUM | 인덱스 변경 (성능 영향) |
| `USING PERIODIC COMMIT` | LOW | 대량 트랜잭션 (메모리 리소스) |

**방어 계층 요약:**

```
Layer 1: CypherBuilder     -> 파라미터화 강제 (Injection 원천 차단)
Layer 2: CypherValidator   -> 금지 패턴 검출 (위험 쿼리 사전 차단)
Layer 3: SecureCypherBuilder -> RBAC 필터 주입 (권한 초과 접근 차단)
Layer 4: Neo4j User/Role    -> DB 레벨 권한 제어 (최종 방어선)
```

---

## 6.7 멀티테넌시 보안 설계

### 테넌트 격리 전략

IMSP는 **공유 스키마 + 속성 기반 격리** 모델을 채택한다.

```
┌─────────────────────────────────┐
│          Neo4j Instance          │
│  ┌───────────┐  ┌───────────┐   │
│  │ tenantId: │  │ tenantId: │   │
│  │  "kriso"  │  │ "civilian"│   │
│  │  ┌─────┐  │  │  ┌─────┐  │   │
│  │  │Vessel│  │  │  │Vessel│  │   │
│  │  └─────┘  │  │  └─────┘  │   │
│  └───────────┘  └───────────┘   │
└─────────────────────────────────┘
```

| 계층 | 격리 방법 | 시점 |
|------|----------|------|
| 데이터 | `tenantId` 속성 필터 (BatchLoader 강제) | Y2 |
| API | JWT `tenant` 클레임 + 미들웨어 검증 | Y2 |
| K8s | Namespace per tenant (대규모 민간 지원 시) | Y4+ |
| Object Storage | Bucket prefix per tenant | Y2 |

### Cypher 쿼리 테넌트 필터 강제

```python
class TenantAwareCypherBuilder(SecureCypherBuilder):
    def build(self) -> str:
        cypher = super().build()
        # 모든 MATCH 절에 tenantId 필터 자동 주입
        return inject_tenant_filter(cypher, self.tenant_id)
```

### 테넌트 프로비저닝 워크플로우

1. 관리자 → Keycloak에 Organization 생성
2. 자동: Neo4j에 `tenantId` 제약조건 초기화
3. 자동: Ceph RGW에 테넌트 버킷 생성 (`imsp-{tenant_id}/`)
4. 자동: 리소스 쿼터 설정 (KG 노드 수, 스토리지, GPU 시간)
5. 사용자 초대 (Keycloak 이메일)

---

## 6.8 ISMS-P 인증 대비 (Y4)

### 주요 통제 항목 매핑

ISMS-P 104개 통제 항목 중 IMSP 아키텍처 관련 핵심 항목:

| ISMS-P 영역 | 통제 항목 | IMSP 대응 | 구현 상태 |
|-------------|----------|----------|----------|
| 2.5 인증 및 권한관리 | 2.5.1 사용자 인증 | Keycloak OIDC + MFA | Y2 구현 |
| 2.5 인증 및 권한관리 | 2.5.4 접근권한 관리 | RBAC 4-Role + 테넌트 격리 | Y2 구현 |
| 2.6 접근통제 | 2.6.1 네트워크 접근 | Istio mTLS + NetworkPolicy | Y2 구현 |
| 2.6 접근통제 | 2.6.7 암호화 적용 | TLS 1.3 (외부), mTLS (내부) | Y2 구현 |
| 2.7 암호화 | 2.7.1 암호정책 수립 | JWT HS256→RS256 전환, Vault 키 관리 | Y3 구현 |
| 2.9 시스템 개발보안 | 2.9.1 보안 요구사항 | Cypher Injection 방어, 입력 검증 | Y1 구현 완료 |
| 2.9 시스템 개발보안 | 2.9.7 소스코드 보안 | GitLab SAST/DAST 파이프라인 | Y2 구현 |
| 2.10 시스템 운영보안 | 2.10.1 보안 모니터링 | Prometheus 알림 + 감사 로그 | Y1 부분, Y2 완성 |
| 2.11 사고 대응 | 2.11.1 침해사고 대응 | AlertManager 에스컬레이션 | Y3 구현 |
| 2.12 재해 복구 | 2.12.1 백업 및 복구 | Neo4j/PG dump + Ceph 복제 | Y1 기초, Y3 완성 |

### ISMS-P 갭 분석 일정

| 시기 | 활동 |
|------|------|
| Y3 Q4 | 1차 갭 분석 (104 항목 전수 점검) |
| Y4 Q1-Q2 | 미흡 항목 보완 개발 |
| Y4 Q3 | 모의 심사 (외부 컨설턴트) |
| Y4 Q4 | 본 심사 신청 |

---

## 관련 문서

| 문서 | 설명 |
|------|------|
| [배포 아키텍처](./05-deployment-architecture.md) | K8s 클러스터 토폴로지, CI/CD |
| [데이터 흐름도](./07-data-flow.md) | Text2Cypher 파이프라인의 보안 검증 단계 |
| [컴포넌트 아키텍처](./03-component-architecture.md) | KG 엔진, RBAC 모듈 상세 |
| [관측성 아키텍처](./10-observability.md) | 감사 로그 수집, 메트릭 상세 |
