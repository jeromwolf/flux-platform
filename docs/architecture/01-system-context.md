# 1. 시스템 컨텍스트 (System Context)

[← 용어 정의](./00-terminology.md) | [다음: 시스템 아키텍처 →](./02-system-architecture.md)

---

## 개요

IMSP는 해사 연구 및 서비스 개발을 지원하는 대화형 플랫폼으로, KRISO 내부 연구자, 민간 이용자(해운사/연구기관/공공), 외부 데이터 소스, Suredata Lab과 상호작용한다. 본 문서는 IMSP 플랫폼의 외부 경계와 주요 액터, 데이터 흐름, 네트워크 구성을 정의한다.

---

## 시스템 컨텍스트 다이어그램

```
                          +------------------+
                          |  KRISO 내부 연구자  |
                          | (Internal Users)  |
                          +--------+---------+
                                   |
                          OIDC (Keycloak) / HTTPS
                                   |
                                   v
+----------------+        +------------------------------------------+        +------------------+
| 외부 데이터 소스  |        |              IMSP Platform               |        | 2차 이용자         |
|                |        |                                          |        | (External Users)  |
| - AIS 수신기    | -Raw-> | +----------+  +----------+  +--------+  | <-OIDC-| - 해운사           |
| - 기상 API     |        | | Gateway  |->| Service  |->| Data   |  |        | - 연구기관         |
| - S-100 해도   |        | |  Layer   |  |  Layer   |  |  Layer |  |        | - 공공기관         |
| - 법규 DB      |        | +----------+  +----------+  +--------+  |        +------------------+
| - 위성 영상    |        |                                          |
| - CCTV        |        |  [VueFlow Canvas] [Chat UI] [Portal]     |
| - 레이더       |        |  [Observability Dashboard] [Auth]        |
+----------------+        +-------------------+----------------------+
                                              |
                                     REST API (OpenAPI 3.0)
                                     + Webhook / Kafka
                                              |
                                              v
                          +----------------------------------+
                          |          Suredata Lab            |
                          |  - 데이터 수집/크롤링              |
                          |  - 데이터 마트 (PostgreSQL DW)    |
                          |  - AI 모델 서빙 (vLLM / Ray)     |
                          |  - DW 파이프라인 (Kafka + Spark)  |
                          +----------------------------------+
```

---

## 1.1 액터 설명

### KRISO 내부 연구자

플랫폼의 1차 이용자. VueFlow 워크플로우 캔버스를 통해 해사 서비스를 설계하고, 대화 인터페이스로 KG 탐색 및 질의를 수행한다. Keycloak OIDC로 인증하며, RBAC 정책에 따라 데이터 접근 권한이 제한된다.

### 외부 데이터 소스

AIS 수신기(NMEA 0183/2000), 기상 API(GRIB2), IHO S-100 해도, 법규 DB, 위성 영상(GeoTIFF), CCTV 스트림(RTSP), 레이더 영상이 포함된다. 각 소스는 Collection Adapter를 통해 Ceph RGW에 Raw 적재된 후 ELT 파이프라인으로 처리된다.

### 데이터 제공 기관 매핑

| 제공 기관 | 데이터 유형 | 연동 방식 | 주기 |
|----------|-----------|---------|------|
| 해수부 | 해사 법규, 항만 정보 | REST API | 일/주 |
| 해양조사원 | 조석/해류, 해저지형 | 파일 다운로드 (GML/HDF5) | 일/월 |
| 국립해양측위정보원 | GNSS 보정, 측위 데이터 | REST API | 실시간 |
| 기상청 | 기상 관측/예보 (GRIB2) | REST API | 매 3시간 |
| 해경 | 해양사고, VTS 레이더 | REST API / Kafka | 실시간/일 |
| 자율운항선박 실증센터 | AIS, 센서, CCTV | Kafka 스트림 | 실시간 |
| KRISO | 실험 데이터, 시설 정보 | 파일 업로드 / API | 수동/일 |

### Suredata Lab

협력사. 데이터 수집/크롤링, PostgreSQL DW, AI 모델 서빙, 파이프라인 인프라를 담당한다. IMSP와는 REST API(OpenAPI 3.0) + Webhook + Kafka로 연동한다. IMSP는 KG 질의/리니지/온톨로지 스키마 API를 제공하고, Suredata는 추출 엔티티/모델 자산/원천 데이터를 IMSP에 등록한다.

### 2차 이용자 (서비스 사용자)

5가지 유형으로 세분화된다:

- **해양 공무원**: 해사 정책 수립/집행을 위한 데이터 분석 및 시각화 활용
- **해운사**: 해상교통 분석, 항로 최적화, 안전 관리 서비스 이용
- **어민**: 어장 정보, 기상/해상 상태 조회 서비스 이용
- **해양레저 사용자**: 해양 안전 정보, 기상 예보 서비스 이용
- **해사 연구자**: 해사 데이터 탐색, 분석 모델 개발, 워크플로우 활용

서비스 포털을 통해 승인된 기능에 접근하며, Keycloak OIDC + 멀티테넌트 RBAC로 격리된다.

---

## 1.2 주요 인터페이스

| 인터페이스 | 프로토콜 | 포트 | 인증 |
|-----------|---------|------|------|
| 내부 연구자 → IMSP | HTTPS / WebSocket | 443 | Keycloak OIDC |
| 2차 이용자 → IMSP | HTTPS | 443 | Keycloak OIDC (별도 Realm) |
| 외부 소스 → IMSP | HTTPS / NMEA / RTSP | 443 / 8001 | API Key |
| IMSP → Suredata Lab | HTTPS / Kafka | 443 / 9092 | mTLS + API Key |
| IMSP → Suredata Lab (AI 서빙) | HTTPS (gRPC) | 443 | JWT Bearer |

---

## 1.3 네트워크 경계 다이어그램

IMSP 플랫폼의 네트워크는 3개 영역(Zone)으로 구분되며, 각 영역 간 통신은 명시적으로 정의된 프로토콜과 포트만 허용한다.

```
+===========================================================================+
|                            인터넷 (Public Zone)                            |
|                                                                           |
|  +------------------+    +------------------+    +---------------------+  |
|  | 2차 이용자         |    | 외부 데이터 소스    |    | 데이터 제공 기관      |  |
|  | (해운사, 연구기관,  |    | (AIS, 기상API,    |    | (해수부, 기상청,     |  |
|  |  공공기관, 어민)    |    |  S-100, CCTV)    |    |  해경, 해양조사원)   |  |
|  +--------+---------+    +--------+---------+    +---------+-----------+  |
|           |                       |                        |              |
+===========|=======================|========================|==============+
            | HTTPS (443)           | HTTPS/NMEA/RTSP        | REST/Kafka
            |                       | (443/8001/554)         | (443/9092)
            v                       v                        v
+===========================================================================+
|                            DMZ (Semi-Trusted Zone)                        |
|                                                                           |
|  +------------------+    +------------------+    +---------------------+  |
|  | API Gateway       |    | Keycloak          |    | Ingress Controller  |  |
|  | (Kong/Nginx)     |    | (OIDC Provider)   |    | (TLS Termination)   |  |
|  | - Rate Limiting  |    | - 내부 Realm      |    | - L7 Routing        |  |
|  | - Request Valid. |    | - 외부 Realm      |    | - WAF Rules         |  |
|  | - API Key 검증   |    | - mTLS 인증서 관리 |    |                     |  |
|  +--------+---------+    +--------+---------+    +---------+-----------+  |
|           |                       |                        |              |
+===========|=======================|========================|==============+
            | REST/gRPC             | OIDC Token             | Proxy
            | (내부 포트)            | Validation             |
            v                       v                        v
+===========================================================================+
|                        KRISO 내부망 (Trusted Zone)                         |
|                                                                           |
|  +-Data Layer-----------+  +-Service Layer--------+  +-AI/GPU Layer----+  |
|  | Neo4j       :7687    |  | FastAPI App  :8000   |  | Ollama   :11434 |  |
|  |  (Bolt Protocol)     |  | KG Engine            |  | vLLM     :8080  |  |
|  | PostgreSQL  :5432    |  | Agent Runtime        |  | Ray      :6379  |  |
|  |  (SQL/libpq)         |  | RAG Engine           |  |                 |  |
|  | Redis       :6379    |  | Argo Workflow        |  +-----------------+  |
|  |  (RESP Protocol)     |  |  (DAG Executor)      |                       |
|  | Ceph RGW    :7480    |  +---------------------+                        |
|  |  (S3 Protocol)       |                                                 |
|  | TimescaleDB :5433    |  +-Infra Layer----------+                       |
|  |  (SQL/libpq)         |  | Prometheus   :9090   |                       |
|  +-----------------------+  | Grafana      :3000   |                       |
|                             | Zipkin       :9411   |                       |
|  +-Suredata 연동---------+  | K8s API      :6443   |                       |
|  | Kafka Broker :9092    |  +---------------------+                       |
|  | Webhook Out  :443     |                                                |
|  +-----------------------+                                                |
+===========================================================================+
```

### 경계 간 프로토콜 요약

| 경계 | 방향 | 프로토콜 | 인증 방식 | 암호화 |
|------|------|---------|----------|--------|
| 인터넷 → DMZ | Inbound | HTTPS, NMEA over TCP, RTSP | API Key / OIDC | TLS 1.3 |
| DMZ → 내부망 | Inbound | REST, gRPC, Bolt | Keycloak Token | mTLS |
| 내부망 → DMZ | Outbound | HTTPS (Webhook) | mTLS + API Key | TLS 1.3 |
| 내부망 → Suredata | Outbound | HTTPS, Kafka | mTLS + API Key | TLS 1.3 |
| 내부망 내부 | Internal | Bolt, SQL, RESP, S3 | K8s ServiceAccount | Network Policy |

---

## 1.4 외부 데이터 수신 인터페이스

각 외부 데이터 소스에 대한 수신 인터페이스의 기술적 상세를 정의한다.

### AIS (Automatic Identification System)

- **프로토콜**: NMEA 0183 (시리얼/TCP) 및 NMEA 2000 (CAN bus over TCP)
- **수신 포트**: TCP 8001 (전용 수신 포트)
- **처리량**: 초당 약 100 메시지 (피크 시 200+)
- **메시지 타입**: Position Report (Type 1-3), Static Data (Type 5), SAR Aircraft (Type 9) 등
- **수신 방식**: Kafka Producer가 TCP 소켓에서 NMEA 문장을 읽어 `ais.raw` 토픽으로 발행
- **파싱**: Collection Adapter가 NMEA 문장을 구조화된 JSON으로 변환 후 Ceph RGW에 Raw 적재
- **지연 허용**: 실시간 (< 5초)

### 기상 API

- **프로토콜**: REST API (HTTPS)
- **데이터 포맷**: GRIB2 (격자 기반 이진 포맷), JSON (관측 데이터)
- **수집 주기**: CronJob으로 3시간 주기 호출 (00, 03, 06, 09, 12, 15, 18, 21 UTC)
- **제공 기관**: 기상청 기상자료개방포털
- **처리**: GRIB2 파일을 Ceph RGW에 원본 적재 후, ELT Transform 단계에서 격자 데이터를 추출하여 TimescaleDB에 시계열 적재
- **용량**: 1회 수집당 약 50-200MB (해상 영역 필터링 후)

### S-100 해도 (IHO S-100 Framework)

- **프로토콜**: 파일 기반 (HTTPS 다운로드 또는 FTP)
- **데이터 포맷**: S-101 (ENC), S-102 (Bathymetry), S-104 (Tidal), S-111 (Surface Current) 등
- **동기화 주기**: 주 1회 (매주 월요일 02:00 KST)
- **처리**: S-100 파서가 GML/HDF5 구조를 파싱하여 공간 데이터는 Neo4j 공간 인덱스에, 메타데이터는 KG에 적재
- **참조**: `domains/maritime/s100/` 모듈에서 S-100 매핑 구현
- **용량**: 한국 연안 전체 약 2-5GB (갱신분만 동기화)

### CCTV / 레이더 영상

- **프로토콜**: RTSP (Real Time Streaming Protocol)
- **수신 포트**: TCP 554 (표준 RTSP)
- **처리 방식**: 실시간 스트림을 프레임 단위로 캡처, 객체 탐지 모델(YOLO 계열)로 선박/장애물 인식
- **저장**: 원본 스트림은 Ceph RGW에 세그먼트 단위(5분)로 저장, 탐지 결과(바운딩 박스 + 메타데이터)는 KG에 이벤트로 적재
- **GPU 요구**: 실시간 추론을 위해 A100 GPU 1대 이상 전용 할당
- **지연 허용**: < 3초 (실시간 모니터링 요구사항)

### 법규 DB / 기타 정형 데이터

- **프로토콜**: REST API (HTTPS)
- **데이터 포맷**: JSON, XML
- **수집 주기**: 일 1회 (변경분 감지) 또는 주 1회 (전체 동기화)
- **처리**: JSON/XML 응답을 구조화하여 Neo4j KG에 법규 노드/관계로 적재
- **제공 기관**: 해수부 (해사법규), 해경 (해양사고 이력)

---

## 1.5 시스템 경계 (System Boundary)

IMSP 플랫폼의 책임 범위를 명확히 하기 위해 시스템 경계를 정의한다.

### In-Scope (IMSP 책임)

| 영역 | 포함 항목 |
|------|----------|
| **플랫폼 코어** | KG 엔진, 온톨로지 관리, ELT 파이프라인, Agent Runtime, RAG 엔진 |
| **사용자 인터페이스** | VueFlow 워크플로우 캔버스, 대화 인터페이스(Chat UI), 서비스 포털, 관측성 대시보드 |
| **데이터 수집** | Collection Adapter 개발 및 운영, Raw 데이터 적재 및 정제 |
| **보안/인증** | Keycloak Realm 설정, RBAC 정책 관리, API Key 발급 |
| **배포/운영** | Kubernetes 클러스터 관리, CI/CD 파이프라인, 모니터링/알림 |
| **API 제공** | KG 질의 API, 온톨로지 스키마 API, 리니지 API, 워크플로우 API |

### Out-of-Scope (외부 책임)

| 영역 | 책임 주체 | 설명 |
|------|----------|------|
| **데이터 수집 인프라** | Suredata Lab | 대규모 크롤링 인프라, Kafka/Spark 클러스터 운영 |
| **AI 모델 학습** | Suredata Lab | GPU 클러스터 기반 모델 학습 및 하이퍼파라미터 튜닝 |
| **PostgreSQL DW** | Suredata Lab | 데이터 마트 구축 및 ETL 스케줄링 |
| **원천 데이터 품질** | 데이터 제공 기관 | AIS 수신기 상태, 기상 관측 장비 정확도 등 |
| **네트워크 인프라** | KRISO IT팀 | 내부망 방화벽, VPN, 물리 서버 관리 |
| **GPU 하드웨어** | KRISO | A100 GPU 서버 도입 및 물리적 유지보수 |

### 경계 인터페이스 계약 (Interface Contracts)

IMSP와 외부 시스템 간의 인터페이스는 다음 계약으로 관리된다:

| 인터페이스 | 계약 방식 | 문서화 |
|-----------|----------|--------|
| IMSP ↔ Suredata Lab | OpenAPI 3.0 스펙 + AsyncAPI (Kafka) | 양사 공동 관리 |
| IMSP ↔ 데이터 제공 기관 | 기관별 API 문서 준수 | IMSP 내부 Adapter 문서 |
| IMSP ↔ 2차 이용자 | 서비스 포털 API 가이드 | IMSP 개발팀 관리 |

---

[← 용어 정의](./00-terminology.md) | [다음: 시스템 아키텍처 →](./02-system-architecture.md)
