# 21. 시각화 및 상호작용 아키텍처

[← NLP/NER 전략](./20-nlp-ner.md) | [→ 지식그래프 고급 아키텍처](./22-kg-advanced.md)

---

## 21.1 개요

IMSP 6대 개발 축 중 "가시화/상호작용"을 담당하는 아키텍처를 기술한다.
전자해도(S-100), 3D 렌더러, 대시보드, 서비스 포털, AR/VR 프로토타입까지
Y1-Y5에 걸쳐 단계적으로 고도화한다.

```
+---------------------------------------------------+
|              Presentation Tier                     |
+--------------------------+------------------------+
|  VueFlow Canvas          |  S-100 전자해도         |
|  (워크플로우 저작)        |  (해상교통 시각화)      |
+--------------------------+------------------------+
|  Dashboard               |  3D Renderer           |
|  (모니터링 + 분석)        |  (항만/수중 지형)      |
+--------------------------+------------------------+
|  Service Portal          |  AR/VR Prototype       |
|  (서비스 카탈로그)        |  (디지털 트윈)         |
+--------------------------+------------------------+
         |                          |
         v                          v
+--------------------------+------------------------+
|     Gateway API          |  WebSocket Server      |
|     (REST)               |  (실시간 스트리밍)      |
+--------------------------+------------------------+
```

---

## 21.2 시각화 컴포넌트 구조

### 컴포넌트 계층

```
ui/src/
+-- canvas/          # VueFlow 워크플로우 캔버스
|   +-- nodes/       # 커스텀 노드 컴포넌트 (6종)
|   +-- edges/       # 커스텀 엣지 컴포넌트
|   +-- panels/      # 속성 패널, 노드 팔레트
|   +-- composables/ # useWorkflow, useNodeDrag
|   +-- store/       # Pinia 상태 관리
|
+-- map/             # S-100 전자해도
|   +-- layers/      # AIS, 항로, 해역 레이어
|   +-- controls/    # 줌, 필터, 시간 슬라이더
|   +-- tiles/       # S-100 타일 로더
|
+-- renderer/        # 3D 렌더러
|   +-- scenes/      # 항만, 수중 지형 씬
|   +-- loaders/     # glTF, GeoTIFF 로더
|   +-- controls/    # OrbitControls, 측정 도구
|
+-- monitor/         # 대시보드
|   +-- widgets/     # 위젯 컴포넌트
|   +-- layouts/     # 그리드 레이아웃 엔진
|   +-- store/       # 위젯 상태 영속화
|
+-- portal/          # 서비스 포털
|   +-- catalog/     # 서비스 카탈로그
|   +-- mypage/      # 마이페이지
|   +-- search/      # 서비스 검색
|
+-- chat/            # 대화창
|   +-- global/      # 전역 대화 (Orchestrator Agent)
|   +-- node/        # 노드별 대화 (Node Agent)
|   +-- history/     # 대화 이력
|
+-- auth/            # Keycloak 연동
    +-- login/       # 로그인/로그아웃
    +-- guard/       # 라우트 가드
```

---

## 21.3 VueFlow 워크플로우 캔버스 (Y1-Y2)

### Y1 산출물: 워크플로우 노드 5종

RFP에서 Y1 산출물로 요구하는 "워크플로우 노드 5종"을 구현한다.

| # | 노드 타입 | 설명 | 아이콘 |
|---|----------|------|--------|
| 1 | DataSource | 데이터 소스 연결 (Ceph, DB, API) | 데이터베이스 |
| 2 | Transform | 데이터 변환 (필터, 매핑, 집계) | 톱니바퀴 |
| 3 | KGQuery | Knowledge Graph 질의 (Text2Cypher) | 그래프 |
| 4 | LLM | LLM 호출 (텍스트 생성, 분류, 요약) | 두뇌 |
| 5 | Visualization | 시각화 출력 (차트, 지도, 테이블) | 차트 |

### 캔버스 기능 로드맵

| 연차 | 기능 |
|------|------|
| Y1 Q3 | 기본 캔버스: 노드 드래그, 연결, 속성 패널 |
| Y1 Q4 | 노드 5종 구현, 워크플로우 저장/불러오기 |
| Y2 Q1 | 노드별 대화창 통합 (Node Agent 연동) |
| Y2 Q2 | Output 노드 (6번째), 워크플로우 실행 (Argo 연동) |
| Y2 Q3 | 노드 자동 생성 (LLM 기반 추천), 템플릿 갤러리 |

### VueFlow → Argo Workflow 변환

```
VueFlow JSON (프론트엔드 정의)
    |
    v
Workflow Compiler (gateway/routes/)
    |
    +-- 노드 → Argo Template 변환
    +-- 엣지 → DAG 의존관계 변환
    +-- 파라미터 → Argo Parameters 매핑
    |
    v
Argo Workflow YAML (실행 정의)
    |
    v
Argo Server API (K8s 실행)
```

---

## 21.4 S-100 전자해도 (Y2-Y3)

### IHO S-100 데이터 모델 연동

S-100은 국제수로기구(IHO)가 정의한 해양 데이터 표준이다.
IMSP는 S-100 기반 전자해도에 실시간 해상교통 데이터를 오버레이한다.

| 데이터 표준 | 내용 | 도입 시기 |
|------------|------|----------|
| S-101 | 전자항해해도 (ENC) | Y2 Q2 |
| S-102 | 수심 측량 격자 | Y3 Q1 |
| S-104 | 조석/조류 | Y3 Q2 |
| S-111 | 해수면 흐름 | Y3 Q3 |
| S-124 | 항행 경보 | Y2 Q3 |

### AIS 항적 오버레이

```
AIS 수신기 (VTS)
    |
    v
Kafka Topic: ais.positions
    |
    v
WebSocket Server (gateway/ws/)
    |
    v
OpenLayers Map (ui/src/map/)
    |
    +-- AIS 마커 레이어 (선박 위치, 침로, 속력)
    +-- 항적 라인 레이어 (최근 N시간 궤적)
    +-- 충돌 위험 레이어 (CPA/TCPA 계산 결과)
```

### 기술 구현

| 항목 | 기술 | 설명 |
|------|------|------|
| 지도 렌더링 | OpenLayers 9.x | 벡터/래스터 타일 렌더링 |
| 타일 서버 | GeoServer + S-100 플러그인 | S-100 데이터 → 타일 변환 |
| 실시간 업데이트 | WebSocket | AIS 위치 업데이트 (< 200ms) |
| 해역 경계 | GeoJSON | EEZ, 영해, 항만 구역 폴리곤 |
| 항로 표시 | GeoJSON LineString | TSS, 추천 항로 |

---

## 21.5 3D 렌더러 (Y3-Y4)

### Three.js 기반 3D 가시화

항만, 수중 지형, 선박 모델의 3D 렌더링을 수행한다.

```
Three.js Scene Graph
    |
    +-- 지형 (Terrain)
    |   +-- GeoTIFF -> HeightMap
    |   +-- LOD 3단계 (원거리/중거리/근거리)
    |
    +-- 항만 구조물 (Port Structures)
    |   +-- glTF 2.0 모델 (부두, 크레인, 건물)
    |   +-- 인스턴싱 (반복 구조물 최적화)
    |
    +-- 선박 (Vessels)
    |   +-- 선종별 3D 모델 (컨테이너선, 유조선 등)
    |   +-- AIS 위치 기반 실시간 배치
    |
    +-- 해수면 (Water Surface)
    |   +-- Shader 기반 파도 시뮬레이션
    |   +-- 조류 방향 화살표 오버레이
    |
    +-- 환경 (Environment)
        +-- Skybox, 조명 (시간대별 변화)
        +-- 기상 효과 (안개, 강우) -- Y4
```

### 데이터 포맷 및 최적화

| 포맷 | 용도 | 최적화 전략 |
|------|------|------------|
| glTF 2.0 | 3D 모델 (항만, 선박) | Draco 압축, LOD 생성 |
| GeoTIFF | 수심/지형 데이터 | 타일 분할, 점진적 로딩 |
| Cesium 3D Tiles | 대규모 지형 (Y4) | 스트리밍, 뷰 프러스텀 컬링 |

### LOD (Level of Detail) 전략

| 거리 | LOD | 폴리곤 비율 | 텍스처 해상도 |
|------|-----|------------|-------------|
| < 500m | LOD 0 (High) | 100% | 2048x2048 |
| 500m - 2km | LOD 1 (Medium) | 30% | 1024x1024 |
| > 2km | LOD 2 (Low) | 10% | 512x512 |

---

## 21.6 대시보드 위젯 시스템 (Y3-Y4)

### Widget Architecture

독립 Vue 컴포넌트로 설계된 위젯 시스템이다.
각 위젯은 자체 데이터 소스, 갱신 주기, 크기 설정을 보유한다.

```typescript
// ui/src/monitor/widgets/types.ts
interface WidgetConfig {
  id: string
  type: WidgetType
  title: string
  dataSource: DataSourceConfig    // KG 쿼리 또는 REST API
  refreshInterval: number         // 초 단위 (0 = 수동)
  size: { w: number; h: number }  // 그리드 단위
  position: { x: number; y: number }
  options: Record<string, unknown> // 위젯별 설정
}

type WidgetType =
  | 'chart'      // ECharts 차트 (bar, line, pie, scatter)
  | 'map'        // 미니맵 (OpenLayers)
  | 'table'      // 데이터 테이블
  | 'kpi-card'   // KPI 카드 (단일 수치 + 트렌드)
  | 'timeline'   // 시계열 타임라인
  | 'graph'      // 그래프 시각화 (KG 서브그래프)
  | 'custom'     // 사용자 정의 (Y4 SDK)
```

### 위젯 유형

| 위젯 | 설명 | 데이터 소스 | 도입 시기 |
|------|------|-----------|----------|
| KPI Card | 핵심 지표 (선박 수, 입출항 건수) | KG 집계 쿼리 | Y3 Q1 |
| Bar/Line Chart | 추이 차트 (일별/월별 통계) | KG 쿼리 + 시계열 DB | Y3 Q1 |
| AIS Mini Map | 관심 해역 실시간 미니맵 | WebSocket AIS | Y3 Q2 |
| Data Table | 쿼리 결과 테이블 (정렬, 필터) | KG 쿼리 | Y3 Q1 |
| Timeline | 이벤트 타임라인 (입출항 이력) | KG 쿼리 | Y3 Q2 |
| Graph View | KG 서브그래프 시각화 | KG 쿼리 | Y3 Q3 |
| Custom Widget | 사용자 정의 위젯 (SDK) | 임의 | Y4 Q2 |

### Layout Persistence

| 연차 | 저장 위치 | 설명 |
|------|----------|------|
| Y3 | LocalStorage | 브라우저 로컬 (단일 기기) |
| Y4 | Redis → PostgreSQL | 서버 동기화 (다중 기기, 협업) |

---

## 21.7 모바일 대응 (Y4)

### Responsive Design 전략

| 컴포넌트 | 데스크톱 | 태블릿 | 모바일 |
|----------|---------|--------|--------|
| VueFlow Canvas | 전체 기능 | 읽기 전용 | 미지원 (Desktop only) |
| S-100 전자해도 | 전체 기능 | 전체 기능 | 축소 뷰 (AIS 마커만) |
| 3D Renderer | 전체 기능 | 축소 뷰 | 미지원 |
| Dashboard | 전체 위젯 | 2열 레이아웃 | 1열 스크롤 |
| Service Portal | 전체 기능 | 전체 기능 | 전체 기능 |
| Chat | 전체 기능 | 전체 기능 | 전체 기능 |

### PWA (Progressive Web App)

```
PWA 기능:
  +-- Service Worker: 오프라인 캐싱 (대시보드 스냅샷)
  +-- Push Notification: 알림 (입출항, 위험 경보)
  +-- App Manifest: 홈 화면 추가 (모바일)
  +-- Background Sync: 오프라인 작업 큐
```

- **캐싱 전략:** NetworkFirst (API), CacheFirst (정적 자산), StaleWhileRevalidate (타일)
- **오프라인 지원:** 최근 조회한 대시보드 스냅샷, 서비스 카탈로그 검색

---

## 21.8 AR/VR 프로토타입 (Y5)

### 기술 스택

| 항목 | 기술 | 설명 |
|------|------|------|
| API | WebXR Device API | 브라우저 기반 XR 지원 |
| 프레임워크 | A-Frame 1.6+ | 선언적 WebXR 컴포넌트 |
| 3D 엔진 | Three.js (공유) | 기존 3D 렌더러 코드 재활용 |
| 타겟 디바이스 | Meta Quest 3 (standalone) | 독립 실행형 HMD |
| 폴백 | Desktop 브라우저 | 키보드/마우스 내비게이션 |

### Use Case: 항만 디지털 트윈 워크스루

```
사용자 (HMD 착용)
    |
    v
A-Frame Scene
    |
    +-- 항만 3D 모델 (glTF) -- 실제 축척 1:1
    +-- AIS 선박 위치 (실시간 WebSocket)
    +-- 정보 패널 (선박 상세, 화물 정보)
    +-- 인터랙션
    |   +-- 선박 선택 (레이캐스트)
    |   +-- 시점 이동 (텔레포트)
    |   +-- 시간 슬라이더 (과거 항적 재생)
    |
    v
Gateway WebSocket
    |
    v
KG Query (선박/항만 데이터)
```

### 기술 평가 일정

| 시기 | 활동 | 산출물 |
|------|------|--------|
| Y4 Q3 | 기술 스카우팅 | WebXR 기술 조사 보고서 |
| Y4 Q4 | PoC 개발 | 단일 항만 VR 워크스루 프로토타입 |
| Y5 Q1 | 사용성 평가 | KRISO 전문가 대상 UX 테스트 결과 |
| Y5 Q2 | 기능 고도화 | 실시간 AIS 연동, 멀티유저 |
| Y5 Q3 | 안정화 | 성능 최적화, 디바이스 호환성 |

---

## 21.9 자동 리포트 생성 (Y5)

### 파이프라인

```
트리거: 사용자 요청 또는 CronJob (주간/월간)
    |
    v
데이터 수집
    +-- KG 쿼리 실행 (통계, 현황)
    +-- 대시보드 위젯 스냅샷 캡처
    +-- 차트 이미지 렌더링 (ECharts server-side)
    |
    v
LLM 서술 생성
    +-- KG 쿼리 결과 -> 자연어 서술 변환
    +-- 템플릿 섹션별 생성 (현황, 분석, 권고)
    +-- 해사 도메인 용어 적용
    |
    v
보고서 조립
    +-- 템플릿 엔진 (Jinja2)
    +-- 차트/테이블 삽입
    +-- 목차 자동 생성
    |
    v
출력 포맷 변환
    +-- PDF (pdf-lib / WeasyPrint)
    +-- HWP (hwp-js 또는 LibreOffice 변환)
    +-- DOCX (python-docx, 폴백)
```

### 보고서 템플릿

| 보고서 유형 | 주기 | 포함 내용 |
|------------|------|----------|
| 해상교통 현황 | 주간 | 입출항 통계, AIS 항적 분석, 위험 이벤트 |
| 연구 과제 현황 | 월간 | KG 데이터 증가량, 워크플로우 실행 현황, 모델 성능 |
| 인프라 운영 | 월간 | 시스템 가용성, GPU 사용률, 에러율 |
| 연차 보고 | 연간 | 연차 산출물 달성 현황, KPI 달성률, 논문/특허 |

---

## 21.10 기술 스택

| 컴포넌트 | 기술 | 버전 | 도입 시기 |
|----------|------|------|----------|
| Workflow Canvas | VueFlow | 1.x | Y1 Q3 |
| Chart | ECharts | 5.x | Y2 Q3 |
| Map | OpenLayers | 9.x | Y2 Q2 |
| 3D Engine | Three.js | r170+ | Y3 Q1 |
| AR/VR | WebXR + A-Frame | 1.6+ | Y5 Q1 |
| Report (PDF) | WeasyPrint / pdf-lib | - | Y5 Q2 |
| Report (HWP) | hwp-js / LibreOffice | - | Y5 Q2 |
| Grid Layout | vue-grid-layout | 3.x | Y3 Q1 |
| Real-time | WebSocket (native) | - | Y1 Q4 |

---

## 21.11 성능 요구사항

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 전자해도 타일 로딩 | < 500ms (초기), < 100ms (캐시) | Lighthouse, 네트워크 탭 |
| AIS 마커 업데이트 | < 200ms (1,000 선박 동시) | WebSocket 지연 측정 |
| 3D 씬 FPS | > 30fps (중형 항만 모델) | Chrome DevTools Performance |
| 대시보드 위젯 렌더링 | < 1s (10개 위젯 동시) | 커스텀 성능 메트릭 |
| 캔버스 노드 렌더링 | < 500ms (100 노드 워크플로우) | VueFlow 벤치마크 |
| 3D 모델 로딩 | < 3s (50MB glTF) | Three.js 로더 이벤트 |
| 보고서 생성 | < 30s (20페이지 PDF) | 서버 처리 시간 |

---

## 21.12 구현 로드맵

| 시기 | 마일스톤 | 컴포넌트 |
|------|---------|---------|
| Y1 Q3 | VueFlow 캔버스 PoC | canvas/ |
| Y1 Q4 | 워크플로우 노드 5종 구현 | canvas/nodes/ |
| Y2 Q1 | 노드별 대화창 통합 | chat/node/ |
| Y2 Q2 | S-100 전자해도 기본 뷰 | map/ |
| Y2 Q3 | AIS 실시간 오버레이 | map/layers/ |
| Y2 Q3 | ECharts 차트 컴포넌트 | monitor/widgets/ |
| Y3 Q1 | 대시보드 위젯 시스템 v1 | monitor/ |
| Y3 Q1 | Three.js 3D 렌더러 PoC | renderer/ |
| Y3 Q2 | 항만 3D 모델 로딩 | renderer/scenes/ |
| Y3 Q3 | KG 그래프 시각화 위젯 | monitor/widgets/ |
| Y4 Q1 | 대시보드 위젯 서버 동기화 | monitor/store/ |
| Y4 Q2 | Custom Widget SDK | monitor/widgets/sdk/ |
| Y4 Q3 | 모바일 PWA 지원 | 전체 |
| Y4 Q3 | AR/VR 기술 스카우팅 | -- |
| Y5 Q1 | AR/VR PoC | renderer/xr/ |
| Y5 Q2 | 자동 리포트 생성 | report/ |
| Y5 Q3 | 전체 안정화 + 성능 최적화 | 전체 |

---

## 21.13 코드 매핑

| 모듈 | 위치 | 상태 | 도입 시기 |
|------|------|------|----------|
| VueFlow 캔버스 | `ui/src/canvas/` | 설계 완료, PoC 예정 | Y1 Q3 |
| 대화창 | `ui/src/chat/` | 설계 완료 | Y1 Q4 |
| 전자해도 | `ui/src/map/` | 설계 중 | Y2 Q2 |
| 대시보드 | `ui/src/monitor/` | 설계 중 | Y3 Q1 |
| 3D 렌더러 | `ui/src/renderer/` | 미착수 | Y3 Q1 |
| 서비스 포털 | `ui/src/portal/` | 미착수 | Y3 Q2 |
| AR/VR | `ui/src/renderer/xr/` | 미착수 | Y5 Q1 |
| 보고서 생성 | `gateway/routes/report/` | 미착수 | Y5 Q2 |

---

[← NLP/NER 전략](./20-nlp-ner.md) | [→ 지식그래프 고급 아키텍처](./22-kg-advanced.md)
