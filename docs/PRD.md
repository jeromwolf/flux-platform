# 대화형 해사서비스 플랫폼 - 제품 요구사항 정의서 (PRD)

> **문서 버전**: v1.0
> **작성일**: 2026-02-05
> **프로젝트 유형**: 정부 R&D 과제
> **문서 상태**: 초안 (Draft)

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [사용자 및 이해관계자](#2-사용자-및-이해관계자)
3. [핵심 기능 요구사항](#3-핵심-기능-요구사항)
4. [기술 스택](#4-기술-스택)
5. [데이터 모델 (해사 온톨로지)](#5-데이터-모델-해사-온톨로지)
6. [멀티모달 지식그래프 구축 파이프라인](#6-멀티모달-지식그래프-구축-파이프라인)
7. [KRISO 데이터 전략](#7-kriso-데이터-전략)
8. [대화형 시나리오](#8-대화형-시나리오)
9. [하드웨어 요구사항](#9-하드웨어-요구사항)
10. [라이선스 요약](#10-라이선스-요약)
11. [구축 로드맵](#11-구축-로드맵)

---

## 1. 프로젝트 개요

### 1.1 프로젝트명

**대화형 해사서비스 플랫폼** (Conversational Maritime Service Platform)

### 1.2 프로젝트 성격

본 프로젝트는 **정부 R&D 과제**로서, 해양수산부 산하 해사 데이터의 통합 활용과 AI 기반 지능형 서비스 제공을 목표로 한다. 해사 분야의 디지털 전환을 가속화하고, 산재된 해사 데이터를 지식그래프로 통합하여 다양한 이해관계자가 자연어 대화만으로 해사 정보에 접근할 수 있는 차세대 플랫폼을 구축한다.

### 1.3 프로젝트 목표

자연어 대화를 통해 해사 데이터를 조회하고, 워크플로우를 자동 생성하는 **멀티모달 AI 플랫폼**을 구축한다. 구체적으로 다음을 달성한다:

- **자연어 기반 데이터 접근**: 전문적인 쿼리 언어(SQL, Cypher 등) 없이도 대화형 인터페이스를 통해 해사 데이터를 조회하고 분석할 수 있는 환경 제공
- **멀티모달 데이터 통합**: 위성영상, CCTV, AIS, 기상, 문서 등 이질적인 해사 데이터를 지식그래프로 통합하여 크로스모달 분석 지원
- **워크플로우 자동화**: 자연어 명령으로 데이터 수집-처리-분석-알림 워크플로우를 자동 생성하고 실행
- **해사 도메인 지식 기반 응답**: RAG(Retrieval-Augmented Generation) 기반으로 해사 규정, 사고 사례, 연구 데이터 등 도메인 전문 지식을 활용한 정확한 응답 제공
- **오픈소스 기반 확장성**: 모든 핵심 구성요소를 오픈소스로 구축하여 지속적 확장과 커뮤니티 기여 가능

### 1.4 핵심 가치

> **해양 공무원, 어민, 해운사, 해양레저 사용자, 해사 연구자가 전문 지식 없이도 해사 데이터와 서비스에 접근할 수 있다.**

본 플랫폼은 기존에 전문가만 활용 가능했던 해사 데이터를 민주화(democratize)한다. 선박 위치 추적, 해양 기상 분석, 사고 이력 조회, 화물 관리 등 복잡한 업무를 자연어 대화만으로 수행할 수 있게 함으로써, 해사 산업 전반의 생산성과 안전성을 향상시킨다.

### 1.5 프로젝트 범위

| 구분 | 포함 | 제외 |
|------|------|------|
| 데이터 | AIS, 위성영상, CCTV, 기상, 해사 문서, KRISO 실험 데이터 | 군사 기밀 데이터, 외국 정부 비공개 데이터 |
| 서비스 | 대화형 조회, 워크플로우 자동화, 모니터링, 알림 | 실시간 항법 제어, 자율운항 직접 제어 |
| 사용자 | 해양 공무원, 어민, 해운사, 해양레저, 연구자 | 일반 대중 (추후 확장 가능) |
| 지역 | 대한민국 관할 해역 (EEZ 포함) | 해외 해역 (추후 확장 가능) |

---

## 2. 사용자 및 이해관계자

### 2.1 서비스 사용자

| 사용자 유형 | 주요 니즈 | 사용 시나리오 |
|------------|----------|-------------|
| **해양 공무원** | 해사 안전 관리, 규정 준수 모니터링, 사고 대응 | 위험물 선박 현황 조회, 불법 조업 탐지, 사고 보고서 검색 |
| **어민** | 기상 정보, 어장 정보, 안전 경보 | 출항 전 기상 확인, 어장 위치 추천, 안전 경보 수신 |
| **해운사** | 선박 운항 관리, 화물 추적, 항만 입출항 관리 | 선박 위치 추적, 최적 항로 조회, 항만 혼잡도 확인 |
| **해양레저 사용자** | 안전 정보, 기상 정보, 레저 활동 가이드 | 해양 레저 활동 전 안전 정보 확인, 기상 조건 확인 |
| **해사 연구자** | 해사 데이터 분석, 연구 데이터 접근, 실험 데이터 조회 | KRISO 실험 데이터 검색, 해양 환경 변화 분석, 논문 데이터 수집 |

### 2.2 데이터 제공처

| 기관 | 제공 데이터 | 연동 방식 |
|------|-----------|----------|
| **해양수산부 (해수부)** | 해사 정책, 규정, 공시 데이터 | REST API, 문서 크롤링 |
| **국립해양조사원 (조사원)** | 해도, 조석, 해류, 수심 데이터 | API, 파일 다운로드 |
| **국립해양측위정보원 (측위정보원)** | GNSS 보정 데이터, 측위 정보 | 실시간 스트림, API |
| **기상청** | 해양 기상, 파고, 풍속, 수온, 시정 | API, 실시간 스트림 |
| **해양경찰청 (해경)** | 해양 사고, 수색 구조, 불법 활동 데이터 | API, 문서 연동 |
| **자율운항선박 실증센터** | 자율운항 실험 데이터, 센서 데이터 | API, 파일 전송 |
| **KRISO (한국해양과학기술원 부설 선박해양플랜트연구소)** | 선박 모형 시험 데이터, 실험 결과, 연구 논문 | 크롤링(Phase A) → 공식 연동(Phase B) |

### 2.3 운영자

| 운영자 유형 | 역할 | 주요 업무 |
|------------|------|----------|
| **플랫폼 관리자** | 시스템 운영 및 유지보수 | 사용자 관리, 서비스 모니터링, 장애 대응, 보안 관리 |
| **연구개발자** | 플랫폼 확장 및 고도화 | 신규 서비스 개발, AI 모델 개선, 데이터 파이프라인 확장 |

---

## 3. 핵심 기능 요구사항

### 3.1 대화형 AI 엔진

대화형 AI 엔진은 플랫폼의 핵심 인터페이스로, 사용자의 자연어 입력을 분석하여 적절한 데이터 조회, 워크플로우 생성, 도메인 지식 응답을 수행한다.

#### 3.1.1 자연어 → 데이터 조회 (Text-to-Cypher via Neo4j)

- **기능 설명**: 사용자가 자연어로 질문하면, LLM이 이를 Neo4j Cypher 쿼리로 변환하여 지식그래프에서 데이터를 조회하고 자연어로 응답한다.
- **기술 구현**: LangChain의 `GraphCypherQAChain`을 활용하여 자연어 → Cypher 변환 → 쿼리 실행 → 응답 생성 파이프라인 구축
- **요구사항**:
  - 해사 도메인 특화 프롬프트 엔지니어링을 통한 정확한 Cypher 변환
  - Neo4j 스키마 자동 인식 및 쿼리 유효성 검증
  - 쿼리 실행 결과의 자연어 변환 및 시각화 (테이블, 차트, 지도)
  - 잘못된 쿼리 생성 시 자동 재시도 및 사용자 안내
  - 쿼리 히스토리 관리 및 즐겨찾기 기능

#### 3.1.2 자연어 → 워크플로우 자동 생성

- **기능 설명**: 사용자가 자연어로 원하는 자동화 작업을 설명하면, LLM이 적절한 워크플로우(Activepieces Flow)를 자동으로 생성한다.
- **요구사항**:
  - 사용 가능한 서비스/노드 목록을 LLM 컨텍스트에 주입
  - 생성된 워크플로우의 미리보기 및 수정 기능
  - 워크플로우 실행 전 사용자 확인 단계
  - 반복 사용되는 워크플로우 패턴의 템플릿화
  - 워크플로우 생성 실패 시 대안 제시

#### 3.1.3 멀티모달 질의 (이미지/문서 이해 기반 응답)

- **기능 설명**: 사용자가 이미지(위성영상, CCTV 캡처, 해도 등)나 문서(PDF, 보고서 등)를 첨부하여 질문하면, 멀티모달 LLM이 시각적 내용을 이해하고 응답한다.
- **기술 구현**: Qwen 2.5 VL 7B 모델을 활용한 이미지-텍스트 통합 이해
- **요구사항**:
  - 위성영상에서 선박 식별 및 위치 파악
  - CCTV 영상 캡처에서 선박 종류 및 상태 분석
  - 해사 문서(한국어) OCR 및 내용 이해
  - 해도/차트에서 항로, 장애물, 수심 정보 추출
  - 복합 질의: 이미지 + 텍스트 질문의 동시 처리

#### 3.1.4 RAG 기반 해사 도메인 지식 응답

- **기능 설명**: 해사 규정(COLREG, SOLAS, MARPOL 등), 사고 사례, 연구 논문 등 도메인 전문 지식을 벡터 검색과 그래프 검색을 결합하여 정확한 응답을 제공한다.
- **기술 구현**: Neo4j 벡터 인덱스 + 그래프 순회를 결합한 GraphRAG
- **요구사항**:
  - 해사 규정 원문의 청크 분할 및 벡터 임베딩 저장
  - 질문과 관련된 규정/사례의 정확한 검색 및 인용
  - 응답에 출처(문서명, 조항) 명시
  - 그래프 관계를 활용한 컨텍스트 확장 (예: 관련 사고 사례 → 적용 규정 → 후속 조치)
  - 주기적인 지식 베이스 업데이트 파이프라인

### 3.2 그래프 기반 워크플로우 저작도구

워크플로우 저작도구는 사용자가 시각적으로 데이터 처리 파이프라인을 설계하고 실행할 수 있는 환경을 제공한다.

#### 3.2.1 그래프 기반 워크플로우 저작 UI (React Flow)

- **기능 설명**: 드래그 앤 드롭 방식의 시각적 워크플로우 편집기를 제공한다. 노드와 엣지를 연결하여 데이터 흐름을 정의한다.
- **기술 구현**: React Flow 라이브러리 기반 커스텀 워크플로우 에디터
- **요구사항**:
  - 노드 팔레트: 데이터 소스, 처리, 분석, 출력 카테고리별 노드 제공
  - 노드 간 연결 시 데이터 타입 호환성 검증
  - 실시간 미리보기 및 디버깅 모드
  - 워크플로우 버전 관리 및 롤백
  - 반응형 UI (데스크톱/태블릿 지원)

#### 3.2.2 커스텀 코드 Node 개발 지원 (Activepieces Piece SDK)

- **기능 설명**: 개발자가 Activepieces의 Piece SDK를 사용하여 커스텀 노드를 개발하고 플랫폼에 등록할 수 있다.
- **요구사항**:
  - TypeScript 기반 Piece SDK 문서 및 템플릿 제공
  - 커스텀 Piece 개발-테스트-배포 워크플로우 지원
  - 해사 도메인 특화 Piece 라이브러리 (AIS 파서, 해도 처리 등)
  - Piece 마켓플레이스: 공유 및 재사용 환경

#### 3.2.3 LLM 기반 워크플로우 자동 생성

- **기능 설명**: 자연어 설명을 입력하면 LLM이 적합한 워크플로우를 자동으로 구성한다.
- **요구사항**:
  - 가용 노드/서비스 목록의 LLM 컨텍스트 주입
  - 생성된 워크플로우의 JSON 스키마 검증
  - 사용자 피드백 기반 워크플로우 수정
  - 유사 워크플로우 추천 기능

#### 3.2.4 자연어 기반 라이브러리 탐색

- **기능 설명**: 사용자가 자연어로 필요한 서비스/노드를 검색하면, 의미 기반 검색으로 관련 라이브러리를 찾아 제안한다.
- **요구사항**:
  - 라이브러리 메타데이터의 벡터 임베딩 및 의미 검색
  - 카테고리, 태그, 사용 빈도 기반 필터링
  - 검색 결과에 사용 예시 및 문서 링크 포함

#### 3.2.5 해사 멀티모달 데이터 어댑터

- **기능 설명**: 다양한 해사 데이터 소스와 연결하기 위한 표준 어댑터를 제공한다.
- **요구사항**:
  - AIS 데이터 어댑터 (NMEA 프로토콜 파싱)
  - 위성영상 어댑터 (GeoTIFF, SAFE 포맷)
  - 기상 데이터 어댑터 (GRIB2, NetCDF)
  - 해도 데이터 어댑터 (S-57, S-100)
  - CCTV 스트림 어댑터 (RTSP, HLS)
  - 실시간 스트림 어댑터 (Kafka Consumer)

#### 3.2.6 해사서비스 특화 라이브러리

- **기능 설명**: 해사 도메인에 특화된 재사용 가능한 서비스 라이브러리를 제공한다.
- **요구사항**:
  - 선박 탐지/추적 라이브러리
  - 궤적 분석 라이브러리 (이상 행동 탐지 포함)
  - 해양 기상 분석 라이브러리
  - 위험물 화물 관리 라이브러리
  - 항만 혼잡도 분석 라이브러리

### 3.3 워크플로우 서비스 운영

워크플로우의 안전한 실행과 외부 공개를 위한 운영 인프라를 제공한다.

#### 3.3.1 워크플로우 서비스 GW (Kong)

- **기능 설명**: 워크플로우를 외부 서비스로 공개할 때 API Gateway를 통한 트래픽 관리 및 보안을 적용한다.
- **요구사항**:
  - 워크플로우 → REST API 자동 변환 및 공개
  - Rate Limiting, 인증, 로깅 플러그인 적용
  - API 버전 관리 및 라우팅
  - 서비스 헬스체크 및 자동 장애 복구
  - API 사용량 통계 및 과금 메타데이터

#### 3.3.2 보안 접근 제어 (Keycloak)

- **기능 설명**: SSO(Single Sign-On) 기반의 통합 인증 및 세밀한 접근 제어를 제공한다.
- **요구사항**:
  - OIDC/OAuth 2.0 기반 인증
  - 역할 기반 접근 제어 (RBAC): 관리자, 연구자, 일반 사용자, 외부 이용자
  - 기관별 접근 권한 관리 (해수부, 해경, 연구기관 등)
  - 감사 로그 (Audit Log) 관리
  - 2단계 인증 (2FA) 지원

#### 3.3.3 서비스 리니지 관리 (Neo4j 그래프 추적)

- **기능 설명**: 워크플로우와 데이터 간의 의존 관계를 그래프로 추적하여 데이터 리니지를 관리한다.
- **요구사항**:
  - 워크플로우 입출력 데이터의 자동 리니지 기록
  - 데이터 소스 → 처리 → 결과물의 전체 추적 경로 시각화
  - 영향도 분석: 특정 데이터 소스 변경 시 영향받는 워크플로우 식별
  - 리니지 기반 데이터 품질 관리

### 3.4 멀티모달 해사 데이터/자원 관리

다양한 형태의 해사 데이터를 통합 관리하고 효율적으로 서빙하는 시스템을 제공한다.

#### 3.4.1 자연어 기반 데이터 탐색

- **기능 설명**: 자연어로 데이터를 검색하고 탐색할 수 있는 인터페이스를 제공한다.
- **요구사항**:
  - 벡터 검색 + 그래프 순회 결합의 하이브리드 검색
  - 데이터 미리보기 (이미지 썸네일, 시계열 차트, 지도 표시)
  - 검색 필터: 시간 범위, 공간 범위, 데이터 유형, 소스 기관
  - 검색 결과의 다운로드 및 API 접근 지원

#### 3.4.2 지식그래프 기반 데이터 및 자원 관리 (Neo4j)

- **기능 설명**: 모든 해사 데이터와 자원을 Neo4j 지식그래프에서 통합 관리한다.
- **요구사항**:
  - 해사 온톨로지 기반 데이터 모델링 및 저장
  - 그래프 + 벡터 + 공간 인덱스 통합 활용
  - 엔티티 간 관계 자동 추출 및 연결
  - 데이터 품질 모니터링 (누락, 중복, 불일치 감지)
  - 그래프 스키마 버전 관리

#### 3.4.3 실시간 데이터 연계/저장 (Kafka + TimescaleDB)

- **기능 설명**: AIS, 기상 등 실시간 스트림 데이터를 수집하고 시계열 DB에 저장한다.
- **요구사항**:
  - Kafka 기반 실시간 데이터 수집 파이프라인
  - AIS 메시지 디코딩 및 정규화
  - TimescaleDB 기반 시계열 데이터 저장 (AIS 궤적, 기상 관측)
  - 데이터 보존 정책 (핫/웜/콜드 티어링)
  - 실시간 데이터 → 지식그래프 자동 반영 (CDC 또는 배치)

#### 3.4.4 Object Storage 기반 데이터 저장 (MinIO)

- **기능 설명**: 위성영상, CCTV 캡처, 문서 원본 등 비정형 파일을 오브젝트 스토리지에 저장한다.
- **요구사항**:
  - S3 호환 API를 통한 파일 업로드/다운로드
  - 버킷 정책 기반 접근 제어
  - 메타데이터 태깅 및 검색
  - 자동 생명주기 관리 (아카이빙, 삭제)
  - 지식그래프 노드와 파일 URI 연결

#### 3.4.5 데이터 서빙 API

- **기능 설명**: 통합된 해사 데이터를 외부 시스템과 사용자에게 API로 제공한다.
- **요구사항**:
  - RESTful API 및 GraphQL 엔드포인트 제공
  - 공간 쿼리 API (bbox, 반경, 폴리곤 기반)
  - 시계열 쿼리 API (시간 범위, 집계, 다운샘플링)
  - 스트리밍 API (WebSocket/SSE 기반 실시간 데이터)
  - API 문서 자동 생성 (OpenAPI/Swagger)

### 3.5 해사 도메인 특화 서비스 Pool

재사용 가능한 해사 서비스 컴포넌트를 체계적으로 관리한다.

#### 3.5.1 해사서비스 특화 서비스 라이브러리 관리

- **기능 설명**: 해사 도메인에 특화된 서비스 컴포넌트를 라이브러리로 관리한다.
- **요구사항**:
  - 서비스 카탈로그: 분류 체계별 서비스 목록 관리
  - 서비스 메타데이터: 입출력 스키마, 의존성, 사용 가이드
  - 버전 관리 및 호환성 매트릭스
  - 서비스 품질 지표 (응답 시간, 정확도, 가용성)

#### 3.5.2 해사서비스 인터페이스 관리

- **기능 설명**: 서비스 간 표준 인터페이스를 정의하고 관리한다.
- **요구사항**:
  - 표준 입출력 데이터 포맷 정의 (JSON Schema)
  - 서비스 계약(Service Contract) 관리
  - 인터페이스 호환성 자동 검증
  - 인터페이스 변경 이력 추적

#### 3.5.3 해사서비스 Pool 등록/관리

- **기능 설명**: 새로운 해사 서비스를 Pool에 등록하고 생명주기를 관리한다.
- **요구사항**:
  - 서비스 등록 워크플로우 (제출 → 검증 → 승인 → 배포)
  - 서비스 상태 관리 (개발중, 테스트, 운영, 폐기)
  - 서비스 의존성 그래프 시각화
  - 서비스 사용 통계 및 인기 서비스 추천

### 3.6 플랫폼 운영

플랫폼의 안정적 운영과 사용자 관리를 위한 기능을 제공한다.

#### 3.6.1 연구개발 사용자 및 그룹 관리

- **기능 설명**: 연구개발 참여자의 계정과 그룹을 관리한다.
- **요구사항**:
  - Keycloak 연동 사용자 프로비저닝
  - 연구 그룹/프로젝트 단위 권한 관리
  - 개인/그룹별 리소스 할당량 관리
  - 활동 이력 및 기여도 추적

#### 3.6.2 플랫폼 운영 모니터링 (Grafana + Prometheus)

- **기능 설명**: 플랫폼 전체의 성능, 가용성, 리소스 사용량을 실시간 모니터링한다.
- **요구사항**:
  - 시스템 메트릭 수집: CPU, 메모리, 디스크, 네트워크
  - 애플리케이션 메트릭: API 응답시간, 에러율, 처리량
  - AI 모델 메트릭: 추론 시간, GPU 사용률, 모델별 요청 수
  - 워크플로우 메트릭: 실행 횟수, 성공률, 실행 시간
  - 대시보드 커스터마이징 및 알림 규칙 설정
  - 이상 탐지 및 자동 알림 (Slack, 이메일)

#### 3.6.3 워크플로우 서비스 Portal

- **기능 설명**: 워크플로우 기반 서비스를 포털 형태로 제공한다.
- **요구사항**:
  - 서비스 카탈로그 브라우징 및 검색
  - 서비스 구독 및 API 키 관리
  - 서비스 사용 통계 대시보드
  - 서비스 평가 및 피드백 시스템

#### 3.6.4 협업 및 작업 공유 관리

- **기능 설명**: 사용자 간 워크플로우, 데이터, 분석 결과를 공유하고 협업한다.
- **요구사항**:
  - 워크플로우 공유 (읽기/쓰기/실행 권한)
  - 분석 결과 공유 및 댓글
  - 작업 이력 공유 및 재현
  - 팀 워크스페이스 관리

#### 3.6.5 워크플로우 서비스 공개 관리

- **기능 설명**: 검증된 워크플로우를 외부에 공개 서비스로 제공한다.
- **요구사항**:
  - 공개 승인 워크플로우 (검증 → 승인 → 공개)
  - 공개 서비스 SLA 관리
  - API 키/토큰 기반 접근 관리
  - 사용량 모니터링 및 과금 지원

---

## 4. 기술 스택

### 4.1 프론트엔드

| 기술 | 라이선스 | 역할 | 선정 사유 |
|------|---------|------|----------|
| **Next.js** | MIT | Portal, 관리 대시보드 | SSR/SSG 지원으로 SEO 및 초기 로딩 최적화, React 생태계 활용 |
| **React Flow** | MIT | 그래프 워크플로우 저작 UI | 고성능 노드 기반 에디터, 커스터마이징 용이 |
| **Leaflet / MapLibre** | BSD | 해사 지도 시각화 | 오픈소스 지도 라이브러리, 해도 오버레이 지원, 벡터 타일 렌더링 |

### 4.2 AI 모델 -- 1계층 (멀티모달 LLM)

| 기술 | 라이선스 | 역할 | 선정 사유 |
|------|---------|------|----------|
| **Qwen 2.5 VL 7B** | Apache 2.0 | 메인 LLM (대화, 이미지 이해, 한국어 OCR) | 멀티모달 지원, 한국어 성능 우수, 7B 파라미터로 A100 단일 GPU 서빙 가능 |
| **MiniCPM-V 4.5** | Apache 2.0 | 경량 백업 LLM | 초경량 멀티모달 모델, 폴백 및 배치 처리용 |
| **vLLM** | Apache 2.0 | LLM 서빙 엔진 | PagedAttention 기반 고효율 GPU 메모리 관리, 높은 처리량 |

### 4.3 AI 모델 -- 2계층 (전문 모델)

| 기술 | 라이선스 | 역할 | 선정 사유 |
|------|---------|------|----------|
| **YOLOv8 / RT-DETR** | AGPL / Apache 2.0 | 위성/CCTV 선박 탐지 | 실시간 객체 탐지, 위성영상/CCTV에서 선박 식별 |
| **DeepSORT** | MIT | CCTV 선박 추적 | 다중 객체 추적, 선박 ID 유지 |
| **PaddleOCR** | Apache 2.0 | 한국어 해사 문서 OCR | 한국어 인식 정확도 우수, 경량 배포 가능 |
| **CLIP / ImageBind** | MIT | 크로스모달 임베딩 | 텍스트-이미지 간 의미적 매칭, 멀티모달 검색 |
| **Unstructured** | Apache 2.0 | 문서 구조 파싱 | PDF, DOCX 등 다양한 문서 포맷의 구조적 파싱 |

### 4.4 대화형 AI 엔진

| 기술 | 라이선스 | 역할 | 선정 사유 |
|------|---------|------|----------|
| **LangChain** | MIT | LLM 프레임워크 | LLM 애플리케이션 개발의 표준 프레임워크, 풍부한 통합 생태계 |
| **LangGraph** | MIT | 에이전트 오케스트레이션 | 상태 기반 멀티스텝 에이전트 워크플로우, 복잡한 의사결정 흐름 지원 |
| **GraphCypherQAChain** | MIT | 자연어 → Cypher → 응답 | Neo4j 지식그래프와 LLM의 원활한 통합 |

### 4.5 워크플로우 엔진

| 기술 | 라이선스 | 역할 | 선정 사유 |
|------|---------|------|----------|
| **Activepieces (포크)** | MIT | 워크플로우 실행/관리 | MIT 라이선스, TypeScript 기반, Piece SDK로 확장 용이, 시각적 편집기 내장 |

**Activepieces 포크 전략**:
- 핵심 엔진은 upstream을 추적하되, 해사 도메인 특화 Piece와 UI 확장을 별도 모듈로 관리
- 해사 데이터 어댑터를 Activepieces Piece로 개발
- LLM 기반 워크플로우 생성 기능을 플러그인으로 통합

### 4.6 지식그래프

| 기술 | 라이선스 | 역할 | 선정 사유 |
|------|---------|------|----------|
| **Neo4j Community** | GPLv3 | 통합 KG DB (그래프+벡터+공간) | 그래프 DB 업계 표준, 벡터 인덱스 내장, 공간 함수 지원, Cypher 쿼리 언어 |
| **n10s (neosemantics)** | Apache 2.0 | OWL → Neo4j 변환 | 온톨로지(OWL/RDF)를 Neo4j 프로퍼티 그래프로 자동 변환 |
| **Protege** | BSD | 온톨로지 설계 도구 | 표준 온톨로지 편집기, OWL 2 지원, 시각적 모델링 |

**Neo4j 통합 활용 전략**:
- **그래프 인덱스**: 엔티티 간 관계 탐색 (선박-항만-화물-사고 관계)
- **벡터 인덱스**: 텍스트/이미지 임베딩 기반 유사도 검색 (RAG, 멀티모달 검색)
- **공간 인덱스**: 좌표 기반 공간 쿼리 (반경 검색, bbox 검색, 궤적 분석)

### 4.7 데이터 저장소

| 기술 | 라이선스 | 역할 | 선정 사유 |
|------|---------|------|----------|
| **Neo4j** | GPLv3 | 그래프 관계 + 벡터 + 공간 | 지식그래프의 중심 저장소, 다중 인덱스 통합 |
| **TimescaleDB** | Apache 2.0 | AIS 궤적, 시계열 | PostgreSQL 확장, 대규모 시계열 데이터 처리에 최적화 |
| **MinIO** | AGPL-3.0 | 멀티모달 원본 파일 | S3 호환 오브젝트 스토리지, 대용량 파일 관리 |
| **PostgreSQL** | PostgreSQL License | 사용자, 워크플로우 메타 | 범용 RDBMS, Activepieces/Keycloak 백엔드 |

### 4.8 데이터 수집

| 기술 | 라이선스 | 역할 | 선정 사유 |
|------|---------|------|----------|
| **Apache Kafka** | Apache 2.0 | AIS 실시간 스트림 | 대용량 실시간 스트림 처리, 내구성 보장 |
| **Scrapy** | BSD | 웹 크롤링 | Python 기반 웹 스크래핑 프레임워크, KRISO 메타데이터 수집 |
| **pystac** | MIT | 위성영상 수집 | STAC(SpatioTemporal Asset Catalog) 표준 기반 위성영상 검색/다운로드 |

### 4.9 인프라

| 기술 | 라이선스 | 역할 | 선정 사유 |
|------|---------|------|----------|
| **Keycloak** | Apache 2.0 | SSO, 사용자 인증 | 오픈소스 IAM, OIDC/SAML 지원, 정부 시스템 연동 |
| **Kong** | Apache 2.0 | API GW | 고성능 API Gateway, 플러그인 아키텍처, 다양한 인증 방식 지원 |
| **Grafana + Prometheus** | AGPL / Apache 2.0 | 모니터링 | 업계 표준 모니터링 스택, 풍부한 시각화, 알림 기능 |
| **Docker + Kubernetes** | Apache 2.0 | 컨테이너 | 컨테이너 오케스트레이션 표준, GPU 워크로드 지원 |

---

## 5. 데이터 모델 (해사 온톨로지)

해사 온톨로지는 플랫폼의 지식그래프를 구성하는 핵심 데이터 모델이다. OWL(Web Ontology Language)로 설계하고 n10s를 통해 Neo4j 프로퍼티 그래프로 변환하여 사용한다.

### 5.1 핵심 엔티티

#### 5.1.1 물리적 엔티티 (Physical Entities)

**Vessel (선박)**

| 속성 | 타입 | 설명 |
|------|------|------|
| mmsi | String | MMSI (Maritime Mobile Service Identity) |
| imo | String | IMO 번호 |
| name | String | 선명 |
| callSign | String | 호출부호 |
| vesselType | Enum | 선종 |
| grossTonnage | Float | 총톤수 |
| deadweight | Float | 재화중량톤수 |
| length | Float | 전장 (m) |
| beam | Float | 폭 (m) |
| draft | Float | 흘수 (m) |
| flag | String | 선적국 |
| status | String | 현재 상태 (항해중, 정박, 계류 등) |
| visualEmbedding | Float[] | 시각 임베딩 벡터 (선박 외관 특징) |

선종 하위 분류:
- `CargoShip` (화물선)
- `Tanker` (유조선)
- `FishingVessel` (어선)
- `PassengerShip` (여객선)
- `NavalVessel` (군함)
- `AutonomousVessel` (자율운항선박)

**Port (항만)**

| 속성 | 타입 | 설명 |
|------|------|------|
| unlocode | String | UN/LOCODE |
| name | String | 항만명 |
| portType | Enum | 항종 |
| country | String | 소속국 |
| location | Point | 좌표 (위도, 경도) |
| maxDraft | Float | 최대 허용 흘수 |
| totalBerths | Integer | 총 선석 수 |

항종 하위 분류:
- `TradePort` (무역항)
- `CoastalPort` (연안항)
- `FishingPort` (어항)

**PortFacility (항만시설)**

| 속성 | 타입 | 설명 |
|------|------|------|
| facilityId | String | 시설 ID |
| facilityType | Enum | 시설 유형 |
| capacity | Float | 수용 능력 |
| status | String | 운영 상태 |

시설 유형:
- `Berth` (선석)
- `Anchorage` (정박지)
- `Terminal` (터미널)
- `CargoHandlingEquipment` (하역 장비)

**Waterway (항로)**

| 속성 | 타입 | 설명 |
|------|------|------|
| waterwayId | String | 항로 ID |
| name | String | 항로명 |
| waterwayType | Enum | 항로 유형 |
| minDepth | Float | 최소 수심 (m) |
| maxDepth | Float | 최대 수심 (m) |
| trafficDensity | Float | 교통 밀도 |
| geometry | LineString | 항로 경로 |

항로 유형:
- `TSS` (통항분리수역)
- `Channel` (수로)
- `FairwayRoute` (항행 항로)

**Cargo (화물)**

| 속성 | 타입 | 설명 |
|------|------|------|
| cargoId | String | 화물 ID |
| cargoType | Enum | 화물 유형 |
| weight | Float | 중량 (톤) |
| volume | Float | 체적 (CBM) |
| imdgClass | String | IMDG 위험물 등급 (1-9등급) |
| unNumber | String | UN 번호 |
| description | String | 화물 설명 |

화물 유형:
- `DangerousGoods` (위험물) -- IMDG 9등급 분류
  - Class 1: 폭발물
  - Class 2: 가스
  - Class 3: 인화성 액체
  - Class 4: 인화성 고체
  - Class 5: 산화성 물질
  - Class 6: 독성 물질
  - Class 7: 방사성 물질
  - Class 8: 부식성 물질
  - Class 9: 기타 유해 물질
- `BulkCargo` (산적화물)
- `ContainerCargo` (컨테이너화물)

**Sensor (센서)**

| 속성 | 타입 | 설명 |
|------|------|------|
| sensorId | String | 센서 ID |
| sensorType | Enum | 센서 유형 |
| location | Point | 설치 위치 |
| status | String | 운영 상태 |
| lastUpdate | DateTime | 최종 갱신 시각 |

센서 유형:
- `AISTransceiver` (AIS 트랜시버)
- `Radar` (레이더)
- `CCTVCamera` (CCTV 카메라)
- `WeatherStation` (기상 관측소)

#### 5.1.2 공간 엔티티 (Spatial Entities)

**SeaArea (해역)**

| 속성 | 타입 | 설명 |
|------|------|------|
| areaId | String | 해역 ID |
| name | String | 해역명 |
| areaType | Enum | 해역 유형 |
| geometry | Polygon | 해역 경계 |
| jurisdiction | String | 관할 기관 |

해역 유형:
- `EEZ` (배타적 경제수역)
- `TerritorialSea` (영해)
- `InternalWaters` (내수)

**CoastalRegion (연안)**

| 속성 | 타입 | 설명 |
|------|------|------|
| regionId | String | 연안 ID |
| name | String | 연안명 |
| coastlineLength | Float | 해안선 길이 (km) |
| geometry | Polygon | 연안 경계 |

**GeoPoint (좌표)**

| 속성 | 타입 | 설명 |
|------|------|------|
| latitude | Float | 위도 |
| longitude | Float | 경도 |
| crs | String | 좌표계 (기본: WGS84/EPSG:4326) |

#### 5.1.3 시간적 엔티티 (Temporal Entities)

**Voyage (항해)**

| 속성 | 타입 | 설명 |
|------|------|------|
| voyageId | String | 항해 ID |
| departureTime | DateTime | 출항 시각 |
| arrivalTime | DateTime | 도착 시각 |
| distance | Float | 항해 거리 (nm) |
| status | String | 항해 상태 |

**PortCall (입출항)**

| 속성 | 타입 | 설명 |
|------|------|------|
| portCallId | String | 입출항 ID |
| arrivalTime | DateTime | 입항 시각 |
| departureTime | DateTime | 출항 시각 |
| purpose | String | 목적 (하역, 급유, 수리 등) |

**TrackSegment (궤적 구간)**

| 속성 | 타입 | 설명 |
|------|------|------|
| segmentId | String | 구간 ID |
| startTime | DateTime | 시작 시각 |
| endTime | DateTime | 종료 시각 |
| startPoint | Point | 시작 좌표 |
| endPoint | Point | 종료 좌표 |
| avgSpeed | Float | 평균 속력 (knots) |
| avgCourse | Float | 평균 침로 (degrees) |
| trajectory | LineString | 궤적 경로 |

**Incident (사고)**

| 속성 | 타입 | 설명 |
|------|------|------|
| incidentId | String | 사고 ID |
| incidentType | Enum | 사고 유형 |
| occurredAt | DateTime | 발생 시각 |
| location | Point | 발생 위치 |
| severity | String | 심각도 |
| description | String | 사고 설명 |
| casualties | Integer | 인명 피해 |

사고 유형:
- `Collision` (충돌)
- `Grounding` (좌초)
- `Pollution` (오염)
- `Distress` (조난)
- `IllegalFishing` (불법 조업)

**WeatherCondition (기상)**

| 속성 | 타입 | 설명 |
|------|------|------|
| observedAt | DateTime | 관측 시각 |
| location | Point | 관측 위치 |
| waveHeight | Float | 파고 (m) |
| windSpeed | Float | 풍속 (m/s) |
| windDirection | Float | 풍향 (degrees) |
| visibility | Float | 시정 (nm) |
| seaTemperature | Float | 수온 (Celsius) |
| airTemperature | Float | 기온 (Celsius) |
| pressure | Float | 기압 (hPa) |

**Activity (활동)**

| 속성 | 타입 | 설명 |
|------|------|------|
| activityId | String | 활동 ID |
| activityType | Enum | 활동 유형 |
| startTime | DateTime | 시작 시각 |
| endTime | DateTime | 종료 시각 |
| location | Point | 활동 위치 |

활동 유형:
- `Loading` (적하)
- `Unloading` (양하)
- `Bunkering` (급유)
- `Anchoring` (정박)
- `Loitering` (배회)

#### 5.1.4 정보 엔티티 (Information Entities)

**Regulation (규정)**

| 속성 | 타입 | 설명 |
|------|------|------|
| regulationId | String | 규정 ID |
| name | String | 규정명 |
| regulationType | Enum | 규정 유형 |
| version | String | 버전 |
| effectiveDate | Date | 시행일 |
| content | String | 규정 내용 |
| textEmbedding | Float[] | 텍스트 임베딩 |

규정 유형:
- `COLREG` (국제해상충돌예방규칙)
- `SOLAS` (해상인명안전협약)
- `MARPOL` (해양오염방지협약)
- `IMDGCode` (국제해상위험물규칙)

**Document (문서)**

| 속성 | 타입 | 설명 |
|------|------|------|
| documentId | String | 문서 ID |
| title | String | 제목 |
| documentType | Enum | 문서 유형 |
| createdAt | DateTime | 작성일 |
| author | String | 작성자 |
| storageURI | String | 원본 파일 URI (MinIO) |
| textEmbedding | Float[] | 텍스트 임베딩 |

문서 유형:
- `AccidentReport` (사고 보고서)
- `InspectionReport` (점검 보고서)
- `NavigationalWarning` (항행 경보)
- `CargoManifest` (화물 목록)

**DataSource (데이터소스)**

| 속성 | 타입 | 설명 |
|------|------|------|
| sourceId | String | 데이터소스 ID |
| name | String | 소스명 |
| sourceType | Enum | 소스 유형 |
| endpoint | String | 접속 URL |
| protocol | String | 프로토콜 |
| updateFrequency | String | 갱신 주기 |
| status | String | 상태 |

소스 유형:
- `APIEndpoint` (API 엔드포인트)
- `StreamSource` (스트림 소스)
- `FileSource` (파일 소스)

**Service (서비스)**

| 속성 | 타입 | 설명 |
|------|------|------|
| serviceId | String | 서비스 ID |
| name | String | 서비스명 |
| serviceType | Enum | 서비스 유형 |
| description | String | 설명 |
| endpoint | String | 서비스 URL |
| status | String | 운영 상태 |

서비스 유형:
- `QueryService` (조회 서비스)
- `AnalysisService` (분석 서비스)
- `AlertService` (알림 서비스)
- `PredictionService` (예측 서비스)

#### 5.1.5 관측 엔티티 (Observation Entities -- 멀티모달)

**SARObservation (위성 레이더 관측)**

| 속성 | 타입 | 설명 |
|------|------|------|
| observationId | String | 관측 ID |
| satellite | String | 위성명 (Sentinel-1 등) |
| acquisitionTime | DateTime | 촬영 시각 |
| footprint | Polygon | 촬영 영역 |
| resolution | Float | 해상도 (m) |
| polarization | String | 편파 모드 |
| storageURI | String | 영상 파일 URI |
| visualEmbedding | Float[] | 시각 임베딩 |

**OpticalObservation (광학 위성 관측)**

| 속성 | 타입 | 설명 |
|------|------|------|
| observationId | String | 관측 ID |
| satellite | String | 위성명 (Sentinel-2, PlanetScope 등) |
| acquisitionTime | DateTime | 촬영 시각 |
| footprint | Polygon | 촬영 영역 |
| resolution | Float | 해상도 (m) |
| cloudCover | Float | 운량 (%) |
| bands | String[] | 밴드 구성 |
| storageURI | String | 영상 파일 URI |
| visualEmbedding | Float[] | 시각 임베딩 |

**CCTVObservation (CCTV 관측)**

| 속성 | 타입 | 설명 |
|------|------|------|
| observationId | String | 관측 ID |
| cameraId | String | 카메라 ID |
| timestamp | DateTime | 캡처 시각 |
| frameURI | String | 프레임 이미지 URI |
| videoClipURI | String | 영상 클립 URI |
| detectedObjects | Integer | 탐지된 객체 수 |
| visualEmbedding | Float[] | 시각 임베딩 |

**AISObservation (AIS 관측)**

| 속성 | 타입 | 설명 |
|------|------|------|
| messageId | String | 메시지 ID |
| mmsi | String | MMSI |
| timestamp | DateTime | 수신 시각 |
| position | Point | 위치 |
| sog | Float | 대지 속력 (knots) |
| cog | Float | 대지 침로 (degrees) |
| heading | Float | 선수 방향 (degrees) |
| navStatus | Integer | 항행 상태 코드 |
| messageType | Integer | AIS 메시지 유형 |

**RadarObservation (레이더 관측)**

| 속성 | 타입 | 설명 |
|------|------|------|
| observationId | String | 관측 ID |
| radarId | String | 레이더 ID |
| timestamp | DateTime | 관측 시각 |
| targetPosition | Point | 대상 위치 |
| targetSpeed | Float | 대상 속력 |
| targetBearing | Float | 대상 방위 |
| signalStrength | Float | 신호 강도 |

**WeatherObservation (기상 관측)**

| 속성 | 타입 | 설명 |
|------|------|------|
| observationId | String | 관측 ID |
| stationId | String | 관측소 ID |
| observedAt | DateTime | 관측 시각 |
| location | Point | 관측 위치 |
| waveHeight | Float | 파고 (m) |
| windSpeed | Float | 풍속 (m/s) |
| visibility | Float | 시정 (nm) |
| temperature | Float | 기온 (Celsius) |

#### 5.1.6 행위자 (Actors)

**Organization (기관)**

| 속성 | 타입 | 설명 |
|------|------|------|
| orgId | String | 기관 ID |
| name | String | 기관명 |
| orgType | Enum | 기관 유형 |
| country | String | 소속국 |
| contactInfo | String | 연락처 |

기관 유형:
- `GovernmentAgency` (정부 기관)
- `ShippingCompany` (해운사)
- `ResearchInstitute` (연구기관)

**Person (인물)**

| 속성 | 타입 | 설명 |
|------|------|------|
| personId | String | 인물 ID |
| name | String | 성명 |
| role | Enum | 역할 |
| organization | String | 소속 기관 |
| certifications | String[] | 보유 자격 |

역할 유형:
- `CrewMember` (선원)
- `Inspector` (검사관)

#### 5.1.7 멀티모달 표현 (Multimodal Representations)

**VisualEmbedding (시각 임베딩)**

| 속성 | 타입 | 설명 |
|------|------|------|
| embeddingId | String | 임베딩 ID |
| vector | Float[] | 임베딩 벡터 (CLIP/ImageBind) |
| model | String | 생성 모델명 |
| dimension | Integer | 벡터 차원수 |
| sourceURI | String | 원본 이미지 URI |

**TrajectoryEmbedding (궤적 임베딩)**

| 속성 | 타입 | 설명 |
|------|------|------|
| embeddingId | String | 임베딩 ID |
| vector | Float[] | 임베딩 벡터 |
| timeRange | String | 시간 범위 |
| pointCount | Integer | 궤적 포인트 수 |

**TextEmbedding (텍스트 임베딩)**

| 속성 | 타입 | 설명 |
|------|------|------|
| embeddingId | String | 임베딩 ID |
| vector | Float[] | 임베딩 벡터 |
| model | String | 생성 모델명 |
| sourceText | String | 원본 텍스트 (요약) |

**FusedEmbedding (융합 임베딩)**

| 속성 | 타입 | 설명 |
|------|------|------|
| embeddingId | String | 임베딩 ID |
| vector | Float[] | 융합 임베딩 벡터 |
| sourceModalities | String[] | 원본 모달리티 목록 |
| fusionMethod | String | 융합 방법 |

#### 5.1.8 KRISO 실험 데이터 (별도 관리)

KRISO(한국해양과학기술원 부설 선박해양플랜트연구소) 데이터는 연구 실험 특성상 별도 하위 그래프로 관리한다.

**Experiment (실험)**

| 속성 | 타입 | 설명 |
|------|------|------|
| experimentId | String | 실험 ID |
| title | String | 실험 제목 |
| purpose | String | 실험 목적 |
| facility | String | 사용 시설 |
| researchTeam | String | 연구팀 |
| conductedDate | Date | 실험일 |
| source | String | 데이터 출처 (scholarworks_crawl / kriso_official) |

**TestFacility (시험 시설)**

| 시설명 | 규격 | 용도 |
|-------|------|------|
| **TowingTank (예인수조)** | 200m x 16m x 7m | 선박 저항/추진 시험 |
| **OceanEngineeringBasin (해양공학수조)** | 56m x 30m x 4.5m | 해양 구조물 파랑 시험 |
| **IceTank (빙해수조)** | 42m x 32m x 2.5m | 빙해역 성능 시험 |
| **DeepOceanBasin (심해공학수조)** | 100m x 50m x 15m | 심해 환경 시뮬레이션 |
| **WaveEnergyTestSite (파력발전 실해역 시험장)** | 104만m2 | 파력발전 실해역 시험 |
| **HyperbaricChamber (고압챔버)** | 600bar | 심해 환경 재현 시험 |

**ExperimentalDataset (실험 데이터셋)**

| 속성 | 타입 | 설명 |
|------|------|------|
| datasetId | String | 데이터셋 ID |
| format | String | 데이터 포맷 |
| sampleRate | Float | 샘플링 레이트 |
| storageURI | String | 저장 위치 (MinIO) |
| fileSize | Long | 파일 크기 |
| checksum | String | 무결성 해시 |

**TestCondition (시험 조건)**

| 속성 | 타입 | 설명 |
|------|------|------|
| conditionId | String | 조건 ID |
| waveHeight | Float | 파고 (m) |
| wavePeriod | Float | 파주기 (s) |
| windSpeed | Float | 풍속 (m/s) |
| shipSpeed | Float | 선속 (knots) |
| iceThickness | Float | 빙두께 (m) |
| pressure | Float | 압력 (bar) |

**ModelShip (모형선)**

| 속성 | 타입 | 설명 |
|------|------|------|
| modelId | String | 모형 ID |
| scale | Float | 축척비 |
| modelLength | Float | 모형 길이 (m) |
| fullScaleLength | Float | 실선 길이 (m) |
| shipType | String | 선종 |
| hullForm | String | 선형 정보 |

**Measurement (계측)**

| 속성 | 타입 | 설명 |
|------|------|------|
| measurementId | String | 계측 ID |
| measurementType | Enum | 계측 유형 |
| value | Float | 계측값 |
| unit | String | 단위 |
| timestamp | DateTime | 계측 시각 |
| uncertainty | Float | 불확도 |

계측 유형:
- `Resistance` (저항)
- `Propulsion` (추진)
- `Maneuvering` (조종)
- `Seakeeping` (내항성)
- `IcePerformance` (빙해 성능)
- `StructuralResponse` (구조 응답)

### 5.2 핵심 관계 (Relationships)

#### 5.2.1 물리적 관계 (Physical Relationships)

| 관계 | 시작 노드 | 종료 노드 | 설명 | 속성 |
|------|----------|----------|------|------|
| `LOCATED_AT` | Vessel | GeoPoint | 선박 현재 위치 | timestamp |
| `DOCKED_AT` | Vessel | PortFacility(Berth) | 선박 접안 | since, until |
| `ANCHORED_AT` | Vessel | PortFacility(Anchorage) | 선박 정박 | since, until |
| `HAS_FACILITY` | Port | PortFacility | 항만-시설 소속 | - |
| `CONNECTED_VIA` | Port | Waterway | 항만 간 항로 연결 | distance |

#### 5.2.2 운영적 관계 (Operational Relationships)

| 관계 | 시작 노드 | 종료 노드 | 설명 | 속성 |
|------|----------|----------|------|------|
| `ON_VOYAGE` | Vessel | Voyage | 선박의 항해 | role |
| `FROM_PORT` | Voyage | Port | 출항지 | departureTime |
| `TO_PORT` | Voyage | Port | 도착지 | arrivalTime |
| `CONSISTS_OF` | Voyage | TrackSegment | 항해 구간 구성 | order |
| `CARRIES` | Vessel | Cargo | 선박의 화물 적재 | loadedAt, quantity |
| `PERFORMS` | Vessel | Activity | 선박의 활동 수행 | - |

#### 5.2.3 관측적 관계 (Observational Relationships)

| 관계 | 시작 노드 | 종료 노드 | 설명 | 속성 |
|------|----------|----------|------|------|
| `PRODUCES` | Sensor | Observation | 센서의 관측 데이터 생성 | - |
| `DEPICTS` | Observation | Entity | 관측이 묘사하는 대상 | confidence |
| `OBSERVED_AT` | Observation | GeoPoint | 관측 위치 | - |
| `HAS_EMBEDDING` | Entity | Embedding | 엔티티의 임베딩 표현 | - |
| `DETECTED` | Observation | Vessel | 관측에서 탐지된 선박 | confidence, bbox |
| `IDENTIFIED` | Observation | Vessel | 관측에서 식별된 선박 | method, confidence |
| `TRACKED` | Observation | Vessel | 관측에서 추적된 선박 | trackId, duration |

#### 5.2.4 크로스모달 관계 (Cross-modal Relationships)

| 관계 | 시작 노드 | 종료 노드 | 설명 | 속성 |
|------|----------|----------|------|------|
| `MATCHED_WITH` | Observation | Observation | 이종 관측 간 매칭 | similarity, method |
| `SAME_ENTITY` | Entity | Entity | 동일 대상 식별 | confidence, evidence |

#### 5.2.5 환경적 관계 (Environmental Relationships)

| 관계 | 시작 노드 | 종료 노드 | 설명 | 속성 |
|------|----------|----------|------|------|
| `AFFECTS` | WeatherCondition | SeaArea | 기상이 해역에 미치는 영향 | severity |
| `CAUSED_BY` | Incident | WeatherCondition | 사고 원인 기상 | contribution |
| `OCCURRED_AT` | Incident | GeoPoint | 사고 발생 위치 | - |
| `INVOLVES` | Incident | Vessel | 사고 관련 선박 | role |

#### 5.2.6 규정적 관계 (Regulatory Relationships)

| 관계 | 시작 노드 | 종료 노드 | 설명 | 속성 |
|------|----------|----------|------|------|
| `APPLIES_TO` | Regulation | SeaArea/Vessel | 규정 적용 대상 | scope |
| `ENFORCED_BY` | Regulation | Organization | 규정 시행 기관 | - |
| `VIOLATED` | Vessel | Regulation | 규정 위반 | incidentId, date |
| `DESCRIBES` | Document | Entity | 문서가 설명하는 대상 | - |
| `ISSUED_BY` | Document | Organization | 문서 발행 기관 | - |

#### 5.2.7 서비스 관계 (Service Relationships)

| 관계 | 시작 노드 | 종료 노드 | 설명 | 속성 |
|------|----------|----------|------|------|
| `USES_DATA` | Service | DataSource | 서비스의 데이터 사용 | - |
| `REQUIRES_INPUT` | Service | DataSource | 서비스의 입력 요구 | format |
| `PRODUCES_OUTPUT` | Service | DataSource | 서비스의 출력 생산 | format |
| `PROVIDED_BY` | Service | Organization | 서비스 제공 기관 | - |
| `COMPOSED_IN` | Service | Workflow | 서비스의 워크플로우 구성 | order |

#### 5.2.8 리니지 관계 (Lineage Relationships)

| 관계 | 시작 노드 | 종료 노드 | 설명 | 속성 |
|------|----------|----------|------|------|
| `FEEDS` | DataSource | Service | 데이터소스의 서비스 공급 | - |
| `GENERATES` | Service | DataSource | 서비스의 데이터 생성 | - |
| `DERIVED_FROM` | Entity | Entity | 파생 관계 | method, timestamp |

#### 5.2.9 KRISO 관계 (KRISO Relationships)

| 관계 | 시작 노드 | 종료 노드 | 설명 | 속성 |
|------|----------|----------|------|------|
| `CONDUCTED_AT` | Experiment | TestFacility | 실험 수행 시설 | - |
| `TESTED` | Experiment | ModelShip | 실험 대상 모형선 | - |
| `PRODUCED` | Experiment | ExperimentalDataset | 실험 결과 데이터 | - |
| `UNDER_CONDITION` | Experiment | TestCondition | 실험 조건 | - |
| `MODEL_OF` | ModelShip | Vessel | 모형선의 실선 대응 | scale |

---

## 6. 멀티모달 지식그래프 구축 파이프라인

멀티모달 지식그래프(MMKG: Multimodal Maritime Knowledge Graph)는 이질적인 해사 데이터를 통합하는 핵심 파이프라인이다. 3단계로 구성된다.

### 6.1 Phase 1: 모달리티별 지식 추출

각 데이터 소스에서 구조화된 엔티티와 관계를 추출한다.

| 데이터 소스 | 추출 도구 | 추출 결과 |
|------------|----------|----------|
| **위성영상 (SAR/광학)** | YOLOv8 / RT-DETR | 선박 탐지 (bbox, 위치, 크기), 시각 임베딩 |
| **CCTV 영상** | YOLOv8 + DeepSORT + PaddleOCR | 선박 탐지/추적, 선명 인식, 시각 임베딩 |
| **AIS 데이터** | NMEA Parser + 궤적 분석기 | 선박 위치, 속도, 침로, 궤적, 행동 패턴 |
| **해사 문서** | Unstructured + LLM NER | 엔티티(선박, 항만, 사고), 관계, 규정 참조 |
| **기상 데이터** | GRIB2/NetCDF 파서 | 기상 관측값, 예보, 위험 기상 경보 |
| **GIS 데이터** | 공간 처리 엔진 (GDAL/Shapely) | 해역 경계, 항로 경로, 항만 위치, 수심 |

**세부 처리 흐름**:

```
위성영상 → 전처리(보정/클리핑) → YOLOv8(선박탐지) → CLIP(임베딩) → (Vessel, SARObservation) 노드 생성
CCTV    → 프레임추출 → YOLOv8(탐지) → DeepSORT(추적) → PaddleOCR(선명) → (Vessel, CCTVObservation) 노드 생성
AIS     → NMEA 디코딩 → 정규화 → 궤적분할 → 이상행동탐지 → (AISObservation, TrackSegment) 노드 생성
문서     → Unstructured(파싱) → LLM NER(엔티티추출) → 관계추출 → (Document, Regulation, Incident) 노드 생성
기상     → GRIB2 파싱 → 시공간 그리드 생성 → (WeatherObservation, WeatherCondition) 노드 생성
GIS     → Shapefile/GeoJSON 로딩 → 공간 인덱싱 → (SeaArea, Waterway, Port) 노드 생성
```

### 6.2 Phase 2: 크로스모달 엔티티 정렬

서로 다른 모달리티에서 추출된 엔티티가 동일 대상을 가리키는지 정렬(alignment)한다.

#### 정렬 전략

| 정렬 방법 | 적용 대상 | 기법 |
|----------|----------|------|
| **시공간 매칭** | 위성-AIS, CCTV-AIS, 레이더-AIS | 시간 윈도우(+/- 5분) + 공간 거리(< 500m) 기반 매칭 |
| **CLIP 임베딩 유사도** | 위성-CCTV, 이미지-텍스트 | 시각 임베딩 코사인 유사도 기반 매칭 (threshold > 0.85) |
| **ID 매칭** | AIS-문서, 입출항-항만 | MMSI, IMO 번호, UNLOCODE 등 식별자 기반 정확 매칭 |

#### 정렬 프로세스

```
1. 시공간 매칭:
   - 위성 탐지 선박 위치+시간 ↔ AIS 위치+시간 → 후보 매칭 쌍 생성
   - 거리 < 500m AND 시간차 < 5분 → MATCHED_WITH 관계 생성

2. CLIP 임베딩 유사도:
   - 위성 선박 이미지 → CLIP 임베딩 생성
   - CCTV 선박 이미지 → CLIP 임베딩 생성
   - 코사인 유사도 > 0.85 → SAME_ENTITY 관계 생성

3. ID 매칭:
   - AIS의 MMSI/IMO ↔ 문서의 선박 ID → 동일 선박 확인
   - 입출항 기록의 UNLOCODE ↔ 항만 데이터 → DOCKED_AT 관계 생성
```

### 6.3 Phase 3: 통합 그래프 저장 (Neo4j)

정렬된 엔티티와 관계를 Neo4j에 통합 저장한다.

#### 저장 전략

- **노드 생성**: 각 엔티티를 Neo4j 노드로 생성 (라벨 = 엔티티 유형)
- **관계 생성**: 정렬된 매칭 결과를 기반으로 관계(Edge) 생성
- **벡터 인덱스**: 임베딩 벡터에 대한 HNSW 벡터 인덱스 생성
- **공간 인덱스**: Point 속성에 대한 공간 인덱스 생성
- **전문 검색 인덱스**: 텍스트 속성에 대한 전문 검색 인덱스 생성

#### 인덱스 설계

```cypher
-- 벡터 인덱스 (시각 임베딩)
CREATE VECTOR INDEX vessel_visual_embedding FOR (v:Vessel) ON v.visualEmbedding
OPTIONS {indexConfig: {`vector.dimensions`: 512, `vector.similarity_function`: 'cosine'}}

-- 벡터 인덱스 (텍스트 임베딩)
CREATE VECTOR INDEX document_text_embedding FOR (d:Document) ON d.textEmbedding
OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}

-- 공간 인덱스
CREATE POINT INDEX vessel_location FOR (v:Vessel) ON v.location

-- 전문 검색 인덱스
CREATE FULLTEXT INDEX document_search FOR (d:Document) ON EACH [d.title, d.content]
```

#### 갱신 주기

| 데이터 유형 | 갱신 주기 | 방법 |
|-----------|----------|------|
| AIS | 실시간 (1-30초) | Kafka Consumer → Neo4j Sink |
| 기상 | 1시간 | 스케줄러 배치 |
| 위성영상 | 6-12시간 | 이벤트 기반 (새 영상 수신 시) |
| CCTV | 실시간 (1분) | 스트림 프로세서 |
| 문서 | 일 1회 | 배치 크롤링 및 처리 |
| GIS | 월 1회 | 수동 갱신 |

---

## 7. KRISO 데이터 전략

KRISO 데이터는 프로젝트 진행 단계에 따라 2단계 전략을 수립한다.

### 7.1 Phase A (현재): 크롤링 기반 메타데이터 확보

공식 데이터 수신 전, 공개된 정보를 크롤링하여 메타데이터를 선제적으로 확보한다.

| 수집 대상 | 수집 규모 | 수집 내용 |
|----------|----------|----------|
| **KRISO ScholarWorks** | 11,159건 | 연구 논문/보고서 메타데이터 (제목, 저자, 초록, 키워드, 발행일) |
| **시설 페이지** | 6개 시험시설 | 시설 제원, 능력, 장비 목록 |
| **뉴스룸** | 최근 2년간 | 연구 성과, 보도자료, 이벤트 |
| **KOLOMVERSE** | 가용 데이터 | 해양 가상현실 관련 데이터 |

**크롤링 구현**:

```python
# Scrapy 스파이더 구조
class KRISOScholarWorksSpider(scrapy.Spider):
    name = "kriso_scholarworks"
    # 메타데이터: title, authors, abstract, keywords, date, doi
    # 저장: Neo4j (Document 노드) + MinIO (PDF 원본)
    # source 필드: "scholarworks_crawl"
```

### 7.2 Phase B (향후): 공식 데이터 수신 및 통합

KRISO와의 공식 데이터 공유 협약 체결 후, 원본 실험 데이터를 수신하여 기존 메타데이터를 보강한다.

| 수신 데이터 | 연동 방식 | 처리 내용 |
|-----------|----------|----------|
| 실험 원본 데이터 | API / 파일 전송 | 실험 데이터셋 노드 생성, MinIO 저장 |
| 정밀 메타데이터 | 구조화된 JSON/XML | 기존 크롤링 메타데이터 교체/보강 |
| 시설 상세 정보 | API | TestFacility 노드 상세 업데이트 |
| 모형선 데이터 | 파일 전송 | ModelShip 노드 생성, 실선 연결 |

### 7.3 전환 규칙

크롤링 데이터에서 공식 데이터로의 전환을 체계적으로 관리한다.

| 규칙 | 설명 |
|------|------|
| **source 필드 구분** | 모든 KRISO 노드에 `source` 속성 부여 |
| **크롤링 데이터** | `source: "scholarworks_crawl"` |
| **공식 데이터** | `source: "kriso_official"` |
| **전환 시 처리** | 동일 엔티티 매칭 → 공식 데이터로 속성 업데이트 → source 변경 |
| **이력 보존** | 원본 크롤링 데이터는 `_crawl_snapshot` 속성으로 보존 |

**전환 Cypher 예시**:

```cypher
// 공식 데이터 수신 시 기존 크롤링 데이터 업데이트
MATCH (d:Document {source: 'scholarworks_crawl', doi: $doi})
SET d.source = 'kriso_official',
    d._crawl_snapshot = properties(d),
    d.title = $official_title,
    d.abstract = $official_abstract,
    d.fullDatasetURI = $dataset_uri,
    d.updatedAt = datetime()
```

---

## 8. 대화형 시나리오

### 8.1 시나리오 1: 자연어 → 데이터 조회

**사용자**: 해양 공무원
**질문**: "부산항에 현재 정박 중인 위험물 적재 선박 현황을 알려줘"

**처리 흐름**:

```
1. 사용자 입력 수신
   → "부산항에 현재 정박 중인 위험물 적재 선박 현황을 알려줘"

2. LangGraph 에이전트 분류
   → 의도: 데이터 조회 (GraphCypherQAChain 라우팅)

3. Text-to-Cypher 변환 (Qwen 2.5 VL + GraphCypherQAChain)
   → MATCH (p:Port {name: '부산항'})-[:HAS_FACILITY]->(f:PortFacility)
     <-[:DOCKED_AT|ANCHORED_AT]-(v:Vessel)-[:CARRIES]->(c:Cargo)
     WHERE c.cargoType = 'DangerousGoods'
     AND v.status IN ['정박', '계류']
     RETURN v.name, v.mmsi, v.vesselType, c.imdgClass, c.description,
            f.facilityId

4. Neo4j 쿼리 실행
   → 결과: 5척의 위험물 적재 선박 정보

5. 응답 생성
   → "부산항에 현재 5척의 위험물 적재 선박이 정박/계류 중입니다.
      1. 한진오사카호 (MMSI: 440XXXXXX) - 3등급 인화성 액체, 2번 선석
      2. 현대글로벌호 (MMSI: 440XXXXXX) - 8등급 부식성 물질, 5번 선석
      ..."

6. 시각화 (선택)
   → 지도에 선박 위치 표시 + 위험물 등급별 색상 구분
```

### 8.2 시나리오 2: 자연어 → 워크플로우 생성

**사용자**: 해양 공무원
**질문**: "매일 아침 6시에 Sentinel-1 위성영상에서 우리나라 EEZ 내 미식별 선박을 탐지해서 슬랙으로 알려줘"

**처리 흐름**:

```
1. 사용자 입력 수신
   → "매일 아침 6시에 Sentinel-1 위성영상에서 우리나라 EEZ 내 미식별 선박을
      탐지해서 슬랙으로 알려줘"

2. LangGraph 에이전트 분류
   → 의도: 워크플로우 생성

3. 워크플로우 구성 분석 (LLM)
   → 필요 노드:
     - 트리거: 스케줄 (매일 06:00 KST)
     - 데이터 수집: Sentinel-1 위성영상 다운로드 (pystac)
     - 영역 필터: 대한민국 EEZ 폴리곤 클리핑
     - AI 처리: YOLOv8 선박 탐지
     - 매칭: 탐지 선박 ↔ AIS 데이터 매칭
     - 필터: 미매칭(미식별) 선박만 추출
     - 알림: Slack 메시지 전송

4. Activepieces Flow JSON 생성
   → 7개 노드로 구성된 워크플로우 자동 생성

5. 미리보기 제공
   → "다음과 같은 워크플로우를 생성했습니다:
      [스케줄(06:00)] → [Sentinel-1 다운로드] → [EEZ 클리핑]
      → [YOLOv8 탐지] → [AIS 매칭] → [미식별 필터] → [Slack 알림]
      실행하시겠습니까?"

6. 사용자 확인 후 워크플로우 배포 및 활성화
```

### 8.3 시나리오 3: 멀티모달 질의

**사용자**: 해사 연구자
**질문**: (위성영상 첨부) "이 위성영상에서 보이는 선박들을 분석해줘. 어떤 선박이고 무엇을 하고 있는 것 같아?"

**처리 흐름**:

```
1. 사용자 입력 수신 (이미지 + 텍스트)
   → 위성영상 파일 + "이 위성영상에서 보이는 선박들을 분석해줘"

2. 멀티모달 LLM (Qwen 2.5 VL) 1차 분석
   → 영상 유형 식별: SAR 영상 (Sentinel-1)
   → 대략적 위치 추정: 남해안 부근
   → 선박 수: 약 7척 식별

3. 전문 모델 호출 (YOLOv8)
   → 선박 7척 정밀 탐지 (bbox, 크기 추정, 신뢰도)
   → 선박 유형 분류: 화물선 3, 유조선 1, 어선 2, 미분류 1

4. 크로스모달 매칭
   → 탐지 위치+시간 ↔ AIS 데이터 매칭
   → 6척 식별 성공, 1척 미식별 (Dark Vessel 의심)

5. 지식그래프 조회
   → 식별된 6척의 상세 정보 (선명, 소속, 항행 목적 등)
   → 미식별 1척의 행동 패턴 분석 (배회 감지)

6. 통합 응답 생성
   → "분석 결과:
      - 총 7척의 선박이 탐지되었습니다.
      - 식별된 선박 6척: (목록 및 상세 정보)
      - 미식별 선박 1척: 남해 34.5N, 128.3E 부근에서 배회 중.
        AIS 신호 미수신으로 Dark Vessel 의심. 크기 약 45m로 추정.
      - 권장 조치: 해경 VTS에 미식별 선박 신고 검토"
```

### 8.4 시나리오 4: KRISO 데이터 조회

**사용자**: 해사 연구자
**질문**: "파고 3m 조건에서 8,000TEU급 컨테이너선의 저항 시험 데이터를 찾아줘"

**처리 흐름**:

```
1. 사용자 입력 수신
   → "파고 3m 조건에서 8,000TEU급 컨테이너선의 저항 시험 데이터를 찾아줘"

2. LangGraph 에이전트 분류
   → 의도: KRISO 데이터 조회

3. Text-to-Cypher 변환
   → MATCH (e:Experiment)-[:UNDER_CONDITION]->(tc:TestCondition),
           (e)-[:TESTED]->(ms:ModelShip),
           (e)-[:PRODUCED]->(ds:ExperimentalDataset),
           (e)-[:CONDUCTED_AT]->(tf:TestFacility)
     WHERE tc.waveHeight >= 2.5 AND tc.waveHeight <= 3.5
     AND ms.shipType CONTAINS 'Container'
     AND ms.fullScaleLength >= 300
     RETURN e.title, e.experimentId, tc.waveHeight, tc.wavePeriod,
            ms.scale, ms.fullScaleLength,
            ds.format, ds.storageURI,
            tf.name

4. Neo4j 쿼리 실행
   → 결과: 3건의 실험 데이터

5. 응답 생성
   → "파고 3m 조건의 대형 컨테이너선 저항 시험 데이터 3건을 찾았습니다:

      1. KRISO-2024-R-0142: 8,200TEU 컨테이너선 저항/추진 시험
         - 시설: 예인수조 (200m x 16m x 7m)
         - 조건: 파고 3.0m, 파주기 8.5s
         - 모형선: 1:30 축척 (실선 350m)
         - 데이터: CSV, 100Hz 샘플링
         - [데이터 다운로드] [상세 보기]

      2. KRISO-2023-R-0087: ...
      3. KRISO-2023-R-0223: ...

      관련 논문도 확인하시겠습니까?"
```

---

## 9. 하드웨어 요구사항

### 9.1 서버 구성

| 구성 | 사양 | 수량 | 용도 | 비고 |
|------|------|------|------|------|
| **GPU 서버** | - CPU: AMD EPYC 7763 (64코어) 이상<br>- RAM: 256GB DDR4 ECC<br>- GPU: NVIDIA A100 80GB x 1~2<br>- SSD: NVMe 2TB<br>- NIC: 100GbE | 1대 | AI 모델 서빙 (Qwen 2.5 VL, YOLOv8, CLIP 등) | vLLM 기반 서빙, GPU 메모리 80GB로 7B 모델 동시 2개 서빙 가능 |
| **앱 서버** | - CPU: Intel Xeon 또는 AMD EPYC 32코어<br>- RAM: 128GB DDR4 ECC<br>- SSD: NVMe 1TB<br>- NIC: 25GbE | 1~2대 | 프론트엔드 (Next.js), 워크플로우 엔진 (Activepieces), API GW (Kong), 인증 (Keycloak) | Kubernetes 클러스터로 운영 |
| **DB 서버** | - CPU: Intel Xeon 또는 AMD EPYC 16코어<br>- RAM: 64GB DDR4 ECC<br>- SSD: NVMe 2TB (RAID-1)<br>- HDD: 4TB (백업)<br>- NIC: 25GbE | 1대 | Neo4j, TimescaleDB, PostgreSQL | SSD 필수 (그래프 순회 I/O 성능) |
| **스토리지 서버** | - CPU: 8코어<br>- RAM: 32GB<br>- HDD: 10TB+ (RAID-6 또는 erasure coding)<br>- NIC: 25GbE | 1~2대 | MinIO (멀티모달 파일 저장) | 위성영상, CCTV, 문서 원본 저장 |

### 9.2 네트워크 요구사항

| 항목 | 사양 | 비고 |
|------|------|------|
| 내부 네트워크 | 25GbE 이상 | 서버 간 통신 |
| GPU-스토리지 간 | 100GbE 권장 | 대용량 영상 데이터 전송 |
| 외부 네트워크 | 1Gbps 이상 | 사용자 접속 및 외부 API 연동 |
| Kafka 클러스터 | 10GbE 이상 | AIS 실시간 스트림 처리 |

### 9.3 예상 리소스 사용량

| 서비스 | CPU | RAM | GPU | 스토리지 |
|--------|-----|-----|-----|---------|
| Qwen 2.5 VL 7B (vLLM) | 8코어 | 32GB | A100 80GB x 1 | 20GB (모델 가중치) |
| YOLOv8 + RT-DETR | 4코어 | 8GB | A100 공유 (10GB) | 5GB |
| CLIP / ImageBind | 2코어 | 4GB | A100 공유 (8GB) | 3GB |
| Neo4j | 8코어 | 32GB | - | 500GB (초기) ~ 2TB |
| TimescaleDB | 4코어 | 16GB | - | 200GB (초기) ~ 1TB |
| Kafka | 4코어 | 8GB | - | 100GB |
| Activepieces | 4코어 | 8GB | - | 10GB |
| Next.js / Kong / Keycloak | 4코어 | 16GB | - | 20GB |
| MinIO | 2코어 | 8GB | - | 10TB+ |
| Grafana + Prometheus | 2코어 | 4GB | - | 50GB |

---

## 10. 라이선스 요약

### 10.1 라이선스 분류

| 분류 | 라이선스 | 해당 기술 | 의무 사항 |
|------|---------|----------|----------|
| **완전 자유** | MIT | Next.js, React Flow, LangChain, LangGraph, CLIP, Qwen 2.5 VL, MiniCPM-V, Activepieces, DeepSORT, pystac | 저작권 고지만 필요, 소스 공개 의무 없음 |
| **완전 자유** | Apache 2.0 | Apache Kafka, Keycloak, Kong, PaddleOCR, TimescaleDB, vLLM, RT-DETR, Unstructured, n10s | 저작권 고지 + 변경 사항 고지, 소스 공개 의무 없음 |
| **완전 자유** | BSD | Leaflet / MapLibre, Scrapy, Protege | 저작권 고지만 필요 |
| **완전 자유** | PostgreSQL License | PostgreSQL | BSD 유사, 자유 사용 |
| **소스 공개 의무** | GPLv3 | Neo4j Community | Neo4j를 수정/배포 시 소스 공개 필요. 단, 네트워크 서비스로만 제공 시에는 공개 의무 없음 (GPLv3는 AGPL과 다름) |
| **소스 공개 의무** | AGPL-3.0 | MinIO, Grafana, YOLOv8 | 네트워크 서비스로 제공해도 소스 공개 필요. 단, 수정하지 않고 그대로 사용 시에는 원본 소스로 갈음 가능 |

### 10.2 라이선스 리스크 및 대응

| 리스크 | 해당 기술 | 대응 방안 |
|--------|----------|----------|
| AGPL 전염 | MinIO | MinIO를 독립 서비스로 운영, 자체 코드와 링킹하지 않음 |
| AGPL 전염 | YOLOv8 | 수정 시 해당 모듈만 소스 공개, 또는 Apache 2.0인 RT-DETR로 대체 |
| AGPL 전염 | Grafana | 수정 없이 표준 배포판 사용, 커스텀 대시보드는 프로비저닝으로 관리 |
| GPLv3 전염 | Neo4j Community | Neo4j를 독립 데이터베이스 서버로 운영, Bolt 프로토콜로만 접근 |

### 10.3 정부 R&D 라이선스 고려사항

- 모든 핵심 구성요소가 오픈소스로, 정부 R&D 과제의 **기술 종속성 최소화** 요건 충족
- 상용 라이선스 비용 없이 전체 플랫폼 구축 가능
- GPLv3/AGPL 구성요소는 독립 서비스로 운영하여 자체 코드의 공개 의무를 최소화
- 프로젝트 종료 후에도 라이선스 비용 없이 지속 운영 가능

---

## 11. 구축 로드맵

### 11.1 전체 일정 개요

```
Phase 1 ████████░░░░░░░░░░░░░░░░░░░░░░  기반 구축
Phase 2 ░░░░░░░░████████░░░░░░░░░░░░░░  데이터 파이프라인
Phase 3 ░░░░░░░░░░░░░░░░████████░░░░░░  AI 엔진
Phase 4 ░░░░░░░░░░░░░░░░░░░░░░░░██████  MMKG 고도화
Phase 5 ░░░░░░░░░░░░░░░░░░░░░░░░░░████  통합 및 검증
```

### 11.2 Phase 1: 기반 구축

**목표**: 플랫폼의 핵심 인프라와 기초 구성요소를 구축한다.

| 작업 항목 | 세부 내용 | 산출물 |
|----------|----------|--------|
| **온톨로지 설계** | Protege를 활용한 해사 온톨로지 OWL 설계, 핵심 엔티티/관계 정의 | `maritime-ontology.owl` |
| **Neo4j 환경 구축** | Neo4j Community 배포, n10s로 온톨로지 임포트, 인덱스 생성 | Neo4j 인스턴스, 스키마 |
| **Activepieces 포크** | Activepieces 소스 포크, 빌드 환경 구성, 해사 확장 모듈 구조 설계 | 포크 저장소, 빌드 파이프라인 |
| **Keycloak + Kong 설정** | SSO 환경 구축, API GW 설정, 기본 인증/인가 정책 | 인증 시스템, API GW |
| **프론트엔드 골격** | Next.js 프로젝트 초기화, 라우팅 구조, UI 컴포넌트 라이브러리, React Flow 통합 | 프론트엔드 프로젝트 |
| **Kubernetes 클러스터** | K8s 환경 구성, Helm 차트 작성, CI/CD 파이프라인 | 인프라 코드 (IaC) |
| **모니터링 스택** | Grafana + Prometheus 배포, 기본 대시보드 구성 | 모니터링 환경 |

### 11.3 Phase 2: 데이터 파이프라인

**목표**: 해사 데이터를 수집하고 저장하는 파이프라인을 구축한다.

| 작업 항목 | 세부 내용 | 산출물 |
|----------|----------|--------|
| **해사 API 연동** | 해수부, 조사원, 기상청 등 공공 API 연동 어댑터 개발 | API 어댑터 모듈 |
| **AIS 실시간 스트림** | Kafka 클러스터 구축, AIS NMEA 디코더, TimescaleDB 저장 파이프라인 | AIS 수집 파이프라인 |
| **위성영상 수집** | pystac 기반 Sentinel-1/2 자동 다운로드, MinIO 저장, 메타데이터 등록 | 위성영상 수집 파이프라인 |
| **CCTV 수집** | RTSP 스트림 연결, 프레임 추출, MinIO 저장 | CCTV 수집 파이프라인 |
| **KRISO 크롤러** | Scrapy 기반 ScholarWorks 크롤러, 메타데이터 파싱, Neo4j 저장 | KRISO 메타데이터 (11,159건) |
| **MMKG 추출 파이프라인** | 모달리티별 엔티티 추출 워커 개발 (1차 배치) | 추출 파이프라인 (초기) |
| **GIS 데이터 적재** | 해역 경계, 항만 위치, 항로 데이터를 Neo4j에 적재 | 공간 데이터 레이어 |

### 11.4 Phase 3: AI 엔진

**목표**: 대화형 AI 엔진과 전문 모델을 배포하고 통합한다.

| 작업 항목 | 세부 내용 | 산출물 |
|----------|----------|--------|
| **Qwen 2.5 VL 배포** | vLLM 기반 서빙 환경 구축, A100 GPU 최적화, 벤치마크 | LLM 서빙 API |
| **전문 모델 배포** | YOLOv8(선박탐지), PaddleOCR(문서OCR), CLIP(임베딩) 배포 | 전문 모델 API |
| **LangChain + GraphCypherQAChain** | 자연어→Cypher 파이프라인 구축, 해사 도메인 프롬프트 최적화 | Text-to-Cypher 엔진 |
| **LangGraph 에이전트** | 멀티스텝 에이전트 오케스트레이션, 의도 분류, 라우팅 로직 | 에이전트 시스템 |
| **RAG 파이프라인** | 해사 규정/문서의 벡터 임베딩, GraphRAG 통합 | RAG 서비스 |
| **워크플로우 자동 생성** | 자연어→Activepieces Flow JSON 생성 LLM 파이프라인 | 워크플로우 생성 API |
| **대화 UI** | 채팅 인터페이스, 이미지 업로드, 응답 시각화 통합 | 대화형 프론트엔드 |

### 11.5 Phase 4: MMKG 고도화

**목표**: 멀티모달 지식그래프의 품질을 높이고 크로스모달 기능을 완성한다.

| 작업 항목 | 세부 내용 | 산출물 |
|----------|----------|--------|
| **크로스모달 정렬** | 시공간 매칭, CLIP 유사도 매칭, ID 매칭 파이프라인 완성 | 엔티티 정렬 엔진 |
| **GraphRAG 고도화** | 그래프 순회 기반 컨텍스트 확장, 멀티홉 추론 지원 | 고도화된 RAG |
| **도메인 파인튜닝** | 해사 도메인 데이터로 Qwen 2.5 VL LoRA 파인튜닝 | 파인튜닝 모델 |
| **DeepSORT 통합** | CCTV 실시간 선박 추적, ID 유지, 궤적 생성 | 선박 추적 시스템 |
| **ImageBind 통합** | 멀티모달 융합 임베딩 생성, FusedEmbedding 저장 | 크로스모달 검색 |
| **KRISO Phase B 준비** | 공식 데이터 수신 인터페이스, 전환 파이프라인 개발 | KRISO 통합 모듈 |

### 11.6 Phase 5: 통합 및 검증

**목표**: 전체 시스템을 통합하고 품질을 검증한다.

| 작업 항목 | 세부 내용 | 산출물 |
|----------|----------|--------|
| **통합 테스트** | 엔드투엔드 시나리오 테스트 (8절의 4개 시나리오 검증) | 테스트 보고서 |
| **성능 최적화** | LLM 응답 시간 최적화, 쿼리 성능 튜닝, 캐싱 전략 | 성능 보고서 |
| **사용자 테스트** | 실 사용자(해양 공무원, 연구자 등) 대상 UAT(User Acceptance Test) | UAT 결과 보고서 |
| **보안 감사** | 취약점 스캔, 인증/인가 검증, 데이터 보호 검증 | 보안 감사 보고서 |
| **문서화** | 사용자 매뉴얼, 관리자 가이드, API 문서, 시스템 아키텍처 문서 | 프로젝트 문서 |
| **배포 및 인수** | 운영 환경 최종 배포, 운영 인수인계, SLA 정의 | 배포 완료 보고서 |

### 11.7 마일스톤 요약

| 마일스톤 | 완료 기준 |
|---------|----------|
| **M1: 기반 구축 완료** | Neo4j 스키마 구축, Activepieces 포크 빌드, 인증/GW 동작, 프론트엔드 골격 확인 |
| **M2: 데이터 수집 동작** | AIS 실시간 수집 확인, 위성영상 자동 다운로드 확인, KRISO 메타데이터 11,159건 적재 |
| **M3: AI 대화 가능** | 자연어→Cypher 조회 동작, 멀티모달 질의 응답, RAG 기반 규정 응답 |
| **M4: MMKG 완성** | 크로스모달 정렬 동작, GraphRAG 멀티홉 추론 확인, 파인튜닝 모델 적용 |
| **M5: 최종 검증 완료** | 4개 시나리오 통과, 성능 SLA 달족, 보안 감사 통과, 사용자 테스트 완료 |

---

## 부록

### A. 용어 정의

| 용어 | 정의 |
|------|------|
| AIS | Automatic Identification System. 선박 자동식별장치 |
| COLREG | Convention on the International Regulations for Preventing Collisions at Sea. 국제해상충돌예방규칙 |
| Cypher | Neo4j의 그래프 쿼리 언어 |
| EEZ | Exclusive Economic Zone. 배타적 경제수역 |
| GraphRAG | Graph-based Retrieval-Augmented Generation. 그래프 기반 검색증강생성 |
| IMDG | International Maritime Dangerous Goods Code. 국제해상위험물규칙 |
| KG | Knowledge Graph. 지식그래프 |
| KRISO | Korea Research Institute of Ships and Ocean Engineering. 선박해양플랜트연구소 |
| MARPOL | International Convention for the Prevention of Pollution from Ships. 해양오염방지협약 |
| MMKG | Multimodal Maritime Knowledge Graph. 멀티모달 해사 지식그래프 |
| MMSI | Maritime Mobile Service Identity. 해상이동업무식별번호 |
| NMEA | National Marine Electronics Association. 해양전자기기 통신 프로토콜 |
| RAG | Retrieval-Augmented Generation. 검색증강생성 |
| SAR | Synthetic Aperture Radar. 합성개구레이더 |
| SOLAS | International Convention for the Safety of Life at Sea. 해상인명안전협약 |
| TSS | Traffic Separation Scheme. 통항분리수역 |
| UNLOCODE | United Nations Code for Trade and Transport Locations |

### B. 참고 문서

- IMO IMDG Code (국제해상위험물규칙)
- IHO S-100 Universal Hydrographic Data Model
- OGC SensorThings API
- W3C Web of Things (WoT)
- STAC (SpatioTemporal Asset Catalog) Specification
- Activepieces Piece SDK Documentation
- Neo4j Graph Data Science Library Documentation
- LangChain / LangGraph Documentation

---

> **문서 끝**
> 본 문서는 대화형 해사서비스 플랫폼의 기초 설계 문서로서, 프로젝트 진행에 따라 지속적으로 갱신됩니다.
