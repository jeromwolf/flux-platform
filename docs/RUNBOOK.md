# IMSP 운영 Runbook

이 문서는 IMSP (Interactive Maritime Service Platform) 운영 중 발생하는 장애 상황에 대한 대응 절차를 정의합니다.

---

## 장애 대응 연락처

| 역할 | 담당 | 연락처 |
|------|------|--------|
| 1차 대응 | 운영팀 | TBD |
| 2차 대응 | 개발팀 | TBD |
| 인프라 | 인프라팀 | TBD |
| KRISO 담당 | 발주처 | TBD |

---

## 서비스 구성

| 서비스 | 포트 | 헬스체크 |
|--------|------|----------|
| KG API | 8000 | `GET /health` |
| Gateway | 7749 | `GET /health` |
| Neo4j | 7687 (Bolt), 7474 (HTTP) | `cypher-shell -u neo4j 'RETURN 1'` |
| PostgreSQL | 5432 | `pg_isready -h localhost -U imsp` |
| Redis | 6379 | `redis-cli ping` |
| Keycloak | 8080 | `GET /health/ready` |
| Qdrant | 6333 | `GET /healthz` |
| Grafana | 3000 | `GET /api/health` |
| Prometheus | 9090 | `GET /-/healthy` |
| Zipkin | 9411 | `GET /health` |

---

## 모니터링 대시보드

| 대시보드 | URL |
|----------|-----|
| Grafana | http://grafana:3000 |
| Prometheus | http://prometheus:9090 |
| AlertManager | http://alertmanager:9093 |
| Zipkin | http://zipkin:9411 |

---

## 장애 유형별 대응

### 1. API 5xx 에러율 급증

**알림:** `HighErrorRate` (5xx 에러율 > 5%, 5분 지속)

**대응 절차:**

1. 로그 확인
   ```bash
   kubectl -n imsp logs deploy/kg-api --tail=100
   kubectl -n imsp logs deploy/gateway --tail=100
   ```

2. Pod 상태 확인
   ```bash
   kubectl -n imsp get pods -l app=imsp-api
   kubectl -n imsp describe pod <pod-name>
   ```

3. Neo4j 연결 확인
   ```bash
   kubectl -n imsp exec deploy/kg-api -- python -c \
     "from neo4j import GraphDatabase; \
      d = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j','<pw>')); \
      d.verify_connectivity(); print('OK')"
   ```

4. OOM 확인: `kubectl -n imsp describe pod <pod-name>` → `Last State` 섹션 확인

5. 재시작 (최후 수단)
   ```bash
   kubectl -n imsp rollout restart deployment/kg-api
   kubectl -n imsp rollout status deployment/kg-api --timeout=120s
   ```

---

### 2. Neo4j 다운

**알림:** `Neo4jDown`, `ServiceDown (job=neo4j)`

**대응 절차:**

1. Pod 상태 확인
   ```bash
   kubectl -n imsp get pods -l app=neo4j
   kubectl -n imsp describe statefulset/neo4j
   ```

2. 로그 확인
   ```bash
   kubectl -n imsp logs statefulset/neo4j --tail=200
   ```

3. 디스크 확인
   ```bash
   kubectl -n imsp exec statefulset/neo4j -- df -h /data
   ```

4. PVC 상태 확인
   ```bash
   kubectl -n imsp get pvc neo4j-data
   ```

5. 재시작 시도
   ```bash
   kubectl -n imsp rollout restart statefulset/neo4j
   kubectl -n imsp rollout status statefulset/neo4j --timeout=180s
   ```

6. 복구 실패 시 백업 복원
   ```bash
   # 최신 백업 확인
   kubectl -n imsp exec <backup-pod> -- ls -la /backups/neo4j/

   # Neo4j 정지
   kubectl -n imsp scale statefulset/neo4j --replicas=0

   # 백업 복원 (neo4j-admin database load)
   kubectl -n imsp exec <neo4j-pod> -- neo4j-admin database load \
     --from-path=/backups/neo4j/<latest>.dump neo4j --overwrite-destination=true

   # Neo4j 재시작
   kubectl -n imsp scale statefulset/neo4j --replicas=1
   ```

---

### 3. PostgreSQL 다운

**알림:** `ServiceDown (job=postgresql)`

**대응 절차:**

1. Pod 확인
   ```bash
   kubectl -n imsp get pods -l app=postgresql
   ```

2. 로그 확인
   ```bash
   kubectl -n imsp logs statefulset/postgresql --tail=200
   ```

3. 연결 테스트
   ```bash
   kubectl -n imsp exec statefulset/postgresql -- pg_isready -U imsp
   ```

4. 재시작 시도
   ```bash
   kubectl -n imsp rollout restart statefulset/postgresql
   ```

5. 복구 실패 시 백업 복원
   ```bash
   kubectl -n imsp exec <backup-pod> -- ls -la /backups/postgresql/
   kubectl -n imsp exec statefulset/postgresql -- \
     pg_restore -U imsp -d imsp /backups/postgresql/<latest>.dump
   ```

---

### 4. 메모리 부족 (OOM)

**알림:** `HighMemoryUsage` (메모리 사용률 > 90%)

**대응 절차:**

1. 어떤 Pod가 메모리를 많이 사용하는지 확인
   ```bash
   kubectl -n imsp top pods
   ```

2. 리소스 제한 확인
   ```bash
   kubectl -n imsp describe deploy/<name> | grep -A5 "Limits"
   ```

3. HPA 상태 확인
   ```bash
   kubectl -n imsp get hpa
   ```

4. 임시 조치: replica 수 증가 (부하 분산)
   ```bash
   kubectl -n imsp scale deploy/kg-api --replicas=3
   ```

5. 근본 원인 분석: 메모리 누수 여부 확인
   - Grafana 메모리 그래프로 증가 패턴 확인
   - 특정 요청 패턴 (대용량 그래프 조회 등) 여부 확인

---

### 5. 디스크 부족

**알림:** `PVCAlmostFull` (사용률 > 85%)

**대응 절차:**

1. PVC별 사용량 확인
   ```bash
   kubectl -n imsp get pvc
   kubectl -n imsp exec <pod> -- df -h
   ```

2. 큰 디렉토리 확인
   ```bash
   kubectl -n imsp exec <pod> -- du -sh /* 2>/dev/null | sort -rh | head -20
   ```

3. 오래된 로그 / 임시 파일 정리

4. PVC 확장 (StorageClass에 `allowVolumeExpansion: true` 필요)
   ```bash
   kubectl -n imsp patch pvc <pvc-name> \
     -p '{"spec":{"resources":{"requests":{"storage":"50Gi"}}}}'
   ```

---

### 6. Keycloak 인증 장애

**알림:** `ServiceDown (job=keycloak)` 또는 API 401 에러 급증

**대응 절차:**

1. Pod 상태 확인
   ```bash
   kubectl -n imsp get pods -l app=keycloak
   ```

2. 헬스 확인
   ```bash
   kubectl -n imsp exec deploy/keycloak -- \
     curl -sf http://localhost:8080/health/ready && echo OK
   ```

3. JWKS 엔드포인트 확인 (API가 공개 키를 가져올 수 있는지)
   ```bash
   kubectl -n imsp exec deploy/kg-api -- \
     curl -sf http://keycloak:8080/realms/imsp/protocol/openid-connect/certs
   ```

4. Realm 설정 확인: Keycloak Admin Console → `imsp` Realm → Realm Settings

5. 재시작 시도
   ```bash
   kubectl -n imsp rollout restart deployment/keycloak
   ```

6. JWKS 복구가 지연될 경우 HS256 fallback 모드 동작 확인
   - `kg.api.auth.jwt_auth` — Keycloak JWKS 실패 시 HS256으로 자동 fallback

---

### 7. 배포 실패 / 롤백

**알림:** CI/CD 파이프라인 실패 알림 또는 배포 후 에러율 급등

**대응 절차:**

1. 배포 상태 확인
   ```bash
   kubectl -n imsp rollout status deploy/<name>
   ```

2. 실패 원인 확인
   ```bash
   kubectl -n imsp describe deploy/<name>
   kubectl -n imsp get events -n imsp --sort-by='.lastTimestamp' | tail -30
   ```

3. 이전 버전 이력 확인
   ```bash
   kubectl -n imsp rollout history deploy/kg-api
   kubectl -n imsp rollout history deploy/gateway
   ```

4. 롤백 실행
   ```bash
   kubectl -n imsp rollout undo deploy/kg-api
   kubectl -n imsp rollout undo deploy/gateway
   kubectl -n imsp rollout status deploy/kg-api --timeout=120s
   kubectl -n imsp rollout status deploy/gateway --timeout=120s
   ```

5. 롤백 후 헬스 확인
   ```bash
   kubectl -n imsp exec deploy/kg-api -- curl -sf http://localhost:8000/health
   kubectl -n imsp exec deploy/gateway -- curl -sf http://localhost:7749/health
   ```

---

### 8. Redis 다운

**알림:** `ServiceDown (job=redis)` 또는 Rate Limit 기능 장애

**대응 절차:**

1. Pod 확인
   ```bash
   kubectl -n imsp get pods -l app=redis
   ```

2. 연결 테스트
   ```bash
   kubectl -n imsp exec deploy/kg-api -- redis-cli -h redis ping
   ```

3. 재시작
   ```bash
   kubectl -n imsp rollout restart deployment/redis
   ```

> **참고:** Redis 다운 시 Rate Limiting은 fail-open (허용) 으로 동작합니다.
> Agent memory는 in-memory fallback으로 전환됩니다. 서비스 중단은 없으나
> Rate Limit 우회 가능성이 있으므로 빠른 복구를 권장합니다.

---

### 9. Qdrant 다운

**알림:** `ServiceDown (job=qdrant)` 또는 RAG 검색 기능 장애

**대응 절차:**

1. Pod 확인
   ```bash
   kubectl -n imsp get pods -l app=qdrant
   kubectl -n imsp exec deploy/qdrant -- curl -sf http://localhost:6333/healthz
   ```

2. 재시작
   ```bash
   kubectl -n imsp rollout restart deployment/qdrant
   ```

3. 복구 후 벡터 인덱스 재구축 (데이터 유실 시)
   ```bash
   # RAG API를 통해 문서 재인덱싱
   PYTHONPATH=. python3 scripts/reindex_vectors.py --collection maritime_docs
   ```

---

## 백업 / 복구

### 백업 스케줄

| 대상 | 주기 | 보관 기간 | 방식 |
|------|------|-----------|------|
| Neo4j | 매일 02:00 KST | 7일 | `neo4j-admin database dump` + APOC export |
| PostgreSQL | 매일 03:00 KST | 7일 | `pg_dump -Fc` |
| Qdrant | 미구현 | - | 재인덱싱으로 복구 |
| Keycloak Realm | 변경 시 수동 | 무기한 | `infra/keycloak/realm-imsp.json` (Git) |

### 복구 목표 (RTO / RPO)

| 지표 | 목표 | 비고 |
|------|------|------|
| RTO (Recovery Time Objective) | 1시간 이내 | 백업 복원 포함 |
| RPO (Recovery Point Objective) | 최대 24시간 | 일일 백업 기준 |

### 수동 백업 실행

```bash
# Neo4j 수동 백업
kubectl -n imsp create job neo4j-backup-manual \
  --from=cronjob/neo4j-backup

# PostgreSQL 수동 백업
kubectl -n imsp exec statefulset/postgresql -- \
  pg_dump -U imsp -Fc imsp > /tmp/imsp-$(date +%Y%m%d).dump
```

---

## 긴급 연락 및 에스컬레이션

| 단계 | 조건 | 조치 |
|------|------|------|
| L1 | 단일 컴포넌트 장애, 자동복구 가능 | 운영팀 대응 |
| L2 | 복구 30분 초과 또는 데이터 손실 가능성 | 개발팀 호출 |
| L3 | 전체 서비스 다운 또는 데이터 손실 발생 | 개발팀 + 인프라팀 + KRISO 담당자 통보 |

---

## 참고 문서

- `docs/DEPLOYMENT_GUIDE.md` — 배포 가이드
- `infra/k8s/` — Kubernetes 매니페스트
- `infra/docker-compose.yml` — 로컬 개발 환경
- `infra/prometheus/alerts/` — AlertManager 규칙
